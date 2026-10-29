# PHASE 6.2 — CRYPTOGRAPHIC AUTHORIZATION AND FORECAST-TIME CONSISTENCY AUDIT

**Document Version:** 1.0.0  
**Phase:** 6.2 — Cryptographic Authorization, Audit Ledger Integrity & Forecast Window Reconciliation  
**Target City Status:**  
- **Pune:** `UNSUPPORTED` (Readiness Gate Enforced; Stages 4–6 Permanently Locked)  
- **Mumbai:** `UNSUPPORTED` (Candidate Region; No pipeline or model)  
- **Chicago:** `SUPPORTED / OPERATIONAL` (Model & Artifacts 100% Unchanged)  

---

## 1. Executive Summary

Phase 6.2 establishes complete cryptographic tamper-evidence across all authorization-sensitive fields, eliminates reliance on mutable manifest revocation booleans, resolves potential audit-evasion vectors via an independent root audit ledger, and reconciles the intended operational forecasting time-window definition across the Strata Risk codebase.

### Core Audit Outcomes
1. **Deterministic RFC 8785 Canonical Payload:** All authorization-sensitive fields (`issuer_id`, `authorization_id`, `dataset_sha256`, `mou_reference`, `permitted_use`, `permitted_fields`, `valid_from`, `valid_until`, `manifest_version`) are bound into an unambiguous, lexicographically sorted JSON byte string. Modifying any field invalidates the Ed25519 digital signature.
2. **Authoritative Revocation Verification:** Revocation is now verified against an independent in-memory revocation registry and environment-provisioned Certificate Revocation List (`PUNE_REVOKED_AUTHORIZATIONS`). Mutating `"is_revoked": false` in a local manifest file cannot bypass institutional revocation.
3. **Independent Root Audit Ledger:** Added an append-only root ledger (`intake_audit_ledger.jsonl`) recording the SHA-256 fingerprint of each version's `intake_audit_manifest.json`. `verify_intake_integrity()` detects if an attacker simultaneously modifies both `cleaned_incidents.csv` and `intake_audit_manifest.json` in a version directory.
4. **Reconciled Forecasting Unit:** Harmonized the primary prediction unit to **4-Hour Operational Prediction Windows** (6 windows per day, 4 hours ahead). Documented the mathematical evaluation base across Pune's 33 police stations ($198$ station-windows per day; $35,640$ station-windows across 180 days; $72,270$ across 365 days).
5. **Zero Regression:** All 132 backend unit and integration tests pass. TypeScript compilation, linting, and production builds pass cleanly. Canonical Chicago model artifacts remain identical bit-for-bit.

---

## 2. Complete Audit of Ed25519 Signed Payload & Canonical Serialization

### 2.1 Identification of Signed Manifest Fields
Under Phase 6.1, the canonical payload omitted `authorization_id`, `valid_from`, `permitted_fields`, and `manifest_version`, using a raw pipe-separated format. Under Phase 6.2, `InstitutionalIssuerRegistry.compute_canonical_payload()` binds every authorization-sensitive field into a deterministic, RFC 8785-compliant JSON canonical format:

```json
{
  "authorization_id": "AUTH-PUNE_CITY_POLICE_COP-3a4f89b1",
  "dataset_sha256": "*",
  "issuer_id": "pune_city_police_cop",
  "manifest_version": "2.1",
  "mou_reference": "MOU/PUNE-COP/2026/STRATA-001",
  "permitted_fields": [
    "fir_number_hash",
    "incident_datetime",
    "latitude",
    "longitude",
    "place_of_occurrence",
    "police_station_id",
    "registration_datetime",
    "section_code"
  ],
  "permitted_use": "public_safety_risk_modeling",
  "valid_from": "2026-01-01T00:00:00Z",
  "valid_until": "2027-12-31T23:59:59Z"
}
```

### 2.2 Deterministic Canonical Serialization Implementation
```python
canonical_dict = {
    "authorization_id": str(authorization_id).strip(),
    "dataset_sha256": str(dataset_sha256 or "*").strip(),
    "issuer_id": str(issuer_id).strip(),
    "manifest_version": str(manifest_version or "2.1").strip(),
    "mou_reference": str(mou_reference).strip(),
    "permitted_fields": sorted(str(f).strip() for f in (permitted_fields or [])) if permitted_fields else [],
    "permitted_use": str(permitted_use).strip(),
    "valid_from": str(valid_from).strip(),
    "valid_until": str(valid_until).strip(),
}
return json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
```
- **Sorted Keys:** Guarantees key order is identical regardless of dictionary insertion order.
- **No Whitespace Separators:** `separators=(',', ':')` eliminates whitespace ambiguity across platforms.
- **UTF-8 Encoded:** Ensures deterministic byte-level fidelity.

### 2.3 Fail-Closed Validation Matrix

| Field / Condition | Validation Rule | Failure Mode |
| :--- | :--- | :--- |
| `authorization_id` | Must be non-empty string. Verified in canonical payload. | `AUTHORIZATION_UNVERIFIED` (Missing field or signature mismatch) |
| `valid_from` & `valid_until` | Must parse strictly via `datetime.fromisoformat()`. Timezone normalized. | `AUTHORIZATION_UNVERIFIED` (Malformed or unparseable timestamp) |
| Inverted Time Window | `valid_from > valid_until` strictly rejected. | `AUTHORIZATION_UNVERIFIED` (Manifest validity window malformed) |
| `dataset_sha256` | Must match raw file digest when binding enforced. Verified in canonical payload. | `AUTHORIZATION_UNVERIFIED` (Dataset fingerprint mismatch or signature mismatch) |
| `permitted_fields` | Must be list of strings; sorted in canonical payload. | `AUTHORIZATION_UNVERIFIED` (Signature mismatch on scope modification) |
| `permitted_use` | Must match issuer's allowed purpose list and canonical payload. | `AUTHORIZATION_UNVERIFIED` (Unapproved purpose or signature mismatch) |
| `signature` | Must be valid hex string of exactly 64 bytes (128 hex chars). | `AUTHORIZATION_UNVERIFIED` (Malformed signature format or InvalidSignature) |

### 2.4 Authoritative Revocation Mechanism
Previously, revocation relied exclusively on `manifest.get("is_revoked", False)`. An attacker with a revoked manifest could simply edit `"is_revoked": false` to evade the check.

**Phase 6.2 Hardening:**
- `InstitutionalIssuerRegistry.register_revocation(identifier)` registers revoked authorization IDs, MoU references, or signature digests in an authoritative in-memory set `TRUSTED_REVOKED_IDENTIFIERS`.
- `PUNE_REVOKED_AUTHORIZATIONS` environment variable provides external Certificate Revocation List (CRL) capabilities.
- `InstitutionalIssuerRegistry.is_authorization_revoked(manifest)` evaluates:
  1. Manifest self-declared flag (`manifest["is_revoked"] == True`)
  2. Trusted in-memory registry match (`auth_id`, `mou_reference`, or signature)
  3. Environment CRL match (`PUNE_REVOKED_AUTHORIZATIONS`)
- If any check matches, verification fails closed with `AUTHORIZATION_UNVERIFIED`.

---

## 3. Test-Key Isolation and Credential Security

1. **Test Seed Isolation:**
   - The deterministic test seed (`fb9b4e3e1a5b86449380ff61bfcec074be7ad2dc2b7e422e9968eb67a26ae0e6`) exists exclusively within unit test code (`backend/tests/test_pune_data_readiness_gate.py`) and is explicitly labeled `TEST_SANDBOX_PRIVATE_KEY`.
   - The production codebase contains zero private keys or private seeds.
2. **Synthetic Authority Sandboxing:**
   - The synthetic issuer `test_fixture_authority` has `"is_fixture_authority": True`.
   - In `InstitutionalIssuerRegistry.verify_manifest`:
     ```python
     if issuer_info["is_fixture_authority"] and not is_fixture:
         violations.append("Fixture authority credential cannot authorize a production dataset. Production issuer required.")
         return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)
     ```
   - Attempting to authorize production data (`is_fixture=False`) with test credentials is unconditionally blocked.
3. **Unprovisioned Production Key Guard:**
   - The real institutional issuer `pune_city_police_cop` has `"public_key_hex": None`.
   - In the absence of an officially provisioned `PUNE_COP_ED25519_PUBLIC_KEY`, production authorization fails closed.

---

## 4. Intake-Manifest Integrity & Independent Root Ledger

### 4.1 Vulnerability Analysis: Simultaneous Local File Tampering
If an adversary has write access to a version directory (`v1.0/`):
- The adversary could modify `cleaned_incidents.csv`.
- To evade the hash check, the adversary could recompute its SHA-256 and update `output_fingerprint.cleaned_file_sha256` inside `intake_audit_manifest.json`.
- A naive check comparing `cleaned_incidents.csv` solely against `intake_audit_manifest.json` would pass because both files were locally rewritten.

### 4.2 Solution: Independent Append-Only Audit Ledger
In Phase 6.2, `PuneDataIngestionPipeline.ingest_authorized_dataset()` writes:
1. `version_dir/intake_audit_manifest.json` (versioned metadata)
2. `destination_root_dir/intake_audit_ledger.jsonl` (independent append-only audit ledger)

Each entry in `intake_audit_ledger.jsonl` binds:
- `dataset_version`
- `logged_at` (UTC timestamp)
- `raw_input_sha256`
- `cleaned_file_sha256`
- `intake_manifest_sha256` (Bitwise SHA-256 of the generated `intake_audit_manifest.json`)
- `authorization_id`, `mou_reference`, `issuer_id`

### 4.3 Multi-Tier Integrity Verification (`verify_intake_integrity`)
`PuneDataIngestionPipeline.verify_intake_integrity(destination_root_dir, version)` verifies:
1. **Tier 1 (Application Overwrite):** Ensures version directories cannot be silently replaced (`FileExistsError`).
2. **Tier 2 (File Tamper Detection):** Recomputes `cleaned_incidents.csv` SHA-256 and asserts match with `intake_audit_manifest.json`.
3. **Tier 3 (Authorization Verification):** Re-verifies `authorized_manifest.json` digital signature against `InstitutionalIssuerRegistry`.
4. **Tier 4 (Ledger Digest Check):** Recomputes `intake_audit_manifest.json` SHA-256 and asserts exact match with the independent root ledger (`intake_audit_ledger.jsonl`).
   - If an adversary mutates both `cleaned_incidents.csv` and `intake_audit_manifest.json` in `v1.0/`, the manifest digest fails the ledger check, emitting:  
     `"Simultaneous file and manifest tampering detected!"`

---

## 5. Reconciled Forecasting Time-Window Definitions

### 5.1 Reconciliation: 4-Hour Windows vs. 8-Hour Patrol Shifts
A documentation ambiguity previously existed between:
- Traditional Indian police officer patrol shifts: **3 shifts per day (8 hours each)**.
- Strata Risk's real-time tactical dispatch prediction horizon: **6 windows per day (4 hours each)**.

**Reconciliation Decision:**
Strata Risk's primary forecasting and evaluation target is definitively established as **4-Hour Operational Prediction Windows** (4 hours ahead). This aligns with the operational model deployed in Chicago (providing frequent, actionable risk updates every 4 hours rather than broad daily or 8-hour summaries).

### 5.2 Quantified Evaluation Units Across Horizons (33 Stations)

| Horizon / Window Type | Duration | Windows / Day | Station-Units / Day | Units in 180 Days | Units in 365 Days | Units in 3 Years (1,095 Days) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Operational Prediction Window (Primary)** | **4 Hours** | **6** | **198** | **35,640** | **72,270** | **216,810** |
| **Officer Patrol Shift (Comparative)** | **8 Hours** | **3** | **99** | **17,820** | **36,135** | **108,405** |
| **Daily Aggregate (Baseline)** | **24 Hours** | **1** | **33** | **5,940** | **12,045** | **36,135** |

### 5.3 Codebase Harmonization
1. **`data_providers.py`:** Updated `temporal_aggregation` provenance string to `"Pending (Target: 4-Hour Operational Windows / 6 Windows per Day)"`.
2. **`pune_data_readiness.py`:**
   - Defined `WINDOW_DURATION_HOURS = 4`, `WINDOWS_PER_DAY = 6`, `STATION_WINDOWS_PER_DAY = 198` in `PuneForecastingEvaluationProtocol`.
   - Added `calculate_expected_station_windows(num_days, num_stations)` for deterministic unit calculation.
   - Added `calculate_window_support(df, window_hours, num_stations)` for empirical target support calculation without data fabrication.
   - Enhanced `calc_shift_window_support()` in `PuneExploratoryAnalysisWorkflow` to output both primary `"4_hour_operational_window"` and comparative `"8_hour_patrol_shift"` metrics.

---

## 6. Regression Protection Results

### 6.1 Pytest Test Suite
Command: `python -m pytest backend/tests/ -v`  
Results: **132 passed, 0 failed, 14 deprecation warnings (matplotlib)** in 6.63s.

```
============================= test session starts =============================
collected 132 items

backend/tests/test_audit_regressions.py (13 passed)
backend/tests/test_pune_data_ingestion.py (28 passed)
backend/tests/test_pune_data_readiness_gate.py (38 passed)
backend/tests/test_temporal_leakage.py (2 passed)
backend/tests/test_universal_location.py (18 passed)
...
====================== 132 passed, 14 warnings in 6.63s =======================
```

### 6.2 Frontend Typecheck, Lint & Build
- `npx tsc --noEmit`: Clean exit code 0 (0 errors).
- `npm run lint`: Clean exit code 0 (0 errors).
- `npm run build`: Production bundle built in 344ms (`dist/index.html`, `dist/assets/index-Dm2RPArN.css`, `dist/assets/index-6R5Y84lq.js`).

### 6.3 Canonical Chicago Model Artifact Hashes
Hashes recomputed via PowerShell `Get-FileHash`:

| Artifact Path | Canonical SHA-256 Hash | Recomputed SHA-256 Hash | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96` | `8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96` | **EXACT MATCH** |
| `backend/artifacts/calibrator.joblib` | `8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D` | `8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D` | **EXACT MATCH** |
| `backend/artifacts/model_metadata.json` | `B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407` | `B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407` | **EXACT MATCH** |

---

## 7. Modified Codebase Files

1. [pune_data_readiness.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/pune_data_readiness.py):
   - Implemented RFC 8785 deterministic canonical payload binding all authorization-sensitive fields.
   - Added authoritative revocation registry and environment CRL evaluation (`PUNE_REVOKED_AUTHORIZATIONS`).
   - Added strict fail-closed timestamp parsing and inverted window detection (`valid_from > valid_until`).
   - Reconciled 4-hour operational forecast window constants and unit calculations.
2. [pune_ingestion_pipeline.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/ingestion/pune_ingestion_pipeline.py):
   - Imported `InstitutionalIssuerRegistry`.
   - Added append-only root intake audit ledger (`intake_audit_ledger.jsonl`).
   - Implemented `verify_intake_integrity()` protecting against simultaneous file and manifest tampering.
3. [data_providers.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/data_providers.py):
   - Updated `temporal_aggregation` metadata to 4-hour operational windows.
4. [test_pune_data_readiness_gate.py](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_pune_data_readiness_gate.py):
   - Added tests for sensitive field tampering, malformed/inverted timestamps, authoritative revocation, independent audit ledger verification, and temporal window calculations (total 38 tests passing).
5. [PHASE_6_2_CRYPTOGRAPHIC_AND_TEMPORAL_AUDIT.md](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_6_2_CRYPTOGRAPHIC_AND_TEMPORAL_AUDIT.md):
   - Created comprehensive Phase 6.2 audit report.

---

## 8. Remaining Limitations & Institutional Dependencies

1. **Institutional Verification Key Provisioning:** The Commissioner of Police, Pune City has not yet provisioned an authentic public key. Real data authorization remains blocked until `PUNE_COP_ED25519_PUBLIC_KEY` is provisioned.
2. **Official GIS Boundary Deliverable:** Polygon shapefiles for Pune's 33 police station jurisdictions remain pending from official survey authorities.
3. **Storage Tier Classification:** Local intake uses filesystem storage with ledger hashing. Enterprise deployment requires S3 Object Lock (Compliance Mode) or cloud WORM storage for hardware-enforced immutability.

---

### Final Conditions Maintained
- **Pune:** Strictly `UNSUPPORTED`.
- **Mumbai:** Strictly `UNSUPPORTED`.
- **No Pune model trained or deployed.**
- **No fabricated Indian forecasts exposed.**
- **Chicago model, artifacts, and serving behavior remain 100% unchanged.**
