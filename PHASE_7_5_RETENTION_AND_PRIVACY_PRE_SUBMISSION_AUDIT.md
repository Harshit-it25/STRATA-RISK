# STRATA RISK — PHASE 7.5 AUDIT REPORT
## RETENTION AUTHORIZATION AND PRIVACY PRE-SUBMISSION AUDIT

**Document Version:** 1.0.0  
**Phase Identifier:** Phase 7.5 (Pre-Submission Audit & Retention Hardening)  
**Security Classification:** Highly Restricted / Institutional Governance Review  
**Author:** Strata Risk Senior Software Engineer, ML Governance Engineer & Data Protection Auditor  
**Date:** October 2026  
**Repository State:** Pune and Mumbai strictly **UNSUPPORTED**; Chicago **PROD / UNCHANGED**  

---

## 1. Executive Summary & Audit Objectives

Phase 7.5 performs an independent, bounded verification of the Phase 7.4 retention-policy reconciliation before the institutional data-request package is formally submitted to the Pune City Police Commissionerate.

### 1.1 Invariant Guarantees
- **No Major Subsystems Added:** All engineering changes were strictly bounded to hardening deletion authorization checks, failure-path cleanup, and documentation consistency.
- **No Pune Model Trained or Deployed:** Model training remains completely disabled (`is_ready_for_training = False`).
- **Zero Fabricated Indian Data:** No artificial crime incidents, coordinates, labels, or forecasts were generated.
- **Chicago Artifact Integrity:** Chicago model artifacts and serving behavior remain 100% untouched bit-for-bit.
- **City Status Invariants:** Pune and Mumbai remain strictly `UNSUPPORTED` (`is_validated = False`, `NO_DATA` / `STAGE_0_UNAUTHORIZED`).

---

## 2. Audit of Retention Approval Tokens

### 2.1 Identification of Phase 7.4 Vulnerability
An inspection of `PuneRetentionPolicyConfig.can_delete_real_data` in Phase 7.4 revealed that while it prohibited deletion under unapproved policies or without manual operator confirmation, it accepted any non-empty string as an `approval_token`:
```python
# Phase 7.4 Vulnerable Implementation:
if not approval_token or not str(approval_token).strip():
    return False
return True  # Arbitrary string like "TOKEN123" authorized deletion!
```
This failed to guarantee:
1. Cryptographic origin authenticity from the authorized institutional issuer.
2. Cryptographic binding to the specific target action, dataset version, dataset SHA-256 fingerprint, policy reference, and approval window.
3. Prevention of replay attacks or reuse of stale/revoked deletion tokens.

### 2.2 Hardened Cryptographic Token Design
In Phase 7.5, `PuneRetentionPolicyConfig` was upgraded with cryptographic verification using **Ed25519 digital signatures** over **RFC 8785 JSON Canonicalization Scheme (JCS)** serialized payloads:

```
+-----------------------------------------------------------------------------------------+
|                  CRYPTOGRAPHIC DELETION APPROVAL TOKEN STRUCTURE                        |
+-----------------------------------------------------------------------------------------+
|  action            : "AUTHORIZE_DATASET_DELETION" (Strict Action Binding)               |
|  dataset_version   : Target Version String (e.g. "v1", "v1.0")                          |
|  dataset_sha256    : Bitwise SHA-256 Digest of Target Real Dataset                      |
|  policy_reference  : Bilateral MoU Approval Reference (e.g. "MOU/PUNE-COP/2026/001")     |
|  authorization_id  : Unique Institutional Authorization Identifier                      |
|  token_id          : Cryptographic Nonce / Single-Use UUID                              |
|  issuer_id         : "pune_city_police_cop"                                             |
|  issued_at         : ISO 8601 Timestamp of Grant Issuance                               |
|  valid_from        : ISO 8601 Timestamp of Start of Approval Period                    |
|  valid_until       : ISO 8601 Timestamp of Expiration of Approval Period                |
|  signature         : 64-byte Ed25519 Signature over RFC 8785 Canonical JSON Payload     |
+-----------------------------------------------------------------------------------------+
```

### 2.3 Verification Gates Enforced in `verify_deletion_approval_token`
Every deletion authorization evaluates 12 sequential fail-closed checks:
1. **Type & Boolean Rejection:** Rejects `None`, Booleans (`True`, `False`), non-JSON strings, or malformed payloads.
2. **Institutional Policy State:** Requires `self.is_approved_by_institution == True` and `self.policy_status == PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE`.
3. **Approval Reference Presence:** Requires non-empty `self.approval_reference`.
4. **Mandatory Token Fields:** Rejects payloads missing any of the 10 required fields.
5. **Action Binding:** Rejects any action other than `"AUTHORIZE_DATASET_DELETION"`.
6. **Policy Reference Binding:** Token `policy_reference` must match `self.approval_reference` exactly.
7. **Dataset Version Binding:** If target version is specified, token `dataset_version` must match.
8. **Fingerprint Binding:** If target SHA-256 is specified, token `dataset_sha256` must match bit-for-bit.
9. **Replay Protection:** Maintains `CONSUMED_DELETION_TOKEN_IDS: Set[str]`. If `token_id` has already been consumed, the token is rejected.
10. **Temporal Validity Window:** Evaluates current time against `[valid_from, valid_until]`. Expired or not-yet-active tokens are rejected.
11. **Revocation Check:** Checks `authorization_id`, `token_id`, `signature`, and `policy_reference` against `InstitutionalIssuerRegistry.TRUSTED_REVOKED_IDENTIFIERS` and persistent CRLs.
12. **Asymmetric Cryptographic Signature:** Canonicalizes payload (excluding `signature`) via `canonicalize_rfc8785` and verifies Ed25519 signature against the issuer's public key (`PUNE_COP_ED25519_PUBLIC_KEY`). Fails closed if the public key is unprovisioned.

### 2.4 Secure Deletion Execution Helper
Added `PuneRetentionPolicyConfig.execute_authorized_deletion(target_path, ...)`:
- Executes deletion only if all cryptographic gates pass.
- Automatically consumes `token_id` in `CONSUMED_DELETION_TOKEN_IDS` to lock out replay attacks.
- Returns a structured audit receipt (`status: "SUCCESS"`, `target_path`, `deletion_timestamp`, `policy_reference`, `dataset_version`, `dataset_sha256`).
- Raises `PermissionError` on any authorization failure.

---

## 3. Verification of Retention Configuration

| Requirement | Implementation Verification | Status |
| :--- | :--- | :---: |
| **Default Policy Status is Unapproved** | `DEFAULT_RETENTION_POLICY_CONFIG.policy_status` is `PROPOSED_PENDING_INSTITUTIONAL_APPROVAL`, `is_approved_by_institution` is `False`. | **VERIFIED** |
| **Proposed Days Not Mistaken for Approved** | `DEFAULT_RETENTION_POLICY_CONFIG.proposed_retention_days = 365`; `approved_retention_days = None`. Fails closed if `approved_retention_days` is set without institutional approval. | **VERIFIED** |
| **Missing Policy Configuration Fails Closed** | Unconfigured policies default to `is_approved_by_institution = False`, blocking all real-data deletion and intake. | **VERIFIED** |
| **Training Data Retention Disabled** | Category 6 (`model_training_datasets`) in retention matrix is set to `LOCKED_DISABLED_IN_PHASE_7 (0 days; creation prohibited)`. | **VERIFIED** |
| **No Automated Purge Enabled** | Zero background daemons, cron jobs, or timer scripts delete real data. Real dataset deletion strictly requires operator confirmation and cryptographic tokens. | **VERIFIED** |
| **Post-Deletion Retained Metadata** | `intake_audit_manifest.json` and `intake_audit_ledger.jsonl` store only hashes, distributions, and counts; zero citizen PII is retained post-deletion. | **VERIFIED** |

---

## 4. Failure-Path Ingestion Cleanup & Raw Data Protection

### 4.1 Ingestion Failure Analysis Matrix
The ingestion workflow in `PuneDataIngestionPipeline.ingest_authorized_dataset` was audited across all failure paths:

| Ingestion Failure Mode | Point of Failure | Partial Output State | Raw Input Dataset Disposition |
| :--- | :--- | :--- | :--- |
| **Schema Validation Failure** | Step 4: `process_records` -> `validate_schema` | Version directory NOT created. In-memory buffers dropped. | Raw dataset untouched. |
| **Privacy-Screening Failure** | Step 4: `process_records` -> `check_pii_compliance` | Version directory NOT created. In-memory buffers dropped. | Raw dataset untouched. |
| **Signature-Verification Failure** | Step 3: `PuneAuthorizationValidator.validate` | Version directory NOT created. Execution aborted. | Raw dataset untouched. |
| **Dataset Fingerprint Mismatch** | Step 3: `PuneAuthorizationValidator.validate` | Version directory NOT created. Execution aborted. | Raw dataset untouched. |
| **Duplicate-Version Rejection** | Step 4: `FileExistsError` pre-check | Existing version directory preserved; no overwriting. | Raw dataset untouched. |
| **Exceptions During Normalization** | Step 4: `process_records` processing | Version directory NOT created. In-memory buffers dropped. | Raw dataset untouched. |
| **Interrupted Output Generation** | Step 6: Artifact writing (`cleaned_incidents.csv`, manifests, ledger) | **Wrapped in `try...except`:** partial `v{version}` directory purged via `shutil.rmtree`. | Raw dataset strictly preserved. |

### 4.2 Implementation of Failure Cleanup Wrapper
In `backend/ingestion/pune_ingestion_pipeline.py`:
```python
# 6. Create version directory and write artifacts (wrapped in failure cleanup)
created_version_dir = False
try:
    os.makedirs(version_dir, exist_ok=True)
    created_version_dir = True
    cleaned_csv_path = os.path.join(version_dir, "cleaned_incidents.csv")
    cleaned_df.to_csv(cleaned_csv_path, index=False)
    ...
    # Write authorized manifest, intake audit manifest, and audit ledger
except Exception:
    # Failure-path cleanup: purge partial version directory
    # INVARIANT: Never delete or alter the authoritative raw dataset
    if created_version_dir and os.path.exists(version_dir):
        shutil.rmtree(version_dir, ignore_errors=True)
    raise
```

### 4.3 Documented Cleanup Limitations
1. **Abrupt OS Termination (SIGKILL / Kernel Panic / Power Loss):** If the host operating system terminates the process abruptly during file I/O, Python exception handlers cannot execute. A partial `v{version}` directory may remain on disk. In this scenario, re-running ingestion safely halts with `FileExistsError`, prompting manual administrative inspection and directory purge.
2. **Storage Controller Flush Latency:** Unbuffered writes flushed to hardware storage controllers cannot be rolled back by software if an unrecoverable hardware fault occurs.
3. **Authoritative Raw Data Immunity:** Raw source files are opened strictly in read-only mode (`open(..., "rb")` or `pd.read_csv(...)`). The ingestion code contains zero logic that deletes or alters `raw_dataset_path`.

---

## 5. Review of Derived-Data Privacy

### 5.1 No Anonymization Claim
> [!WARNING]
> **Definitive Legal & Technical Position:**
> Strata Risk does **NOT** claim that the derived dataset is anonymized merely because direct identifiers (citizen names, phone numbers, Aadhaar numbers, residential door addresses) have been removed. The dataset is **pseudonymized personal data** under Section 3 of the Digital Personal Data Protection Act (DPDPA), 2023.

### 5.2 Multi-Dimensional Privacy Assessment

#### 1. Pseudonymous Identifiers (`fir_number_hash`)
- **Mechanism:** Salted SHA-256 hash of the administrative FIR number.
- **Vulnerability:** Police FIR numbers follow predictable sequential formats (`<STATION>-<YEAR>-<NUMBER>`). Because a typical police station handles fewer than 10,000 FIRs annually, the total search space is small ($< 10^4$). Without a strong, secret institutional salt, an attacker can compute rainbow tables in seconds.
- **Governance Control:** The salt must remain under the exclusive physical and administrative custody of the Pune Police Commissionerate. The salt is never transferred to or embedded within Strata Risk code.

#### 2. Truncated Geographic Coordinates (3 Decimal Places, ~111m)
- **Mechanism:** Rounding latitude and longitude to 3 decimal places ($111\text{ m} \times 111\text{ m}$ bounding grid).
- **Vulnerability:** In high-density commercial corridors (e.g., FC Road, Swargate), 111m contains hundreds of individuals. However, in low-density peri-urban beats (e.g., outskirts of Hadapsar, Bavdhan, or Lonikand), an incident location paired with a timestamp may pinpoint an isolated building or residence.
- **Governance Control:** Micro-spatial coordinates remain optional. If institutional review determines re-identification risk is non-negligible, coordinate modeling is disabled and data is aggregated strictly to the police station polygon level.

#### 3. Small-Cell Aggregation & Rare Offense Categories
- **Mechanism:** Spatiotemporal lattice ($33 \text{ stations} \times 6 \text{ four-hour shifts/day}$).
- **Vulnerability:** Rare violent offenses (e.g., IPC 302 / 307 - homicide, attempted murder) occur at low frequency. A cell where $Y_{i, t} = 1$ in a small precinct during late night hours is quasi-identifiable when cross-referenced against public news coverage or social media blotters.
- **Governance Control:** IPC/BNS sections are mapped into broad operational harm tiers (`violent_street_harm`, `property_harm`, `public_disorder`). Furthermore, small-cell suppression ($N < 5$) is proposed for institutional DPO review before any public or derived reporting.

#### 4. Time-and-Location Combinations (Quasi-Identifiers)
- **Mechanism:** 4-hour temporal shift binning.
- **Vulnerability:** Exact incident timestamps ($t_{\text{incident}}$) combined with station ID and offense type form a quasi-identifier triplet: $(\text{station}, \text{timestamp}, \text{offence})$.
- **Governance Control:** Minute-level and second-level precision are stripped in derived feature matrices; timestamps are mapped to discrete 4-hour shift indices ($W_0 \dots W_5$).

#### 5. Unstructured Narrative Fields (`place_of_occurrence`)
- **Mechanism:** Multi-pass regex filter scanning for structured Indian identity patterns (10-digit mobile, 12-digit Aadhaar, 10-char PAN).
- **Vulnerability:** Regex filters **cannot detect contextual vernacular descriptions** (e.g., "in front of Sharma kirana store, flat 402, opposite Joshi bungalow").
- **Governance Control:** The institutional submission specifies standardized categorical typology codes (`public_road`, `transit_hub`, `commercial_market`) as the preferred intake format, omitting free-text narratives entirely.

#### 6. Dataset Fingerprints & Audit Manifest Metadata
- **Mechanism:** SHA-256 digests and station record counts in `intake_audit_manifest.json`.
- **Vulnerability:** Preserving audit records post-deletion could theoretically leak high-level trends if station annual counts correlate with external reports.
- **Governance Control:** Audit manifests store aggregate counts without individual event timestamps, names, or micro-locations, preserving scientific accountability while protecting individual privacy.

### 5.3 Implemented Controls vs. Approval-Dependent Controls Matrix

| Governance Dimension | Control Description | Implementation Status | Approving Authority |
| :--- | :--- | :--- | :--- |
| **Direct PII Screening** | Automated fail-closed multi-pass regex scan | **Implemented in Code** | Operational Pipeline Gate |
| **Coordinate Truncation** | Rounding to 3 decimal places (~111m) | **Implemented in Code** | Operational Pipeline Gate |
| **Harm Tier Aggregation** | Mapping 20+ penal codes to 3 operational tiers | **Implemented in Code** | Operational Pipeline Gate |
| **Station Normalization** | Strict 33-station whitelist with alias resolution | **Implemented in Code** | Operational Pipeline Gate |
| **Cryptographic Deletion Tokens** | Ed25519 token bound to version, hash, policy, & expiry | **Implemented in Code** | Operational Pipeline Gate |
| **Failure-Path Cleanup** | Automated rollback of partial version directories | **Implemented in Code** | Operational Pipeline Gate |
| **Cell Suppression ($N < 5$)** | Suppressing spatiotemporal cells with count $< 5$ | **Proposed / Awaiting Approval** | Institutional DPO Sign-Off |
| **Narrative Omission** | Replacing free-text narratives with typology enum | **Proposed / Awaiting Approval** | Institutional DPO Sign-Off |
| **Salt Lifecycle Management** | External Commissionerate-managed cryptographic salt | **Proposed / Awaiting Approval** | Commissionerate Technical Cell |
| **Post-Acquisition Retention (365d)** | 365-day storage life before mandatory purge | **Proposed / Awaiting Approval** | Bilateral MoU Execution |
| **Model-Training Data Retention** | Retaining feature matrices for model training | **LOCKED / DISABLED** (Prohibited in Stage 0–3) | Stage 4 Addendum Required |

---

## 6. Documentation Consistency Audit

Every institutional submission document was reviewed to verify consistency:

1. **Coverage vs. Retention Distinction:**
   - **Historical Observation Coverage (~36 Months / 1,080 Days):** Consistently defined as retrospective crime history necessary to capture annual seasonality and BNS transitions.
   - **Post-Acquisition Retention (Proposed 365 Days):** Consistently defined as prospective shelf-life of received files, marked as **Proposed and Awaiting Institutional Ratification**.
2. **Disaggregated Lifecycle across 8 Data Categories:**
   - Raw data: Proposed 365 days, AES-256 vault, multi-signature purge.
   - Cleaned data: Synchronized with raw data retention.
   - Temporary processing files: 0 days (ephemeral in-memory scratch).
   - Intermediate analytical files: Active exploratory analysis duration only.
   - Aggregated statistical reports: Permanent research record (zero PII).
   - Model-training datasets: **LOCKED / DISABLED (0 days)**.
   - Audit manifests: Permanent legal integrity provenance (hashes and counts only).
   - Backups: Synchronized strictly with raw data retention.
3. **Terminology Precision:**
   - Replaced unqualified claims of "immutable storage" with "application-level overwrite prevention."
   - Explicitly documented that application file unlinking does not provide hardware WORM immutability without underlying Object Lock storage.

---

## 7. Regression Protection & Test Verification

### 7.1 Full Backend Test Suite
Executed the complete test suite across all 217 unit and integration tests:
```bash
python -m pytest backend/tests/ -v
============================ 217 passed in 18.70s =============================
```
- **Phase 7.5 Suite (`test_phase_7_5_retention_and_cleanup.py`):** 14/14 tests PASSED.
- **Phase 7.4 Suite (`test_phase_7_4_retention_policy.py`):** 7/7 tests PASSED.
- **Readiness Gate Suite (`test_pune_data_readiness_gate.py`):** 38/38 tests PASSED.
- **Temporal & Pipeline Suites:** All tests PASSED.

### 7.2 Frontend Compilation & Linting
- `npx tsc --noEmit`: Exited with code **0** (zero TypeScript type errors).
- `npm run lint`: Exited with code **0** (zero ESLint warnings/errors).
- `npm run build`: Production bundle built successfully via Vite (dist size verified).

### 7.3 Canonical Chicago Model Artifact Hashes
Recalculated SHA-256 digests of established Chicago production artifacts:

| Artifact Path | Expected Canonical SHA-256 | Recomputed SHA-256 | Verification Status |
| :--- | :--- | :--- | :---: |
| `backend/artifacts/forecaster_catboost.cbm` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | **MATCH (BIT-FOR-BIT)** |
| `backend/artifacts/calibrator.joblib` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | **MATCH (BIT-FOR-BIT)** |
| `backend/artifacts/model_metadata.json` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | **MATCH (BIT-FOR-BIT)** |

---

## 8. Exact Approvals Required Before Processing Real Pune Data

Before any real Pune City incident data can be received, ingested, or processed, the following formal institutional instruments must be executed:

```
+-----------------------------------------------------------------------------------------+
|                  MANDATORY PRE-PROCESSING INSTITUTIONAL INSTRUMENTS                     |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  1. Bilateral Memorandum of Understanding (MoU)                                         |
|     - Parties: Institutional Entity & Office of the Commissioner of Police, Pune City   |
|     - Ratification of: Purpose of study, research boundaries, permitted fields         |
|                                                                                         |
|  2. Institutional Data Protection Officer (DPO) Formal Sign-Off                         |
|     - DPDPA 2023 Section 17 Research Compliance Assessment Memorandum                  |
|     - Review and approval of cell-suppression threshold (N < 5) and narrative omission  |
|                                                                                         |
|  3. Data Retention & Decommissioning Agreement Addendum                                 |
|     - Formalization of approved retention window (ratifying or modifying proposed 365d) |
|     - Multi-signature cryptographic deletion token protocol specification                |
|     - Confirmation of permanent retention of non-PII audit manifests                    |
|                                                                                         |
|  4. Secure Cryptographic Credential Exchange                                            |
|     - Out-of-band delivery of Pune Police Ed25519 Public Verification Key               |
|     - Environment provisioning of PUNE_COP_ED25519_PUBLIC_KEY                           |
|     - Commissionerate-managed private key and salt custody protocol                     |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

---

## 9. Final Conditions Compliance Sign-Off

- **Pune Status:** `UNSUPPORTED` (`is_validated = False`, `NO_DATA` / `STAGE_0_UNAUTHORIZED`).
- **Mumbai Status:** `UNSUPPORTED` (`is_validated = False`, `NO_DATA`).
- **Model Training Status:** Zero Pune models trained or deployed (`is_ready_for_training = False`).
- **Data Integrity:** Zero fabricated Indian incidents or forecasts exist.
- **Chicago Status:** Production baseline serving behavior unchanged.

*Report compiled and certified for Institutional Pre-Submission Audit.*
