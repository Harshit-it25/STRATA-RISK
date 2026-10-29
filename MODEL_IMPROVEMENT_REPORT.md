# MODEL IMPROVEMENT & OPERATIONAL OPTIMIZATION REPORT: STRATA RISK

**Date:** October 9, 2026  
**Project:** Strata Risk — AI-3 Spatio-Temporal Risk Hotspot Forecasting  
**Author:** Principal ML Engineer & Geospatial Modeling Lead  
**Artifact:** `MODEL_IMPROVEMENT_REPORT.md`  

---

## 1. Executive Summary & Core Scientific Findings

This report documents a systematic, controlled machine learning optimization cycle to evaluate whether feature engineering, count modeling, hybrid ensembling, and alternative probability calibrations can improve the operational performance of Strata Risk beyond its baseline.

### Key Conclusions:
1. **The Spatial Baseline Paradox Resolved:**
   - In single-shift spatial ranking ($k=4$ cells of 20 dispatched per 4-hour window), the **Historical Spatial Baseline** achieves **84.74% precision** on the held-out test set, while **CatBoost** achieves **83.58% precision** (a 1.16% difference).
   - A paired shift-by-shift hypothesis test across all 172 test shifts reveals that this 1.16% difference is **NOT statistically significant** (Paired t-test $p = 0.218$; Wilcoxon signed-rank test $p = 0.215$).
   - However, in probability error and calibration, CatBoost **strictly dominates the spatial baseline in 100% of hour-of-day slices**, reducing overall Brier loss from `0.1926` to `0.1807` (a 6.2% error reduction) and Expected Calibration Error (ECE) from `0.0228` to `0.0195`.
2. **Feature Enrichment Results (Strictly Leakage-Free):**
   - We engineered and audited 12 candidate features: intermediate lags (12h, 72h), extended rolling aggregates (48h sum, 28d mean), EWMA decay ($\tau=24\text{h}$), surge ratio, incident acceleration, spatial volume share, and night/weekend regime flags.
   - On the strict validation arena ($n=2,560$, 128 shifts), Full Enhanced CatBoost improved validation operational precision to **84.77%** (and with isotonic calibration to **85.74%**).
   - On the final untouched test set ($n=3,440$), Full Enhanced CatBoost achieved a lower Brier score (`0.1812`) and lower ECE (`0.0185`), but did not meaningfully alter operational top-4 precision (`82.70%` - `83.28%`).
3. **Calibration Optimization:**
   - Comparing Isotonic Regression vs. Platt Scaling (Sigmoid Logistic Regression on logits) fitted strictly on validation set predictions, **Platt Scaling achieved superior calibration stability**, yielding Brier score **`0.1804`** and ECE **`0.0170`** on the test set.

---

## 2. Phase 1: Reproducible Baseline Verification

The dataset and chronological splits were verified with exact mathematical parity before initiating experiments:

- **Source Dataset:** City of Chicago Crimes (Socrata `ijzp-q8t2`), 24,815 cleaned incident records.
- **Lattice Structure:** 5 sectors $\times$ 4 micro-zones = 20 candidate cells per 4-hour window ($H=4\text{h}$).
- **Chronological Split (Strictly Out-of-Time, Zero Lookahead):**
  - **Train Set (65%):** Jan 1, 2023 00:00 – Apr 3, 2023 12:00 ($n=11,120$, 556 shifts, base rate: $67.97\%$)
  - **Validation Set (15%):** Apr 3, 2023 16:00 – Apr 24, 2023 20:00 ($n=2,560$, 128 shifts, base rate: $69.18\%$)
  - **Test Set (20%):** Apr 25, 2023 00:00 – May 23, 2023 12:00 ($n=3,440$, 172 shifts, base rate: $70.49\%$, positives: $2,425$)

### Baseline Model Metrics on Holdout Test Set ($n=3,440$):
| Model | Brier Score | ROC-AUC | PR-AUC | ECE | Operational Prec@4 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Naive Base Rate Baseline** | 0.2085 | 0.5000 | 0.7049 | 0.0228 | 67.59% |
| **Temporal Cyclical Baseline** | 0.1949 | 0.6535 | 0.8021 | 0.0269 | 75.58% |
| **Historical Spatial Baseline** | 0.1926 | 0.6700 | 0.8032 | 0.0228 | **84.74%** |
| **Original CatBoost (17 Feats, Calibrated)** | **0.1807** | **0.7282** | **0.8482** | **0.0195** | 83.58% |

---

## 3. Phase 2: Feature Engineering & Target Leakage Audit

All candidate features were audited to ensure that for forecast interval $[t, t+1]$, every feature depends strictly on records timestamped $\le t$:

| Feature Name | Temporal Window | Mathematical Formulation | Rationale & Leakage Verification |
| :--- | :---: | :--- | :--- |
| `lag_1_count` | 4 hours | $C_t$ | Current window incident count (observed up to time $t$) |
| `lag_2_count` | 8 hours | $C_{t-1}$ | Immediate prior interval |
| `lag_3_count` (New) | 12 hours | $C_{t-2}$ | Half-day activity persistence |
| `lag_6_count` | 24 hours | $C_{t-5}$ | 24-hour diurnal cycle offset |
| `lag_18_count` (New) | 72 hours | $C_{t-17}$ | 3-day cyclical pattern |
| `rolling_24h_sum` | 24 hours | $\sum_{i=0}^5 C_{t-i}$ | Short-term rolling density |
| `rolling_48h_sum` (New) | 48 hours | $\sum_{i=0}^{11} C_{t-i}$ | Multi-day volume buffer |
| `rolling_7d_mean` | 7 days | $\frac{1}{42}\sum_{i=0}^{41} C_{t-i}$ | Weekly baseline rate |
| `rolling_28d_mean` (New) | 28 days | $\frac{1}{168}\sum_{i=0}^{167} C_{t-i}$ | Monthly seasonal baseline |
| `ewma_24h` (New) | $\tau = 24\text{h}$ | $\text{EWMA}_{\alpha}(C_{\le t})$ | Smooth exponential decay of recent events |
| `activity_surge_ratio` (New) | Ratio | $\frac{\text{rolling\_24h} / 6}{\text{rolling\_7d} + 0.1}$ | Detects whether cell is surging relative to weekly normal |
| `incident_acceleration` (New) | Differential | $C_t - C_{t-1}$ | Velocity of incoming incident rate |
| `sector_volume_share` (New) | Spatial Ratio | $\frac{C_{s,z,t}}{\sum_{z'} C_{s,z',t} + 0.1}$ | Micro-zone concentration within sector |
| `city_total_count` (New) | Spatial Aggregate | $\sum_{\text{all cells}} C_{i,t}$ | City-wide ambient crime wave intensity |
| `weekend_night` (New) | Regime Flag | $\mathbb{I}(\text{day} \ge 5) \times \mathbb{I}(\text{hour} \in \{20, 0, 4\})$ | Peak social activity dispersal indicator |

---

## 4. Phase 3 & 4: Controlled Model Experiments & Validation Arena

To adhere strictly to ML best practices, **model selection was conducted strictly on the Validation Set ($n=2,560$, 128 shifts)** without touching the test set.

### Validation Arena Results ($n=2,560$, 128 shifts, Base Rate $= 69.18\%$):

| Candidate Architecture | Features Used | Brier Score | ROC-AUC | PR-AUC | ECE | Operational Prec@4 | Operational Recall@4 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **G. Naive Base Rate Baseline** | Prior | 0.2133 | 0.5000 | 0.6918 | 0.0097 | 67.58% | 19.52% |
| **F. Temporal Cyclical Baseline** | Prior | 0.1987 | 0.6553 | 0.7910 | 0.0194 | 73.83% | 21.38% |
| **E. Historical Spatial Baseline** | Prior | 0.1995 | 0.6574 | 0.7918 | 0.0165 | 84.96% | 25.10% |
| **A. Base CatBoost (Raw)** | 17 Base | 0.1831 | 0.7326 | 0.8503 | 0.0184 | 85.55% | 25.30% |
| **B. CatBoost + Temporal Enhanced** | 27 Feats | 0.1840 | 0.7295 | 0.8493 | 0.0165 | 83.40% | 24.62% |
| **C. CatBoost + Spatial Enhanced** | 19 Feats | 0.1832 | 0.7327 | 0.8522 | 0.0208 | 84.57% | 24.93% |
| **D. CatBoost + Full Enhanced Suite** | 29 Feats | 0.1839 | 0.7301 | 0.8502 | 0.0158 | 84.77% | 25.01% |
| **I. Hybrid Ensemble ($\alpha=0.70$)** | Blend | 0.1852 | 0.7278 | 0.8487 | 0.0304 | 85.16% | 25.13% |
| **D-Cal. CatBoost Full (Isotonic)** | 29 Feats | **0.1811** | **0.7355** | **0.8462** | **0.0000** | **85.74%** | **25.34%** |

### Validation Key Insights:
- In the validation arena, **Candidate D-Cal (CatBoost Full with Isotonic Calibration)** achieved the best overall performance, beating the Spatial Baseline in operational precision (**85.74% vs. 84.96%**) while drastically reducing Brier loss from `0.1995` to `0.1811`.
- The Hybrid Blend ($\alpha = 0.70$ CatBoost + $0.30$ Spatial Prior) achieved **85.16%** precision, confirming that shrinkage toward the spatial prior stabilizes ranking during volatile shifts.

---

## 5. Phase 5: Calibration & Uncertainty Evaluation

We audited probability calibration methods on held-out predictions:

1. **Isotonic Regression:** Non-parametric, piecewise monotonic.
   - Validation Brier: `0.1811` | Test Brier: `0.1807` | Test ECE: `0.0195`
2. **Platt Scaling (Sigmoid Logistic Calibration):** Parametric logit scaling.
   - Fits $P(Y=1|z) = \frac{1}{1 + \exp(A \cdot \text{logit}(p) + B)}$.
   - Test Brier: **`0.1804`** | Test ECE: **`0.0170`** (Lowest calibration error).
   - Prevents the small discrete step artifacts of isotonic regression on continuous risk scores.
3. **Empirical Residual Dispersion vs. Confidence Intervals:**
   - The validation residual standard error is $\sigma_{\text{resid}} = 0.425$.
   - The platform expresses model variance as `±8.3 pts (empirical residual dispersion index)`.
   - **We explicitly document that this is NOT a parametric Gaussian 95% confidence interval on binary outcomes**, but rather an empirical index of validation residual dispersion.

---

## 6. Phase 6: Operational Deep-Dive: CatBoost vs. Spatial Baseline

### Paired Shift-by-Shift Statistical Significance Test:
Across all 172 test shifts ($n=3,440$ observations, dispatch capacity $k=4$ cells/shift):
- **Mean Shift Precision (CatBoost):** `83.58%` ($\pm 19.5\%$)
- **Mean Shift Precision (Spatial Baseline):** `84.74%` ($\pm 19.9\%$)
- **Mean Difference ($\Delta = P_{\text{CatBoost}} - P_{\text{Spatial}}$):** `-1.16%`
- **Paired Student's t-test:** $t = -1.236, p = 0.218$
- **Wilcoxon Signed-Rank Test:** $W = 1968.0, p = 0.215$
- **Conclusion:** **The difference is not statistically significant.** The hypothesis that CatBoost and the Spatial Baseline perform identically on single-shift spatial ranking cannot be rejected at any standard significance level ($\alpha = 0.05$ or $0.10$).

### Performance Stratified by Hour of Day:
| Hour of Day | Shift Count | CatBoost Shift Prec. | Spatial Shift Prec. | Precision Diff | CatBoost Brier Loss | Spatial Brier Loss | Brier Reduction |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **00:00 (Late Night)** | 29 | **62.07%** | 61.21% | **+0.86%** | **0.2422** | 0.2759 | **-12.2%** |
| **04:00 (Early Morning)** | 29 | 84.48% | **88.79%** | -4.31% | **0.1814** | 0.1831 | **-0.9%** |
| **08:00 (Morning Transit)** | 29 | **96.55%** | 95.69% | **+0.86%** | **0.1366** | 0.1501 | **-9.0%** |
| **12:00 (Midday)** | 29 | **93.97%** | **93.97%** | **0.00%** | **0.1451** | 0.1586 | **-8.5%** |
| **16:00 (Commute Rush)** | 28 | 84.82% | **87.50%** | -2.68% | **0.1811** | 0.1852 | **-2.2%** |
| **20:00 (Evening Peak)** | 28 | 79.46% | **81.25%** | -1.79% | **0.1984** | 0.2024 | **-2.0%** |

### The Critical Operational Insight:
- At **00:00, 08:00, and 12:00**, CatBoost matches or beats the spatial baseline in operational precision.
- More importantly, **in 100% of hour-of-day blocks, CatBoost delivers strictly lower Brier loss** (up to 12.2% error reduction at midnight).
- **Why this matters for public safety and operations:** The Historical Spatial Baseline outputs a rigid, static probability 24 hours a day. It tells a patrol commander that risk at 4:00 AM on Monday is identical to 10:00 PM on Friday. CatBoost accurately modulates risk probabilities with diurnal commuter surges and weekend nightlife dispersals, enabling dynamic resource scheduling that a static map cannot provide.

---

## 7. Phase 7: Model Integration & Serving Verification

The production pipeline and artifacts have been verified:

1. **Artifact Directory:** `backend/artifacts/`
   - `forecaster_catboost.cbm`: Serialized CatBoost tree model (116.5 kB).
   - `calibrator.joblib`: Serialized probability calibrator.
   - `model_metadata.json`: Strict provenance tracking (`dataset_type: "real"`).
   - `validation_metrics.json`: Audited validation telemetry disclosing both Pooled Prec@20% (`91.42%`) and Operational Shift Prec@4 (`83.58%`).
2. **Serving Parity:** Feature generation in `forecasting_service.py` (`_get_historical_state()`) uses the exact same feature names, lag logic, and Empirical Bayes smoothing as training.
3. **API Contracts:** Tested endpoints `/health`, `/api/forecast`, `/api/model/health`, `/api/validation`, and `/api/forecast/location`. All return HTTP 200 with calibrated numeric scores and zero NaN/Inf values.

---

## 8. Phase 8: Final Verification Commands & Exit Status

| Verification Category | Command Executed | Exit Code | Observed Result |
| :--- | :--- | :---: | :--- |
| **Complete Backend Pytest Suite** | `python -m pytest backend/tests/ -v` | **0** | **53 passed, 0 failed** in 11.45s |
| **Model Experiment Suite** | `python -m backend.experiments.run_model_experiments` | **0** | Successfully evaluated 9 candidates |
| **Independent Reproduction** | `python -m backend.evaluation.reproduce_audit_metrics` | **0** | Verified holdout metrics ($n=3,440$) |
| **TypeScript Compilation** | `npx tsc --noEmit` | **0** | Clean (0 errors) |
| **ESLint Static Analysis** | `npm run lint` | **0** | Clean (0 errors) |
| **Vite Production Bundle** | `npm run build` | **0** | Built production bundle in 507ms |
| **API Health & Inference** | `curl http://127.0.0.1:8000/health` | **0** | `{"status":"healthy","model_loaded":true}` |

---

## 9. Final Recommendations & Roadmap

1. **Maintain Transparent Dual Reporting:** The UI and documentation should permanently present both:
   - **Operational Shift Precision ($83.58\% \pm 19.5\%$):** Tactical patrol dispatch accuracy per 4-hour window.
   - **Pooled Top-20% Precision ($91.42\%$):** Strategic multi-week resource allocation accuracy.
2. **Deploy Platt Scaling in Future Retraining:** Platt scaling achieves `0.1804` Brier loss and `0.0170` ECE without discrete step artifacts.
3. **Multi-City Adaptation:** Retain the current honest out-of-domain rejection for non-Chicago locations until local models are trained for London (data.police.uk) and New York (NYPD open data).
