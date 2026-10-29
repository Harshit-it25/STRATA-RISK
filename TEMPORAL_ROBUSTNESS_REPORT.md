# STRATA RISK — TEMPORAL-DEPENDENCE SENSITIVITY & ROBUSTNESS REPORT

**Project:** Strata Risk — AI-3 Spatio-Temporal Risk Hotspot Forecasting  
**Author:** Principal ML Systems Engineer & Statistical Verification Lead  
**Date:** October 9, 2026  
**Artifact:** `TEMPORAL_ROBUSTNESS_REPORT.md`  
**Focus:** Moving-Block Bootstrap (MBB) Sensitivity Analysis ($L \in \{1, 3, 6, 12, 18\}$, $B=5,000$), Expanding-Window Historical Baseline Audit, and Temporal Autocorrelation Robustness.

---

## 1. Executive Summary

This investigation evaluates the sensitivity of the Strata Risk statistical audit to temporal autocorrelation and serial dependence in consecutive 4-hour shifts. 

While standard shift-level bootstrap resampling treats 4-hour shifts as independent clusters, urban crime incidents and environmental conditions often exhibit short-to-medium term serial dependence across shifts (e.g., multi-shift weather fronts, weekend crime surges, and diurnal rhythms). 

To test whether temporal dependence alters any audit conclusions, a **Moving-Block Bootstrap (MBB)** (Künsch 1989; Liu & Singh 1992) was implemented and evaluated across five distinct block lengths ($L \in \{1, 3, 6, 12, 18\}$ shifts, spanning 4 hours to 72 hours) with $B = 5,000$ replicates per block length using a fixed random seed (`42`).

### Core Findings & Invariance Confirmation
1. **Zero Conclusions Change Under Temporal Dependence:**
   Across all evaluated block lengths ($L = 1$ shift up to $L = 18$ shifts / 3 days), **every statistical conclusion from the shift-level audit remains invariant**:
   - **Brier Score (CatBoost vs. Spatial Baseline):** Decisively significant ($p < 0.0001$) across all block lengths. CatBoost maintains a Brier error reduction of $\sim 0.012$ regardless of block duration.
   - **Operational Ranking (CatBoost vs. Spatial Baseline):** CatBoost **does not beat the historical spatial baseline** under any block length. The mean difference in Precision@4 remains consistently negative ($\Delta \approx -1.0\%$), and $95\%$ confidence intervals contain zero ($p \in [0.25, 0.30]$).
   - **Brier Score (Isotonic vs. Platt):** The two calibrators remain **statistically indistinguishable** on Brier loss across all block lengths ($p \in [0.60, 0.66]$).
   - **Log Loss (Isotonic vs. Platt):** Platt scaling consistently achieves **statistically significantly lower log loss** across all block lengths ($p \le 0.028$).
2. **Expanding-Window Baseline Invariance:**
   An expanding historical baseline using strictly observations prior to each forecast shift ($t < \text{shift}$) achieves **identically $84.74\%$ Precision@4**, matching the static pre-split baseline. The top 4 geographic crime centers in Chicago remain invariant across time.
3. **Artifact Integrity Preserved:**
   No code, features, or artifacts were modified. The deployed calibrator hash remains verified:
   `SHA256: 8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d`.

---

## 2. Moving-Block Bootstrap (MBB) Methodology

### A. Mathematical Formulation
Given a time series of $T = 172$ consecutive shifts indexed $t \in \{0, 1, \dots, 171\}$:
1. **Overlapping Blocks:** For a chosen block length $L \in \mathbb{N}$, there are $N_B = T - L + 1$ overlapping contiguous blocks:
   $$B_j = \{ j, j+1, \dots, j+L-1 \}, \quad j \in \{0, 1, \dots, T-L\}$$
2. **Chronological Preservation:** Each block $B_j$ preserves the exact chronological order and spatial lattice structure of its $L$ constituent shifts ($L \times 20$ micro-cell observations).
3. **Resampling:** To generate replicate $b \in \{1, \dots, B\}$, we draw $K = \lceil T / L \rceil$ blocks uniformly with replacement from $\{ B_0, \dots, B_{N_B-1} \}$, concatenate them, and truncate the resulting sequence to length $T = 172$.
4. **Paired Alignment:** In each replicate, the identical resampled block sequence is evaluated across all candidate estimators (`spatial`, `expanding_spatial`, `raw`, `iso`, `platt`). Differences are calculated consistently as $\text{Model A} - \text{Model B}$.
5. **Zero Test-Label Contamination:** No model or calibrator was fitted or tuned on holdout test observations.

### B. Block-Length Selection Rationale
Sensitivity was evaluated across five domain-grounded block lengths:
- **$L = 1$ (4 hours):** Standard shift-level cluster benchmark (zero serial block dependence).
- **$L = 3$ (12 hours):** Half-day diurnal phase (captures day vs. night transitions).
- **$L = 6$ (24 hours):** Primary diurnal block (captures full daily cycle of 6 four-hour shifts).
- **$L = 12$ (48 hours):** Multi-day block (captures entire weekend / 2-day weather regimes).
- **$L = 18$ (72 hours):** Multi-day block (captures 3-day structural persistence).

---

## 3. Empirical Sensitivity Matrix Across Block Lengths ($B = 5,000$, Seed: 42)

### Table 1: Paired Difference Sensitivity Across Block Lengths

| Comparison | Block Length $L$ | Duration | Mean Diff | 95% Bootstrap CI Lower | 95% Bootstrap CI Upper | Empirical p-Value (2-sided) | Interpretation |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Brier (Iso - Platt)** | $L=1$ | 4h | $+0.000250$ | $-0.000602$ | $+0.001195$ | **0.5968** | Indistinguishable |
| | $L=3$ | 12h | $+0.000233$ | $-0.000710$ | $+0.001257$ | **0.6552** | Indistinguishable |
| | $L=6$ | 24h | $+0.000280$ | $-0.000752$ | $+0.001370$ | **0.6088** | Indistinguishable |
| | $L=12$ | 48h | $+0.000281$ | $-0.000773$ | $+0.001373$ | **0.6172** | Indistinguishable |
| | $L=18$ | 72h | $+0.000266$ | $-0.000782$ | $+0.001394$ | **0.6364** | Indistinguishable |
| **Log Loss (Iso - Platt)** | $L=1$ | 4h | $+0.028370$ | $+0.000957$ | $+0.063948$ | **0.0280** | Platt significantly lower |
| | $L=3$ | 12h | $+0.028464$ | $+0.001501$ | $+0.062184$ | **0.0216** | Platt significantly lower |
| | $L=6$ | 24h | $+0.029122$ | $+0.002098$ | $+0.062392$ | **0.0120** | Platt significantly lower |
| | $L=12$ | 48h | $+0.029813$ | $+0.003741$ | $+0.060551$ | **0.0052** | Platt significantly lower |
| | $L=18$ | 72h | $+0.031057$ | $+0.008230$ | $+0.056310$ | **0.0052** | Platt significantly lower |
| **Brier (Iso - Spatial)** | $L=1$ | 4h | $-0.011854$ | $-0.015832$ | $-0.007927$ | **< 0.0001** | CatBoost significantly superior |
| | $L=3$ | 12h | $-0.012282$ | $-0.016020$ | $-0.008742$ | **< 0.0001** | CatBoost significantly superior |
| | $L=6$ | 24h | $-0.012444$ | $-0.015753$ | $-0.009056$ | **< 0.0001** | CatBoost significantly superior |
| | $L=12$ | 48h | $-0.012457$ | $-0.015619$ | $-0.009481$ | **< 0.0001** | CatBoost significantly superior |
| | $L=18$ | 72h | $-0.012472$ | $-0.015517$ | $-0.009466$ | **< 0.0001** | CatBoost significantly superior |
| **Prec@4 (Iso - Spatial)** | $L=1$ | 4h | $-1.17\%$ | $-3.05\%$ | $+0.58\%$ | **0.2476** | Spatial higher point estimate |
| | $L=3$ | 12h | $-1.10\%$ | $-2.76\%$ | $+0.58\%$ | **0.2500** | Spatial higher point estimate |
| | $L=6$ | 24h | $-1.05\%$ | $-2.62\%$ | $+0.73\%$ | **0.2676** | Spatial higher point estimate |
| | $L=12$ | 48h | $-0.97\%$ | $-2.47\%$ | $+0.58\%$ | **0.2612** | Spatial higher point estimate |
| | $L=18$ | 72h | $-0.94\%$ | $-2.47\%$ | $+0.59\%$ | **0.2960** | Spatial higher point estimate |
| **Recall@4 (Iso - Spatial)**| $L=1$ | 4h | $-0.33\%$ | $-0.98\%$ | $+0.30\%$ | **0.3084** | Spatial higher point estimate |
| | $L=3$ | 12h | $-0.31\%$ | $-0.90\%$ | $+0.29\%$ | **0.3256** | Spatial higher point estimate |
| | $L=6$ | 24h | $-0.30\%$ | $-0.89\%$ | $+0.34\%$ | **0.3580** | Spatial higher point estimate |
| | $L=12$ | 48h | $-0.28\%$ | $-0.90\%$ | $+0.36\%$ | **0.3692** | Spatial higher point estimate |
| | $L=18$ | 72h | $-0.28\%$ | $-0.92\%$ | $+0.38\%$ | **0.3892** | Spatial higher point estimate |
| **Prec@4 (Platt - Spatial)**| $L=1$ | 4h | $-1.03\%$ | $-2.62\%$ | $+0.44\%$ | **0.2164** | Spatial higher point estimate |
| | $L=3$ | 12h | $-1.04\%$ | $-2.47\%$ | $+0.29\%$ | **0.1676** | Spatial higher point estimate |
| | $L=6$ | 24h | $-1.05\%$ | $-2.33\%$ | $+0.29\%$ | **0.1500** | Spatial higher point estimate |
| | $L=12$ | 48h | $-1.07\%$ | $-2.47\%$ | $+0.15\%$ | **0.1168** | Spatial higher point estimate |
| | $L=18$ | 72h | $-1.12\%$ | $-2.47\%$ | $+0.00\%$ | **0.0788** | Spatial higher point estimate |

---

## 4. Expanding-Window Baseline Formal Verification

### A. Mathematical Formulation & Update Procedure
To audit whether dynamic historical accumulation alters baseline ranking, the **Time-Aware Expanding Historical Baseline** was formalized:

For cell $i \in \{1, \dots, 20\}$ at forecast shift $t$:
$$\hat{p}_{i, t} = \frac{S_{i, t} + m \cdot \bar{p}_0}{N_{i, t} + m}$$
where:
- **Prior ($\bar{p}_0$):** Global event prevalence computed strictly from the training period ($67.97\%$).
- **Smoothing Constant ($m$):** Empirical Bayes shrinkage weight $m = 5.0$.
- **Cumulative Events ($S_{i, t}$):**
  $$S_{i, t} = \sum_{\tau < t} \mathbb{I}(\text{count}_{i, \tau} > 0)$$
- **Cumulative Observation Count ($N_{i, t}$):** Count of shifts prior to $t$ ($N_{i, t} = t$).

### B. Verification of Temporal Strictness & Shared Information
1. **Strictly Preceding Information:** At forecast shift $t$, $S_{i, t}$ and $N_{i, t}$ depend strictly on observations $\tau \in \{0, 1, \dots, t-1\}$. Observations at $\tau \ge t$ are completely excluded.
2. **Shared Information with Training Period:**
   - The cumulative history starts at shift $0$ of the training set (Jan 1, 2023).
   - The prior $\bar{p}_0 = 0.6797$ is fixed using the training set.
3. **Empirical Results:**
   Across all 172 test shifts, the expanding-window baseline achieves:
   - **Brier Score:** `0.1923` (vs. static baseline `0.1926`)
   - **Precision@4:** **`84.74%`** (identical to static baseline `84.74%`)
   - **Recall@4:** **`24.38%`** (identical to static baseline `24.38%`)
   - **Paired Difference ($\text{Expanding} - \text{Static}$):** Exactly $+0.00\%$ across all 5,000 bootstrap replicates ($p = 1.0000$).
   - *Rationale:* The 4 highest-risk cells in Chicago (`('zone-07', 'riverside')`, `('zone-07', 'east')`, `('zone-02', 'central')`, `('zone-12', 'east')`) experience persistent incident occurrences in $>80\%$ of all shifts. Their ranking relative to other cells is structurally cemented; adding new shift observations never reorders the top 4.

---

## 5. Critical Scientific Interpretations & Invariance Proof

### 1. Robustness to Autocorrelation
Moving-block bootstrap resampling accounts for serial autocorrelation up to lag $L-1$.
- As block length increases from $L = 1$ (4h) to $L = 18$ (72h), the confidence intervals widen slightly for some metrics, yet **none of the hypothesis testing boundaries change**.
- CatBoost’s Brier score superiority remains unequivocally established ($p < 0.0001$ across all $L$).
- CatBoost’s lack of operational top-4 ranking superiority remains unequivocally established ($p \in [0.25, 0.30]$ across all $L$).

### 2. Separation of Probabilistic Quality vs. Operational Ranking
- **Probabilistic Forecasting:** CatBoost models non-linear interactions between weather, diurnal commuting schedules, and temporal lags that static spatial heuristics cannot capture. It reduces Brier error by $6.2\%$ over the spatial baseline.
- **Operational Ranking:** If an operational commander’s sole objective is to assign patrol cars to the top 4 locations in Chicago for the next shift, always dispatching to the 4 structural crime hubs yields an observed precision of $84.74\%$. CatBoost's dynamic shifts achieve $83.58\%$.
- **Non-Significance is NOT Equivalence:** The paired difference ($\Delta \approx -1.0\%, p \approx 0.25$) does not reject $H_0: \Delta = 0$, but the empirical point estimate favors the baseline. Claiming that CatBoost outperforms the baseline for operational ranking is factually false.

---

## 6. Artifact Verification & Regression Matrix

### A. Serialized Production Calibrator Hash
Recomputed directly from `backend/artifacts/calibrator.joblib`:
- **SHA256:** `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d`
- **Class:** `<class 'sklearn.isotonic.IsotonicRegression'>`
- **Status:** **UNMODIFIED & PRESERVED**

### B. Automated Regression & Build Matrix

```bash
# 1. Full PyTest Regression Suite
$ python -m pytest backend/tests/ -q
Result: 56 passed in 10.07s (Exit Code 0)

# 2. TypeScript Static Typecheck
$ npx tsc --noEmit
Result: 0 errors (Exit Code 0)

# 3. ESLint Code Quality
$ npm run lint
Result: 0 errors, 0 warnings (Exit Code 0)

# 4. Vite Production Build
$ npm run build
Result: ✓ built in 528ms (Exit Code 0)
```

---

## 7. Remaining Limitations & Honest Boundaries

1. **Stationarity of Crime Hubs:** Chicago's spatial crime distribution displays extreme structural persistence. In such environments, machine learning models adding temporal variance face an uphill battle to outperform static spatial priors on top-$k$ ranking.
2. **Block Length Upper Bound:** At $L=18$, there are $172 - 18 + 1 = 155$ overlapping blocks. Testing blocks larger than $L=24$ (4 days) would reduce effective sample degrees of freedom on a 172-shift test set.
3. **Regional Bound:** These conclusions reflect Chicago Police Department data. Cities with more dynamic or shifting crime patterns may show different relative ranking value between CatBoost and static baselines.
