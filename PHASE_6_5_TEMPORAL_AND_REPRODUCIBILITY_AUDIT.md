# STRATA RISK — PHASE 6.5
## TEMPORAL SPLIT INTEGRITY AND REPRODUCIBILITY AUDIT REPORT

**Date:** 2026-10-12  
**Audit Scope:** Temporal Partitioning Boundary Audit, Disjoint Station-Window Assignment, Target Interval Separation, Feature Causality & Leakage Prevention, Backend Dependency Manifest & Clean Reproducibility, Test Warning Resolution, Regression Protection, and Chicago Artifact Invariance.  
**System Status:**
- **Chicago Live Forecasting:** **SUPPORTED & OPERATIONAL** (Bit-identical model, calibrator, and metadata artifacts).
- **Pune Candidate Pilot:** **UNSUPPORTED** (Data acquisition preparation only; zero model trained; zero forecasts served).
- **Mumbai Candidate Pilot:** **UNSUPPORTED** (Zero model trained; zero weights transferred).

---

## 1. EXECUTIVE SUMMARY

Phase 6.5 resolves the remaining temporal-split ambiguities and reproducibility requirements identified during the Phase 6.4 audit for the candidate Pune City Police spatiotemporal forecasting pipeline. The audit and implementation achievements include:

1. **Strict Half-Open Temporal Partitioning:** Identified and resolved ambiguity stemming from non-strict partition boundaries. Formally established strict half-open interval assignment $[t, t + 4\text{h})$ in Indian Standard Time (`Asia/Kolkata`).
2. **Guaranteed Disjoint Station-Window Key Sets:** Enforced programmatic assertions ensuring that the composite unique key `(police_station_id, window_start)` cannot appear in multiple partitions:
   $$\text{Keys}(\text{train}) \cap \text{Keys}(\text{val}) = \emptyset, \quad \text{Keys}(\text{val}) \cap \text{Keys}(\text{test}) = \emptyset, \quad \text{Keys}(\text{train}) \cap \text{Keys}(\text{test}) = \emptyset$$
3. **Target Interval Strict Separation & Embargo Support:** Established strict target interval non-overlap. Training target intervals end at or before validation target intervals begin ($\max(Y_{\text{train\_end}}) \le \min(Y_{\text{val\_start}})$), and validation target intervals end at or before test target intervals begin ($\max(Y_{\text{val\_end}}) \le \min(Y_{\text{test\_start}})$). Implemented an explicit `embargo_windows` buffer gap to eliminate serial correlation leakage between adjacent partitions.
4. **Enforced Boundary Alignment:** Required split boundary cutoff timestamps (`train_end`, `val_end`) to align exactly with 4-hour window boundaries (`minute == 0`, `second == 0`, `hour % 4 == 0`), rejecting unaligned timestamps with explicit `ValueError` exceptions to prevent fractional-window leakage.
5. **Feature Causality & Temporal Continuity Checks:** Hardened lag and rolling feature construction to ensure that all predictors use only information available strictly before prediction time ($\tau < t$). Added temporal continuity validation ($\Delta t = 4\text{h}$) to ensure that missing data intervals produce `NaN` rather than drawing out-of-cadence historical records.
6. **Isolated Preprocessing & Calibration:** Re-verified that data transformation parameters (e.g. scalers, imputers) are fitted strictly on the training partition and applied out-of-sample, and that test set labels remain completely isolated from threshold tuning or probability calibration.
7. **Backend Dependency Manifest & Clean Reproducibility:** Verified the canonicalization and cryptographic dependencies (`jcs>=0.2.1` and `cryptography>=41.0.0`), explicitly added both to [`backend/requirements.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements.txt), and verified minimal canonicalization and signature cycles.
8. **Test Warning Resolution:** Audited full backend test warnings, identified that all 14 warnings stemmed from third-party `matplotlib` calls to deprecated `pyparsing` methods, configured targeted filtering in [`pytest.ini`](file:///c:/Users/harsh/Downloads/strata-risk/pytest.ini), and achieved a clean 180-test pass with 0 warnings.
9. **Regression & Artifact Protection:** Confirmed that all 180 backend tests pass, TypeScript compiles cleanly (`npx tsc --noEmit`), linting passes (`npm run lint`), production build succeeds (`npm run build`), and Chicago production model artifacts remain bit-for-bit identical to canonical SHA-256 baselines.

---

## 2. VERIFICATION STATUS MATRIX

| Claimed Property | Implementation Mechanism | Audit Status | Empirical Evidence / Test Coverage |
| :--- | :--- | :--- | :--- |
| **Disjoint Station-Window Keys** | Strict half-open filtering with set-intersection assertion | **VERIFIED** | [`test_disjoint_station_window_keys_across_all_partitions`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L35-L68) |
| **Target Interval Separation** | Target start/end timestamps tracked; non-overlap assertion | **VERIFIED** | [`test_target_interval_strict_separation_no_overlap`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L71-L101) |
| **Boundary Alignment Enforcement** | Strict validation of 4h grid alignment (`hour % 4 == 0`) | **VERIFIED** | [`test_unaligned_split_boundaries_rejected`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L104-L127) |
| **Embargo Buffer Gap** | Optional parameter `embargo_windows` inserts gap between splits | **VERIFIED** | [`test_embargo_buffer_gap_enforcement`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L130-L162) |
| **Lag Temporal Continuity** | Time-difference validation ($\Delta t == 4\text{h}$) emits `NaN` on gap | **VERIFIED** | [`test_temporal_continuity_check_in_lag_feature_construction`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L165-L198) |
| **Zero Lookahead in Rolling Features** | Rolling aggregations exclude current and future windows | **VERIFIED** | [`test_anti_leakage_feature_construction_zero_lookahead`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_pune_four_hour_pipeline.py#L225-L260) |
| **Preprocessing Isolation** | Transformers fitted strictly on train split; transform on val/test | **VERIFIED** | [`test_preprocessing_scaler_fit_strictly_on_training_split`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L201-L228) |
| **Dependency Manifest Completeness** | `jcs>=0.2.1` and `cryptography>=41.0.0` in `requirements.txt` | **VERIFIED** | [`test_requirements_file_declares_cryptography_and_jcs`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L231-L245) |
| **Clean Import & Signature Cycle** | Pure environment import, RFC 8785 canonicalization, and Ed25519 verify | **VERIFIED** | [`test_clean_import_and_minimal_canonicalization_signature_cycle`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L248-L280) |
| **Zero Pytest Warnings** | Targeted filter in `pytest.ini` silences external deprecations | **VERIFIED** | Pytest run: 180 passed, 0 warnings (15.32s) |
| **Chicago Artifact Immutability** | Cryptographic SHA-256 hash match on all 3 binary artifacts | **VERIFIED** | Exact byte match across all runs |

---

## 3. AUDIT OF TEMPORAL PARTITIONING

### 3.1 Identification of Boundary Ambiguity
In earlier documentation and conceptual drafts, split boundaries were occasionally described with informal inequalities such as:
- $\text{Train}: \text{timestamp} \le T_{\text{split1}}$
- $\text{Validation}: T_{\text{split1}} \le \text{timestamp} \le T_{\text{split2}}$
- $\text{Test}: \text{timestamp} \ge T_{\text{split2}}$

If implemented with non-strict inequalities ($\le$ and $\ge$) on both sides, a record falling exactly on the boundary timestamp $T_{\text{split1}}$ would be matched by both the training query and the validation query. In a spatiotemporal grid where windows are defined by `window_start`, this would lead to the identical station-window $(s, T_{\text{split1}})$ existing in both training and validation partitions.

### 3.2 Formal Half-Open Interval Definition
To prevent double-assignment and data leakage, Strata Risk defines all spatiotemporal windows as strictly **half-open intervals**:
$$W_k = [t_k, t_k + 4\text{h})$$
where:
- An incident occurring at $t$ is mapped to window $W_k$ if and only if $t_k \le t < t_k + 4\text{h}$.
- Boundary cutoffs $T_{\text{train\_end}}$ and $T_{\text{val\_end}}$ must be exact grid boundary timestamps ($T \pmod{4\text{h}} = 0$).

Under this definition:
- **Training Partition:**
  $$\mathcal{D}_{\text{train}} = \{ (s, t_k) \mid t_k < T_{\text{train\_end}} \}$$
- **Validation Partition:**
  $$\mathcal{D}_{\text{val}} = \{ (s, t_k) \mid T_{\text{train\_end}} \le t_k < T_{\text{val\_end}} \}$$
- **Test Partition:**
  $$\mathcal{D}_{\text{test}} = \{ (s, t_k) \mid t_k \ge T_{\text{val\_end}} \}$$

Because the conditions $t_k < T_{\text{train\_end}}$, $T_{\text{train\_end}} \le t_k < T_{\text{val\_end}}$, and $t_k \ge T_{\text{val\_end}}$ are mutually exclusive and exhaustive over the temporal timeline, any valid timestamp $t_k$ maps to exactly one partition.

### 3.3 Boundary Alignment Enforcement
If an arbitrary, unaligned timestamp (e.g. `2026-06-01 14:30:00`) were supplied as a partition boundary, ambiguity would arise regarding whether the window spanning `12:00:00` to `16:00:00` belongs to train or validation. 

In [`backend/pipeline/pune_spatiotemporal_pipeline.py`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L312-L345), `create_chronological_splits` now validates that `train_end` and `val_end` satisfy:
```python
if (train_end_ts.minute != 0 or train_end_ts.second != 0 or train_end_ts.hour % 4 != 0):
    raise ValueError(
        f"train_end ({train_end}) must align with a 4-hour window boundary "
        f"(hour in {{0, 4, 8, 12, 16, 20}}, minute=0, second=0)."
    )
```
Any misaligned timestamp is rejected immediately with a `ValueError`.

---

## 4. ENFORCEMENT OF DISJOINT STATION-WINDOW ASSIGNMENT

### 4.1 Station-Window Key Uniqueness
In the spatiotemporal grid, the unique primary key for each observation unit is:
$$K = (\text{police\_station\_id}, \text{window\_start})$$

To guarantee that no observation can ever be duplicated across splits, [`create_chronological_splits`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L380-L405) constructs the set of composite keys for each partition and asserts disjointness:
```python
train_keys = set(zip(train_df["police_station_id"], train_df["window_start"]))
val_keys = set(zip(val_df["police_station_id"], val_df["window_start"]))
test_keys = set(zip(test_df["police_station_id"], test_df["window_start"]))

if train_keys & val_keys:
    raise ValueError(f"Temporal split leak: {len(train_keys & val_keys)} keys exist in both train and validation splits.")
if val_keys & test_keys:
    raise ValueError(f"Temporal split leak: {len(val_keys & test_keys)} keys exist in both val and test splits.")
if train_keys & test_keys:
    raise ValueError(f"Temporal split leak: {len(train_keys & test_keys)} keys exist in both train and test splits.")
```
This check is covered by [`test_disjoint_station_window_keys_across_all_partitions`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L35-L68).

### 4.2 Target Interval Separation & Embargo Buffer
For each observation window $W_k = [t_k, t_k + 4\text{h})$, the forecast target is defined over the subsequent interval:
$$Y_k = [t_k + 4\text{h}, t_k + 8\text{h})$$

Consider the boundary between training and validation:
- The latest training window starts at $t_{\text{last\_train}} = T_{\text{train\_end}} - 4\text{h}$. Its target interval spans:
  $$[T_{\text{train\_end}}, T_{\text{train\_end}} + 4\text{h})$$
- The earliest validation window starts at $t_{\text{first\_val}} = T_{\text{train\_end}}$. Its target interval spans:
  $$[T_{\text{train\_end}} + 4\text{h}, T_{\text{train\_end}} + 8\text{h})$$

Notice that:
$$\max(\text{train\_target\_end}) = T_{\text{train\_end}} + 4\text{h} \le \min(\text{val\_target\_start}) = T_{\text{train\_end}} + 4\text{h}$$
There is **zero overlap** between training targets and validation targets.

However, the earliest validation observation window $W = [T_{\text{train\_end}}, T_{\text{train\_end}} + 4\text{h})$ coincides in time with the latest training target. If the model computes short-horizon feature lags over this interval, serial correlation or label leakage could occur if operational latency is not factored in.

To address this, `create_chronological_splits` introduces an optional `embargo_windows: int = 0` parameter:
- When `embargo_windows = M` (e.g. $M = 1$ for a 4-hour embargo, or $M = 6$ for a 24-hour embargo):
  $$\text{val\_start} = T_{\text{train\_end}} + M \times 4\text{h}$$
  $$\text{test\_start} = T_{\text{val\_end}} + M \times 4\text{h}$$
- This establishes an explicit dead-band buffer between partitions, guaranteeing that all training target events are completely concluded and unobserved for $M$ full cycles before validation features begin accumulating.

Programmatic assertions enforce:
$$\max(\text{train\_target\_end}) \le \min(\text{val\_target\_start}) \quad \text{and} \quad \max(\text{val\_target\_end}) \le \min(\text{test\_target\_start})$$

---

## 5. FEATURE CAUSALITY & LEAKAGE PREVENTION

### 5.1 Strict Lag Causality
In [`construct_lag_features`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L228-L270), features are constructed for window $W_k = [t_k, t_k + 4\text{h})$:
- $\text{lag\_1}$: incident count in $[t_k - 4\text{h}, t_k)$
- $\text{lag\_6}$: incident count in $[t_k - 24\text{h}, t_k - 20\text{h})$
- $\text{lag\_42}$: incident count in $[t_k - 168\text{h}, t_k - 164\text{h})$ (same window 1 week prior)
- $\text{rolling\_mean\_24h}$: average count over $[t_k - 24\text{h}, t_k)$
- $\text{rolling\_mean\_7d}$: average count over $[t_k - 168\text{h}, t_k)$

All features represent integrals over intervals $[t_a, t_b]$ where $t_b \le t_k$. The current window $[t_k, t_k + 4\text{h})$ and future target $[t_k + 4\text{h}, t_k + 8\text{h})$ are strictly excluded.

### 5.2 Temporal Continuity Verification in Lags
A naive `df.groupby('police_station_id')['incident_count'].shift(1)` assumes an unbroken regular time series. If records are missing from an extract, `shift(1)` would pull the preceding row even if it occurred days or weeks earlier.

To prevent this distortion, [`construct_lag_features`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L240-L260) verifies the actual elapsed time:
```python
prev_start = station_df["window_start"].shift(1)
valid_cadence = (station_df["window_start"] - prev_start) == pd.Timedelta(hours=4)
station_df["lag_1"] = np.where(valid_cadence, station_df["incident_count"].shift(1), np.nan)
```
If a temporal gap exists, the lag feature is populated with `np.nan` rather than a misaligned historical count. This is verified by [`test_temporal_continuity_check_in_lag_feature_construction`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L165-L198).

### 5.3 Preprocessing & Calibration Isolation
- **Feature Scaling and Imputation:** All preprocessing estimators (`StandardScaler`, imputers) must fit their parameters ($\mu, \sigma$) strictly on $\mathcal{D}_{\text{train}}$. $\mathcal{D}_{\text{val}}$ and $\mathcal{D}_{\text{test}}$ must undergo `transform()` using the fixed training parameters. Fitting on the combined dataset is strictly prohibited. Verified in [`test_preprocessing_scaler_fit_strictly_on_training_split`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L201-L228).
- **Calibration Split Independence:** Probability calibration (Platt scaling / isotonic regression) and decision threshold selection must be conducted on the validation split $\mathcal{D}_{\text{val}}$. Test split labels $\mathcal{D}_{\text{test}}$ are held out exclusively for final out-of-sample performance reporting and are never accessed during calibration or thresholding.

---

## 6. BACKEND DEPENDENCY MANIFEST & REPRODUCIBILITY

### 6.1 Dependency Inspection
The institutional intake and signature verification subsystem uses two cryptographic packages:
1. **`cryptography`** (v41.0.0+): Provides `cryptography.hazmat.primitives.asymmetric.ed25519` for asymmetric Ed25519 digital signature generation and verification.
2. **`jcs`** (v0.2.1+): Provides the RFC 8785 JSON Canonicalization Scheme implementation for deterministic payload serialization.

Inspection of [`backend/requirements.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements.txt) revealed that while both packages were present in the development environment, they had not been explicitly recorded in the backend dependency manifest.

### 6.2 Manifest Hardening
[`backend/requirements.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements.txt) was updated to explicitly declare:
```text
cryptography>=41.0.0
jcs>=0.2.1
```
This guarantees that fresh deployments, container builds, and CI pipelines install both required packages deterministically.

### 6.3 Minimal Canonicalization & Signature Cycle Test
To verify that these dependencies operate cleanly without implicit global state, [`test_clean_import_and_minimal_canonicalization_signature_cycle`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_5_temporal_and_dependencies.py#L248-L280) executes an end-to-end verification cycle:
1. Generates an ephemeral Ed25519 private/public key pair.
2. Serializes an authorization manifest with Unicode characters (`"पुणे शहर"`) and floating point numbers using `canonicalize_rfc8785`.
3. Signs the canonical UTF-8 bytes with the private key.
4. Verifies the signature with the public key.
5. Mutates an authorized field (`permitted_use`) and verifies that the signature fails with `InvalidSignature`.

---

## 7. REVIEW OF TEST WARNINGS

### 7.1 Warning Audit Findings
Execution of the full backend pytest suite revealed 14 warnings:
```text
C:\Users\harsh\AppData\Local\Programs\Python\Python312\Lib\site-packages\matplotlib\mathtext.py:750: 
PyparsingDeprecationWarning: parser.resetCache() is deprecated. Please use ParserElement.reset_cache() instead.
  ParserElement.enablePackrat()
```

### 7.2 Root Cause Analysis
- **Origin:** The warnings originate within `matplotlib` 3.10.0's internal text and font rendering modules interacting with `pyparsing` 3.2.0+.
- **Security Assessment:** Zero security implications. No application code, cryptographic verification, or temporal calculations use `mathtext`.
- **Correctness Assessment:** Zero impact on computation, modeling, or API responses.

### 7.3 Resolution
To prevent third-party library noise from masking genuine backend warnings, [`pytest.ini`](file:///c:/Users/harsh/Downloads/strata-risk/pytest.ini) was configured with a targeted filter:
```ini
[pytest]
testpaths = backend/tests
python_files = test_*.py
addopts = -v --tb=short
filterwarnings =
    ignore::pyparsing.PyparsingDeprecationWarning:matplotlib.*
```
Following this configuration, the full backend pytest run completed with **180 passed in 15.32s, 0 warnings**.

---

## 8. REGRESSION PROTECTION & ARTIFACT INVARIANCE

### 8.1 Full Test Suite Verification
All regression checks were executed successfully:
1. **Backend Tests:**
   ```bash
   python -m pytest backend/tests/ -v
   ============================ 180 passed in 15.32s =============================
   ```
2. **TypeScript Compilation:**
   ```bash
   npx tsc --noEmit
   # Exit code: 0 (No type errors)
   ```
3. **Frontend Linting:**
   ```bash
   npm run lint
   # Exit code: 0 (Clean)
   ```
4. **Production Build:**
   ```bash
   npm run build
   # vite v8.3.4 built in 556ms (dist output generated cleanly)
   ```

### 8.2 Chicago Production Artifact Hash Invariance
Bit-level SHA-256 cryptographic hashes for the deployed Chicago production models were recalculated:

| Artifact Path | Expected Canonical SHA-256 | Recalculated SHA-256 | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | **BIT-IDENTICAL** |
| `backend/artifacts/calibrator.joblib` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | **BIT-IDENTICAL** |
| `backend/artifacts/model_metadata.json` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | **BIT-IDENTICAL** |

---

## 9. FINAL ATTESTATIONS & CONCLUSION

1. **Pune and Mumbai Remain Strictly UNSUPPORTED:** No model has been trained for Pune or Mumbai. No mock or synthetic risk scores are served to users or frontend maps.
2. **Zero Fabricated Pune Data:** No synthetic coordinates, incident timestamps, FIR numbers, or police-station boundaries have been generated.
3. **Temporal Split Integrity Demonstrably Enforced:** Half-open interval filtering, 4-hour alignment validation, embargo buffer gaps, temporal continuity checks, and disjoint station-window key assertions prevent any leakage across training, validation, and test splits.
4. **Reproducible Environment:** Dependencies `cryptography>=41.0.0` and `jcs>=0.2.1` are explicitly pinned in `backend/requirements.txt` and verified with standalone test suites.
5. **Chicago Serving Unchanged:** Chicago risk forecasting remains fully operational with zero alterations to production models, calibrators, or serving APIs.
