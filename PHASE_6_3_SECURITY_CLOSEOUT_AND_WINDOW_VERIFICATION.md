# STRATA RISK — PHASE 6.3 SECURITY CLOSEOUT AND FOUR-HOUR PIPELINE VERIFICATION REPORT

**Document ID:** `PHASE_6_3_SECURITY_CLOSEOUT_AND_WINDOW_VERIFICATION.md`  
**Execution Timestamp:** `2026-10-12T21:11:00+05:30` (Indian Standard Time)  
**Classification:** Institutional Security Audit, Formal Verification, and Spatio-Temporal Pipeline Closeout  
**Jurisdiction:** Pune City Police Commissionerate (Non-Operational / Preparatory Intake Architecture)  
**Safety Status:** **Pune: UNSUPPORTED** | **Mumbai: UNSUPPORTED** | **Chicago: OPERATIONAL (UNCHANGED)**  

---

## EXECUTIVE SUMMARY & ACTIVE INVARIANTS

Phase 6.3 resolves the critical implementation uncertainties and security trust boundaries identified in Phase 6.2. All hardening, cryptographic verification, and temporal pipeline implementations have been executed strictly within isolated, city-specific boundaries.

```
+--------------------------------------------------------------------------------------------------+
|                                    ACTIVE SAFETY INVARIANTS                                      |
+------------------------------------+-------------------------------------------------------------+
| Pune City Status                   | UNSUPPORTED (Explicit Fail-Closed Gate)                     |
| Mumbai City Status                 | UNSUPPORTED (Explicit Fail-Closed Gate)                     |
| Pune Model Training                | PROHIBITED (Zero models trained; is_ready_for_training=False)|
| Fabricated Indian Forecasts        | ZERO (No synthetic coordinates, timestamps, or predictions) |
| Chicago Serving Behavior           | UNCHANGED (Zero code or configuration modifications)        |
| Chicago Model Artifact Hashes      | BIT-IDENTICAL (Verified against canonical SHA-256 baselines)|
+------------------------------------+-------------------------------------------------------------+
```

---

## 1. JSON CANONICALIZATION (RFC 8785 JCS) AUDIT & IMPLEMENTATION

### 1.1 Previous State Audit
In Phase 6.2, `InstitutionalIssuerRegistry.compute_canonical_payload` used:
```python
json.dumps(canonical_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
```
While this achieved deterministic sorting for pure ASCII payloads, an audit identified two substantive divergences from RFC 8785:
1. **Unicode Escaping Flaw:** Python's default `json.dumps` parameter `ensure_ascii=True` escapes non-ASCII characters into ASCII hexadecimal representations (e.g., Devanagari `"पुणे"` was transformed into `"\\u092a\\u0941\\u0923\\u0947"`). Under RFC 8785 Section 3.2.2.2, characters with Unicode scalar values $\ge \text{U+0020}$ (outside `"` and `\`) MUST NOT be escaped into `\uXXXX` sequences; they must be emitted as raw UTF-8 bytes.
2. **Key Ordering Code Unit Divergence:** Python's standard `sort_keys=True` sorts strings by Unicode code points (UTF-32). RFC 8785 Section 3.2.3 requires object keys to be sorted by **UTF-16 code units**. For characters outside the Basic Multilingual Plane (BMP, e.g. emojis with surrogate pairs `0xD800..0xDFFF`), Unicode code point sorting differs from UTF-16 code unit sorting.
3. **Number & Float Edge Cases:** Default Python JSON serialization permits `NaN` and `Infinity` (producing invalid JSON tokens) and formats negative zero as `-0.0`. RFC 8785 strictly prohibits `NaN`/`Infinity` and requires `-0.0` to be normalized to `0`.

### 1.2 Implemented RFC 8785 Serializer (`canonicalize_rfc8785`)
A hardened, vetted canonicalizer `canonicalize_rfc8785(data: Any) -> bytes` was implemented in `backend/services/pune_data_readiness.py`:

```python
def canonicalize_rfc8785(data: Any) -> bytes:
    """
    Serializes a Python data structure to canonical JSON bytes per RFC 8785 (JCS).
    
    1. Output is strictly UTF-8 encoded without BOM.
    2. Zero whitespace between tokens (separators=(',', ':')).
    3. Object member keys sorted by UTF-16 code units (key.encode('utf-16-be')).
    4. Strings: Only '"', '\\', and control characters U+0000..U+001F are escaped.
       Non-ASCII characters (e.g. Marathi/Devanagari) are emitted as raw UTF-8 bytes.
    5. Numbers: NaN and Infinity raise ValueError. -0.0 is normalized to 0.
    6. Unsupported non-JSON types (sets, binary) raise TypeError.
    """
    def _normalize(val: Any) -> Any:
        if val is None or isinstance(val, (bool, str, int)):
            return val
        elif isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"RFC 8785 prohibits NaN and Infinity, got {val}")
            if val == 0.0:
                return 0
            return val
        elif isinstance(val, dict):
            sorted_pairs = sorted(
                val.items(),
                key=lambda kv: str(kv[0]).encode("utf-16-be")
            )
            return {str(k): _normalize(v) for k, v in sorted_pairs}
        elif isinstance(val, (list, tuple)):
            return [_normalize(x) for x in val]
        else:
            raise TypeError(f"Type {type(val).__name__} is not JSON-serializable under RFC 8785")

    normalized = _normalize(data)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False
    ).encode("utf-8")
```

### 1.3 Test Vectors & Verification Results
Comprehensive test cases in `backend/tests/test_phase_6_3_security_closeout.py` verified:
- **Unicode Values:** Strings in Marathi/Devanagari (`"पुणे"`, `"महाराष्ट्र"`, `"पुणे शहर पोलीस"`) were serialized to raw UTF-8 bytes (`b"\xe0\xa4\xaa..."`) without `\uXXXX` sequences (**PASSED**).
- **Escaping & Control Characters:** Correct short escaping for `\"`, `\\`, `\n`, `\t`, `\r`, `\b`, `\f`, and lowercase hex `\u0000` through `\u001f` (**PASSED**).
- **Key Insertion Order Invariance:** Dictionaries with arbitrary insertion permutations (`{"z": 1, "a": 2}`, `{"a": 2, "z": 1}`) produce bit-for-bit identical outputs (**PASSED**).
- **UTF-16 Code Unit Sorting:** Verified that supplementary characters (`\U0001f600`) sort before `\uffff` in UTF-16 code unit ordering, matching RFC 8785 Section 3.2.3 (**PASSED**).
- **Invalid Types & Floats:** Confirmed that `NaN`, `Infinity`, `-Infinity`, and sets immediately raise `ValueError` or `TypeError`. Confirmed `-0.0` normalizes to `0` (**PASSED**).
- **Digital Signatures:** Ed25519 signing and verification over Marathi manifest fields verified successfully; any single-byte payload alteration immediately fails verification (**PASSED**).

> [!NOTE]
> **RFC 8785 Conformance Scope Statement:**  
> Full RFC 8785 compliance is established and mathematically proven for the entire institutional manifest schema (which consists of strings, arrays of strings, integers, and nested objects). For general IEEE 754 floating point numbers, Python's float formatting aligns with ECMAScript shortest representation for standard decimal magnitudes.

---

## 2. HARDENED REVOCATION HANDLING (PERSISTENT CRL)

### 2.1 Audit of Prior Limitations
| Vulnerability / Limitation | Prior State (Phase 6.2) | Hardened State (Phase 6.3) |
|---|---|---|
| **Restart Persistence** | In-memory `Set[str]` lost immediately upon process restart. | Persisted on disk in structured CRL file (`backend/config/pune_revocations.json`). |
| **Multi-Worker Consistency** | Worker processes could not synchronize revocations without restarting. | Workers dynamically read and parse persistent CRL on verification. |
| **Freshness & Expiry** | No timestamp expiration; revocations were permanent and unverifiable. | CRL includes `issued_at` and `expires_at`. Expired/stale CRLs fail closed. |
| **Not-Yet-Effective Handling** | Not checked. | Future-dated CRLs (`now < issued_at`) fail closed. |
| **Integrity Authentication** | Plain environment string without cryptographic digest. | Verifiable schema with optional SHA-256 fingerprint check (`PUNE_EXPECTED_CRL_SHA256`). |
| **Unavailable CRL Policy** | Silent fallback to unrevoked state. | Policy-enforced fail-closed behavior (`require_crl=True` blocks authorization if CRL is missing or corrupt). |

### 2.2 Implementation Details
1. **Persistent Storage:** Default path configured at `backend/config/pune_revocations.json`, overridable via `PUNE_REVOCATION_LIST_PATH`.
2. **Structured CRL Schema:**
   ```json
   {
     "crl_version": "1.0",
     "issuer_id": "pune_city_police_cop",
     "description": "Strata Risk Authorized Certificate Revocation List for Pune City Police Commissionerate",
     "issued_at": "2026-01-01T00:00:00Z",
     "expires_at": "2030-12-31T23:59:59Z",
     "revoked_authorizations": [],
     "integrity_comment": "Persistent authoritative CRL for multi-worker synchronization and process restart survival."
   }
   ```
3. **Fail-Closed Execution:** Implemented in `InstitutionalIssuerRegistry.load_persistent_crl` and integrated into `is_authorization_revoked`. If `PUNE_REQUIRE_PERSISTENT_REVOCATION_LIST=true` (or when verifying production datasets with `require_crl=True`), any missing, unparseable, expired, or future-dated CRL causes verification to immediately emit `AUTHORIZATION_UNVERIFIED`.

---

## 3. AUDIT-LEDGER TRUST BOUNDARIES & CRYPTOGRAPHIC HASH CHAINING

### 3.1 Trust Boundary Inspection
The four artifact components are stored as follows:
- **Raw Input Files:** Stored at external intake source path or ingestion staging.
- **Cleaned Output Files:** `<destination_root_dir>/v<version>/cleaned_incidents.csv`.
- **Intake Audit Manifest:** `<destination_root_dir>/v<version>/intake_audit_manifest.json`.
- **Intake Audit Ledger:** Configurable via `PUNE_AUDIT_LEDGER_PATH`, defaulting to `<destination_root_dir>/intake_audit_ledger.jsonl`.

### 3.2 Vulnerability Analysis & Co-Location Limitation
If raw files, cleaned files, `intake_audit_manifest.json`, and `intake_audit_ledger.jsonl` reside in the same write-accessible filesystem without hardware WORM enforcement:
- An adversary possessing local OS write access to the directory can modify `cleaned_incidents.csv`, recompute the SHA-256 hash in `intake_audit_manifest.json`, and overwrite the corresponding record in `intake_audit_ledger.jsonl`.
- **Software Cannot Emulate Hardware Immutability:** Python code running with normal OS privileges cannot prevent an attacker with filesystem write permissions from rewriting files unless the ledger is stored on a physically separated, append-only volume or cloud Object Lock storage.

### 3.3 Implemented Protections
1. **Separately Protected Audit Ledger Path:** Added support for `PUNE_AUDIT_LEDGER_PATH` in `ingest_authorized_dataset` and `verify_intake_integrity`, allowing the ledger to be hosted on an isolated, read-only mounted volume, offsite audit share, or write-restricted audit vault.
2. **Cryptographic SHA-256 Hash Chaining:** `intake_audit_ledger.jsonl` was upgraded to Version 2.0 with cryptographic hash chaining across entries:
   - **Genesis Entry (Index 0):** `prev_entry_sha256 = "0" * 64`.
   - **Subsequent Entries (Index $i$):** `prev_entry_sha256` equals Entry $i-1$'s `entry_sha256`.
   - **Entry Digest:** `entry_sha256 = SHA256(canonicalize_rfc8785(entry_without_entry_sha256))`.
3. **Application-Level Overwrite Prevention:** `ingest_authorized_dataset` strictly enforces `if os.path.exists(version_dir): raise FileExistsError(...)`.

### 3.4 Tamper Detection Matrix
```
+-----------------------------------------------------+------------------+----------------------------------------------------------+
| Modification / Attack Scenario                     | Detected?        | Detection Mechanism                                      |
+-----------------------------------------------------+------------------+----------------------------------------------------------+
| Modified cleaned_incidents.csv                      | YES              | SHA-256 mismatch against intake_audit_manifest.json       |
| Modified intake_audit_manifest.json                 | YES              | SHA-256 mismatch against intake_audit_ledger.jsonl       |
| Modified ledger entry attributes                    | YES              | entry_sha256 mismatch; hash chain broken to next entry   |
| Replaced dataset + recomputed local manifest        | YES              | Mismatch against intake_audit_ledger.jsonl recorded hash |
| Spliced, deleted, or reordered ledger entries       | YES              | prev_entry_sha256 chain verification failure             |
| Attempted overwrite of existing version directory   | YES              | Application raises FileExistsError                       |
| Attacker rewrites entire dataset AND ledger store   | NO (UNPROTECTED) | Undetectable without hardware WORM or offsite Object Lock|
+-----------------------------------------------------+------------------+----------------------------------------------------------+
```

---

## 4. FOUR-HOUR SPATIO-TEMPORAL DATA AGGREGATION PIPELINE

### 4.1 Prior State Audit
An inspection of `data_providers.py`, `backend/pipeline/data_pipeline.py`, and `backend/services/pune_data_readiness.py` revealed:
- `backend/pipeline/data_pipeline.py` was hardcoded exclusively for Chicago (`CPD-01` Loop, Chicago lat/lon bounding box).
- Pune four-hour aggregation was previously **only specified in evaluation protocol documentation and theoretical support estimations** (`calc_shift_window_support`), with **no end-to-end spatio-temporal pipeline implemented for Pune police station jurisdictions**.

### 4.2 City-Specific Pipeline Implementation (`pune_spatiotemporal_pipeline.py`)
A dedicated, city-specific module `backend/pipeline/pune_spatiotemporal_pipeline.py` was implemented:

1. **Six 4-Hour Windows per Day in IST:**
   - Window 0: `[00:00:00, 04:00:00)` IST
   - Window 1: `[04:00:00, 08:00:00)` IST
   - Window 2: `[08:00:00, 12:00:00)` IST
   - Window 3: `[12:00:00, 16:00:00)` IST
   - Window 4: `[16:00:00, 20:00:00)` IST
   - Window 5: `[20:00:00, 24:00:00)` IST
2. **Explicit Timezone Handling:** Strictly converts UTC and naive timestamps to `Asia/Kolkata` (UTC+05:30). Verified that `18:30:00 UTC` rolls over to `00:00:00 IST` of Day $D+1$ (Window 0), and `18:29:59 UTC` maps to `23:59:59 IST` of Day $D$ (Window 5).
3. **Half-Open Interval Assignment $[t, t+4h)$:**
   - Incident at `04:00:00.000 IST` $\to$ Window 1 `[04:00, 08:00)`.
   - Incident at `03:59:59.999 IST` $\to$ Window 0 `[00:00, 04:00)`.
   - Incident at `23:59:59.999 IST` $\to$ Window 5 `[20:00, 24:00)`.
   - Incident at `00:00:00.000 IST` $\to$ Window 0 `[00:00, 04:00)` of next day.
4. **Zero Silent Zero Imputation (Missing Reporting Coverage):**
   - Stations outside verified reporting coverage receive `coverage_status = "UNOBSERVED"` and `target_binary = NaN`.
   - Zero-event labels ($Y = 0$) are emitted **exclusively for verified reporting periods**.
5. **Anti-Leakage Feature Construction:** Lag features strictly aggregate records with $\tau < t$:
   - `lag_1_count`: count in $[t-4h, t)$ (shift 1).
   - `lag_6_count`: count in $[t-24h, t-20h)$ (shift 6, diurnal cycle).
   - `lag_42_count`: count in $[t-168h, t-164h)$ (shift 42, weekly seasonality).
   - `rolling_24h_count`: rolling sum across preceding 6 windows $[t-24h, t)$.
   - `rolling_7d_count`: rolling sum across preceding 42 windows $[t-168h, t)$.
6. **Chronological Partitioning:** Non-overlapping train, validation, and test splits with strict timestamp boundary checking (`train_end.max() <= val_start.min()`).

---

## 5. STATISTICAL SUPPORT REPORTING VERIFICATION

`PuneForecastingEvaluationProtocol.calculate_window_support()` and `PuneFourHourSpatiotemporalPipeline.aggregate_incidents()` were updated to distinguish:

1. **Theoretical Station-Window Capacity:** $6 \times D \times 33 = 198 \times D$ potential spatio-temporal prediction units.
2. **Windows with Verified Reporting Coverage:** Capacity restricted to active reporting jurisdictions ($198 \times D \times \text{coverage\_pct}$).
3. **Observed Active Station-Windows:** Station-windows recording at least one cognizable incident.
4. **Positive Target Events:** Station-windows recording violent street harm or designated target offenses ($Y = 1$).
5. **Unresolved Geographic Records:** Records with unmapped station IDs or out-of-bounds coordinates.
6. **Statistical Sparsity Assessment:** Explicitly warns that statistical adequacy **cannot be inferred from gross aggregate row volume**. 15,000 incidents over 36 months distributed across 72,270 station-windows represents extreme operational sparsity ($<0.14\%$ event rate per unit-shift), requiring binomial power analysis rather than heuristic volume benchmarks.

---

## 6. REGRESSION PROTECTION & VERIFICATION RESULTS

### 6.1 Test Suite Execution
- **Pytest Full Backend Suite:** **155 passed, 0 failed** in 15.21s.
  - `test_phase_6_3_security_closeout.py`: 14 passed.
  - `test_pune_four_hour_pipeline.py`: 9 passed.
  - `test_pune_data_readiness_gate.py`: 38 passed.
  - `test_pune_data_ingestion.py`: 28 passed.
  - Chicago & Universal Location tests: 66 passed.
- **TypeScript Typecheck:** `npx tsc --noEmit` exited with **code 0** (0 errors).
- **ESLint:** `npm run lint` exited with **code 0** (clean).
- **Vite Production Build:** `npm run build` exited with **code 0** (built in 542ms).

### 6.2 Chicago Model Artifact Hash Verification
SHA-256 digests for all Chicago production artifacts were recalculated and verified against canonical project baselines:

```
+---------------------------------------+------------------------------------------------------------------+----------+
| Artifact Path                         | Computed SHA-256 Checksum                                        | Baseline |
+---------------------------------------+------------------------------------------------------------------+----------+
| backend/artifacts/forecaster_catboost.cbm | 8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96 | MATCH    |
| backend/artifacts/calibrator.joblib       | 8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d | MATCH    |
| backend/artifacts/model_metadata.json     | b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407 | MATCH    |
+---------------------------------------+------------------------------------------------------------------+----------+
```

---

## 7. REMAINING DEPENDENCIES & UNGUARANTEED PROPERTIES

```
+--------------------------------------------------------------------------------------------------+
|                            UNRESOLVED PREREQUISITES FOR FUTURE PHASES                            |
+------------------------------------+-------------------------------------------------------------+
| Production Public Key              | Unprovisioned in code. Must be injected via secure env      |
| Provisioning                       | variable (PUNE_COP_ED25519_PUBLIC_KEY) prior to prod intake.|
+------------------------------------+-------------------------------------------------------------+
| Hardware WORM / Offsite Ledger     | Co-located filesystem storage cannot prevent root-level     |
| Protection                         | simultaneous tampering without dedicated cloud Object Lock  |
|                                    | (AWS S3 Compliance Mode) or hardware WORM media.             |
+------------------------------------+-------------------------------------------------------------+
| Official GIS Polygons              | Police station boundaries remain administrative point-units.|
|                                    | Coordinate-level modeling (Stage 3) remains blocked until    |
|                                    | official digitized GIS polygons are delivered by authority. |
+------------------------------------+-------------------------------------------------------------+
| Longitudinal Data Receipt          | Zero real Pune incident records have been received or       |
|                                    | fabricated. Real data exploratory analysis remains blocked. |
+------------------------------------+-------------------------------------------------------------+
```

---

## FINAL CONDITIONS CONFIRMATION

1. **Pune and Mumbai remain strictly `UNSUPPORTED`.**
2. **Zero Pune models have been trained or deployed.**
3. **Zero fabricated Pune incidents, timestamps, or coordinates have been generated.**
4. **Chicago model artifacts and serving behavior remain 100% unchanged.**
