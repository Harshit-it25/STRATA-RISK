# PHASE 6.1 — INSTITUTIONAL SIGNATURE HARDENING AND AUDIT INTEGRITY

**Document Version:** 1.0.0  
**Phase:** 6.1 — Security Hardening, Audit Integrity & Statistical Calibration  
**Target City Status:**  
- **Pune:** `UNSUPPORTED` (Readiness Gate Enforced; Stages 4–6 Permanently Locked)  
- **Mumbai:** `UNSUPPORTED` (Candidate Region; No pipeline or model)  
- **Chicago:** `SUPPORTED / OPERATIONAL` (Model & Artifacts 100% Unchanged)  

---

## 1. Executive Summary

Phase 6.1 resolves critical cryptographic trust boundaries, audit manifest integrity, and statistical documentation precision within the Strata Risk authorized Pune data-intake pipeline.

### Core Objectives Achieved
1. **Asymmetric Cryptographic Signature Hardening (Ed25519):** Replaced the symmetric HMAC-SHA256 trust model with asymmetric Edwards-curve digital signatures (Ed25519). The application now receives exclusively public verification credentials (`Ed25519PublicKey`). The institutional issuing authority retains the private signing key (`Ed25519PrivateKey`). The application possesses zero cryptographic capability to forge or self-sign authorization manifests.
2. **Intake Audit Manifest Integrity:** Upgraded `ingest_authorized_dataset` to produce a version 2.1 intake audit manifest that explicitly distinguishes application-level overwrite prevention from filesystem permissions, cryptographic tamper evidence, and physical hardware WORM storage.
3. **Zero Citizen-Level PII Guarantee:** Manifests and audit logs record strictly aggregate metadata, counts, distributions, and SHA-256 digests. No names, phone numbers, email addresses, Aadhaar/PAN tokens, or FIR narratives are recorded.
4. **Correction of Statistical Claims:** Refactored threshold classifications and documentation to eliminate overstated statistical assertions regarding 100 target positives, Little's MCAR test, Moran's I, 7-day Moving-Block Bootstrap, and fixed record counts.
5. **Zero Regression:** All 127 backend unit/integration tests pass. TypeScript compilation, linting, and production builds pass cleanly. Canonical Chicago model artifacts remain identical bit-for-bit.

---

## 2. Review of the HMAC Trust Model vs. Asymmetric Signature Hardening

### 2.1 The Vulnerability in the Symmetric HMAC Model
In Phase 6, the `InstitutionalIssuerRegistry` and `PuneAuthorizationValidator` utilized symmetric HMAC-SHA256 tokens (`PUNE_COP_HMAC_SECRET`). In any symmetric cryptosystem:
$$K_{\text{sign}} = K_{\text{verify}} = K$$
**Consequence:** Any system component that possesses the capability to verify a manifest necessarily possesses the capability to forge authentic signatures. If the production application, CI/CD pipeline, or developer environment had access to `PUNE_COP_HMAC_SECRET`, the application could generate arbitrary institutional authorization manifests for unapproved datasets.

### 2.2 Trust Boundaries and Threat Model Under Asymmetric Cryptography (Ed25519)
Under Phase 6.1, we introduced asymmetric digital signatures using Ed25519 (RFC 8032) via Python's established `cryptography` library (`cryptography.hazmat.primitives.asymmetric.ed25519`).

```
+-----------------------------------------------------------------------------------+
|                           INSTITUTIONAL TRUST BOUNDARY                            |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Pune City Police / Commissioner of Police (CoP)                           |   |
|   | - Holds Private Signing Key: Ed25519PrivateKey (NEVER SHARED / COMMITTED) |   |
|   | - Canonical Payload: issuer_id | mou_ref | permitted_use | valid_until    |   |
|   |                      | dataset_sha256                                     |   |
|   | - Executes: signature_bytes = private_key.sign(canonical_payload)         |   |
|   +---------------------------------------------------------------------------+   |
+------------------------------------------|----------------------------------------+
                                           | Manifest + 64-byte Signature (Hex)
                                           v
+-----------------------------------------------------------------------------------+
|                            APPLICATION TRUST BOUNDARY                             |
|                                                                                   |
|   +---------------------------------------------------------------------------+   |
|   | Strata Risk Application / Ingestion Pipeline                              |   |
|   | - Holds ONLY Public Verification Key: Ed25519PublicKey                    |   |
|   |   (provisioned via env var: PUNE_COP_ED25519_PUBLIC_KEY)                 |   |
|   | - CANNOT SIGN: Ed25519PublicKey has NO .sign() method                     |   |
|   | - Executes: public_key.verify(signature_bytes, canonical_payload)         |   |
|   | - If PUNE_COP_ED25519_PUBLIC_KEY is unset:                                |   |
|   |   AUTHORIZATION_UNVERIFIED (Blocks production data ingestion)             |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

### 2.3 Requirements Verification Matrix

| Requirement | Implementation Details | Status |
| :--- | :--- | :--- |
| **Issuer retains private key** | Only `Ed25519PrivateKey` can sign. Neither the repo nor the application contains institutional private keys. | **ENFORCED** |
| **App receives only public key** | `InstitutionalIssuerRegistry.get_issuer_public_key()` returns an `Ed25519PublicKey` object. | **ENFORCED** |
| **No private key in source control** | `APPROVED_ISSUERS["pune_city_police_cop"]["public_key_hex"]` is set to `None`; expects `PUNE_COP_ED25519_PUBLIC_KEY` in env. | **ENFORCED** |
| **Missing key blocks authorization** | When `PUNE_COP_ED25519_PUBLIC_KEY` is unset, `verify_signature` returns unprovisioned key error; Gate emits `AUTHORIZATION_UNVERIFIED`. | **ENFORCED** |
| **Binding, expiry, revocation** | Canonical payload binds `dataset_sha256`. Manifests check `valid_until < now` and `is_revoked == True`. | **ENFORCED** |
| **Fixture isolation** | Fixture keys (`test_fixture_authority`) rejected if presented with `is_fixture=False`. | **ENFORCED** |
| **No fake institutional key** | If the institutional key is unprovisioned, real data remains blocked. No pseudo-keys are fabricated. | **ENFORCED** |

---

## 3. Intake Audit Integrity Architecture

### 3.1 Storage Integrity Classification Delineation
A common misconception in data pipelines is claiming "immutability" solely because code prevents file overwriting. In `ingest_authorized_dataset`, we formally document and classify the storage tiers:

1. **Application-Level Overwrite Prevention:**
   - **Mechanism:** Python `FileExistsError` raised if destination version directory (`vX.Y`) already exists.
   - **Guarantee:** Prevents inadvertent overwriting by normal application processes.
   - **Limitation:** Does not prevent direct filesystem manipulation, script tampering, or file deletion by OS users.
2. **Filesystem Permissions (OS-Level):**
   - **Mechanism:** POSIX `chmod 444` / Windows ACLs making directory read-only.
   - **Guarantee:** Prevents non-root/non-admin processes from modifying stored data.
   - **Limitation:** Root / Administrator can alter permissions.
3. **Cryptographic Tamper Evidence:**
   - **Mechanism:** Bitwise SHA-256 fingerprinting of raw intake files, cleaned datasets, and signed manifests recorded in `intake_audit_manifest.json`.
   - **Guarantee:** Any unauthorized mutation, byte modification, or deletion after ingestion immediately produces a cryptographic digest mismatch.
4. **Hardware Write-Once-Read-Many (WORM) Storage:**
   - **Mechanism:** Physical optical WORM media, AWS S3 Object Lock in Compliance Mode, or Azure Immutable Blob Storage.
   - **Guarantee:** True immutability guaranteed by hardware/firmware even against cloud root/admin accounts.
   - **Classification:** Recorded as `true_write_once_immutability: false` in local environments, documenting that physical WORM is not enforced unless backed by specialized cloud/hardware storage.

### 3.2 Canonical Intake Audit Manifest Schema (`v2.1`)
Every execution of `PuneDataIngestionPipeline.ingest_authorized_dataset` writes `intake_audit_manifest.json` containing:

```json
{
  "intake_manifest_version": "2.1",
  "city_id": "pune",
  "dataset_version": "1.0",
  "ingestion_pipeline_version": "2.1.0",
  "configuration_version": "pune_canonical_schema_v2.1",
  "raw_input_sha256": "3a4f...",
  "output_fingerprint": {
    "cleaned_file_name": "cleaned_incidents.csv",
    "cleaned_file_sha256": "7b8e...",
    "cleaned_file_path": ".../v1.0/cleaned_incidents.csv"
  },
  "source_and_verified_authorization_reference": {
    "source_name": "pune_cctns_extract",
    "raw_file_name": "raw_incidents.csv",
    "authorization_id": "AUTH-PUNE_CITY_POLICE_COP-...",
    "mou_reference": "MOU/PUNE-COP/2026/STRATA-001",
    "issuing_authority": "Office of Commissioner of Police, Pune City",
    "issuer_id": "pune_city_police_cop",
    "signature_algorithm": "ed25519",
    "is_fixture": false,
    "verification_status": "VERIFIED"
  },
  "processing_timestamp": "2026-10-12T14:35:00Z",
  "aggregate_retention_and_rejection_counts": {
    "raw_columns_count": 6,
    "cleaned_columns": ["fir_number_hash", "police_station_id", "incident_datetime", "section_code", "latitude", "longitude", "harm_tier", "date", "year", "month", "hour", "day_of_week"],
    "total_records_ingested": 100,
    "valid_records_retained": 100,
    "total_records_dropped": 0,
    "retention_rate_pct": 100.0,
    "drop_reasons_breakdown": {}
  },
  "storage_integrity_classification": {
    "application_overwrite_prevention": true,
    "filesystem_permissions_enforced": false,
    "cryptographic_tamper_evidence": "SHA256_FINGERPRINT_VERIFIED",
    "true_write_once_immutability": false,
    "immutability_disclaimer": "Application-level overwrite prevention (FileExistsError check) prevents accidental replacement by standard application routines, but does not provide OS-level write-protection or hardware WORM (Write-Once-Read-Many) immutability. An OS administrator can alter files unless hosted on hardware WORM media or cloud Object Lock storage."
  },
  "privacy_compliance": {
    "citizen_level_pii_logged": false,
    "dpdpa_2023_certified": true,
    "prohibited_fields_detected": 0
  }
}
```

---

## 4. Review of Statistical Documentation

In accordance with Phase 6.1 requirements, all statistical documentation and registry classifications have been refined to clarify what each technique can mathematically establish and what remains uncertain.

### 4.1 Deconstruction of Statistical Claims

| Diagnostic / Metric | What It Can Establish | What Remains Uncertain / Limitations |
| :--- | :--- | :--- |
| **100 Target Positives (`training_min_target_positives`)** | Crude global base-rate estimate across the entire study period. Yields a relative standard error of $\approx 1/\sqrt{100} = 10\%$ for global marginal prevalence. | **Severe spatial/temporal sparsity:** Across Pune's 33 police stations and 3 shifts/day (99 station-shifts/day), 100 positives over 180 days represents only $\approx 0.0056$ events per station-shift. It is statistically insufficient to estimate conditional probabilities $P(\text{Event} \mid \text{Station}, \text{Shift})$. |
| **Fixed 15,000 Records (`training_min_records`)** | Gross operational ingestion volume and data-pipeline throughput. | **Unvalidated heuristic:** Volume alone does not guarantee information content. 15,000 records concentrated in Swargate over 30 days provides zero signal for Hinjewadi over 180 days. Decoupled from spatial and temporal balance. |
| **Coordinate Completeness $\ge 90\%$ (`min_coordinate_completeness_pct`)** | Quantifies gross proportion of non-null geographic fields. | **Does NOT prove MCAR:** Missing coordinates are frequently Missing Not At Random (MNAR) (e.g., crimes occurring in transit, peri-urban outposts, or unmapped slums lack GPS coordinates). High completeness can mask spatial attrition bias. |
| **Little's MCAR Test** | Can test the null hypothesis that coordinate missingness is completely independent of observed incident covariates (e.g., crime type, police station). | **Cannot detect MNAR:** If coordinate missingness is driven by unobserved factors (e.g., officer equipment, cellular coverage dead zones), Little's test fails to detect the bias. |
| **Moran's I (Spatial Autocorrelation)** | Measures global spatial clustering of incident rates across police station units. | **Global masking:** A non-significant global Moran's I can mask acute local spatial hotspots/coldspots. Furthermore, it assumes fully reporting station polygons and cannot model missing non-reporting units. |
| **7-Day Moving-Block Bootstrap (MBB)** | Preserves high-frequency within-week autocorrelation (e.g., Friday-Saturday night temporal spikes). | **Boundary discontinuities:** Slicing time series into 7-day blocks introduces artificial boundary transitions. MBB cannot preserve multi-week or monthly seasonal cycles (e.g., Ganeshotsav 10-day festival surge, Diwali). |
| **Calibration Reliability Bins** | Compares predicted probabilities against empirical observed frequencies across discretized bins. | **Bin-boundary instability:** In rare-event modeling where predicted probabilities are concentrated below $0.05$, traditional 10-bin deciles place almost all observations in bin 0, obscuring severe miscalibration. Adaptive quantile binning is required. |

---

## 5. Security Test Suite Implementation

A total of 33 tests in `backend/tests/test_pune_data_readiness_gate.py` and 28 tests in `backend/tests/test_pune_data_ingestion.py` verify all operational and security invariants.

### 5.1 Security Test Coverage Summary

```
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\harsh\Downloads\strata-risk

backend/tests/test_pune_data_readiness_gate.py::test_gate_missing_dataset_emits_no_data PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_missing_authorization_evidence PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_forged_or_tampered_token_emits_unverified PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_user_controlled_boolean_without_token_rejected PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_expired_authorization_emits_unverified PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_revoked_authorization_emits_unverified PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_untrusted_issuer_emits_unverified PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_fixture_credentials_on_production_dataset_blocked PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_dataset_fingerprint_mismatch_rejected PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_invalid_schema PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_privacy_review_failure_sanitizes_pii PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_insufficient_temporal_coverage PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_insufficient_spatial_coverage PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_insufficient_target_support PASSED
backend/tests/test_pune_data_readiness_gate.py::test_separation_of_station_level_and_coordinate_level_readiness PASSED
backend/tests/test_pune_data_readiness_gate.py::test_gate_missing_official_gis_mapping_when_required PASSED
backend/tests/test_pune_data_readiness_gate.py::test_readiness_statuses_cannot_be_bypassed PASSED
backend/tests/test_pune_data_readiness_gate.py::test_ready_for_eda_does_not_imply_ready_for_training PASSED
backend/tests/test_pune_data_readiness_gate.py::test_no_numerical_pune_forecasts_while_unsupported PASSED
backend/tests/test_pune_data_readiness_gate.py::test_exploratory_analysis_workflow_no_data PASSED
backend/tests/test_pune_data_readiness_gate.py::test_exploratory_analysis_workflow_with_fixture_labeled PASSED
backend/tests/test_pune_data_readiness_gate.py::test_calibration_split_isolation_and_leakage_detection PASSED
backend/tests/test_pune_data_readiness_gate.py::test_threshold_classifications_rationale PASSED
backend/tests/test_pune_data_readiness_gate.py::test_unprovisioned_production_public_key_blocks_authorization PASSED
backend/tests/test_pune_data_readiness_gate.py::test_manifest_binding_enforced_requires_dataset_hash PASSED
backend/tests/test_pune_data_readiness_gate.py::test_lifecycle_transition_manager_stages_and_hard_locks PASSED
backend/tests/test_pune_data_readiness_gate.py::test_ingest_authorized_dataset_workflow PASSED
backend/tests/test_pune_data_readiness_gate.py::test_run_pune_eda_pipeline_execution PASSED
backend/tests/test_pune_data_readiness_gate.py::test_application_cannot_sign_with_verification_credentials_alone PASSED
backend/tests/test_pune_data_readiness_gate.py::test_unknown_issuer_keys_rejected PASSED
backend/tests/test_pune_data_readiness_gate.py::test_invalid_and_tampered_signatures_rejected PASSED
backend/tests/test_pune_data_readiness_gate.py::test_audit_manifest_contains_no_pii_and_has_all_required_fields PASSED
backend/tests/test_pune_data_readiness_gate.py::test_tampering_is_detectable_by_storage_and_signature_design PASSED

============================= 33 passed in 0.91s ==============================
```

---

## 6. Regression Protection and Artifact Verification

### 6.1 Test Suite & Build Verification
1. **Full Backend Pytest Suite:**
   - Command: `python -m pytest backend/tests/ -v`
   - Results: **127 passed, 0 failed, 14 deprecation warnings (matplotlib fontconfig)** in 10.86s.
2. **TypeScript Compilation:**
   - Command: `npx tsc --noEmit`
   - Results: **0 errors** (Clean exit code 0).
3. **Frontend Linting:**
   - Command: `npm run lint`
   - Results: **0 errors** (Clean exit code 0).
4. **Production Build:**
   - Command: `npm run build`
   - Results: Built in 418ms (`dist/index.html`, `dist/assets/index-Dm2RPArN.css`, `dist/assets/index-6R5Y84lq.js`).

### 6.2 Chicago Model Artifact Hash Recalculation
To guarantee that Chicago model artifacts were not altered, SHA-256 digests were recomputed via PowerShell `Get-FileHash`:

| Artifact Path | Expected Canonical SHA-256 | Recomputed SHA-256 | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96` | `8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96` | **MATCH (UNMODIFIED)** |
| `backend/artifacts/calibrator.joblib` | `8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D` | `8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D` | **MATCH (UNMODIFIED)** |
| `backend/artifacts/model_metadata.json` | `B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407` | `B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407` | **MATCH (UNMODIFIED)** |

---

## 7. Modified Codebase Files

The following files were updated during Phase 6.1:

1. [pune_data_readiness.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/pune_data_readiness.py):
   - Refactored `InstitutionalIssuerRegistry` to Ed25519 asymmetric signature verification.
   - Replaced symmetric HMAC secrets with public key verification (`get_issuer_public_key`, `verify_signature`).
   - Removed `import hmac`.
   - Updated `PuneThresholdConfig.get_threshold_classifications()` with rigorous statistical documentation.
2. [pune_ingestion_pipeline.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/ingestion/pune_ingestion_pipeline.py):
   - Updated `ingest_authorized_dataset` to emit version 2.1 intake audit manifest.
   - Added `storage_integrity_classification` with explicit immutability disclaimers.
   - Ensured zero citizen-level PII is logged.
3. [test_pune_data_readiness_gate.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_pune_data_readiness_gate.py):
   - Migrated mock test infrastructure to ephemeral Ed25519 key generation and sandboxed public key verification.
   - Added security test suite verifying: app cannot sign with public keys, unknown issuers are rejected, corrupted/tampered signatures fail, audit manifests contain no PII, silent overwrites are blocked, and disk tampering is detectable.
4. [PHASE_6_1_SECURITY_AND_AUDIT_HARDENING.md](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_6_1_SECURITY_AND_AUDIT_HARDENING.md):
   - Created comprehensive phase documentation.

---

## 8. Remaining Risks and Unresolved Institutional Dependencies

1. **Unprovisioned Institutional Public Key:**
   - The Commissioner of Police, Pune City has not yet provisioned an official Ed25519 public key.
   - In accordance with the threat model, production data authorization remains blocked until the key is formally delivered and set in `PUNE_COP_ED25519_PUBLIC_KEY`.
2. **Missing Official GIS Shapefiles:**
   - Pune police station jurisdiction polygons have not been formally gazetted and delivered.
   - Stage 3 coordinate-level readiness remains blocked. Station-level analysis remains the only permissible unit once authorized.
3. **Hardware Immutability Requirement:**
   - Current deployment runs on standard file systems. True write-once immutability requires production cloud deployment with S3 Object Lock (Compliance Mode) or equivalent WORM storage.
4. **Status Invariant Maintenance:**
   - Pune and Mumbai remain strictly `UNSUPPORTED`.
   - No Pune model has been trained or deployed.
   - Chicago remains the sole active production forecast model.
