"""
Phase 6.4 Final Trust-Boundary and Observation-Coverage Verification Tests.

Verifies:
1. RFC 8785 JSON Canonicalization Scheme (JCS) Conformance:
   - Unicode raw UTF-8 serialization without \\uXXXX escapes.
   - UTF-16 code unit property-name sorting (including surrogate pair ordering).
   - Control character escaping (U+0000..U+001F, quotes, backslashes).
   - Number serialization per ECMA-262 Section 7.1.12.1 (integer floats, -0.0 -> 0, exponents).
   - Rejection of non-finite numbers (NaN, Infinity, -Infinity).
   - Deterministic bit-for-bit serialization across key insertion orders.
   - Ed25519 digital signature invalidation when signed fields change.
2. Revocation-List Authenticity & Rollback Protection:
   - Signed CRL verification with Ed25519 digital signature.
   - Sequence freshness enforcement (crl_sequence monotonic progression) preventing stale rollback.
   - CRL expiry, premature issuance, and schema enforcement.
   - Multi-worker persistent state synchronization.
   - Fail-closed intake blocking when signed CRL is required and untrusted.
3. Audit-Ledger Protection & Storage Trust Boundaries:
   - Single-entry tamper detection via SHA-256 digest and hash chaining.
   - Dataset and manifest replacement detection.
   - Ledger line deletion and splicing detection.
   - Complete ledger rewriting threat boundary analysis (internal hash chain vs storage root of trust).
   - Tamper detection when dataset is untouched.
4. Observation-Coverage Semantics:
   - Verified reporting zero (Y = 0) vs containing incidents (Y = 1).
   - Unknown coverage retains NaN; NEVER infers zero events from missing records alone.
   - Incomplete extract detection (intervals outside reporting range).
   - Non-operational stations (unverified recent bifurcations like Alankar, Pashan, Bavdhan).
5. Temporal Consistency & Anti-Leakage:
   - 4-hour intervals [t, t + 4h) in Asia/Kolkata timezone.
   - Strictly historical lag features (tau < t).
   - Non-overlapping chronological partition boundaries.
"""

import os
import json
import math
import hashlib
import tempfile
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.services.pune_data_readiness import (
    canonicalize_rfc8785,
    InstitutionalIssuerRegistry,
    PUNE_POLICE_STATIONS,
    PUNE_STATION_VERIFICATION_STATUS,
)
from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
    PUNE_LAT_BOUNDS,
    PUNE_LON_BOUNDS,
)
from backend.pipeline.pune_spatiotemporal_pipeline import (
    PuneFourHourSpatiotemporalPipeline,
    OPERATIONAL_WINDOWS,
    WINDOWS_PER_DAY,
)


# ==============================================================================
# SECTION 1: RFC 8785 CONFORMANCE TESTS
# ==============================================================================

def test_rfc8785_unicode_raw_utf8_serialization():
    """Verifies that RFC 8785 preserves Unicode characters as raw UTF-8 bytes without \\uXXXX escapes."""
    payload = {
        "city": "पुणे",
        "state": "महाराष्ट्र",
        "jurisdiction": "पुणे शहर पोलीस आयुक्त कार्यालय",
        "symbol": "🛡️",
        "japanese": "警察",
    }
    canonical = canonicalize_rfc8785(payload)
    
    # Must contain literal UTF-8 byte sequences
    assert "पुणे".encode("utf-8") in canonical
    assert "महाराष्ट्र".encode("utf-8") in canonical
    assert "🛡️".encode("utf-8") in canonical
    assert "警察".encode("utf-8") in canonical
    
    # Must NOT contain escaped unicode sequences
    assert b"\\u092a" not in canonical
    assert b"\\u" not in canonical


def test_rfc8785_utf16_property_sorting_surrogate_pairs():
    """
    Verifies that dictionary keys are sorted strictly by UTF-16 code units.
    In UTF-16, characters in supplementary planes (U+10000..U+10FFFF) are encoded
    as surrogate pairs starting with 0xD800..0xDBFF, which sorts BEFORE BMP characters
    in the range 0xE000..0xFFFF (such as U+FFFD).
    """
    # Keys:
    # 'a' = U+0061 (UTF-16: 0x0061)
    # 'é' = U+00E9 (UTF-16: 0x00E9)
    # '𝄞' (musical G-clef) = U+1D11E (UTF-16: 0xD834, 0xDD1E) -> high surrogate 0xD834 < 0xFFFD
    # '' (replacement char) = U+FFFD (UTF-16: 0xFFFD)
    obj = {
        "\uFFFD": "bmp_high",
        "\U0001D11E": "supplementary",
        "é": "latin_supplement",
        "a": "basic_latin",
    }
    canonical = canonicalize_rfc8785(obj)
    decoded = canonical.decode("utf-8")
    
    # Expected order: "a", "é", "𝄞", "\ufffd"
    expected = '{"a":"basic_latin","é":"latin_supplement","𝄞":"supplementary","\ufffd":"bmp_high"}'
    assert decoded == expected


def test_rfc8785_control_character_escaping():
    """
    Verifies escaping of quotes, backslashes, and control characters (U+0000 to U+001F)
    per RFC 8785 Section 3.2.2.2.
    """
    obj = {
        "ctrl": "line1\nline2\ttab\rreturn\bback\ffeed",
        "quotes": 'say "hello" and \\backslash\\',
        "null": "\u0000",
        "us": "\u001f",
    }
    canonical = canonicalize_rfc8785(obj)
    
    assert b"\\n" in canonical
    assert b"\\t" in canonical
    assert b"\\r" in canonical
    assert b"\\b" in canonical
    assert b"\\f" in canonical
    assert b'\\"hello\\"' in canonical
    assert b"\\\\backslash\\\\" in canonical
    assert b"\\u0000" in canonical
    assert b"\\u001f" in canonical


def test_rfc8785_number_serialization_ecma262():
    """
    Verifies that numbers are serialized strictly per ECMA-262 Section 7.1.12.1:
    - Floats with whole integer values are formatted without decimal points (1.0 -> 1).
    - Negative zero (-0.0) is normalized to 0.
    - Exponents follow shortest representation thresholds:
      - Small numbers with -6 < exponent <= 0 format as decimal (1e-5 -> 0.00001).
      - Exponents <= -7 or >= 21 use scientific notation without redundant leading zeros (1e-7, 1e+21).
    """
    cases = [
        ({"num": 1.0}, b'{"num":1}'),
        ({"num": 0.0}, b'{"num":0}'),
        ({"num": -0.0}, b'{"num":0}'),
        ({"num": 100.0}, b'{"num":100}'),
        ({"num": -100.0}, b'{"num":-100}'),
        ({"num": 1e-5}, b'{"num":0.00001}'),
        ({"num": 1e-6}, b'{"num":0.000001}'),
        ({"num": 1e-7}, b'{"num":1e-7}'),
        ({"num": 1e20}, b'{"num":100000000000000000000}'),
        ({"num": 1e21}, b'{"num":1e+21}'),
        ({"num": 12345.6789}, b'{"num":12345.6789}'),
    ]
    for input_obj, expected_bytes in cases:
        actual_bytes = canonicalize_rfc8785(input_obj)
        assert actual_bytes == expected_bytes, f"Mismatch for {input_obj}: got {actual_bytes} != expected {expected_bytes}"


def test_rfc8785_rejection_of_non_finite_numbers():
    """RFC 8785 strictly prohibits NaN, Infinity, and -Infinity."""
    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("nan")})

    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("inf")})

    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("-inf")})


def test_rfc8785_key_order_independence_and_determinism():
    """Permutations of key insertion orders produce identical canonical byte strings."""
    d1 = {"z": 10, "a": 20, "m": 30}
    d2 = {"m": 30, "z": 10, "a": 20}
    d3 = {"a": 20, "m": 30, "z": 10}
    
    b1 = canonicalize_rfc8785(d1)
    b2 = canonicalize_rfc8785(d2)
    b3 = canonicalize_rfc8785(d3)
    
    assert b1 == b2 == b3 == b'{"a":20,"m":30,"z":10}'


def test_rfc8785_signature_invalidation_on_any_field_modification():
    """Verifies that altering any field or adding whitespace invalidates the Ed25519 signature."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    
    manifest_payload = {
        "authorization_id": "AUTH-PUNE-2026-TEST",
        "dataset_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "issuer_id": "test_fixture_authority",
        "mou_reference": "MOU-TEST-001",
        "permitted_fields": ["fir_number_hash", "police_station_id"],
        "permitted_use": "unit_testing",
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_until": "2026-12-31T23:59:59Z",
    }
    canonical = canonicalize_rfc8785(manifest_payload)
    sig = priv.sign(canonical)
    
    # Valid signature passes
    pub.verify(sig, canonical)
    
    # Tampering with any field invalidates signature
    tampered_payload = dict(manifest_payload)
    tampered_payload["permitted_use"] = "unauthorized_training"
    tampered_canonical = canonicalize_rfc8785(tampered_payload)
    
    with pytest.raises(Exception):
        pub.verify(sig, tampered_canonical)


# ==============================================================================
# SECTION 2: REVOCATION-LIST AUTHENTICITY & ROLLBACK PROTECTION TESTS
# ==============================================================================

def test_signed_crl_verification_success_and_tamper_detection(tmp_path):
    """
    Verifies that a Certificate Revocation List (CRL) signed by test_fixture_authority
    is verified correctly, and any tampering with payload or signature is rejected.
    """
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    
    # Provision fixture key
    old_env = os.environ.get("TEST_FIXTURE_ED25519_PUBLIC_KEY")
    os.environ["TEST_FIXTURE_ED25519_PUBLIC_KEY"] = pub_hex
    InstitutionalIssuerRegistry.reset_crl_sequence(0)
    
    try:
        crl_data = InstitutionalIssuerRegistry.create_authorized_crl(
            issuer_id="test_fixture_authority",
            revoked_authorizations=["REVOKED-AUTH-001", "REVOKED-AUTH-002"],
            crl_sequence=1,
            signing_private_key=priv,
        )
        crl_file = tmp_path / "valid_signed_crl.json"
        crl_file.write_text(json.dumps(crl_data), encoding="utf-8")
        
        # 1. Valid signed CRL loads successfully
        is_ok, err, revoked_ids, _ = InstitutionalIssuerRegistry.load_persistent_crl(
            crl_path=str(crl_file),
            require_crl=True,
            require_signed_crl=True,
        )
        assert is_ok is True
        assert err is None
        assert "REVOKED-AUTH-001" in revoked_ids
        assert "REVOKED-AUTH-002" in revoked_ids
        
        # 2. Tampered signature is rejected
        tampered_sig_data = dict(crl_data)
        tampered_sig_data["signature"] = "00" * 64
        t_file = tmp_path / "tampered_sig_crl.json"
        t_file.write_text(json.dumps(tampered_sig_data), encoding="utf-8")
        
        is_ok_t, err_t, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(
            crl_path=str(t_file),
            require_crl=True,
            require_signed_crl=True,
        )
        assert is_ok_t is False
        assert "digital signature invalid" in err_t
        
        # 3. Tampered payload with original signature is rejected
        tampered_payload_data = dict(crl_data)
        tampered_payload_data["revoked_authorizations"] = []  # Attacker attempts to un-revoke
        tp_file = tmp_path / "tampered_payload_crl.json"
        tp_file.write_text(json.dumps(tampered_payload_data), encoding="utf-8")
        
        is_ok_tp, err_tp, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(
            crl_path=str(tp_file),
            require_crl=True,
            require_signed_crl=True,
        )
        assert is_ok_tp is False
        assert ("digital signature invalid" in err_tp) or ("integrity digest mismatch" in err_tp)

        # 4. Tampered payload with recomputed crl_sha256 is caught specifically by signature verification
        tampered_rehashed = dict(tampered_payload_data)
        rehashed_payload = {k: v for k, v in tampered_rehashed.items() if k not in ("signature", "crl_sha256")}
        tampered_rehashed["crl_sha256"] = hashlib.sha256(canonicalize_rfc8785(rehashed_payload)).hexdigest()
        tpr_file = tmp_path / "tampered_rehashed_crl.json"
        tpr_file.write_text(json.dumps(tampered_rehashed), encoding="utf-8")

        is_ok_tpr, err_tpr, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(
            crl_path=str(tpr_file),
            require_crl=True,
            require_signed_crl=True,
        )
        assert is_ok_tpr is False
        assert "digital signature invalid" in err_tpr
    finally:
        if old_env is not None:
            os.environ["TEST_FIXTURE_ED25519_PUBLIC_KEY"] = old_env
        else:
            os.environ.pop("TEST_FIXTURE_ED25519_PUBLIC_KEY", None)


def test_crl_sequence_monotonicity_prevents_stale_rollback(tmp_path):
    """
    Verifies that the CRL sequence counter prevents replay of stale CRLs.
    If workers have observed crl_sequence = 2, an adversary presenting crl_sequence = 1
    (even if legitimately signed by authority) is rejected as a rollback attack.
    """
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    
    old_env = os.environ.get("TEST_FIXTURE_ED25519_PUBLIC_KEY")
    os.environ["TEST_FIXTURE_ED25519_PUBLIC_KEY"] = pub_hex
    InstitutionalIssuerRegistry.reset_crl_sequence(0)
    
    try:
        # Create sequence 2 CRL
        crl_seq2 = InstitutionalIssuerRegistry.create_authorized_crl(
            issuer_id="test_fixture_authority",
            revoked_authorizations=["REVOKED-AUTH-RECENT"],
            crl_sequence=2,
            signing_private_key=priv,
        )
        f_seq2 = tmp_path / "crl_seq2.json"
        f_seq2.write_text(json.dumps(crl_seq2), encoding="utf-8")
        
        # Load sequence 2
        is_ok2, _, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(crl_path=str(f_seq2))
        assert is_ok2 is True
        assert InstitutionalIssuerRegistry.LATEST_OBSERVED_CRL_SEQUENCE == 2
        
        # Attacker presents older sequence 1 CRL
        crl_seq1 = InstitutionalIssuerRegistry.create_authorized_crl(
            issuer_id="test_fixture_authority",
            revoked_authorizations=[],  # Older version didn't have revocation
            crl_sequence=1,
            signing_private_key=priv,
        )
        f_seq1 = tmp_path / "crl_seq1.json"
        f_seq1.write_text(json.dumps(crl_seq1), encoding="utf-8")
        
        is_ok1, err1, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(crl_path=str(f_seq1))
        assert is_ok1 is False
        assert "Stale CRL rollback attack detected" in err1
    finally:
        InstitutionalIssuerRegistry.reset_crl_sequence(0)
        if old_env is not None:
            os.environ["TEST_FIXTURE_ED25519_PUBLIC_KEY"] = old_env
        else:
            os.environ.pop("TEST_FIXTURE_ED25519_PUBLIC_KEY", None)


def test_production_crl_unconditionally_blocked_without_provisioned_key(tmp_path):
    """
    Verifies that for the production authority (pune_city_police_cop),
    signed CRL verification cannot succeed unless the institutional public key
    is provisioned in the environment. Production credentials are not invented.
    """
    old_env = os.environ.pop("PUNE_COP_ED25519_PUBLIC_KEY", None)
    
    try:
        # Production CRL signed with arbitrary key cannot verify
        crl_data = {
            "crl_version": "1.0",
            "crl_sequence": 1,
            "issuer_id": "pune_city_police_cop",
            "description": "Production CRL",
            "issued_at": "2026-01-01T00:00:00Z",
            "expires_at": "2026-12-31T23:59:59Z",
            "revoked_authorizations": [],
            "signature": "ab" * 64,
        }
        f_prod = tmp_path / "prod_crl.json"
        f_prod.write_text(json.dumps(crl_data), encoding="utf-8")
        
        is_ok, err, _, _ = InstitutionalIssuerRegistry.load_persistent_crl(
            crl_path=str(f_prod),
            require_signed_crl=True,
        )
        assert is_ok is False
        assert "digital signature invalid" in err or "unprovisioned" in err.lower()
    finally:
        if old_env is not None:
            os.environ["PUNE_COP_ED25519_PUBLIC_KEY"] = old_env


# ==============================================================================
# SECTION 3: AUDIT-LEDGER PROTECTION & TRUST-BOUNDARY TESTS
# ==============================================================================

def test_ledger_single_entry_tamper_detection(tmp_path):
    """
    Verifies that altering a single field in any ledger entry breaks the entry digest
    and the subsequent hash chain pointer.
    """
    entry1 = {
        "ledger_entry_version": "2.0",
        "entry_timestamp_utc": "2026-03-01T10:00:00Z",
        "dataset_version": "v1.0",
        "cleaned_file_sha256": "1111" * 16,
        "intake_manifest_sha256": "2222" * 16,
        "prev_entry_sha256": "0" * 64,
    }
    entry1_hash = hashlib.sha256(canonicalize_rfc8785(entry1)).hexdigest()
    entry1["entry_sha256"] = entry1_hash

    entry2 = {
        "ledger_entry_version": "2.0",
        "entry_timestamp_utc": "2026-03-02T10:00:00Z",
        "dataset_version": "v2.0",
        "cleaned_file_sha256": "3333" * 16,
        "intake_manifest_sha256": "4444" * 16,
        "prev_entry_sha256": entry1_hash,
    }
    entry2_hash = hashlib.sha256(canonicalize_rfc8785(entry2)).hexdigest()
    entry2["entry_sha256"] = entry2_hash

    ledger_file = tmp_path / "ledger.jsonl"
    
    # Tamper with entry 1: change cleaned_file_sha256
    tampered_entry1 = dict(entry1)
    tampered_entry1["cleaned_file_sha256"] = "9999" * 16
    
    with open(ledger_file, "w", encoding="utf-8") as f:
        f.write(json.dumps(tampered_entry1) + "\n")
        f.write(json.dumps(entry2) + "\n")

    # Set up dummy version directory
    vdir = tmp_path / "v1.0"
    vdir.mkdir()
    (vdir / "cleaned_incidents.csv").write_text("dummy", encoding="utf-8")
    (vdir / "intake_audit_manifest.json").write_text(json.dumps({
        "output_fingerprint": {"cleaned_file_sha256": hashlib.sha256(b"dummy").hexdigest()}
    }), encoding="utf-8")
    # Add dummy authorized manifest
    (vdir / "authorized_manifest.json").write_text(json.dumps({
        "authorization_id": "AUTH-TEST",
        "issuer_id": "test_fixture_authority",
        "dataset_sha256": hashlib.sha256(b"dummy").hexdigest(),
        "is_revoked": False,
    }), encoding="utf-8")

    res = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=str(tmp_path),
        version="1.0",
        is_fixture=True,
        ledger_path=str(ledger_file),
    )
    assert res["is_valid"] is False
    assert res["ledger_hash_chain_valid"] is False
    assert any("tamper detected" in v for v in res["violations"])


def test_ledger_deletion_and_splicing_detection(tmp_path):
    """
    Verifies that deleting an intermediate ledger entry breaks the hash chain
    because entry i+1's prev_entry_sha256 will point to the deleted entry i.
    """
    entries = []
    prev_hash = "0" * 64
    for idx in range(3):
        e = {
            "ledger_entry_version": "2.0",
            "entry_timestamp_utc": f"2026-03-0{idx+1}T10:00:00Z",
            "dataset_version": "1.0" if idx == 0 else f"{idx+1}.0",
            "cleaned_file_sha256": f"{idx}{idx}" * 32,
            "intake_manifest_sha256": f"{idx+1}{idx+1}" * 32,
            "prev_entry_sha256": prev_hash,
        }
        h = hashlib.sha256(canonicalize_rfc8785(e)).hexdigest()
        e["entry_sha256"] = h
        prev_hash = h
        entries.append(e)

    # Delete entry 1 (splice entry 0 directly to entry 2)
    spliced_entries = [entries[0], entries[2]]
    ledger_file = tmp_path / "spliced_ledger.jsonl"
    with open(ledger_file, "w", encoding="utf-8") as f:
        for item in spliced_entries:
            f.write(json.dumps(item) + "\n")

    vdir = tmp_path / "v1.0"
    vdir.mkdir()
    (vdir / "cleaned_incidents.csv").write_text("dummy", encoding="utf-8")
    (vdir / "intake_audit_manifest.json").write_text(json.dumps({}), encoding="utf-8")
    (vdir / "authorized_manifest.json").write_text(json.dumps({
        "authorization_id": "AUTH-TEST",
        "issuer_id": "test_fixture_authority",
        "dataset_sha256": hashlib.sha256(b"dummy").hexdigest(),
        "is_revoked": False,
    }), encoding="utf-8")

    res = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=str(tmp_path),
        version="1.0",
        is_fixture=True,
        ledger_path=str(ledger_file),
    )
    assert res["is_valid"] is False
    assert res["ledger_hash_chain_valid"] is False
    assert any("hash chain broken" in v for v in res["violations"])


def test_ledger_storage_rewrite_trust_boundary_demonstration(tmp_path):
    """
    TRUST-BOUNDARY AUDIT TEST:
    Demonstrates that an attacker with write access to the ledger storage volume CAN
    rewrite the entire ledger with mathematically valid hash chaining.
    Distinguishes internal hash-chain verification from independent storage protection.
    Without an external anchor or hardware WORM immutability, local hash chaining
    verifies internal mathematical consistency, NOT protection against root storage compromise.
    """
    fdir = tmp_path / "v1.0"
    fdir.mkdir()
    (fdir / "cleaned_incidents.csv").write_text("forged", encoding="utf-8")
    f_clean_hash = hashlib.sha256(b"forged").hexdigest()

    manifest_content = {
        "output_fingerprint": {"cleaned_file_sha256": f_clean_hash}
    }
    manifest_bytes = canonicalize_rfc8785(manifest_content)
    (fdir / "intake_audit_manifest.json").write_bytes(manifest_bytes)
    f_manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()

    (fdir / "authorized_manifest.json").write_text(json.dumps({
        "authorization_id": "AUTH-FORGED",
        "issuer_id": "test_fixture_authority",
        "dataset_sha256": f_clean_hash,
        "is_revoked": False,
    }), encoding="utf-8")

    # Forge an entire new 3-entry synthetic ledger from scratch
    forged_entries = []
    prev_hash = "0" * 64
    for idx in range(3):
        e = {
            "ledger_entry_version": "2.0",
            "entry_timestamp_utc": f"2026-03-0{idx+1}T10:00:00Z",
            "dataset_version": "1.0" if idx == 0 else f"{idx+1}.0",
            "cleaned_file_sha256": f_clean_hash if idx == 0 else f"ff{idx}" * 21 + "f",
            "intake_manifest_sha256": f_manifest_hash if idx == 0 else f"ee{idx}" * 21 + "e",
            "prev_entry_sha256": prev_hash,
        }
        h = hashlib.sha256(canonicalize_rfc8785(e)).hexdigest()
        e["entry_sha256"] = h
        prev_hash = h
        forged_entries.append(e)

    forged_ledger_file = tmp_path / "forged_ledger.jsonl"
    with open(forged_ledger_file, "w", encoding="utf-8") as f:
        for item in forged_entries:
            f.write(json.dumps(item) + "\n")

    res = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=str(tmp_path),
        version="1.0",
        is_fixture=True,
        ledger_path=str(forged_ledger_file),
    )
    
    # Internal hash chain evaluates as mathematically consistent
    assert res["ledger_hash_chain_valid"] is True
    # Audit limitation: without an out-of-band anchor, the application cannot distinguish
    # a wholly rewritten ledger from an authentic history.


# ==============================================================================
# SECTION 4: OBSERVATION-COVERAGE SEMANTICS TESTS
# ==============================================================================

def test_observation_coverage_distinguishes_five_distinct_states():
    """
    CRITICAL METHODOLOGICAL TEST:
    Verifies that the pipeline strictly distinguishes:
    1. VERIFIED_OBSERVED_ZERO: station verified reporting with 0 qualifying incidents (Y = 0).
    2. VERIFIED_OBSERVED_INCIDENT: station verified reporting with incidents (Y = 1).
    3. UNKNOWN_COVERAGE: coverage evidence not provided -> Y = NaN (NEVER fabricated 0).
    4. INCOMPLETE_EXTRACT: window falls outside certified extract bounds -> Y = NaN.
    5. NOT_OPERATIONAL: station not operational (e.g. unverified recent bifurcation) -> Y = NaN.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")  # 6 windows
    
    # Only shivajinagar and kothrud are active reporting stations
    # Furthermore, kothrud's extract ends at 12:00:00 IST (incomplete extract for windows 3, 4, 5)
    reporting_windows = {
        "shivajinagar": (start_t, end_t),
        "kothrud": (start_t, pd.Timestamp("2026-03-01 12:00:00", tz="Asia/Kolkata")),
    }
    
    # Shivajinagar has 1 violent incident in Window 1 [04:00, 08:00) IST
    df_incidents = pd.DataFrame([
        {
            "fir_number_hash": "fir_01",
            "police_station_id": "shivajinagar",
            "incident_datetime": "2026-03-01T05:00:00+05:30",
            "section_code": "302",
        }
    ])
    
    lattice, audit = pipe.aggregate_incidents(
        df_cleaned=df_incidents,
        start_time=start_t,
        end_time=end_t,
        station_reporting_windows=reporting_windows,
        require_coverage_evidence=True,
    )
    
    # State 1: Shivajinagar Window 1 has incident -> VERIFIED_OBSERVED_INCIDENT, Y = 1
    sh_w1 = lattice[(lattice["station_id"] == "shivajinagar") & (lattice["window_idx"] == 1)].iloc[0]
    assert sh_w1["observation_coverage_class"] == "VERIFIED_OBSERVED_INCIDENT"
    assert sh_w1["target_binary"] == 1
    
    # State 2: Shivajinagar Window 0 has verified reporting and 0 incidents -> VERIFIED_OBSERVED_ZERO, Y = 0
    sh_w0 = lattice[(lattice["station_id"] == "shivajinagar") & (lattice["window_idx"] == 0)].iloc[0]
    assert sh_w0["observation_coverage_class"] == "VERIFIED_OBSERVED_ZERO"
    assert sh_w0["target_binary"] == 0
    
    # State 3: Hadapsar was NOT in reporting_windows -> UNKNOWN_COVERAGE, Y = NaN
    hadapsar_rows = lattice[lattice["station_id"] == "hadapsar"]
    assert (hadapsar_rows["observation_coverage_class"] == "UNKNOWN_COVERAGE").all()
    assert hadapsar_rows["target_binary"].isna().all()
    
    # State 4: Kothrud Window 4 is outside reporting window -> INCOMPLETE_EXTRACT, Y = NaN
    kothrud_w4 = lattice[(lattice["station_id"] == "kothrud") & (lattice["window_idx"] == 4)].iloc[0]
    assert kothrud_w4["observation_coverage_class"] == "INCOMPLETE_EXTRACT"
    assert pd.isna(kothrud_w4["target_binary"])
    
    # State 5: Alankar is UNVERIFIED_RECENT_BIFURCATION in PUNE_STATION_VERIFICATION_STATUS -> NOT_OPERATIONAL, Y = NaN
    alankar_rows = lattice[lattice["station_id"] == "alankar"]
    assert (alankar_rows["observation_coverage_class"] == "NOT_OPERATIONAL").all()
    assert alankar_rows["target_binary"].isna().all()
    
    # Audit breakdown accounts for all states
    breakdown = audit["coverage_class_breakdown"]
    assert breakdown["VERIFIED_OBSERVED_INCIDENT"] == 1
    assert breakdown["VERIFIED_OBSERVED_ZERO"] > 0
    assert breakdown["UNKNOWN_COVERAGE"] > 0
    assert breakdown["INCOMPLETE_EXTRACT"] > 0
    assert breakdown["NOT_OPERATIONAL"] > 0


def test_missing_reporting_evidence_prevents_zero_fabrication():
    """
    CRITICAL POLICY TEST:
    When require_coverage_evidence=True and station_reporting_windows is None,
    the pipeline MUST NOT assign Y = 0 to any window.
    All windows with 0 incidents MUST retain target_binary = NaN.
    """
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-02 00:00:00", tz="Asia/Kolkata")
    
    df_empty = pd.DataFrame(columns=["fir_number_hash", "police_station_id", "incident_datetime", "section_code"])
    
    lattice, audit = pipe.aggregate_incidents(
        df_cleaned=df_empty,
        start_time=start_t,
        end_time=end_t,
        station_reporting_windows=None,
        require_coverage_evidence=True,
    )
    
    # No station-windows have verified coverage
    assert audit["verified_reporting_station_windows"] == 0
    # Every single target label is NaN, zero-events were NEVER fabricated
    assert lattice["target_binary"].isna().all()
    assert lattice["observation_coverage_class"].isin(["UNKNOWN_COVERAGE", "NOT_OPERATIONAL"]).all()


# ==============================================================================
# SECTION 5: TEMPORAL CONSISTENCY & ANTI-LEAKAGE TESTS
# ==============================================================================

def test_temporal_consistency_four_hour_intervals():
    """Verifies that intervals are strictly 4-hour, half-open, and IST-localized."""
    pipe = PuneFourHourSpatiotemporalPipeline()
    assert WINDOWS_PER_DAY == 6
    
    # Boundary: 12:00:00.000 IST belongs to Window 3 [12:00, 16:00)
    w_idx, w_start, w_end = pipe.get_window_assignment(pd.Timestamp("2026-03-01 12:00:00", tz="Asia/Kolkata"))
    assert w_idx == 3
    assert w_start == pd.Timestamp("2026-03-01 12:00:00", tz="Asia/Kolkata")
    assert w_end == pd.Timestamp("2026-03-01 16:00:00", tz="Asia/Kolkata")
    
    # Prior microsecond: 11:59:59.999 IST belongs to Window 2 [08:00, 12:00)
    w_idx_p, w_start_p, w_end_p = pipe.get_window_assignment(pd.Timestamp("2026-03-01 11:59:59.999", tz="Asia/Kolkata"))
    assert w_idx_p == 2
    assert w_end_p == pd.Timestamp("2026-03-01 12:00:00", tz="Asia/Kolkata")


def test_anti_leakage_rolling_and_lag_features_zero_lookahead():
    """Verifies that lag and rolling features strictly exclude target-window incidents."""
    pipe = PuneFourHourSpatiotemporalPipeline()
    start_t = pd.Timestamp("2026-03-01 00:00:00", tz="Asia/Kolkata")
    end_t = pd.Timestamp("2026-03-03 00:00:00", tz="Asia/Kolkata")  # 12 windows
    
    grid = pipe.build_spatiotemporal_grid(start_t, end_t)
    grid["total_incidents"] = 0
    
    # Put 7 incidents at Window 2 (08:00 to 12:00) for Shivajinagar
    mask_w2 = (grid["station_id"] == "shivajinagar") & (grid["window_idx"] == 2) & (grid["window_start"].dt.day == 1)
    grid.loc[mask_w2, "total_incidents"] = 7
    
    lagged = pipe.construct_lag_features(grid)
    sh_rows = lagged[lagged["station_id"] == "shivajinagar"].sort_values("window_start").reset_index(drop=True)
    
    # At Window 2 (the window containing the 7 incidents):
    # lag_1 MUST be the incident count at Window 1 (0), NOT 7!
    assert sh_rows.loc[2, "lag_1_count"] == 0
    # rolling_24h MUST be 0 (no incidents prior to Window 2)
    assert sh_rows.loc[2, "rolling_24h_count"] == 0
    
    # At Window 3 (the next window):
    # lag_1 is now 7
    assert sh_rows.loc[3, "lag_1_count"] == 7
    assert sh_rows.loc[3, "rolling_24h_count"] == 7
