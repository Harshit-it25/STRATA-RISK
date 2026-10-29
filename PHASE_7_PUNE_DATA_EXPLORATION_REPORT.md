# STRATA RISK — PHASE 7
## AUTHORIZED PUNE DATA EXPLORATION AND FORECASTING FEASIBILITY REPORT

**Date:** 2026-10-12  
**Audit Scope:** Real-Data Verification, Authorization Gate Evaluation, Reporting Coverage Semantics, Reporting Delay Methodology, Exploratory Data Analysis Feasibility, Full Regression Suite, and Chicago Artifact Invariance.  
**System Status:**
- **Chicago Live Forecasting:** **SUPPORTED & OPERATIONAL** (Bit-identical model, calibrator, and metadata artifacts).
- **Pune Candidate Pilot:** **UNSUPPORTED** (Data acquisition preparation only; zero model trained; zero forecasts served).
- **Mumbai Candidate Pilot:** **UNSUPPORTED** (Zero model trained; zero weights transferred).

---

## 1. EXECUTIVE SUMMARY

Phase 7 transitions the project from architectural preparation to empirical evaluation of an authorized Pune incident dataset. The governing principle of this phase is empirical honesty: establishing actual data quality and forecasting feasibility without fabricating incidents, timestamps, coordinates, crime labels, reporting coverage, or police-station boundaries.

### Core Findings & Current Readiness State
1. **Intake Status: `NO_DATA` / `STAGE_0_UNAUTHORIZED`:** Inspection of approved storage locations (`data/`, `data/raw/`, `fixtures/`) confirmed that **no authorized production Pune incident dataset exists on disk**.
2. **Zero Fabrication Policy Strictly Enforced:** In accordance with Phase 7 requirements, zero synthetic incidents, coordinates, timestamps, or station distributions were generated. Test fixtures (`fixtures/sample_pune_cctns_fixture.csv`) are strictly segregated for unit testing and are **not** treated as real observations.
3. **Empirical Sections Left Explicitly Unmeasured:** Because no authorized dataset has been provisioned, all empirical data metrics (records per month, station event counts, reporting delay distributions, and positive target frequencies) are recorded as **UNMEASURED (AWAITING AUTHORIZED INTAKE)**. Phase 7 empirical analysis cannot and will not be claimed as complete until authentic data is delivered.
4. **Institutional Dependencies Documented:** The precise bilateral, statutory, cryptographic, and geographic prerequisites necessary to unlock Stage 1 (Authorization Verified) and Stage 2 (Station-Level EDA) are formally articulated.
5. **Full Regression Protection Maintained:** All 191 backend tests pass with 0 warnings, TypeScript compiles cleanly (`npx tsc --noEmit`), linting passes (`npm run lint`), production build succeeds (`npm run build`), and Chicago production artifacts remain 100% bit-identical to canonical SHA-256 baselines.

---

## 2. SECTION 1: AUDIT OF APPROVED INPUT LOCATIONS & AUTHORIZATION WORKFLOW

### 2.1 Inspection of Data Locations
All repository data paths were audited for candidate incident files:

| Storage Location | Contents Discovered | Classification | Audit Disposition |
| :--- | :--- | :--- | :--- |
| `data/` | `processed_chicago_crimes.csv`, `processed_real_incident_records.csv` | Chicago historical crime data (City of Chicago Data Portal) | Proxy data for Chicago baseline serving; zero Indian crime records. |
| `data/raw/` | `chicago_crimes_2023-01-01_2023-12-31_5dist_25000.csv` | Raw Chicago incident feed archive | Verified Chicago historical records. |
| `fixtures/` | `sample_pune_cctns_fixture.csv`, `malformed_pune_cctns_fixture.csv` | Unit test fixtures (20 mock rows with explicit header disclaimer) | Strictly restricted to unit testing; blocked from production intake. |
| `backend/config/` | `pune_revocations.json` | Authoritative Certificate Revocation List (CRL v1.0, 0 revocations) | Operational security config; no incident records. |

### 2.2 Execution of the Hardened Readiness Gate
Executing the automated intake CLI [`scripts/run_pune_eda.py`](file:///c:/Users/harsh/Downloads/strata-risk/scripts/run_pune_eda.py) without an external path yielded:

```text
================================================================================
STRATA RISK — PUNE DATA READINESS & EXPLORATORY ANALYSIS
================================================================================
STATUS: NO_DATA
Notice: No dataset path supplied.
Default behavior: Emitting NO_DATA evaluation.
Active Safety: Pune remains strictly UNSUPPORTED for forecasting.
================================================================================
```

The programmatic evaluation returned:
- `gate_status`: **`NO_DATA`**
- `readiness_status`: **`NO_DATA`**
- `is_ready_for_eda`: **`False`**
- `is_ready_for_station_level_eda`: **`False`**
- `is_ready_for_coordinate_level_eda`: **`False`**
- `is_ready_for_training`: **`False`** (Hard-locked)
- `is_ready_for_deployment`: **`False`** (Hard-locked)
- `current_lifecycle_stage`: **`STAGE_0_UNAUTHORIZED`**

### 2.3 Strict Rejection of Test Fixtures as Real Observations
[`fixtures/sample_pune_cctns_fixture.csv`](file:///c:/Users/harsh/Downloads/strata-risk/fixtures/sample_pune_cctns_fixture.csv) carries an explicit notice:
```text
# [TEST FIXTURE: SAMPLE PSEUDONYMIZED PUNE CCTNS SCHEMA - FOR INGESTION UNIT TESTING ONLY]
# [DO NOT USE FOR MODEL TRAINING OR RISK INFERENCE - NO SYNTHETIC INCIDENTS PERMITTED IN PRODUCTION]
```
Regression test [`test_test_fixtures_strictly_blocked_from_production_intake`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_7_data_exploration.py#L66-L92) verified that submitting this fixture in production intake mode (`is_fixture=False`) without an authorized Ed25519 manifest fails closed immediately with `AUTHORIZATION_MISSING`.

### 2.4 Precise Institutional Dependencies Required to Unlock Intake
Transition from `STAGE_0_UNAUTHORIZED` to `STAGE_1_AUTHORIZATION_VERIFIED` requires:
1. **Institutional Agreement:** Formally executed Memorandum of Understanding (MoU) with the Office of the Commissioner of Police, Pune City, containing a binding Data Protection Annexure under the Digital Personal Data Protection Act (DPDPA), 2023.
2. **Asymmetric Key Exchange:** Receipt of an authorized public key (`pune_city_police_cop.pub`) and verification of the corresponding private signing key retained securely by the Commissionerate.
3. **Signed Authorization Manifest:** Delivery of an RFC 8785 canonicalized manifest (`dataset.auth.json`) containing an authentic Ed25519 signature binding the SHA-256 fingerprint of the raw dataset.
4. **CCTNS Database Export:** Longitudinal extract covering at least 36 months of incident records across the standardized 33 police station jurisdictions.
5. **Official GIS Shapefiles:** High-resolution boundary polygon shapefiles from Pune Police / Pune Municipal Corporation (PMC) covering all 33 station jurisdictions, specifically including recently bifurcated precincts (*Pashan*, *Bavdhan*, *Alankar*).

---

## 3. SECTION 2: REPORTING COVERAGE AUDIT

### 3.1 Five-State Observation Coverage Taxonomy
Strata Risk enforces a formal 5-state observation coverage taxonomy to prevent statistical distortion:

| State | Definition | Mathematical Interpretation | Target Label ($Y$) |
| :--- | :--- | :--- | :--- |
| **`VERIFIED_OBSERVED_INCIDENT`** | Station was actively reporting and $\ge 1$ target incident was recorded. | True positive observation. | $Y = 1$ |
| **`VERIFIED_OBSERVED_ZERO`** | Station was actively reporting and 0 target incidents were recorded. | True negative observation. | $Y = 0$ |
| **`UNKNOWN_COVERAGE`** | Station reporting status cannot be verified from institutional metadata. | Censored / missing observation. | $Y = \text{NaN}$ |
| **`INCOMPLETE_EXTRACT`** | Station reported for only a fraction of the 4-hour window (e.g. system outage). | Partially observed. | $Y = \text{NaN}$ |
| **`NOT_OPERATIONAL`** | Station was closed, merged, or not yet commissioned during window. | Structurally out-of-scope. | $Y = \text{NaN}$ |

### 3.2 Strict Rule Against Zero-Inference
A fundamental flaw in naive crime forecasting pipelines is inferring zero incidents ($Y = 0$) whenever a station has no rows in an incident export. In municipal policing:
- System network outages, shift changeover backlogs, or incomplete database exports produce windows with zero records.
- Treating these unobserved periods as $Y = 0$ artificially inflates model specificity, degrades probability calibration, and creates severe suburban and socio-economic biases.

Under [`test_empty_incident_extract_does_not_infer_zero_events`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_7_data_exploration.py#L97-L130), passing an empty incident extract to [`PuneFourHourSpatiotemporalPipeline.aggregate_incidents`](file:///c:/Users/harsh/Downloads/strata-risk/backend/pipeline/pune_spatiotemporal_pipeline.py#L209-L375) produces:
- `verified_reporting_station_windows = 0`
- `VERIFIED_OBSERVED_ZERO = 0`
- `UNKNOWN_COVERAGE = 396` (for all 33 stations)
- All target binary values: **`NaN`**

### 3.3 Empirical Coverage Status: UNMEASURED
Because no authorized real dataset has been provisioned:
- Station operational reporting calendars are **UNMEASURED**.
- Verified zero vs. unknown coverage proportions are **UNMEASURED**.
- Reporting uptime distributions across the 33 precincts are **UNMEASURED**.

---

## 4. SECTION 3: REPORTING DELAYS & POINT-IN-TIME FEATURE AUDIT

### 4.1 Reporting Latency Anatomy
To ensure operational realism, the intake contract defines three sequential timestamps:
1. **$t_{\text{incident}}$ (`incident_datetime`):** Estimated time of incident occurrence.
2. **$t_{\text{fir}}$ (`registration_datetime`):** Formal time of FIR registration at the police station.
3. **$t_{\text{system}}$ (`system_entry_datetime`):** Time the record became indexed and queryable in CCTNS.

The operational reporting delay is defined as:
$$\Delta t_{\text{delay}} = t_{\text{system}} - t_{\text{incident}}$$

### 4.2 Point-in-Time Feature Construction vs. Split Embargo
A critical distinction established during Phase 6.6 and verified in Phase 7:
- **Split Embargo ($M$ Windows):** An embargo holds out a buffer gap between training, validation, and test partition boundaries (e.g. 24 hours). This prevents cross-split boundary leakage from serial correlation.
- **Point-in-Time Feature Filtering:** An embargo **does not substitute** for point-in-time feature construction. At any prediction timestamp $t$:
  $$\mathcal{D}_{\text{available}}(t) = \{ i \mid t_{\text{system}, i} \le t \}$$
  If an incident occurred at $t - 1\text{h}$ but was only registered in CCTNS at $t + 6\text{h}$, including that incident in lag or rolling features at time $t$ constitutes catastrophic lookahead leakage, regardless of whether a split embargo exists.

Regression test [`test_point_in_time_registration_delay_filtering`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_7_data_exploration.py#L135-L170) verifies that when registration timestamps are present, unregistered incidents are excluded from historical predictor sets.

### 4.3 Empirical Delay Distribution Status: UNMEASURED
Because no authorized dataset exists:
- Median and 95th percentile FIR registration delays are **UNMEASURED**.
- Distribution of missing registration timestamps is **UNMEASURED**.
- Point-in-time latency bounds remain **UNMEASURED**.

---

## 5. SECTION 4: AGGREGATE EXPLORATORY DATA ANALYSIS (EDA)

In compliance with the Phase 7 directive ("*If no authorized real dataset is available, record NO_DATA, explain the blocker, and leave empirical sections explicitly unmeasured*"), all empirical EDA sections remain explicitly unmeasured:

| Analysis Domain | Empirical Status | Required Real-Data Evidence |
| :--- | :--- | :--- |
| **Actual Date Range & Duration** | **UNMEASURED** | Minimum 180 days for station-level EDA (36 months required for longitudinal models). |
| **Temporal Continuity & Gap Analysis** | **UNMEASURED** | Analysis of missing 4-hour intervals ($\Delta t > 4\text{h}$) across the 33 station grids. |
| **Monthly Incident Volume** | **UNMEASURED** | Month-by-month record counts to evaluate seasonal stability and volume sufficiency. |
| **Precinct Volume Distribution** | **UNMEASURED** | Breakdown of incident counts across the 33 standardized Pune police stations. |
| **IPC / BNS Offense Distribution** | **UNMEASURED** | Breakdown across violent street harm, property harm, public disorder, and other cognizable offenses. |
| **July 1, 2024 Statutory Transition** | **UNMEASURED** | Verification of section-code cross-walk from Indian Penal Code to Bharatiya Nyaya Sanhita. |
| **Field Missingness & Null Ratios** | **UNMEASURED** | Audit of null rates in section codes, place descriptions, and coordinates. |
| **Deduplication & Amendment Rates** | **UNMEASURED** | Frequency of repeated FIR hashes across stations or amended incident timestamps. |
| **Geographic Coordinate Completeness** | **UNMEASURED** | Proportion of records with valid coordinates within Pune bounding box ($[18.35, 18.70]^\circ\text{N}, [73.65, 74.10]^\circ\text{E}$). |
| **Positive Support per 4-Hour Window** | **UNMEASURED** | Frequency of $Y=1$ events across the 6 daily operational shifts. |

---

## 6. SECTION 5: FORECASTING FEASIBILITY ASSESSMENT

### 6.1 Feasibility Evaluation Framework
Forecasting feasibility cannot be determined from total record volume alone. Feasibility requires evaluating multiple interacting dimensions:

1. **Temporal Coverage:** Are there sufficient continuous observations to learn diurnal cycles (24h) and weekly rhythms (7d) without confounding seasonal shifts? (Minimum 180 days for pilot EDA; 36 months for production modeling).
2. **Spatial Representativeness:** Are all 33 police station jurisdictions represented, or is the extract biased toward a few central stations (e.g. *Shivajinagar*, *Faraskhana*, *Swargate*) while suburban precincts (*Bavdhan*, *Pashan*, *Warje Malwadi*) are absent?
3. **Class Imbalance & Support:** At a 4-hour station-window resolution (198 station-windows per day across 33 stations), violent street crime is an extreme low-prevalence event ($< 0.5\%$). Without verified reporting coverage to distinguish true zeros from non-reporting, models risk severe probability collapse.
4. **Point-in-Time Latency:** If FIR registration delay regularly exceeds 8 to 12 hours, a 4-hour ahead forecasting task cannot rely on short-horizon lag features ($\text{lag\_1}$).
5. **Statutory Continuity:** The July 1, 2024 transition to BNS creates semantic drift in section codes that must be harmonized before training.

### 6.2 Formal Feasibility Determination: BLOCKED & INDETERMINATE
- **Feasibility Verdict:** **INDETERMINATE (BLOCKED AT STAGE 0)**.
- **Model Training Status:** **STRICTLY PROHIBITED**. Zero models have been trained or initialized for Pune.
- **Serving Status:** Pune remains strictly **`UNSUPPORTED`**.

---

## 7. SECTION 6: REGRESSION PROTECTION & ARTIFACT INVARIANCE

### 7.1 Test Suite & Build Verification
The complete test and verification suite was executed:
1. **Backend Tests:**
   ```bash
   python -m pytest backend/tests/ -v
   ============================ 191 passed in 14.87s =============================
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
   # vite v8.3.4 built in 542ms (dist output generated cleanly)
   ```

### 7.2 Chicago Production Artifact Hash Invariance
Bit-level SHA-256 cryptographic hashes for the deployed Chicago production models were recalculated:

| Artifact Path | Expected Canonical SHA-256 | Recalculated SHA-256 | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | **BIT-IDENTICAL** |
| `backend/artifacts/calibrator.joblib` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | **BIT-IDENTICAL** |
| `backend/artifacts/model_metadata.json` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | **BIT-IDENTICAL** |

---

## 8. FINAL ATTESTATIONS

1. **Pune and Mumbai Remain Strictly UNSUPPORTED:** No Pune model has been trained. No numerical or mock risk scores are served to users or frontend maps for Pune or Mumbai.
2. **Zero Fabricated Incident Data:** No synthetic incidents, timestamps, coordinates, or station distributions were generated or exposed.
3. **No Fixture Contamination:** Test fixtures remain strictly segregated for unit testing.
4. **Empirical Honesty Maintained:** In the absence of an authorized production dataset, all empirical metrics remain explicitly **UNMEASURED**.
5. **Chicago Serving Unchanged:** Chicago live forecasting remains 100% operational with bit-identical models, calibrators, and serving logic.
