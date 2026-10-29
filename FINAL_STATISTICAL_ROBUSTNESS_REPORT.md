# STRATA RISK — FINAL STATISTICAL ROBUSTNESS REPORT

**Project:** Strata Risk — AI-3 Spatio-Temporal Risk Hotspot Forecasting  
**Author:** Principal ML Systems Engineer & Statistical Verification Lead  
**Date:** October 9, 2026  
**Artifact:** `FINAL_STATISTICAL_ROBUSTNESS_REPORT.md`  
**Scope:** Shift-Level Paired Bootstrap Resampling ($B=5,000$), Log-Loss Convergence Analysis, Evaluation Integrity & Temporal Leakage Audit, Time-Aware Baseline Verification, and Final Artifact Preservation.

---

## 1. Executive Summary

This report delivers the final statistical robustness verification of the Strata Risk forecasting engine. The evaluation was conducted on the frozen holdout test set of **172 four-hour shifts** ($3,440$ spatial cell-shift observations from April 25, 2023 to May 23, 2023) using **paired bootstrap resampling of complete shifts** ($B = 5,000$ replicates, fixed random seed `42`) to honor the temporal cluster structure of the data.

### Primary Verified Findings
1. **Probabilistic Forecast Quality:**
   - CatBoost (both Isotonic and Platt calibrated) achieves **statistically significantly lower Brier score error** than the Historical Spatial Baseline:
     $$\Delta_{\text{Brier}}(\text{Isotonic} - \text{Spatial}) = -0.0119 \quad [95\% \text{ CI: } -0.0158, -0.0079], \quad p < 0.0001$$
     $$\Delta_{\text{Brier}}(\text{Platt} - \text{Spatial}) = -0.0121 \quad [95\% \text{ CI: } -0.0159, -0.0083], \quad p < 0.0001$$
   - CatBoost dynamically adapts to diurnal cycles, weekend interactions, recent lag surges, and weather, delivering strictly superior probability calibration over static geographic persistence.
2. **Operational Shift Ranking (Top-4 Cell Dispatch):**
   - CatBoost **DOES NOT beat the Historical Spatial Baseline for operational shift ranking**:
     $$\text{Precision@4: Spatial } = 84.74\% \quad \text{vs} \quad \text{CatBoost (Isotonic) } = 83.58\% \quad (\Delta = -1.17\%, \ p = 0.2476)$$
     $$\text{Precision@4: Spatial } = 84.74\% \quad \text{vs} \quad \text{CatBoost (Platt) } = 83.72\% \quad (\Delta = -1.03\%, \ p = 0.2164)$$
   - The Historical Spatial Baseline has an observed point estimate that is **higher by $>1.0\%$**.
   - While the paired bootstrap difference is not statistically significant at $\alpha = 0.05$ ($p \approx 0.22 - 0.25$), **a nonsignificant test is NOT proof of equivalence**. In urban crime forecasting, spatial persistence is an exceptionally strong operational dispatch heuristic.
3. **Log-Loss and Calibrator Convergence (Isotonic vs. Platt):**
   - **Brier Score:** $\Delta = +0.00025$ ($95\%$ CI: $[-0.00060, +0.00120]$, $p = 0.5968$). The Brier score difference is **statistically indistinguishable from random noise**.
   - **Log Loss:** $\Delta = +0.02837$ ($95\%$ CI: $[+0.00096, +0.06395]$, $p = 0.0280$). Platt scaling achieves **statistically significantly lower log loss** ($0.5369$ vs $0.5649$). Both the 95% confidence interval (lower bound $> 0$) and the two-sided empirical p-value ($0.0280 < 0.05$) agree that Platt's continuous sigmoid avoids the discretization penalties of step functions near distribution tails.
4. **Artifact Safety Confirmation:**
   - The deployed artifact `backend/artifacts/calibrator.joblib` hash is verified:
     `SHA256: 8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d`
   - It is preserved unchanged as `<class 'sklearn.isotonic.IsotonicRegression'>`. Zero feature engineering, model weights, API contracts, or UI components were altered.

---

## 2. Bootstrap Implementation Verification

Inspection of `backend/experiments/run_bootstrap_audit.py` confirmed strict adherence to statistical best practices:

1. **Replicate Count & Seed Control:**
   All 5,000 bootstrap replicates were generated using `numpy.random.default_rng(42)`. Point estimates and confidence intervals reproduce deterministically.
2. **Cluster Resampling Over Complete Shifts:**
   Resampling was performed on the array of shift indices $s \in \{0, \dots, 171\}$. For each replicate $b$, 172 shifts were drawn with replacement. All 20 micro-cells belonging to a sampled shift were kept strictly intact as a block, preserving within-shift spatial correlation.
3. **Paired Comparison Alignment:**
   In each replicate $b$, the identical sampled shift index vector `b_idx` was passed to all models (`spatial`, `raw`, `iso`, `platt`). Differences were calculated consistently as $\text{Model A} - \text{Model B}$ on the exact same resampled data.
4. **Confidence Intervals and Empirical p-Values:**
   - Confidence intervals were calculated as empirical percentiles at $\alpha/2 = 2.5\%$ and $1 - \alpha/2 = 97.5\%$.
   - Two-sided empirical p-values were calculated as:
     $$p = 2 \times \min\left(\frac{1}{B}\sum_{b=1}^B \mathbb{I}(\Delta_b \le 0), \ \frac{1}{B}\sum_{b=1}^B \mathbb{I}(\Delta_b \ge 0)\right)$$
5. **Zero Test-Label Contamination:**
   Models and calibrators were fitted strictly on `train_df` ($n=11,120$) and `val_df` ($n=2,560$). Holdout test labels ($n=3,440$) were accessed solely to evaluate squared error, log loss, and top-4 selection.

---

## 3. Log-Loss Comparison: Isotonic vs. Platt Scaling

### A. Point Estimate & Confidence Interval Reproduction
- **Observed Test Log Loss:**
  - Platt Scaling: **`0.5369`** (mean across 172 shifts)
  - Isotonic Regression: **`0.5649`** (mean across 172 shifts)
  - Observed Difference ($\text{Isotonic} - \text{Platt}$): **`+0.0280`**
- **Bootstrap Distribution ($B = 5,000$):**
  - Bootstrap Mean Difference: **`+0.02837`**
  - 95% Percentile Confidence Interval: **`[+0.00096, +0.06395]`**
  - Two-Sided Empirical p-Value: **`0.0280`**

### B. Statistical Agreement Between Interval and p-Value
- Both the confidence interval and the empirical p-value are computed from the **identical empirical bootstrap distribution** $\{ \Delta_b \}_{b=1}^{5000}$.
- Across 5,000 replicates, exactly 70 replicates had $\Delta_b \le 0$ ($70 / 5,000 = 1.4\%$).
- Because $1.4\% < 2.5\%$, the null value $\Delta = 0$ lies strictly outside the central $95\%$ percentile interval ($[+0.00096, +0.06395]$).
- Correspondingly, the two-sided p-value is $2 \times 1.4\% = 2.8\% = 0.0280 < 0.05$.
- **Conclusion:** Both methods agree: Platt scaling achieves statistically significantly lower log loss than Isotonic regression at the 5% significance level. This occurs because Isotonic regression flattens probabilities into 11 discrete step values, which imposes high cross-entropy penalties on tail observations where a step probability of $\sim 0.88$ encounters an unexpected negative event ($y=0$), whereas Platt's continuous logistic sigmoid maintains smoother tail gradients.

---

## 4. Metric Definitions & Aggregation Integrity

| Metric | Mathematical Definition | Per-Shift Computation | Holdout Aggregation |
| :--- | :--- | :--- | :--- |
| **Brier Score** | $\frac{1}{K} \sum_{i=1}^K (p_i - y_i)^2$ | Mean squared error across all $K=20$ cells in shift $s$. | Unweighted mean across 172 shifts (equivalent to pooled mean). |
| **Log Loss** | $-\frac{1}{K} \sum_{i=1}^K [y_i \ln(p_i) + (1-y_i) \ln(1-p_i)]$ | Cross-entropy with $p_i \in [10^{-15}, 1 - 10^{-15}]$ across $K=20$ cells. | Unweighted mean across 172 shifts. |
| **Precision@4** | $\frac{1}{4} \sum_{i \in \text{Top-4}} y_i$ | Fraction of the top 4 ranked cells with positive event $y=1$. | Unweighted mean across 172 shifts. |
| **Recall@4** | $\frac{\sum_{i \in \text{Top-4}} y_i}{\sum_{i=1}^K y_i}$ | Fraction of the shift's total positive events captured in top 4. | Mean across shifts with $N_s > 0$. (In our dataset, all 172 shifts had $N_s \ge 1$; no division-by-zero occurred). |

### Eligible Cells & Shift Lattice
- Every shift contains the **exact same 20 eligible spatial cells** (5 sectors $\times$ 4 micro-zones: `('zone-01', 'central')`, `('zone-01', 'east')`, ..., `('zone-12', 'riverside')`).
- Zero shifts have missing, imputed, or filtered cells ($172 \times 20 = 3,440$).

### Tie Handling in Top-Four Selection
- **Spatial Baseline, Raw CatBoost, and Platt Scaling:** Predictions are continuous floating-point numbers with unique values. Zero ties occurred across all 3,440 test instances. Sorting is strictly descending.
- **Isotonic-Calibrated CatBoost:** Isotonic regression maps continuous probabilities into 11 discrete step values. Stable sort (`kind="stable"`) was used to break ties by preserving input lattice row order. Tie-breaking slightly altered top-4 selection in 37 of 172 shifts, with a net Precision@4 difference of only $0.14\%$ vs Platt.

---

## 5. Baseline Fairness & Time-Aware Historical Baseline Evaluation

### A. Training-Period Audit of Historical Spatial Baseline
The production `HistoricalSpatialBaseline` was audited:
- Fitted exclusively on `train_df` ($n=11,120$, Jan 1, 2023 to Apr 3, 2023).
- Fixed empirical cell rates (with Empirical Bayes shrinkage $m=5.0$) computed strictly from historical training incidents.
- Zero temporal leakage: The baseline receives no updates from validation or test observations.
- The baseline's static top 4 cells are:
  1. `('zone-07', 'riverside')`: $0.8439$
  2. `('zone-07', 'east')`: $0.8403$
  3. `('zone-02', 'central')`: $0.8296$
  4. `('zone-12', 'east')`: $0.8171$

### B. Time-Aware Expanding Historical Baseline
To ensure maximum fairness and test whether a time-varying historical baseline changes the ranking benchmark, a **Time-Aware Expanding Historical Baseline** was evaluated offline on the frozen holdout test set using only data available strictly before each forecast shift ($t < \text{shift}$):
$$\hat{p}_{i, t} = \frac{\sum_{\tau < t} \mathbb{I}(\text{count}_{i, \tau} > 0) + 5.0 \cdot \bar{p}}{\tau_t + 5.0}$$

**Results Comparison:**
- **Static Historical Spatial Baseline:** Brier = `0.1926`, Precision@4 = **`84.74%`**, Recall@4 = **`24.38%`**
- **Time-Aware Expanding Spatial Baseline:** Brier = `0.1923`, Precision@4 = **`84.74%`**, Recall@4 = **`24.38%`**

*Finding:* Because Chicago crime distribution exhibits extreme structural geographic stability, the top 4 highest-crime cells remain completely invariant whether using pre-April 3 historical data or dynamically expanding data up to shift $t-1$. In both formulations, the spatial baseline achieves identical operational ranking performance ($84.74\%$).

---

## 6. Comprehensive 5,000-Replicate Bootstrap Matrix

| Model Architecture | Metric | Point Estimate | 95% Bootstrap CI Lower | 95% Bootstrap CI Upper |
| :--- | :--- | :---: | :---: | :---: |
| **Historical Spatial Baseline** | **Brier Score** | 0.1926 | 0.1845 | 0.2009 |
| | **Log Loss** | 0.5701 | 0.5518 | 0.5890 |
| | **Precision@4** | **84.74%** | 81.69% | 87.65% |
| | **Recall@4** | 24.38% | 23.56% | 25.23% |
| **Raw CatBoost (Uncalibrated)** | **Brier Score** | 0.1805 | 0.1725 | 0.1884 |
| | **Log Loss** | 0.5372 | 0.5179 | 0.5563 |
| | **Precision@4** | 83.72% | 80.67% | 86.63% |
| | **Recall@4** | 24.06% | 23.26% | 24.89% |
| **Deployed CatBoost (Isotonic)** | **Brier Score** | **0.1807** | **0.1725** | **0.1888** |
| | **Log Loss** | **0.5649** | **0.5305** | **0.6064** |
| | **Precision@4** | **83.58%** | **80.67%** | **86.34%** |
| | **Recall@4** | **24.05%** | **23.23%** | **24.89%** |
| **CatBoost (Platt Calibrated)** | **Brier Score** | 0.1804 | 0.1723 | 0.1884 |
| | **Log Loss** | 0.5369 | 0.5171 | 0.5563 |
| | **Precision@4** | 83.72% | 80.67% | 86.63% |
| | **Recall@4** | 24.06% | 23.26% | 24.89% |

### Paired Hypothesis Testing Summary

| Paired Model Comparison | Mean Difference | 95% Bootstrap CI Lower | 95% Bootstrap CI Upper | Empirical p-Value (2-sided) | Interpretation |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Brier (Isotonic - Platt)** | $+0.000250$ | $-0.000602$ | $+0.001195$ | **0.5968** | Statistically indistinguishable on Brier loss. |
| **Log Loss (Isotonic - Platt)** | $+0.028370$ | $+0.000957$ | $+0.063948$ | **0.0280** | Platt significantly lower cross-entropy. |
| **Brier (Isotonic - Spatial)** | $-0.011854$ | $-0.015832$ | $-0.007927$ | **< 0.0001** | CatBoost significantly superior probability calibration. |
| **Brier (Platt - Spatial)** | $-0.012105$ | $-0.015887$ | $-0.008347$ | **< 0.0001** | CatBoost significantly superior probability calibration. |
| **Precision@4 (Isotonic - Spatial)** | **$-1.17\%$** | $-3.05\%$ | $+0.58\%$ | **0.2476** | Spatial baseline higher point estimate; CatBoost does not beat baseline. |
| **Precision@4 (Platt - Spatial)** | **$-1.03\%$** | $-2.62\%$ | $+0.44\%$ | **0.2164** | Spatial baseline higher point estimate; CatBoost does not beat baseline. |
| **Recall@4 (Isotonic - Spatial)** | **$-0.33\%$** | $-0.98\%$ | $+0.30\%$ | **0.3084** | CatBoost captures slightly fewer positive events in top 4. |

---

## 7. Critical Interpretations & Defensible Scientific Conclusions

1. **Clear Separation of Probabilistic Quality vs. Operational Ranking:**
   - **Where CatBoost Dominates:** Probability forecasting and diurnal risk estimation. CatBoost achieves a Brier error reduction of $\sim 0.012$ ($p < 0.0001$), providing police planners with accurate, calibrated shift-by-shift incident probabilities.
   - **Where Spatial Baseline Dominates:** Top-4 hotspot ranking. The Historical Spatial Baseline achieves **$84.74\%$** operational precision vs CatBoost's **$83.58\%$** (Isotonic) and **$83.72\%$** (Platt).
2. **Do Not Claim Equivalence or Outperformance:**
   - The paired test on Precision@4 yields $p = 0.2476$. In statistical inference, **failing to reject the null hypothesis of equal means ($p = 0.25$) is NOT evidence of equivalence**.
   - The point estimate favors the simple baseline by $>1.0\%$.
   - **It is false to claim CatBoost outperforms the spatial baseline for operational patrol dispatch.**
3. **Calibrator Selection Decision:**
   - On Brier score, Isotonic and Platt calibration are indistinguishable ($p = 0.5968$).
   - The deployed `sklearn.isotonic.IsotonicRegression` artifact is operating correctly, free of leakage, correctly clamped to $[0.0, 1.0]$, and fully validated across the codebase.
   - In accordance with conservative engineering practices, the deployed artifact is preserved unchanged.

---

## 8. Artifact Verification & Test Suite Execution Matrix

### A. Artifact Hash Verification
The SHA-256 hash of the serialized production calibrator artifact was recomputed directly from disk:
- **File:** `backend/artifacts/calibrator.joblib`
- **SHA256:** `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d`
- **Status:** **UNMODIFIED & PRESERVED**

### B. Automated Regression & Build Matrix

```bash
# 1. Full PyTest Regression Suite
$ python -m pytest backend/tests/ -v
Result: 56 passed, 0 failed in 10.21s (Exit Code 0)

# 2. TypeScript Static Typecheck
$ npx tsc --noEmit
Result: 0 errors (Exit Code 0)

# 3. ESLint Code Quality
$ npm run lint
Result: 0 errors, 0 warnings (Exit Code 0)

# 4. Vite Production Build
$ npm run build
Result: ✓ built in 534ms (Exit Code 0)
```

---

## 9. Remaining Limitations & Honest Boundaries

1. **Spatial Baseline Persistence:** In urban crime data with fixed environmental features (e.g. transit hubs, nightlife corridors), static spatial persistence accounts for the vast majority of dispatch ranking signal.
2. **Shift Granularity:** The evaluation reflects fixed 4-hour non-overlapping windows. Micro-interval dispatching or continuous-time point process modeling could alter temporal dynamics.
3. **Jurisdiction Bound:** All evaluated models and spatial rates are strictly valid only for Chicago. Models cannot be transferred to other metropolitan areas without local data ingestion and calibration.
