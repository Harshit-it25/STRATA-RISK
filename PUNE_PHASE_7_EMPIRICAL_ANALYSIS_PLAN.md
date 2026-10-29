# STRATA RISK — PUNE PHASE 7 EMPIRICAL ANALYSIS PLAN (PHASE 7.3)
**Methodological Protocol for Evaluating Data Quality, Reporting Stability, and Forecasting Feasibility upon Authorized Dataset Receipt**

> [!WARNING]
> **METHODOLOGICAL STATUS: PROSPECTIVE PROTOCOL — ZERO REAL DATA ACCESSED**
> This document specifies the exact quantitative analysis protocols to be executed **if and when** an authorized CCTNS dataset is delivered by Pune City Police.
> **No empirical statistics, distributions, or forecasts are generated in this document.**
> Pune remains strictly **UNSUPPORTED** (`NO_DATA` / `STAGE_0_UNAUTHORIZED`).

---

## 1. Executive Protocol Objectives

The purpose of this Empirical Analysis Plan is to establish ground-truth data quality and forecasting feasibility on real municipal incident records before any predictive model training is attempted.

The plan enforces five inviolable principles:
1. **Zero Fictional EDA:** No synthetic incidents, coordinates, timestamps, or recording distributions are fabricated.
2. **Decoupled Evaluation:** Station-level exploratory analysis is evaluated independently from coordinate-level point process modeling.
3. **No Inferred Zeros:** Absence of records in an extract is never interpreted as zero crime without corroborating transmission evidence.
4. **Theoretical vs. Observed Capacity Distinction:** Theoretical spatiotemporal lattice capacity is strictly segregated from observed reporting windows.
5. **Threshold Humility:** Numerical readiness thresholds are treated as provisional policy requirements or operational heuristics, not empirical constants.

---

## 2. Theoretical Capacity Accounting vs. Observed Spatiotemporal Windows

To avoid misleading prevalence calculations, analytical evaluations must explicitly distinguish between theoretical lattice capacity and observed station-windows:

### 2.1 Theoretical Spatiotemporal Capacity
In a regular lattice defined by 33 police station jurisdictions and 6 four-hour operational shifts per day in Indian Standard Time (Asia/Kolkata):
- Daily capacity: $33 \text{ stations} \times 6 \text{ windows/day} = 198 \text{ station-windows/day}$
- Annual capacity (365 days): $198 \times 365 = 72,270 \text{ station-windows/year}$
- Multi-year study capacity (1,095 days / 36 months):
  $$33 \times 6 \times 1,095 = 216,810 \text{ theoretical station-windows}$$

### 2.2 Observed and Verified Capacity
The actual evaluation denominator is strictly limited to verified operational windows:
$$N_{\text{eval}} = \sum_{s=1}^{33} \sum_{w \in W} \mathbb{I}(\text{Station } s \text{ was operational and transmitting during shift } w)$$

Windows where transmission logs are missing or stations were non-operational are quarantined as `UNKNOWN_COVERAGE` or `NOT_OPERATIONAL` ($Y = \text{NaN}$). They are excluded from the target prevalence denominator.

---

## 3. Ten Prospective Empirical Analysis Modules

Upon authorized data receipt, the research team must execute and report the following ten analytical modules:

```
┌────────────────────────────────────────────────────────────────────────┐
│           TEN-MODULE EMPIRICAL EVALUATION PROTOCOL (PHASE 7)           │
├────────────────────────────────┬───────────────────────────────────────┤
│ 1. Temporal Coverage & Gaps    │ 6. Registration-to-Sync Delays        │
│ 2. Station Breadth & Shifts    │ 7. Positive Event Shift Support       │
│ 3. Reporting Completeness      │ 8. Geocoding Completeness & Bias      │
│ 4. Offense Category Audit      │ 9. Statutory Transition Breaks        │
│ 5. Occurrence-to-Reg Delays    │ 10. Representativeness & Uncertainty  │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

### Module 1: Actual Temporal Coverage and Missing Period Detection
- **Objective:** Measure total continuous duration, record volume over time, and detect logging blackouts.
- **Metrics to Compute:**
  - Minimum and maximum observed incident timestamps: $t_{\min}, t_{\max}$.
  - Total elapsed calendar span: $D = (t_{\max} - t_{\min}) \text{ days}$.
  - Weekly and monthly time-series histograms of ingested record volume.
  - Anomaly detection: Flag any multi-day intervals with zero recorded incidents across the entire city ($> 48\text{h}$ citywide void indicates database export truncation).
- **Feasibility Rule:** If $D < 180\text{ days}$, dataset is halted (`INSUFFICIENT_TEMPORAL_COVERAGE`). If $180 \le D < 1,080\text{ days}$, approved for exploratory analysis only; training requires $\ge 1,080\text{ days}$ (36 months).

---

### Module 2: Station Jurisdictional Representation & Bifurcation Audit
- **Objective:** Quantify geographical coverage across all 33 Pune police stations and audit recent administrative reorganizations.
- **Metrics to Compute:**
  - Station presence rate: $\frac{N_{\text{stations present}}}{33} \times 100\%$.
  - Record counts per station (min, median, max, interquartile range).
  - Explicit audit of the 3 recent bifurcations:
    - *Pashan* (bifurcated from Chaturshringi in 2021)
    - *Bavdhan* (bifurcated from Hinjawadi / Kothrud)
    - *Alankar* (bifurcated from Kothrud)
  - Time series of record volume for parent vs bifurcated stations to identify exact historical activation dates.
- **Feasibility Rule:** If station representation $< 80.0\%$ (fewer than 26 stations), gate returns `INSUFFICIENT_SPATIAL_COVERAGE`.

---

### Module 3: Reporting Completeness & Transmission Downtime Analysis
- **Objective:** Audit station transmission logs to distinguish true zero-event shifts from server/network outages.
- **Metrics to Compute:**
  - Station uptime percentage: $\frac{\text{Operational Shifts}}{\text{Total Calendar Shifts}} \times 100\%$ per station.
  - Distribution of missing reporting windows across stations.
  - Correlation between reporting downtime and station geographic location (suburban vs central).
- **Classification Output:** Tabulate station-windows into the 5-state taxonomy:
  1. `VERIFIED_OBSERVED_INCIDENT` ($Y = 1$)
  2. `VERIFIED_OBSERVED_ZERO` ($Y = 0$)
  3. `UNKNOWN_COVERAGE` ($Y = \text{NaN}$)
  4. `INCOMPLETE_EXTRACT` ($Y = \text{NaN}$)
  5. `NOT_OPERATIONAL` ($Y = \text{NaN}$)
- **Feasibility Rule:** Verified reporting coverage must be $\ge 70.0\%$ across the theoretical grid to support baseline evaluation.

---

### Module 4: Incident and Offense-Category Distribution Audit
- **Objective:** Analyze penal section distributions and map them to Strata Risk operational harm tiers.
- **Metrics to Compute:**
  - Breakdown of records across penal codes (IPC and BNS sections).
  - Proportion mapped to Strata Risk operational tiers:
    - Violent Street Harm (Robbery, Murder, Grievous Hurt, Extortion, Chain Snatching)
    - Property Harm (Theft, Burglary, House-breaking by night)
    - Public Order & Miscellaneous Offenses
  - Unmapped penal code frequency (target: $0.0\%$ unmapped for core violent offenses).
- **Feasibility Rule:** If unmapped penal codes exceed $5.0\%$ of total records, statutory cross-walk tables must be updated prior to model feature construction.

---

### Module 5: Occurrence-to-Registration Delay Distributions ($\Delta t_{\text{reporting}}$)
- **Objective:** Quantify human and administrative reporting latency to determine minimum causal forecasting horizons.
- **Metrics to Compute:**
  - Latency metric: $\Delta t_{\text{reporting}} = t_{\text{fir}} - t_{\text{incident}}$.
  - Distribution statistics: Median, 25th percentile, 75th percentile, 90th percentile, 95th percentile, and maximum delay (in hours and days).
  - Sub-analysis by crime category: Violent street crimes vs property crimes vs financial offenses.
  - Anomaly rate: Proportion of inverted timestamps ($t_{\text{fir}} < t_{\text{incident}}$) and future timestamps ($t > t_{\text{current}}$).
- **Feasibility Rule:** If 90th-percentile reporting delay exceeds 48 hours for violent street crime, operational forecasting horizons must be adjusted to account for delayed observation.

---

### Module 6: Registration-to-System-Entry Delays ($\Delta t_{\text{sync}}$)
- **Objective:** Quantify database synchronization latency between police station general diaries and central CCTNS servers.
- **Metrics to Compute:**
  - Latency metric: $\Delta t_{\text{sync}} = t_{\text{system}} - t_{\text{fir}}$ (where `system_entry_datetime` is provided).
  - Distribution statistics: Median and 90th-percentile sync latency.
  - Evaluation of batch synchronization schedules (e.g. hourly, daily midnight syncs).
- **Feasibility Rule / Constraint:**
  - *If $t_{\text{system}}$ is unrecorded:* Formally document that feature engineering assumes zero synchronization delay ($\Delta t_{\text{sync}} = 0$). Prohibit claiming "exact point-in-time causality."

---

### Module 7: Positive-Event Counts per Station and Four-Hour Shift
- **Objective:** Establish the actual empirical prevalence and sparsity of target offenses across the operational lattice.
- **Metrics to Compute:**
  - Total positive target events ($N_{\text{pos}}$) across the entire study period.
  - Station-year positive rate: $\frac{N_{\text{pos}}}{33 \times (D / 365.25)}$.
  - Positive event rate per operational shift (shifts 0 through 5).
  - Empirical shift distribution: Evaluate nocturnal concentration (Shifts 4 and 5) vs daytime rates.
  - Number of stations with zero positive events across the entire dataset.
- **Methodological Evaluation:**
  - Evaluate the operational heuristic: 100 events across 33 stations over 3 years equates to $\approx 1.01$ events/station-year ($\approx 0.046\%$ of theoretical 4-hour windows).
  - Tabulate positive event support per station to identify severe local sample depletion.
- **Feasibility Rule:** If positive target events $< 20$, gate returns `INSUFFICIENT_TARGET_SUPPORT`. If $< 100$, model training remains blocked.

---

### Module 8: Geographic Completeness & Geocoding Attrition Bias
- **Objective:** Measure coordinate completeness and audit for socio-spatial selection bias before attempting micro-spatial modeling.
- **Metrics to Compute:**
  - Coordinate validity rate: $\frac{N_{\text{valid WGS84}}}{N_{\text{total}}} \times 100\%$.
  - Bound compliance rate within Pune box ($18.350 \le \text{lat} \le 18.700$, $73.650 \le \text{lon} \le 74.100$).
  - Coordinate completeness by individual police station (identify stations with $< 50\%$ coordinates).
  - Missingness test: Test whether coordinate missingness is Missing Completely at Random (MCAR) or correlated with offense severity or station location.
- **Feasibility Rule:** If coordinate completeness $< 90.0\%$, coordinate-level micro-spatial modeling is disqualified; station-level aggregate modeling remains eligible.

---

### Module 9: Potential Recording-Practice Changes & Statutory Transition Breaks
- **Objective:** Test for structural breaks caused by the July 1, 2024 IPC-to-BNS statutory transition or administrative reporting shifts.
- **Metrics to Compute:**
  - Pre-transition vs post-transition incident logging rates (Chow test or interrupted time-series regression).
  - Audit section code transitions: Verify that IPC 302 / BNS 103, IPC 392 / BNS 309, and IPC 379 / BNS 303 map to identical operational harm categories.
  - Test for recording artifacts: Investigate sudden spikes or drops coinciding with Commissionerate leadership transitions or municipal election enforcement drives.
- **Feasibility Rule:** Any identified structural break must be documented with an adjusted baseline or category-specific adjustment factor before longitudinal model fitting.

---

### Module 10: Dataset Representativeness, Effective Sample Size, and Uncertainty Quantification
- **Objective:** Quantify statistical estimation power under temporal autocorrelation and spatial clustering.
- **Metrics to Compute:**
  - Temporal autocorrelation: Autocorrelation function (ACF) of target counts at lags 1 through 42 (1 to 7 days).
  - Spatial autocorrelation: Global Moran's I across station polygons.
  - Effective sample size ($N_{\text{eff}}$): Adjusted sample size accounting for serial dependence.
  - Variance estimation: Moving-block bootstrap confidence intervals for baseline crime rate estimates.
- **Feasibility Output:** Formal declaration of whether observed event volume provides non-degenerate power to train gradient-boosted trees without severe metric instability.

---

## 4. Execution Workflow & Artifact Generation

Upon completing the ten modules, the analysis team will generate:
1. `PUNE_AUTHORIZED_DATA_EXPLORATION_REPORT.md` containing all tables, charts, and empirical distributions.
2. `eda_quality_report.json` containing machine-readable metrics.
3. Updated readiness gate checklist certifying whether the project may advance from `STAGE_2` / `STAGE_3` to `STAGE_4_CONTROLLED_TRAINING_ELIGIBLE`.

Until authorized data is received and audited through this plan, the project remains at Stage 0.
