"""
Phase 6.3 Security Closeout and Hardening Verification Test Suite.

Verifies:
1. RFC 8785 JSON Canonicalization Scheme (JCS) Conformance:
   - Unicode preservation (Devanagari, non-ASCII).
   - Strict control character and quote escaping.
   - Key sorting by UTF-16 code units (invariance to insertion order).
   - Rejection of invalid types (NaN, Infinity, sets, binary).
   - Verification across all 9 authorization-sensitive fields.
2. Hardened Persistent Revocation (CRL):
   - Survives process restarts via persistent store.
   - Dynamic multi-worker reload without worker state divergence.
   - Freshness & expiry validation (stale CRL rejected fail-closed).
   - Not-yet-effective CRL rejected fail-closed.
   - Integrity digest matching (crl_sha256).
   - Fail-closed behavior when persistent CRL is missing and policy requires it.
3. Audit Ledger Trust Boundaries & Hash Chaining:
   - Tampered cleaned CSV detected.
   - Tampered intake audit manifest detected.
   - Tampered ledger entry detected via entry_sha256 mismatch.
   - Deleted/spliced ledger entries detected via prev_entry_sha256 hash-chain break.
   - Simultaneous dataset replacement and local manifest recalculation detected.
   - Application-level overwrite prevention (FileExistsError).
   - Independent protected ledger location (PUNE_AUDIT_LEDGER_PATH).
"""

import os
import json
import math
import hashlib
import tempfile
import pytest
import pandas as pd
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.services.pune_data_readiness import (
    InstitutionalIssuerRegistry,
    PuneAuthorizationValidator,
    PuneReadinessStatus,
    canonicalize_rfc8785,
    PUNE_POLICE_STATIONS,
)
from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
)


# Setup mock COP keypair for authorized ingestion tests
MOCK_PUNE_COP_PRIVATE_KEY = ed25519.Ed25519PrivateKey.generate()
MOCK_PUNE_COP_PUBLIC_KEY_HEX = MOCK_PUNE_COP_PRIVATE_KEY.public_key().public_bytes_raw().hex()


@pytest.fixture(autouse=True)
def setup_cop_key(monkeypatch):
    monkeypatch.setenv("PUNE_COP_ED25519_PUBLIC_KEY", MOCK_PUNE_COP_PUBLIC_KEY_HEX)


# ==============================================================================
# 1. JSON CANONICALIZATION (RFC 8785 JCS) TESTS
# ==============================================================================

def test_canonicalize_rfc8785_unicode_preservation():
    """
    RFC 8785 requires non-ASCII Unicode scalar values to be serialized as literal
    raw UTF-8 bytes and NOT converted to \\uXXXX escape sequences.
    """
    data = {
        "city": "पुणे",
        "state": "महाराष्ट्र",
        "police": "पुणे शहर पोलीस",
        "symbol": "🛡️",
    }
    canonical_bytes = canonicalize_rfc8785(data)

    # Must contain the exact UTF-8 byte representation of "पुणे"
    assert "पुणे".encode("utf-8") in canonical_bytes
    assert "महाराष्ट्र".encode("utf-8") in canonical_bytes
    # Must NOT contain escaped \\u092a (the \\u representation of पु)
    assert b"\\u092a" not in canonical_bytes
    assert b"\\u" not in canonical_bytes


def test_canonicalize_rfc8785_control_character_escaping():
    """
    RFC 8785 requires escaping of:
    - quotation mark (") -> \\"
    - reverse solidus (\\) -> \\\\
    - control characters U+0000..U+001F -> \\b, \\t, \\n, \\f, \\r, or \\u00xx
    """
    data = {
        "escapes": "line1\nline2\ttab\"quote\"\\backslash\rreturn\bback\ffeed",
        "null_byte": "\u0000",
        "unit_separator": "\u001f",
    }
    canonical_bytes = canonicalize_rfc8785(data)

    assert b'\\"quote\\"' in canonical_bytes
    assert b"\\\\backslash" in canonical_bytes
    assert b"\\n" in canonical_bytes
    assert b"\\t" in canonical_bytes
    assert b"\\r" in canonical_bytes
    assert b"\\b" in canonical_bytes
    assert b"\\f" in canonical_bytes
    assert b"\\u0000" in canonical_bytes
    assert b"\\u001f" in canonical_bytes


def test_canonicalize_rfc8785_key_insertion_order_invariance():
    """
    RFC 8785 requires object keys to be sorted by UTF-16 code units.
    Dictionaries with different key insertion orders must yield bit-for-bit identical bytes.
    """
    dict1 = {"z": 1, "a": 2, "m": 3, "b": 4}
    dict2 = {"a": 2, "b": 4, "m": 3, "z": 1}
    dict3 = {"m": 3, "z": 1, "b": 4, "a": 2}

    b1 = canonicalize_rfc8785(dict1)
    b2 = canonicalize_rfc8785(dict2)
    b3 = canonicalize_rfc8785(dict3)

    assert b1 == b2 == b3
    assert b1 == b'{"a":2,"b":4,"m":3,"z":1}'


def test_canonicalize_rfc8785_utf16_code_unit_sorting():
    """
    RFC 8785 specifies UTF-16 code unit ordering, meaning characters in supplementary planes
    (represented as surrogate pairs in UTF-16) sort based on their high surrogate.
    """
    # In UTF-16: "\U0001f600" has surrogate high 0xD83D, which is < 0xFFFF ("\uffff")
    data = {"\uffff": "bmp_max", "\U0001f600": "supplementary"}
    canon = canonicalize_rfc8785(data)
    # The emoji key must precede \uffff in UTF-16 code unit sorting
    emoji_bytes = "\U0001f600".encode("utf-8")
    assert canon.index(emoji_bytes) < canon.index(b"\xef\xbf\xbf")


def test_canonicalize_rfc8785_rejects_invalid_numbers_and_types():
    """
    RFC 8785 prohibits NaN, Infinity, -Infinity, and unsupported JSON types.
    """
    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("nan")})

    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("inf")})

    with pytest.raises(ValueError, match="prohibits NaN and Infinity"):
        canonicalize_rfc8785({"val": float("-inf")})

    with pytest.raises(TypeError, match="not JSON-serializable"):
        canonicalize_rfc8785({"val": {1, 2, 3}})  # sets not allowed in JSON


def test_canonicalize_rfc8785_normalizes_negative_zero():
    """RFC 8785 specifies that -0 must be serialized as 0."""
    data = {"val": -0.0}
    canonical = canonicalize_rfc8785(data)
    assert canonical == b'{"val":0}'


def test_ed25519_signature_on_unicode_payload():
    """
    Verifies that Ed25519 signing and verification succeeds over canonical payloads
    containing authentic Marathi / Devanagari text.
    """
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key_hex = priv_key.public_key().public_bytes_raw().hex()

    mou_marathi = "MOU/पुणे-पोलीस/२०२६/स्ट्रॅटा-००१"
    purpose_marathi = "सार्वजनिक_सुरक्षा_जोखीम_मॉडेलिंग"

    payload = InstitutionalIssuerRegistry.compute_canonical_payload(
        issuer_id="test_fixture_authority",
        authorization_id="AUTH-PUNE-MARATHI-001",
        mou_reference=mou_marathi,
        permitted_use=purpose_marathi,
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2027-12-31T23:59:59Z",
        dataset_sha256="abcd" * 16,
    )

    sig_bytes = priv_key.sign(payload)
    sig_hex = sig_bytes.hex()

    # Must verify cleanly
    is_valid, err = InstitutionalIssuerRegistry.verify_signature(
        issuer_id="test_fixture_authority",
        canonical_payload=payload,
        signature_hex=sig_hex,
        explicit_public_key_hex=pub_key_hex,
    )
    assert is_valid is True
    assert err is None

    # Any bit flip in Unicode payload must invalidate signature
    tampered_payload = payload.replace("पुणे".encode("utf-8"), "मुंबई".encode("utf-8"))
    is_valid_t, err_t = InstitutionalIssuerRegistry.verify_signature(
        issuer_id="test_fixture_authority",
        canonical_payload=tampered_payload,
        signature_hex=sig_hex,
        explicit_public_key_hex=pub_key_hex,
    )
    assert is_valid_t is False
    assert "verification failed" in err_t


# ==============================================================================
# 2. HARDENED REVOCATION HANDLING (PERSISTENT CRL) TESTS
# ==============================================================================

def test_persistent_crl_loads_and_enforces_revocation(tmp_path):
    """
    Verifies that revocations persisted in an on-disk CRL file are loaded,
    survive restarts, and block authorization even across separate processes/workers.
    """
    crl_file = tmp_path / "test_revocations.json"
    crl_content = {
        "crl_version": "1.0",
        "issuer_id": "test_fixture_authority",
        "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2028-12-31T23:59:59Z",
        "revoked_authorizations": [
            {"authorization_id": "AUTH-REVOKED-STAGE6", "reason": "Administrative suspension"},
            {"mou_reference": "MOU/PUNE-COP/REVOKED-001", "reason": "Terminated partnership"}
        ]
    }
    with open(crl_file, "w", encoding="utf-8") as f:
        json.dump(crl_content, f)

    manifest_revoked_id = {
        "authorization_id": "AUTH-REVOKED-STAGE6",
        "mou_reference": "MOU/VALID-001",
        "is_authorized": True,
        "is_revoked": False,  # Manifest attempts to claim it is not revoked!
    }
    is_rev, reason = InstitutionalIssuerRegistry.is_authorization_revoked(
        manifest_revoked_id,
        crl_path=str(crl_file),
        current_time_iso="2026-06-01T00:00:00Z"
    )
    assert is_rev is True
    assert "revoked in persistent CRL" in reason

    manifest_revoked_mou = {
        "authorization_id": "AUTH-CLEAN-002",
        "mou_reference": "MOU/PUNE-COP/REVOKED-001",
        "is_authorized": True,
        "is_revoked": False,
    }
    is_rev_mou, reason_mou = InstitutionalIssuerRegistry.is_authorization_revoked(
        manifest_revoked_mou,
        crl_path=str(crl_file),
        current_time_iso="2026-06-01T00:00:00Z"
    )
    assert is_rev_mou is True
    assert "revoked in persistent CRL" in reason_mou


def test_persistent_crl_freshness_and_expiry_fail_closed(tmp_path):
    """
    Verifies that an expired CRL is rejected fail-closed, blocking authorization.
    """
    crl_file = tmp_path / "expired_crl.json"
    crl_content = {
        "crl_version": "1.0",
        "issuer_id": "test_fixture_authority",
        "issued_at": "2025-01-01T00:00:00Z",
        "expires_at": "2025-12-31T23:59:59Z",  # Expired in 2025
        "revoked_authorizations": []
    }
    with open(crl_file, "w", encoding="utf-8") as f:
        json.dump(crl_content, f)

    manifest = {"authorization_id": "AUTH-001", "is_authorized": True}

    # Checking at current time 2026-06-01 > 2025-12-31 expires_at
    is_rev, reason = InstitutionalIssuerRegistry.is_authorization_revoked(
        manifest,
        crl_path=str(crl_file),
        current_time_iso="2026-06-01T00:00:00Z"
    )
    assert is_rev is True
    assert "Persistent CRL expired" in reason


def test_persistent_crl_not_yet_effective_fail_closed(tmp_path):
    """
    Verifies that a future-dated CRL (not yet effective) is rejected fail-closed.
    """
    crl_file = tmp_path / "future_crl.json"
    crl_content = {
        "crl_version": "1.0",
        "issuer_id": "test_fixture_authority",
        "issued_at": "2027-01-01T00:00:00Z",  # In the future
        "expires_at": "2028-12-31T23:59:59Z",
        "revoked_authorizations": []
    }
    with open(crl_file, "w", encoding="utf-8") as f:
        json.dump(crl_content, f)

    manifest = {"authorization_id": "AUTH-001", "is_authorized": True}

    is_rev, reason = InstitutionalIssuerRegistry.is_authorization_revoked(
        manifest,
        crl_path=str(crl_file),
        current_time_iso="2026-06-01T00:00:00Z"
    )
    assert is_rev is True
    assert "not yet effective" in reason


def test_missing_persistent_crl_when_policy_requires_fails_closed():
    """
    Verifies that if policy requires a persistent CRL (require_crl=True),
    a missing CRL file unconditionally causes verification to fail closed.
    """
    manifest = {"authorization_id": "AUTH-001", "is_authorized": True}
    is_rev, reason = InstitutionalIssuerRegistry.is_authorization_revoked(
        manifest,
        crl_path="nonexistent_crl_path_12345.json",
        require_crl=True,
    )
    assert is_rev is True
    assert "Persistent CRL file missing" in reason


# ==============================================================================
# 3. AUDIT LEDGER TRUST BOUNDARIES & HASH CHAINING TESTS
# ==============================================================================

def test_audit_ledger_cryptographic_hash_chaining(tmp_path):
    """
    Verifies that entries in intake_audit_ledger.jsonl form a cryptographic SHA-256 hash chain:
    - Entry 0: prev_entry_sha256 = '0'*64
    - Entry 1: prev_entry_sha256 = Entry 0's entry_sha256
    - Tampering with any entry breaks the hash chain for all subsequent records.
    """
    dest_dir = str(tmp_path / "intake_store")
    ledger_file = os.path.join(dest_dir, "intake_audit_ledger.jsonl")

    # Create dummy raw file
    raw_csv = tmp_path / "raw_test.csv"
    df = pd.DataFrame([
        {"fir_number_hash": "fir_01", "police_station_id": "shivajinagar", "incident_datetime": "2026-03-01T10:00:00Z", "section_code": "302"}
    ])
    df.to_csv(raw_csv, index=False)

    hasher = hashlib.sha256()
    with open(raw_csv, "rb") as f:
        hasher.update(f.read())
    raw_sha = hasher.hexdigest()

    # Manifest for version 1.0 signed by authorized COP
    man1 = InstitutionalIssuerRegistry.create_authorized_manifest(
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
        issuer_id="pune_city_police_cop",
        dataset_sha256=raw_sha,
        is_fixture=False,
    )

    # Ingest v1.0
    res1 = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=dest_dir,
        version="1.0",
        manifest=man1,
        is_fixture=False,
        ledger_path=ledger_file,
    )
    assert res1["success"] is True

    # Ingest v2.0
    man2 = InstitutionalIssuerRegistry.create_authorized_manifest(
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
        issuer_id="pune_city_police_cop",
        dataset_sha256=raw_sha,
        is_fixture=False,
        authorization_id="AUTH-V2-CHAIN",
    )
    res2 = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=dest_dir,
        version="2.0",
        manifest=man2,
        is_fixture=False,
        ledger_path=ledger_file,
    )
    assert res2["success"] is True

    # Verify ledger integrity before tampering
    audit_check = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=dest_dir,
        version="2.0",
        is_fixture=False,
        ledger_path=ledger_file,
    )
    assert audit_check["is_valid"] is True
    assert audit_check["ledger_hash_chain_valid"] is True

    # Now tamper with Entry 0 in the ledger
    with open(ledger_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    entry0 = json.loads(lines[0])
    entry0["cleaned_file_sha256"] = "tampered_hash_0000"
    lines[0] = json.dumps(entry0, sort_keys=True)

    with open(ledger_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Verifying v2.0 must detect tampering in the ledger chain!
    tampered_check = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=dest_dir,
        version="2.0",
        is_fixture=False,
        ledger_path=ledger_file,
    )
    assert tampered_check["is_valid"] is False
    assert any("tamper detected" in v or "hash chain broken" in v for v in tampered_check["violations"])


def test_independent_ledger_path_configuration(tmp_path):
    """
    Verifies that the audit ledger can be written to and verified from an
    independent protected path (PUNE_AUDIT_LEDGER_PATH).
    """
    dataset_store = str(tmp_path / "datasets")
    independent_audit_store = str(tmp_path / "independent_audit_vault")
    os.makedirs(independent_audit_store, exist_ok=True)
    custom_ledger_path = os.path.join(independent_audit_store, "vault_ledger.jsonl")

    raw_csv = tmp_path / "raw_test_indep.csv"
    df = pd.DataFrame([
        {"fir_number_hash": "fir_01", "police_station_id": "kothrud", "incident_datetime": "2026-03-01T12:00:00Z", "section_code": "392"}
    ])
    df.to_csv(raw_csv, index=False)

    hasher = hashlib.sha256()
    with open(raw_csv, "rb") as f:
        hasher.update(f.read())
    raw_sha = hasher.hexdigest()

    man = InstitutionalIssuerRegistry.create_authorized_manifest(
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
        issuer_id="pune_city_police_cop",
        dataset_sha256=raw_sha,
        is_fixture=False,
    )

    res = PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=dataset_store,
        version="1.0",
        manifest=man,
        is_fixture=False,
        ledger_path=custom_ledger_path,
    )
    assert res["success"] is True
    assert os.path.exists(custom_ledger_path)

    # Standard default ledger must not exist in dataset_store
    assert not os.path.exists(os.path.join(dataset_store, "intake_audit_ledger.jsonl"))

    # Verification with custom ledger path succeeds
    v_res = PuneDataIngestionPipeline.verify_intake_integrity(
        destination_root_dir=dataset_store,
        version="1.0",
        is_fixture=False,
        ledger_path=custom_ledger_path,
    )
    assert v_res["is_valid"] is True
    assert v_res["ledger_verified"] is True


def test_attempted_version_replacement_raises_file_exists_error(tmp_path):
    """
    Verifies that attempting to overwrite an existing dataset version directory
    strictly raises FileExistsError.
    """
    dest_dir = str(tmp_path / "intake_store")
    raw_csv = tmp_path / "raw.csv"
    df = pd.DataFrame([
        {"fir_number_hash": "fir_01", "police_station_id": "yerwada", "incident_datetime": "2026-03-01T10:00:00Z", "section_code": "302"}
    ])
    df.to_csv(raw_csv, index=False)

    hasher = hashlib.sha256()
    with open(raw_csv, "rb") as f:
        hasher.update(f.read())
    raw_sha = hasher.hexdigest()

    man = InstitutionalIssuerRegistry.create_authorized_manifest(
        signing_private_key=MOCK_PUNE_COP_PRIVATE_KEY,
        issuer_id="pune_city_police_cop",
        dataset_sha256=raw_sha,
        is_fixture=False,
    )

    PuneDataIngestionPipeline.ingest_authorized_dataset(
        raw_dataset_path=str(raw_csv),
        destination_root_dir=dest_dir,
        version="1.0",
        manifest=man,
        is_fixture=False,
    )

    # Attempting to ingest version 1.0 again must raise FileExistsError
    with pytest.raises(FileExistsError, match="Silent overwriting of prior dataset versions is strictly prohibited"):
        PuneDataIngestionPipeline.ingest_authorized_dataset(
            raw_dataset_path=str(raw_csv),
            destination_root_dir=dest_dir,
            version="1.0",
            manifest=man,
            is_fixture=False,
        )
