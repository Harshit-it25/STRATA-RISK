"""
Unit and integration tests for Phase 7.4 Retention Policy Safety Configuration.

Verifies:
1. Strict separation of historical coverage (e.g. 36 months / 1,080 days) from post-acquisition retention (proposed 365 days).
2. Distinct proposed vs approved policy states; missing approval cannot be interpreted as authorization.
3. Fail-closed rejection of inconsistent or invalid retention policy configurations.
4. Prevention of automatic deletion of real datasets based merely on elapsed proposed days.
5. Disaggregation of retention rules across all 8 data categories (raw, cleaned, temporary, derived, statistical, training, audit, backups).
"""

import pytest
from backend.services.pune_data_readiness import (
    PuneRetentionPolicyConfig,
    PuneRetentionPolicyStatus,
    DEFAULT_RETENTION_POLICY_CONFIG,
    PuneThresholdConfig,
)


def test_default_retention_policy_is_unapproved():
    """Default policy must be strictly PROPOSED and NOT approved."""
    config = DEFAULT_RETENTION_POLICY_CONFIG
    assert config.is_approved_by_institution is False
    assert config.policy_status == PuneRetentionPolicyStatus.PROPOSED_PENDING_INSTITUTIONAL_APPROVAL
    assert config.approved_retention_days is None
    assert config.approval_reference is None
    assert config.proposed_retention_days == 365
    # Default policy validation should pass without error
    config.validate_configuration()


def test_historical_coverage_distinct_from_post_acquisition_retention():
    """Historical data coverage (1,080 days) is distinct from post-acquisition retention (365 days)."""
    thresh_cfg = PuneThresholdConfig()
    ret_cfg = PuneRetentionPolicyConfig()

    # Historical coverage is how far back past observations extend
    assert thresh_cfg.training_timespan_days == 1080.0  # 36 months of crime history
    assert thresh_cfg.eda_timespan_days == 180.0        # 6 months of crime history

    # Retention is how long received files may be kept post-receipt
    assert ret_cfg.proposed_retention_days == 365       # Proposed post-acquisition shelf-life
    assert ret_cfg.approved_retention_days is None      # Not yet approved

    # Values must not be conflated
    assert thresh_cfg.training_timespan_days != ret_cfg.proposed_retention_days


def test_unapproved_policy_cannot_assert_approved_days():
    """Setting approved_retention_days without institutional approval raises ValueError."""
    config = PuneRetentionPolicyConfig(
        is_approved_by_institution=False,
        approved_retention_days=365,
    )
    with pytest.raises(ValueError, match="Approved retention days cannot be set when is_approved_by_institution is False"):
        config.validate_configuration()


def test_unapproved_policy_cannot_claim_approved_status():
    """Setting policy_status to APPROVED without institutional approval raises ValueError."""
    config = PuneRetentionPolicyConfig(
        is_approved_by_institution=False,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
    )
    with pytest.raises(ValueError, match="Policy status cannot be APPROVED_BY_COMMISSIONERATE when is_approved_by_institution is False"):
        config.validate_configuration()


def test_approved_policy_requires_reference_and_positive_days():
    """Approved policy must have positive days and an approval reference."""
    # Missing reference
    c1 = PuneRetentionPolicyConfig(
        is_approved_by_institution=True,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
        approved_retention_days=365,
        approval_reference=None,
    )
    with pytest.raises(ValueError, match="Approved retention policy requires an official institutional approval reference"):
        c1.validate_configuration()

    # Zero or negative days
    c2 = PuneRetentionPolicyConfig(
        is_approved_by_institution=True,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
        approved_retention_days=0,
        approval_reference="MOU/PUNE-COP/2026/001",
    )
    with pytest.raises(ValueError, match="Approved retention policy must specify a positive approved_retention_days integer"):
        c2.validate_configuration()

    # Valid approved policy
    c3 = PuneRetentionPolicyConfig(
        is_approved_by_institution=True,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
        approved_retention_days=365,
        approval_reference="MOU/PUNE-COP/2026/001",
    )
    c3.validate_configuration()
    assert c3.approved_retention_days == 365
    assert c3.is_approved_by_institution is True


def test_prevention_of_automatic_real_data_deletion():
    """Real datasets must NEVER be deleted automatically merely because proposed days elapsed."""
    config = PuneRetentionPolicyConfig()  # Unapproved default

    # Cannot delete under unapproved policy
    assert config.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="TOKEN123") is False

    # Cannot delete automatically (without manual operator confirmation) even under approved policy
    approved_cfg = PuneRetentionPolicyConfig(
        is_approved_by_institution=True,
        policy_status=PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE,
        approved_retention_days=365,
        approval_reference="MOU/PUNE-COP/2026/001",
    )
    assert approved_cfg.can_delete_real_data(is_manual_operator_confirmed=False, approval_token="TOKEN123") is False

    # Cannot delete without approval token
    assert approved_cfg.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=None) is False
    assert approved_cfg.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="") is False

    # Arbitrary strings or booleans cannot authorize deletion (Phase 7.5 audit hardening)
    assert approved_cfg.can_delete_real_data(is_manual_operator_confirmed=True, approval_token="TOKEN123") is False
    assert approved_cfg.can_delete_real_data(is_manual_operator_confirmed=True, approval_token=True) is False

    # Can only delete when approved, manually confirmed, and authentic cryptographic token provided
    import os
    from unittest.mock import patch
    from cryptography.hazmat.primitives.asymmetric import ed25519
    test_key = ed25519.Ed25519PrivateKey.generate()
    pub_hex = test_key.public_key().public_bytes_raw().hex()
    with patch.dict(os.environ, {"PUNE_COP_ED25519_PUBLIC_KEY": pub_hex}):
        token = PuneRetentionPolicyConfig.create_deletion_approval_token(
            signing_private_key=test_key,
            dataset_version="v1",
            dataset_sha256="abc123",
            policy_reference="MOU/PUNE-COP/2026/001",
            issuer_id="pune_city_police_cop",
        )
        assert approved_cfg.can_delete_real_data(
            is_manual_operator_confirmed=True,
            approval_token=token,
            dataset_version="v1",
            dataset_sha256="abc123",
        ) is True


def test_data_category_retention_matrix_coverage():
    """Matrix must specify distinct retention and sanitization rules for all 8 categories."""
    matrix = PuneRetentionPolicyConfig.get_data_category_retention_matrix()
    expected_categories = [
        "raw_authorized_dataset",
        "cleaned_incident_dataset",
        "temporary_processing_files",
        "intermediate_analytical_datasets",
        "aggregated_statistical_reports",
        "model_training_datasets",
        "audit_manifests_and_integrity_records",
        "backups_and_recoverable_copies",
    ]
    for cat in expected_categories:
        assert cat in matrix, f"Missing retention category: {cat}"
        cat_info = matrix[cat]
        assert "classification" in cat_info
        assert "proposed_retention" in cat_info
        assert "storage_tier" in cat_info
        assert "deletion_authority" in cat_info
        assert "sanitization_standard" in cat_info
        assert "audit_evidence" in cat_info

    # Verify specific category invariants
    assert "Ephemeral" in matrix["temporary_processing_files"]["proposed_retention"] or "0 days" in matrix["temporary_processing_files"]["proposed_retention"]
    assert "Permanent" in matrix["aggregated_statistical_reports"]["proposed_retention"]
    assert "Permanent" in matrix["audit_manifests_and_integrity_records"]["proposed_retention"]
    assert "LOCKED_DISABLED" in matrix["model_training_datasets"]["proposed_retention"]
