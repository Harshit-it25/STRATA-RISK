# STRATA RISK — PHASE 6.6
## FINAL DEPENDENCY AND TEST-CONFIGURATION CLOSEOUT REPORT

**Date:** 2026-10-12  
**Audit Scope:** Dependency Reproducibility & Lockfile Architecture, Targeted Pytest Warning Scope, Temporal Embargo Observation Accounting & Autocorrelation Limits, Full Regression Suite, and Chicago Production Artifact Invariance.  
**System Status:**
- **Chicago Live Forecasting:** **SUPPORTED & OPERATIONAL** (Bit-identical model, calibrator, and metadata artifacts).
- **Pune Candidate Pilot:** **UNSUPPORTED** (Data acquisition preparation only; zero model trained; zero forecasts served).
- **Mumbai Candidate Pilot:** **UNSUPPORTED** (Zero model trained; zero weights transferred).

---

## 1. EXECUTIVE SUMMARY

Phase 6.6 completes the final dependency, configuration, and statistical closeout tasks identified during the Phase 6.5 audit for the Strata Risk platform. Key achievements include:

1. **Dual Dependency Strategy (Abstract vs. Locked):** Clarified the distinction between abstract dependency specifications and exact pins. [`backend/requirements.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements.txt) specifies abstract lower-bound constraints (`>=`) for resolution flexibility, while [`backend/requirements-lock.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements-lock.txt) specifies exact, bit-for-bit version pins (`==`) for reproducible production deployments and CI pipelines.
2. **Cryptographic Package Verification:** Verified that `jcs` (RFC 8785) and `cryptography` (Ed25519) dependencies are declared consistently across both manifests and verified that minimal canonicalization and digital signature verification cycles succeed out-of-the-box in clean environments.
3. **Targeted Pytest Warning Scoping:** Confirmed that the warning filter in [`pytest.ini`](file:///c:/Users/harsh/Downloads/strata-risk/pytest.ini) strictly targets the known upstream deprecation warning between `matplotlib` (3.10.x) and `pyparsing` (3.2.x+). Verified that internal backend warnings, deprecations, and security alerts remain fully visible and unsuppressed.
4. **Temporal Embargo Mathematical Accounting:** Formally documented the statistical trade-offs of the temporal embargo mechanism:
   - Why `embargo_windows = 0` is the default (preserves all observations in sparse pilot data).
   - When a nonzero embargo ($M > 0$) is warranted (operational reporting latency, multi-step label windows).
   - The exact observation depletion formula: $\Delta N = 2 \times M \times S$ station-windows across train/val and val/test splits.
   - Why non-overlapping target windows eliminate label leakage but **do not eliminate all temporal dependence or autocorrelation**.
5. **Comprehensive Regression Protection:** Executed the complete backend pytest suite (186 passed, 0 warnings), TypeScript compiler check (`npx tsc --noEmit`), linter (`npm run lint`), and production build (`npm run build`). Verified that Chicago production model artifacts remain bit-for-bit identical to canonical SHA-256 baselines.

---

## 2. SECTION 1: DEPENDENCY REPRODUCIBILITY & LOCKFILE STRATEGY

### 2.1 Abstract Constraints vs. Exact Pins
In Python package management, lower-bound requirements (e.g. `cryptography>=41.0.0`) are **abstract minimum-version constraints**, not exact pins. Describing them as "pins" is technically inaccurate. 

To provide both development flexibility and deterministic reproducibility, the backend implements a formal **dual-manifest strategy**:

1. **[`backend/requirements.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements.txt) (Abstract Constraints):**
   Declares minimum supported versions for libraries. Used by library consumers and development environments allowing minor patch updates:
   ```text
   fastapi>=0.100.0
   uvicorn[standard]>=0.22.0
   pydantic>=2.0.0
   pandas>=2.0.0
   numpy>=1.24.0
   scikit-learn>=1.3.0
   catboost>=1.2.0
   shap>=0.42.0
   pytest>=8.0.0
   httpx>=0.27.0
   cryptography>=41.0.0
   jcs>=0.2.1
   ```

2. **[`backend/requirements-lock.txt`](file:///c:/Users/harsh/Downloads/strata-risk/backend/requirements-lock.txt) (Exact Version Pins):**
   Declares exact, verified versions (`==`) installed and tested in the validated environment. Used for container builds, production deployments, and audit verification:
   ```text
   fastapi==0.136.3
   uvicorn==0.48.0
   pydantic==2.10.3
   pandas==2.2.3
   numpy==2.1.3
   scikit-learn==1.5.2
   catboost==1.2.10
   shap==0.51.0
   pytest==9.1.1
   httpx==0.28.1
   cryptography==50.0.0
   jcs==0.2.1
   ```

### 2.2 Installation & Execution Verification
Tests in [`backend/tests/test_phase_6_6_dependency_and_config.py`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_6_dependency_and_config.py) confirm:
- `test_requirements_file_has_abstract_constraints`: Asserts that `requirements.txt` contains lower-bound constraints (`>=`) and zero exact pins (`==`).
- `test_requirements_lock_file_has_exact_pins`: Asserts that `requirements-lock.txt` contains exact pins (`==`) for all 12 dependencies, specifically verifying `cryptography==50.0.0` and `jcs==0.2.1`.
- `test_canonicalization_and_ed25519_execution_in_environment`: Executes an end-to-end cycle of RFC 8785 canonicalization using `jcs`, Ed25519 asymmetric key generation and signing using `cryptography`, signature verification, and tamper detection.

---

## 3. SECTION 2: TEST WARNING REVIEW & CONFIGURATION AUDIT

### 3.1 Warning Inventory & Root Cause Analysis
During pytest execution prior to configuration, 14 warnings were captured when running with `-W default`:
```text
C:\Users\harsh\AppData\Local\Programs\Python\Python312\Lib\site-packages\matplotlib\_fontconfig_pattern.py:64: 
PyparsingDeprecationWarning: 'oneOf' deprecated - use 'one_of'
  prop = Group((name + Suppress("=") + comma_separated(value)) | oneOf(_CONSTANTS))

C:\Users\harsh\AppData\Local\Programs\Python\Python312\Lib\site-packages\matplotlib\_fontconfig_pattern.py:85: 
PyparsingDeprecationWarning: 'parseString' deprecated - use 'parse_string'
  parse = parser.parseString(pattern)

C:\Users\harsh\AppData\Local\Programs\Python\Python312\Lib\site-packages\matplotlib\_fontconfig_pattern.py:89: 
PyparsingDeprecationWarning: 'resetCache' deprecated - use 'reset_cache'
  parser.resetCache()

C:\Users\harsh\AppData\Local\Programs\Python\Python312\Lib\site-packages\matplotlib\_mathtext.py:45: 
PyparsingDeprecationWarning: 'enablePackrat' deprecated - use 'enable_packrat'
  ParserElement.enablePackrat()
```

- **Root Cause:** Third-party upstream incompatibility between `matplotlib` 3.10.0 and `pyparsing` 3.2.0+. `matplotlib` internal modules call older camelCase methods on `pyparsing.ParserElement` that were deprecated in favor of snake_case equivalents.
- **Security Assessment:** Zero security relevance. Font and math rendering in `matplotlib` is completely decoupled from API authentication, authorization manifests, data validation, and modeling.
- **Correctness Assessment:** Zero computational impact. Font parsing executes correctly and produces expected glyph mappings.

### 3.2 Narrow Scoping of the Filter in `pytest.ini`
To avoid masking genuine backend application warnings, the filter in [`pytest.ini`](file:///c:/Users/harsh/Downloads/strata-risk/pytest.ini) was strictly constrained:
```ini
[pytest]
testpaths = backend/tests

# Targeted warning filters:
# Only suppress the known upstream incompatibility between matplotlib (3.10.x)
# and pyparsing (3.2.x+), where matplotlib internal modules (_fontconfig_pattern, _mathtext)
# call deprecated pyparsing camelCase methods ('oneOf', 'parseString', 'resetCache', 'enablePackrat').
# This filter strictly targets:
#   Category: pyparsing.PyparsingDeprecationWarning
#   Module:   matplotlib.*
# No internal backend warnings, deprecations, or security-related warnings are suppressed.
filterwarnings =
    ignore::pyparsing.PyparsingDeprecationWarning:matplotlib.*
```

### 3.3 Disposition Summary
- **Third-Party Upstream Deprecations:** `pyparsing.PyparsingDeprecationWarning` from `matplotlib.*` is **SUPPRESSED** via narrowly targeted filter.
- **Application Warnings:** Standard `DeprecationWarning`, `UserWarning`, `FutureWarning`, and any warnings originating from `backend.*` remain **UNSUPPRESSED and FULLY VISIBLE**.
- **Result:** Complete backend test run produces **0 warnings**.

---

## 4. SECTION 3: TEMPORAL EVALUATION & EMBARGO MATHEMATICAL DOCUMENTATION

### 4.1 Why the Default Embargo is Zero (`embargo_windows = 0`)
In [`PuneFourHourSpatiotemporalPipeline.create_chronological_splits`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L430-L515), the default embargo is set to `0`:
1. **Contiguous Non-Overlapping Windows:** When spatiotemporal windows are strictly half-open $[t, t+4\text{h})$, the latest training window ends at $T_{\text{train\_end}}$, and the earliest validation window begins at $T_{\text{train\_end}}$. The station-window keys are already mathematically disjoint:
   $$\text{Keys}(\text{train}) \cap \text{Keys}(\text{val}) = \emptyset$$
2. **Data Scarcity in Police Pilots:** In early-stage municipal data intakes (e.g. 30 to 90 days), violent and high-harm crime incidents are statistically rare (prevalence typically $< 1.0\%$). Discarding multiple 4-hour windows across all 33 police stations depletes the limited positive target observations ($Y = 1$), increasing evaluation variance and reducing statistical power.
3. **Contiguous Timeline Integrity:** Defaulting to zero allows the pipeline to evaluate continuous backtesting performance across the complete historical timeline without arbitrary gaps.

### 4.2 When a Nonzero Embargo is Warranted
Setting `embargo_windows = M` ($M > 0$) is appropriate under specific operational and methodological conditions:
1. **Operational Reporting Latency:** In real-world police operations, FIRs recorded at time $t$ often take 12 to 24 hours to be entered, reviewed, and finalized in the CCTNS database. If a validation forecast is evaluated at $T_{\text{train\_end}}$, assuming that incidents occurring up to $T_{\text{train\_end}} - 1\text{min}$ are already indexed into feature lags creates an unrealistic operational lookahead bias. An embargo matching the operational reporting delay (e.g. $M = 6$ windows = 24 hours) enforces operational fidelity.
2. **Multi-Horizon Target Accumulation:** If the forecasting target is defined over an extended multi-step horizon (e.g. predicting the next 24 hours $[t, t+24\text{h})$ rather than the immediate 4 hours $[t, t+4\text{h})$), consecutive windows overlap in target coverage. An embargo equal to the horizon length ($M \ge \text{horizon}$) is mathematically required to prevent target-to-target overlap.
3. **Transient Shock Spillover:** When a major localized disruption (e.g. a bandh, festival riot, or major raid) spans across the partition boundary, an embargo prevents validation metrics from being dominated by transient short-term shocks originating in the training period.

### 4.3 Observation Depletion Accounting
When an embargo of $M$ four-hour windows is applied:
- The validation start time is shifted forward: $T_{\text{val\_start}} = T_{\text{train\_end}} + M \times 4\text{h}$.
- The test start time is shifted forward: $T_{\text{test\_start}} = T_{\text{val\_end}} + M \times 4\text{h}$.

The total number of station-windows excluded from evaluation across both split boundaries is:
$$\Delta N_{\text{dropped}} = 2 \times M \times S$$
where $S$ is the number of police stations ($S = 33$ for Pune City Police Commissionerate).

| Embargo Parameter ($M$) | Duration per Boundary | Station-Windows Dropped per Boundary | Total Station-Windows Dropped ($2 \times M \times 33$) | Equivalent Station-Days Lost |
| :--- | :--- | :--- | :--- | :--- |
| **$M = 0$ (Default)** | 0 hours | 0 | **0** | 0.0 days |
| **$M = 1$** | 4 hours | 33 | **66** | 0.33 days |
| **$M = 2$** | 8 hours | 66 | **132** | 0.67 days |
| **$M = 6$** | 24 hours (1 day) | 198 | **396** | 2.00 days |
| **$M = 12$** | 48 hours (2 days) | 396 | **792** | 4.00 days |

Tested and verified in [`test_embargo_nonzero_observation_accounting`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_6_6_dependency_and_config.py#L170-L212).

### 4.4 Why Non-Overlapping Windows Do Not Eliminate All Autocorrelation
It is a common methodological misconception to believe that creating disjoint split boundaries or inserting an embargo buffer "eliminates autocorrelation."

**Mathematical Reality:**
1. **Disjoint Labels $\ne$ Independent Processes:** Disjoint station-window keys ensure that no observation $(s, t)$ is reused across partitions. However, crime occurrence is a non-stationary spatiotemporal point process governed by latent environmental, social, and structural factors:
   $$\mathbb{E}[Y_{s, t} \mid Y_{s, t-k}] \ne \mathbb{E}[Y_{s, t}]$$
2. **Long-Memory Persistence:** Spatiotemporal crime rates exhibit multi-scale persistence:
   - Diurnal cycles ($k = 6$ windows / 24 hours).
   - Weekly cycles ($k = 42$ windows / 7 days).
   - Seasonal and weather-induced trends (monsoon vs. winter months).
   - Spatial hot-spot stability (infrastructure, commercial hubs, transit terminals).
3. **What Embargo Actually Achieves:** An embargo of $M$ windows dampens short-horizon serial correlation of order $k \le M$ across the split boundary. It prevents the model from exploiting immediate 1-step persistence.
4. **What Embargo Does Not Achieve:** An embargo **does not eliminate** long-term seasonality, macro trends, spatial cross-correlation, or structural shifts. Evaluation protocols must employ block bootstrap confidence intervals or time-series rolling origin cross-validation rather than relying on an embargo alone to assume independence.

---

## 5. SECTION 4: REGRESSION PROTECTION & ARTIFACT INVARIANCE

### 5.1 Test Suite & Build Verification
The complete test and build pipeline executed successfully:
1. **Backend Tests:**
   ```bash
   python -m pytest backend/tests/ -v
   ============================ 186 passed in 15.54s =============================
   ```
2. **TypeScript Compilation:**
   ```bash
   npx tsc --noEmit
   # Exit code: 0 (Clean)
   ```
3. **Frontend Linting:**
   ```bash
   npm run lint
   # Exit code: 0 (Clean)
   ```
4. **Production Build:**
   ```bash
   npm run build
   # vite v8.3.4 built in 551ms (dist output generated cleanly)
   ```

### 5.2 Chicago Production Artifact Hash Invariance
Recalculated SHA-256 cryptographic hashes for the deployed Chicago production models confirm 100% bit-level preservation:

| Artifact Path | Expected Canonical SHA-256 | Recalculated SHA-256 | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | **BIT-IDENTICAL** |
| `backend/artifacts/calibrator.joblib` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | **BIT-IDENTICAL** |
| `backend/artifacts/model_metadata.json` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | **BIT-IDENTICAL** |

---

## 6. SECTION 5: UNRESOLVED ISSUES & FUTURE RECOMMENDATIONS

1. **Third-Party Upstream Deprecation:** The `PyparsingDeprecationWarning` in `matplotlib` 3.10.0 will be resolved when upstream `matplotlib` releases a patch replacing deprecated camelCase methods (`oneOf`, `parseString`, `resetCache`, `enablePackrat`) with snake_case alternatives. Once updated upstream, the filter in `pytest.ini` can be safely removed.
2. **Pune and Mumbai Authorization Status:** Both Pune and Mumbai remain strictly `UNSUPPORTED`. The data acquisition architecture is complete, cryptographically verified, and fully audited. Real data intake remains blocked until an authorized institutional dataset with a valid Ed25519 signature is received from the Pune City Police Commissionerate.

---

## 7. FINAL ATTESTATIONS

1. **Pune and Mumbai Remain Strictly UNSUPPORTED:** No model has been trained for Pune or Mumbai. No mock or synthetic risk scores are served to users or frontend maps.
2. **Zero Fabricated Pune Data:** No synthetic coordinates, incident timestamps, FIR numbers, or police-station boundaries have been generated.
3. **Chicago Serving Unchanged:** Chicago risk forecasting remains fully operational with zero alterations to production models, calibrators, or serving APIs.
4. **Reproducible Environment:** Dependencies are documented in abstract form (`requirements.txt`) and exact frozen form (`requirements-lock.txt`), verified with end-to-end cryptographic and temporal tests.
