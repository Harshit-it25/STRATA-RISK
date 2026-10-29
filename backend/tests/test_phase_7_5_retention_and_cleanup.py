"""
Unit and integration tests for Phase 7.5 Retention Authorization and Privacy Pre-Submission Audit.

Verifies:
1. Cryptographic Deletion Approval Tokens:
   - Cryptographic authentication using Ed25519 signatures over RFC 8785 canonical payloads.
   - Strict binding to action ('AUTHORIZE_DATASET_DELETION'), dataset version, dataset SHA-256 fingerprint,
     active retention policy reference, and temporal approval period.
   - Rejection of arbitrary strings, user-controlled Booleans, malformed JSON, and unprovisioned keys.
   - Rejection of expired, not-yet-valid, revoked, or replayed deletion approval tokens.
   - Missing institutional approval strictly prevents real-data deletion.
   - execute_authorized_deletion execution with audit receipt generation and replay lockout.
2. Failure-Path Ingestion Cleanup:
   - Schema validation, PII violation, signature failure, and fingerprint mismatch leave raw datasets untouched.
   - Output generation failure / interruption purges partial version directory without deleting raw data.
   - Duplicate-version collisions preserve existing version directories and raw data untouched.
"""

import os
import json
import shutil
import hashlib
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
import pandas as pd
from cryptography.hazmat.primitives.asymmetric import ed25519

from backend.services.pune_data_readiness import (
    PuneRetentionPolicyConfig,
    PuneRetentionPolicyStatus,
    DEFAULT_RETENTION_POLICY_CONFIG,
    InstitutionalIssuerRegistry,
    canonicalize_rfc8785,
)
from backend.ingestion.pune_ingestion_pipeline import (
    PuneDataIngestionPipeline,
    PIIViolationError,
    SchemaValidationError,
)

# Standard test sandbox private key whose public key matches DEFAULT_TEST_FIXTURE_PUBLIC_KEY
TEST_SANDBOX_PRIVATE_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(
    bytes.fromhex("fb9b4e3e1a5b86449380ff61bfcec074be7ad2dc2b7e422e9968eb67a26ae0e6")
)


@pytest.fixture(autouse=True)
def clean_test_registries():
    """Ensures revocation and token consumption registries are reset for every test."""
    InstitutionalIssuerRegistry.clear_trusted_revocations()
    PuneRetentionPolicyConfig.clear_consumed_tokens()
    yield
    InstitutionalIssuerRegistry.clear_trusted_revocations()
    PuneRetentionPolicyConfig.clear_consumed_tokens()


@pytest.fixture
def mock_institutional_keypair():
    """Generates an ephemeral Ed25519 keypair for mock institutional signing."""
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_hex = priv.public_key().public_bytes_raw().hex()
    return priv, pub_hex


@pytest.fixture
def approved_retention_policy():
    """Returns an officially approved Pune retention policy configuration."""
    return PuneRetentionPolicyConfig(
        is_approved_by_institution=True,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
        approved_retention_days=365,
        approval_reference="MOU/PUNE-COP/2026/STRATA-001",
    )


# ==============================================================================
# SECTION 1: AUDIT RETENTION APPROVAL TOKENS
# ==============================================================================

def test_unapproved_policy_strictly_prohibits_real_data_deletion(mock_institutional_keypair):
    """Missing institutional approval prevents real-data deletion, even with valid token and operator confirmation."""
    priv_key, pub_hex = mock_institutional_keypair
    unapproved_cfg = DEFAULT_RETENTION_POLICY_CONFIG

    # Generate a syntactically valid signed token
    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="deadbeef" * 8,
            policy_reference="MOU/PUNE-COP/2026/STRATA-001",
            issuer_id="pune_city_police_cop",
        )

        # can_delete_real_data must return False
        assert unapproved_cfg.can_delete_real_data(
            is_manual_operator_confirmed=True,
            approval_token=token,
            dataset_version="v1",
            dataset_sha256="deadbeef" * 8,
        ) is False

        # execute_authorized_deletion must raise PermissionError
        with pytest.raises(PermissionError, match="Deletion blocked: Institutional retention policy is unapproved"):
            unapproved_cfg.execute_authorized_deletion(
                target_path="dummy_path",
                is_manual_operator_confirmed=True,
                approval_token=token,
            )


def test_user_controlled_boolean_and_arbitrary_string_rejected(approved_retention_policy):
    """User-controlled Booleans and arbitrary strings cannot approve deletion."""
    policy = approved_retention_policy

    # Arbitrary strings
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="TOKEN123") is False
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="APPROVED") is False
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="true") is False

    # User-controlled booleans
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=True) is False
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=False) is False

    # Empty / None
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=None) is False
    assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="") is False

    # Arbitrary JSON object missing cryptographic fields
    assert policy.can_delete_real_data(
        is_manual_operator_confirmed=True,
        approval_token=json.dumps({"approved": True, "token": "arbitrary"}),
    ) is False


def test_cryptographically_authenticated_deletion_token_success(approved_retention_policy, mock_institutional_keypair):
    """Authentic Ed25519 token bound to matching action, version, sha256, and policy authorizes deletion."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1.0",
            dataset_sha256="aa" * 32,
            policy_reference=policy.approval_reference,
            issuer_id="pune_city_police_cop",
        )

        assert policy.can_delete_real_data(
            is_manual_operator_confirmed=True,
            approval_token=token,
            dataset_version="v1.0",
            dataset_sha256="aa" * 32,
        ) is True

        # Stringified JSON token also works
        token_json = json.dumps(token)
        assert policy.can_delete_real_data(
            is_manual_operator_confirmed=True,
            approval_token=token_json,
            dataset_version="v1.0",
            dataset_sha256="aa" * 32,
        ) is True


def test_unprovisioned_institutional_public_key_fails_closed(approved_retention_policy, mock_institutional_keypair):
    """When institutional public key is unprovisioned, token verification fails closed."""
    priv_key, _ = mock_institutional_keypair
    policy = approved_retention_policy

    # Ensure environment variable is unset
    with patch.dict(os.environ, {}, clear=True):
        if "PUNE_COP_ED25519_PUBLIC_KEY" in os.environ:
            del os.environ["PUNE_COP_ED25519_PUBLIC_KEY"]

        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="bb" * 32,
            policy_reference=policy.approval_reference,
            issuer_id="pune_city_police_cop",
        )

        is_valid, reason = policy.verify_deletion_approval_token(token)
        assert is_valid is False
        assert "Institutional public verification key for issuer 'pune_city_police_cop' is unprovisioned" in reason
        assert policy.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=token) is False


def test_token_binding_mismatches_rejected(approved_retention_policy, mock_institutional_keypair):
    """Token bound to mismatched action, version, fingerprint, or policy reference is rejected."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        # 1. Action mismatch
        token_bad_action = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="cc" * 32,
            policy_reference=policy.approval_reference,
            action="UNAUTHORIZED_ACTION",
        )
        is_valid, reason = policy.verify_deletion_approval_token(token_bad_action)
        assert is_valid is False
        assert "Invalid token action" in reason

        # 2. Policy reference mismatch
        token_bad_policy = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="cc" * 32,
            policy_reference="DIFFERENT/POLICY/REF/999",
        )
        is_valid, reason = policy.verify_deletion_approval_token(token_bad_policy)
        assert is_valid is False
        assert "Token policy reference 'DIFFERENT/POLICY/REF/999' does not match active approved policy reference" in reason

        # 3. Dataset version mismatch
        token_valid = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="cc" * 32,
            policy_reference=policy.approval_reference,
        )
        is_valid, reason = policy.verify_deletion_approval_token(token_valid, expected_dataset_version="v2")
        assert is_valid is False
        assert "Token dataset version 'v1' does not match target version 'v2'" in reason

        # 4. Dataset SHA-256 fingerprint mismatch
        is_valid, reason = policy.verify_deletion_approval_token(token_valid, expected_dataset_sha256="dd" * 32)
        assert is_valid is False
        assert "Token dataset fingerprint" in reason


def test_expired_and_not_yet_valid_tokens_rejected(approved_retention_policy, mock_institutional_keypair):
    """Tokens outside their temporal validity period are rejected."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        # Expired token
        expired_token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="ee" * 32,
            policy_reference=policy.approval_reference,
            valid_from_iso="2025-01-01T00:00:00Z",
            valid_until_iso="2025-01-02T00:00:00Z",
        )
        is_valid, reason = policy.verify_deletion_approval_token(expired_token)
        assert is_valid is False
        assert "Token has expired" in reason

        # Future token (not yet valid)
        future_token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="ee" * 32,
            policy_reference=policy.approval_reference,
            valid_from_iso="2030-01-01T00:00:00Z",
            valid_until_iso="2030-01-02T00:00:00Z",
        )
        is_valid, reason = policy.verify_deletion_approval_token(future_token)
        assert is_valid is False
        assert "Token is not yet active" in reason


def test_revoked_token_rejected(approved_retention_policy, mock_institutional_keypair):
    """Revoked deletion tokens are rejected."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="ff" * 32,
            policy_reference=policy.approval_reference,
            authorization_id="REVOKED-DEL-001",
        )

        # Register revocation
        InstitutionalIssuerRegistry.register_revocation("REVOKED-DEL-001")

        is_valid, reason = policy.verify_deletion_approval_token(token)
        assert is_valid is False
        assert "revoked" in reason.lower()


def test_replayed_deletion_token_rejected(approved_retention_policy, mock_institutional_keypair):
    """A consumed deletion approval token cannot be replayed."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="11" * 32,
            policy_reference=policy.approval_reference,
            token_id="SINGLE-USE-TOKEN-001",
        )

        # First consumption succeeds
        is_valid, reason = policy.verify_deletion_approval_token(token, consume_token=True)
        assert is_valid is True

        # Second attempt (replay) must be rejected
        is_valid, reason = policy.verify_deletion_approval_token(token, consume_token=True)
        assert is_valid is False
        assert "Replay rejected: token_id 'SINGLE-USE-TOKEN-001' has already been consumed" in reason


def test_tampered_token_signature_rejected(approved_retention_policy, mock_institutional_keypair):
    """Tampering with signed token payload invalidates Ed25519 signature."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=priv_key,
            dataset_version="v1",
            dataset_sha256="22" * 32,
            policy_reference=policy.approval_reference,
        )

        # Tamper with dataset_version in payload without updating signature
        tampered_token = dict(token)
        tampered_token["dataset_version"] = "v2"

        is_valid, reason = policy.verify_deletion_approval_token(tampered_token)
        assert is_valid is False
        assert "Cryptographic token verification failed" in reason


def test_execute_authorized_deletion_success_and_replay_lock(approved_retention_policy, mock_institutional_keypair):
    """execute_authorized_deletion deletes target file, emits audit receipt, and prevents replay."""
    priv_key, pub_hex = mock_institutional_keypair
    policy = approved_retention_policy

    temp_dir = tempfile.mkdtemp()
    target_file = os.path.join(temp_dir, "incident_data.csv")
    with open(target_file, "w") as f:
        f.write("test,data\n1,2\n")

    hasher = hashlib.sha256()
    with open(target_file, "rb") as f:
        hasher.update(f.read())
    file_sha256 = hasher.hexdigest()

    try:
        with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
            token = PuneRetentionPolicyConfig.create_deletion_approval_token(
                signing_private_key=priv_key,
                dataset_version="v1",
                dataset_sha256=file_sha256,
                policy_reference=policy.approval_reference,
                token_id="EXEC-TOKEN-001",
            )

            # Deletion succeeds
            receipt = policy.execute_authorized_deletion(
                target_path=target_file,
                is_manual_operator_confirmed=True,
                approval_token=token,
                dataset_version="v1",
                dataset_sha256=file_sha256,
            )

            assert receipt["status"] == "SUCCESS"
            assert receipt["target_path"] == target_file
            assert receipt["policy_reference"] == policy.approval_reference
            assert not os.path.exists(target_file)

            # Replaying the same token on another file must fail with PermissionError
            target_file_2 = os.path.join(temp_dir, "other.csv")
            with open(target_file_2, "w") as f:
                f.write("hello")

            with pytest.raises(PermissionError, match="Replay rejected"):
                policy.execute_authorized_deletion(
                    target_path=target_file_2,
                    is_manual_operator_confirmed=True,
                    approval_token=token,
                    dataset_version="v1",
                    dataset_sha256=file_sha256,
                )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# SECTION 2: FAILURE-PATH CLEANUP AND RAW DATA PROTECTION
# ==============================================================================

def test_failure_during_output_generation_purges_partial_version_dir(mock_institutional_keypair):
    """If an exception occurs while writing artifacts, the partial version_dir is cleaned up and raw data preserved."""
    priv_key, pub_hex = mock_institutional_keypair
    temp_dir = tempfile.mkdtemp()
    try:
        # Create a valid raw dataset
        raw_csv_path = os.path.join(temp_dir, "raw_pune_data.csv")
        df_raw = pd.DataFrame([
            {
                "fir_number_hash": hashlib.sha256(f"FIR-2024-{i:04d}".encode("utf-8")).hexdigest(),
                "police_station_id": "shivajinagar",
                "incident_datetime": "2024-06-01T10:00:00Z",
                "section_code": "379",
                "registration_datetime": "2024-06-01T11:00:00Z",
                "place_of_occurrence": "FC Road Pune",
                "latitude": 18.5204,
                "longitude": 73.8567,
            }
            for i in range(25)
        ])
        df_raw.to_csv(raw_csv_path, index=False)

        raw_sha256 = hashlib.sha256(open(raw_csv_path, "rb").read()).hexdigest()

        with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
            auth_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
                mou_reference="MOU/PUNE-COP/2026/STRATA-001",
                issuer_id="pune_city_police_cop",
                signing_private_key=priv_key,
                dataset_sha256=raw_sha256,
                is_fixture=False,
            )

            dest_root = os.path.join(temp_dir, "intake_store")
            target_version_dir = os.path.join(dest_root, "v1")

            # Simulate write failure during intake manifest writing
            with patch("json.dump", side_effect=[None, RuntimeError("Simulated disk write failure on manifest")]):
                with pytest.raises(RuntimeError, match="Simulated disk write failure"):
                    PuneDataIngestionPipeline.ingest_authorized_dataset(
                        raw_dataset_path=raw_csv_path,
                        destination_root_dir=dest_root,
                        version="1",
                        manifest=auth_manifest,
                        is_fixture=False,
                    )

            # 1. Partial version directory must have been purged
            assert not os.path.exists(target_version_dir)

            # 2. Authoritative raw dataset must remain completely untouched
            assert os.path.exists(raw_csv_path)
            assert hashlib.sha256(open(raw_csv_path, "rb").read()).hexdigest() == raw_sha256
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_schema_and_pii_failures_preserve_raw_data_and_create_no_artifacts(mock_institutional_keypair):
    """Schema and PII screening failures fail before version directory creation and preserve raw data."""
    priv_key, pub_hex = mock_institutional_keypair
    temp_dir = tempfile.mkdtemp()
    dest_root = os.path.join(temp_dir, "intake_store")

    try:
        with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
            # 1. PII Violation
            pii_csv_path = os.path.join(temp_dir, "pii_data.csv")
            df_pii = pd.DataFrame([
                {
                    "fir_number": "FIR-001",
                    "police_station": "shivajinagar",
                    "incident_date": "2024-06-01 10:00:00",
                    "ipc_section": "IPC 379",
                    "registration_date": "2024-06-01 11:00:00",
                    "place_of_occurrence": "FC Road",
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "victim_name": "Citizen Jane Doe",  # Prohibited PII
                }
            ])
            df_pii.to_csv(pii_csv_path, index=False)
            pii_sha = hashlib.sha256(open(pii_csv_path, "rb").read()).hexdigest()

            auth_pii = InstitutionalIssuerRegistry.create_authorized_manifest(
                mou_reference="MOU/PUNE-COP/2026/STRATA-001",
                issuer_id="pune_city_police_cop",
                signing_private_key=priv_key,
                dataset_sha256=pii_sha,
                is_fixture=False,
            )

            with pytest.raises(PIIViolationError):
                PuneDataIngestionPipeline.ingest_authorized_dataset(
                    raw_dataset_path=pii_csv_path,
                    destination_root_dir=dest_root,
                    version="1",
                    manifest=auth_pii,
                    is_fixture=False,
                )

            # Raw file preserved, destination version dir never created
            assert os.path.exists(pii_csv_path)
            assert not os.path.exists(os.path.join(dest_root, "v1"))

            # 2. Schema Validation Failure
            schema_csv_path = os.path.join(temp_dir, "schema_fail.csv")
            df_schema = pd.DataFrame([
                {
                    "fir_number": "FIR-001",
                    # missing police_station, incident_date, ipc_section
                    "place_of_occurrence": "FC Road",
                }
            ])
            df_schema.to_csv(schema_csv_path, index=False)
            schema_sha = hashlib.sha256(open(schema_csv_path, "rb").read()).hexdigest()

            auth_schema = InstitutionalIssuerRegistry.create_authorized_manifest(
                mou_reference="MOU/PUNE-COP/2026/STRATA-001",
                issuer_id="pune_city_police_cop",
                signing_private_key=priv_key,
                dataset_sha256=schema_sha,
                is_fixture=False,
            )

            with pytest.raises(SchemaValidationError):
                PuneDataIngestionPipeline.ingest_authorized_dataset(
                    raw_dataset_path=schema_csv_path,
                    destination_root_dir=dest_root,
                    version="2",
                    manifest=auth_schema,
                    is_fixture=False,
                )

            assert os.path.exists(schema_csv_path)
            assert not os.path.exists(os.path.join(dest_root, "v2"))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_signature_and_fingerprint_failures_preserve_raw_data(mock_institutional_keypair):
    """Signature verification failures and hash mismatches fail closed before version creation."""
    priv_key, pub_hex = mock_institutional_keypair
    temp_dir = tempfile.mkdtemp()
    dest_root = os.path.join(temp_dir, "intake_store")

    try:
        raw_csv = os.path.join(temp_dir, "data.csv")
        with open(raw_csv, "w") as f:
            f.write("fir_number,police_station,incident_date,ipc_section\n1,shivajinagar,2024-01-01 00:00:00,IPC 379\n")

        with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
            # Manifest with mismatched SHA-256
            auth_bad_hash = InstitutionalIssuerRegistry.create_authorized_manifest(
                mou_reference="MOU/PUNE-COP/2026/STRATA-001",
                issuer_id="pune_city_police_cop",
                signing_private_key=priv_key,
                dataset_sha256="00" * 32,  # Wrong hash
                is_fixture=False,
            )

            with pytest.raises(ValueError, match="Dataset intake blocked by authorization failure"):
                PuneDataIngestionPipeline.ingest_authorized_dataset(
                    raw_dataset_path=raw_csv,
                    destination_root_dir=dest_root,
                    version="1",
                    manifest=auth_bad_hash,
                    is_fixture=False,
                )

            assert os.path.exists(raw_csv)
            assert not os.path.exists(os.path.join(dest_root, "v1"))
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_duplicate_version_rejection_preserves_existing_directory_and_raw_data(mock_institutional_keypair):
    """Existing version directory raises FileExistsError and preserves both existing files and raw data."""
    priv_key, pub_hex = mock_institutional_keypair
    temp_dir = tempfile.mkdtemp()
    dest_root = os.path.join(temp_dir, "intake_store")

    try:
        # Pre-create v1 directory with existing content
        v1_dir = os.path.join(dest_root, "v1")
        os.makedirs(v1_dir, exist_ok=True)
        sentinel_file = os.path.join(v1_dir, "sentinel.txt")
        with open(sentinel_file, "w") as f:
            f.write("EXISTING_DATA_V1")

        raw_csv = os.path.join(temp_dir, "raw_data.csv")
        df_raw = pd.DataFrame([
            {
                "fir_number": "FIR-001",
                "police_station": "shivajinagar",
                "incident_date": "2024-06-01 10:00:00",
                "ipc_section": "IPC 379",
                "registration_date": "2024-06-01 11:00:00",
                "place_of_occurrence": "FC Road",
                "latitude": 18.5204,
                "longitude": 73.8567,
            }
        ])
        df_raw.to_csv(raw_csv, index=False)
        raw_sha = hashlib.sha256(open(raw_csv, "rb").read()).hexdigest()

        with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
            auth_manifest = InstitutionalIssuerRegistry.create_authorized_manifest(
                mou_reference="MOU/PUNE-COP/2026/STRATA-001",
                issuer_id="pune_city_police_cop",
                signing_private_key=priv_key,
                dataset_sha256=raw_sha,
                is_fixture=False,
            )

            # Ingestion targeting existing v1 must raise FileExistsError
            with pytest.raises(FileExistsError, match="Intake destination version directory already exists"):
                PuneDataIngestionPipeline.ingest_authorized_dataset(
                    raw_dataset_path=raw_csv,
                    destination_root_dir=dest_root,
                    version="1",
                    manifest=auth_manifest,
                    is_fixture=False,
                )

            # Sentinel file in v1 must still exist completely unmodified
            assert os.path.exists(sentinel_file)
            with open(sentinel_file, "r") as f:
                assert f.read() == "EXISTING_DATA_V1"

            # Raw dataset must remain intact
            assert os.path.exists(raw_csv)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

