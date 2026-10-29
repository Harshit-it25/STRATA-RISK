# STRATA RISK — PHASE 3: PUNE DATA QUALITY AUDIT AND FORECASTING FEASIBILITY REPORT
## Methodological Audit, Deduplication Verification, Privacy Assessment, Anti-Leakage Controls, and Baseline Roadmap

**Document Identifier:** `PUNE_DATA_QUALITY_AND_FEASIBILITY_REPORT.md`  
**Author:** Principal ML Systems Engineer & Geospatial Safety Auditor  
**Date:** October 12, 2026  
**Status:** Audit Completed — Pune and Mumbai Remain Strictly UNSUPPORTED  
**Scope:** Phase 3 comprehensive forensic audit of the Pune data ingestion pipeline, deduplication edge cases, DPDPA 2023 privacy safeguards, police-station administrative registry verification, temporal anti-leakage mechanisms, and forecasting feasibility roadmap.

---

## 1. Executive Summary & Audit Verdict

This audit evaluates the newly implemented Pune ingestion engine (`backend/ingestion/pune_ingestion_pipeline.py`) and assesses whether an authorized, real historical incident feed from the Pune City Police Commissionerate would be suitable for a future spatio-temporal crime-risk forecasting model.

### Absolute Safety Guarantees Maintained
1. **Zero Model Training / Live Inference:** No model has been trained, fitted, or enabled for Pune. Both Pune and Mumbai remain registered with `coverage_status: "UNSUPPORTED"` and `is_validated: False` in `backend/config/city_config.py`.
2. **Zero Synthetic Crime Incidents:** No synthetic incident records have been generated or ingested. All pipeline tests operate exclusively on isolated unit test fixtures clearly marked for software schema verification (`fixtures/sample_pune_cctns_fixture.csv`, `fixtures/malformed_pune_cctns_fixture.csv`).
3. **Chicago Production Parity & Artifact Immutability:** The deployed Chicago CatBoost model (`forecaster_catboost.cbm`) and isotonic calibrator (`calibrator.joblib`) remain completely untouched. Their SHA-256 cryptographic hashes match their canonical values identically.
4. **No Cross-City Weight Transfer:** Chicago model weights, spatial centroids, and probability estimators are strictly isolated; zero Chicago parameters can be borrowed by Indian coordinates.

---

## 2. Step 1: Audit of the Existing Implementation (Actual vs. Intended Behavior)

A comprehensive forensic code review was conducted across the codebase:
- `backend/ingestion/pune_ingestion_pipeline.py`
- `backend/services/pune_data_readiness.py`
- `backend/config/city_config.py`
- `backend/pipeline/data_pipeline.py`
- `backend/tests/test_pune_data_ingestion.py`
- `fixtures/sample_pune_cctns_fixture.csv`
- `fixtures/malformed_pune_cctns_fixture.csv`

### Identified Discrepancies and Code Deficiencies Prior to Audit

| Component | Intended Behavior | Actual Code Behavior (Pre-Audit) | Remediated Behavior (Post-Audit) |
| :--- | :--- | :--- | :--- |
| **Deduplication Signature** | Unique 256-bit cryptographic non-PII signature. | SHA-256 hash was truncated to 16 hex characters (`[:16]`, 64 bits), increasing theoretical birthday collision risk on massive datasets. | Upgraded to full 64-hex character (256-bit) SHA-256 hash without truncation. |
| **Deduplication Granularity** | Differentiate incident vs. offence level deduplication. | Deduplication only operated on `(fir_number_hash, station, datetime)`. Multi-offence FIRs sharing timestamps had secondary penal sections dropped. | Added configurable `dedup_mode: "incident"` (default) vs. `"offence"` (preserves distinct `section_code` entries). |
| **Zero FIR Cross-Station Transfers** | Detect repeated FIRs across stations. | Records for same FIR at different stations received distinct hashes and were silently retained without audit notification. | Added `cross_station_repeated_fir_count` and tracked `cross_station_firs` in audit report. |
| **PII Content Scanning** | Scan all incident rows for prohibited citizen data. | Regex scan only evaluated `.head(100)` rows! Row 101 onwards was completely uninspected for text patterns. | Upgraded to vectorized full-dataset scanning across all rows of string/object columns. |
| **PII Pattern Coverage** | Detect all common citizen PII patterns. | Only scanned for 10-digit mobile and 12-digit Aadhaar. Email addresses, PAN cards, and contact numbers were missed. | Added regex detection for Email addresses (`email_pattern`), PAN cards (`pan_pattern`), phone numbers, and Aadhaar across all rows. |
| **Exception Sanitization** | Report PII violations without data leakage. | Potential for raw offending string values to be reported in logs or exception messages. | Strict sanitization: exceptions report column name and pattern type only, never the private matched value. |
| **Police Station Registry** | 33 verified administrative police stations. | `wanowrie` and `wanawadi` were listed as two separate stations. In Pune, they are transliteration variants of the same station. | Documented `wanawadi` as transliteration alias of `wanowrie`; categorized registry into 29 core vs. 4 unverified/bifurcated units. |
| **Temporal Anti-Leakage** | Guarantee $\max(t_{\text{train}}) < \min(t_{\text{val}})$. | Quantile row splitting (`int(n * frac)`) failed if boundary rows shared identical timestamps. | Added `enforce_clean_boundaries` and cross-split FIR duplication detection (`cross_split_fir_leakage_detected`). |

---

## 3. Step 2: Deduplication Audit

### Deduplication Signature Mechanics
The deduplication key is computed as:
$$\text{dedup\_key} = \text{SHA-256}\big(\texttt{fir\_number\_hash} \mathbin{\Vert} \texttt{police\_station\_id\_normalized} \mathbin{\Vert} \texttt{incident\_datetime\_iso} \ [\mathbin{\Vert} \texttt{section\_code}]\big)$$
- **Zero Citizen PII:** Key components are strictly pseudonymized FIR hashes, standardized station slugs, and normalized ISO timestamps. No citizen names, phone numbers, or residential addresses are incorporated.
- **Collision Resistance:** Full 256-bit SHA-256 guarantees zero birthday-paradox hash collisions across billions of records.

### Edge Case Analysis and Test Findings

```
                            DEDUPLICATION EDGE CASES
                            
  Case A: Exact Duplicate Row
  [FIR-01, swargate, 12:00, Sec 379]  ──┐
  [FIR-01, swargate, 12:00, Sec 379]  ──┴──> Retains 1 record (1 dropped as duplicate)
  
  Case B: Zero FIR Cross-Station Transfer
  [FIR-01, shivajinagar, 10:00] (Station A) ──┐
  [FIR-01, swargate, 10:00]      (Station B) ──┴──> Retains 2 records; flags cross_station_repeated_fir
  
  Case C: Amended Occurrence Time
  [FIR-02, kothrud, 10:00] (Initial filing)   ──┐
  [FIR-02, kothrud, 14:30] (Corrected occurrence) ┴> Retains 2 records; flags corrected_timestamp_repeated_fir
  
  Case D: Multi-Offence FIR
  [FIR-03, hadapsar, 15:00, Sec 379 (Theft)] ──┐
  [FIR-03, hadapsar, 15:00, Sec 326 (Hurt)]  ──┴──> Incident mode: retains 1
                                                     Offence mode:  retains 2
```

1. **Idempotence Verified:** Repeated ingestion of identical datasets produces identical deterministic deduplication outputs, row counts, and cryptographic hashes (`test_idempotent_repeated_ingestion`).
2. **Deterministic Duplicate Counts:** Duplicate drops are counted exclusively from identical signature collisions.

---

## 4. Step 3: Privacy Audit (DPDPA 2023 Compliance)

### Privacy Defense Layers
1. **Column-Name Rejection:** Rejects any dataset column matching `PROHIBITED_PII_FIELDS` (`complainant_name`, `victim_name`, `accused_name`, `suspect_name`, `phone_number`, `mobile_no`, `contact_number`, `email_id`, `aadhaar_number`, `pan_number`, `voter_id`, `passport_number`, `residential_address`, `witness_name`, `caste`, `religion`).
2. **Vectorized Content Pattern Scanning:** Scans 100% of rows across all object and string columns for:
   - Indian 10-digit mobile numbers: `\b[6-9]\d{9}\b`
   - Email addresses: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
   - Aadhaar 12-digit patterns: `\b\d{4}\s?\d{4}\s?\d{4}\b`
   - Income Tax PAN cards: `\b[A-Z]{5}[0-9]{4}[A-Z]\b`
3. **Zero Credential / Sensitive Value Leakage:** When a pattern violation is detected, the exception message reports:
   ```
   PIIViolationError: Dataset failed DPDPA 2023 PII audit with 1 violation(s): 
   Phone number pattern detected in column 'place_of_occurrence'
   ```
   The offending citizen's phone number or email is **never included in exception strings, system logs, or audit JSON artifacts**.

### Remaining Privacy Limitations & Mandatory Institutional Safeguards
> [!WARNING]
> **Fundamental Limitation of Automated Anonymization:**
> Regex and column-name checks cannot guarantee zero re-identification risk in unstructured free text.
> 1. **Indirect Identifiers:** Descriptive phrases in `place_of_occurrence` (e.g. *"in front of corporator's residence"*, *"near prominent landmark owner's clinic"*) can re-identify individuals without triggering regex filters.
> 2. **Bilingual Text:** Marathi narratives and mixed Devanagari/English transliterations may conceal names and addresses.
> 3. **Mandatory Institutional Safeguards:** Strata Risk must never ingest raw FIR narratives directly into public environments. Data processing must take place on an on-premise police enclave or an encrypted air-gapped environment under an executed MoU with differential privacy / $k$-anonymity guarantees.

---

## 5. Step 4: Police-Station Registry Verification

### Administrative Reality of Pune Police Commissionerate
Administratively, Pune City Police Commissionerate encompasses 2 Regions, 5 Zones, and ~33 Police Stations. However, historical and municipal realities require distinguishing verified stations from unverified assumptions:

```
+-----------------------------------------------------------------------------------------+
|                         PUNE POLICE STATION REGISTRY AUDIT                              |
+-----------------------------------------------------------------------------------------+
| Verified Core Municipal Stations (29 Stations)                                          |
|   khadki, vishrantwadi, yerwada, vimantal, chandan_nagar, kalyani_nagar, koregaon_park, |
|   bundgarden, shivajinagar, deccan_gymkhana, faraskhana, vishrambaug, khadak, samarth,   |
|   swargate, sahakar_nagar, dattawadi, bharati_vidyapeeth, bibvewadi, kondhwa, wanowrie, |
|   hadapsar, mundhwa, lashkar_cantonment, kothrud, warje_malwadi, uttam_nagar,           |
|   sinhagad_road, chaturshringi                                                          |
+-----------------------------------------------------------------------------------------+
| Unverified / Transliteration Duplicate (1 Station)                                      |
|   wanawadi: Transliteration duplicate of wanowrie. Normalized as alias.                 |
+-----------------------------------------------------------------------------------------+
| Unverified Recent Bifurcations / Suburban Carve-Outs (3 Stations)                       |
|   alankar: Bifurcated from Kothrud. Boundary GIS polygon unconfirmed.                    |
|   pashan:  Carved from Chaturshringi. Boundary GIS polygon unconfirmed.                 |
|   bavdhan: Carved from Hinjewadi/Chaturshringi/Kothrud border. Boundary unconfirmed.    |
+-----------------------------------------------------------------------------------------+
| PCMC Border Boundary Notice                                                             |
|   Hinjewadi, Wakad, Sangvi, Bhosari were transferred to Pimpri-Chinchwad Police (PCMC)  |
|   Commissionerate in August 2018. They MUST NOT be included in Pune City Police data.   |
+-----------------------------------------------------------------------------------------+
```

- **Confirmation Needed:** Ingestion of the official GIS shapefile / GeoJSON boundary layer published by the Office of Commissioner of Police (CoP), Pune or PMC Town Planning Department.

---

## 6. Step 5: Temporal Anti-Leakage Audit

### Strict Chronological Partitioning
The pipeline implements `create_chronological_splits`:
- Enforces $\max(t_{\text{train}}) < \min(t_{\text{val}}) < \min(t_{\text{test}})$.
- `enforce_clean_boundaries: True` shifts partition cutoffs forward or backward so records with identical boundary timestamps are never split across train and val.
- `cross_split_fir_leakage_detected`: Verifies that no FIR ID in the training set also appears in validation or test (`test_cross_split_fir_leakage_detection`).

### Feature-Engineering Anti-Leakage Rules for Spatio-Temporal Models
To maintain zero lookahead bias when building temporal features at time $t$:
1. **Strictly Causal Lags:** All lag features for shift window $t$ must aggregate incident counts strictly from $t - \Delta$ where $\Delta \ge \text{forecast\_horizon}$ (e.g. 4 hours).
2. **Zero In-Shift Aggregation:** Contemporaneous events occurring during shift $t$ cannot enter the input feature vector for predicting risk at shift $t$.
3. **Training-Only Preprocessing:** Global target encodings, historical rate baselines, and empirical priors must be computed **strictly on the training split**. Using full-dataset statistics leaks test distributions.
4. **Timezone Invariance:** India Standard Time (`Asia/Kolkata`, UTC+05:30) does not observe Daylight Saving Time (DST). This eliminates the 1-hour temporal discontinuity artifacts found in US/UK datasets.
5. **Target Prevalence Audit:** Evaluates whether each partition contains adequate positive cases (`target_prevalence["sufficient_test_positives"]`).

---

## 7. Step 6: Data Quality Audit Report (Machine-Readable Schema)

The pipeline produces a comprehensive JSON audit report.

> [!NOTE]
> **Data Quality Statistics Distinction:**
> The statistics below represent the execution on the **software test fixture** (`sample_pune_cctns_fixture.csv`, $N=20$).
> Real authorized Pune data has **not yet been supplied** pending an institutional MoU. Zero synthetic metrics are fabricated.

```json
{
  "city_id": "pune",
  "pipeline_name": "PuneDataIngestionPipeline",
  "audit_timestamp": "2026-10-12T05:30:00Z",
  "source_provenance": {
    "source_name": "sample_pune_cctns_fixture",
    "jurisdiction": "Pune City Police Commissionerate",
    "target_system": "CCTNS",
    "legal_statute": "DPDPA 2023 / BNS 2023 / IPC",
    "pii_compliance_status": "CERTIFIED_NON_PII",
    "data_timezone": "Asia/Kolkata",
    "daylight_saving_observed": false
  },
  "records_summary": {
    "total_records_read": 20,
    "valid_records_retained": 20,
    "total_records_dropped": 0,
    "retention_rate_pct": 100.0
  },
  "drop_reasons_breakdown": {
    "missing_required_fields": 0,
    "invalid_or_missing_timestamp": 0,
    "invalid_or_unmapped_station": 0,
    "duplicate_records": 0
  },
  "deduplication_audit": {
    "dedup_mode": "incident",
    "exact_duplicates_dropped": 0,
    "cross_station_repeated_fir_count": 0,
    "cross_station_firs": [],
    "corrected_timestamp_repeated_fir_count": 0,
    "idempotent_ingestion_verified": true
  },
  "category_distribution": {
    "violent_street_harm": 6,
    "property_harm": 13,
    "public_disorder": 1
  },
  "unmapped_categories_count": 0,
  "station_distribution": {
    "shivajinagar": 1,
    "swargate": 1,
    "kothrud": 1,
    "hadapsar": 1,
    "deccan_gymkhana": 1,
    "chaturshringi": 1,
    "kondhwa": 1,
    "yerwada": 1,
    "khadki": 1,
    "vimantal": 1,
    "koregaon_park": 1,
    "bundgarden": 1,
    "faraskhana": 1,
    "vishrambaug": 1,
    "bibvewadi": 1,
    "wanowrie": 1,
    "sahakar_nagar": 1,
    "dattawadi": 1,
    "sinhagad_road": 1,
    "warje_malwadi": 1
  },
  "stations_represented_count": 20,
  "total_authorized_stations": 33,
  "station_verification_audit": {
    "verified_core_station_records": 20,
    "unverified_or_bifurcated_station_records": 0,
    "unverified_stations_present": []
  },
  "spatial_coverage": {
    "records_with_coordinates": 20,
    "records_missing_coordinates": 0,
    "out_of_bounds_coordinates_count": 0,
    "coordinate_completeness_pct": 100.0
  },
  "temporal_coverage": {
    "earliest_incident": "2023-03-01T08:30:00",
    "latest_incident": "2024-06-08T16:50:00",
    "timespan_days": 465.35
  },
  "operational_readiness": {
    "is_sufficient_for_forecasting": false,
    "minimum_required_records": 500,
    "status": "INSUFFICIENT_VOLUME",
    "active_safety_warning": "Pune remains UNSUPPORTED for live API forecasting. Processed data is strictly sequestered for offline validation. Zero models are trained or enabled."
  }
}
```

---

## 8. Step 7: Forecasting Feasibility & Future Model Baseline Roadmap

### Non-Universal Data Sufficiency Criteria
Data sufficiency cannot be reduced to a single arbitrary threshold (e.g. "1,000 rows"). Sufficiency depends mathematically on:
1. **Event Frequency & Base Rate:** High-frequency property crimes (theft, vehicle theft) require fewer historical months to achieve stable Poisson/Binomial estimation than low-frequency violent crimes (murder, armed dacoity).
2. **Spatial Granularity:** A 33-station administrative partition requires sufficient positive occurrences per station across shift intervals ($33 \times 6 = 198$ unit-shifts per day). If $> 95\%$ of intervals have zero events, high sparsity requires Bayesian shrinkage or hierarchical regularization.
3. **Temporal Depth:** A minimum of 36 continuous months is required to distinguish day-of-week and diurnal cycles from seasonal variations (monsoon vs. festival peaks like Ganeshutsav).
4. **Signal-to-Noise Ratio & Uncertainty:** Adequate positive events are required in the chronological holdout test set to construct narrow empirical confidence intervals via block bootstrap.

### Prerequisites Before Entering Model Training Phase
1. Executed Memorandum of Understanding (MoU) with Pune City Police Commissionerate.
2. Verified non-PII CCTNS extract covering minimum 36 continuous months ($N \ge 15,000$ records).
3. Official GIS shapefile mapping 33 Police Station boundaries and police chowkis.
4. Harmonized IPC-to-BNS penal section mapping for the July 2024 statutory transition.
5. Chronologically separated holdout evaluation split (e.g. 2021–2023 Train, 2024 Holdout Test).

### Mandatory Future Baseline Progression
Before deploying any machine-learning model (such as CatBoost), Strata Risk requires establishing and outperforming three local empirical baselines:

```
+-----------------------------------------------------------------------------------------+
|                         HIERARCHY OF BENCHMARK FORECASTERS                              |
+-----------------------------------------------------------------------------------------+
|                                                                                         |
|  Level 1: Historical Spatial Baseline                                                   |
|  └── Computes empirical crime incidence rate per police station: P(Y=1|station)         |
|  └── Non-temporal, stationary benchmark.                                                |
|                                                                                         |
|  Level 2: Time-Aware Expanding Historical Baseline                                      |
|  └── Computes expanding-window empirical rate strictly prior to forecast time t:        |
|      P(Y=1|station, t) using observations strictly from [t_0, t).                       |
|                                                                                         |
|  Level 3: Cyclical Spatio-Temporal Baseline                                             |
|  └── Incorporates diurnal shift-of-day (4-hour windows) and day-of-week interactions:    |
|      P(Y=1|station, shift_window, day_of_week).                                         |
|                                                                                         |
|  Level 4: CatBoost Spatio-Temporal Classifier with Platt / Isotonic Calibration         |
|  └── Evaluated ONLY after Levels 1–3 are established.                                   |
|  └── Must demonstrate statistically significant improvements in both:                   |
|      - Probability calibration: Brier score, Log loss, ECE.                             |
|      - Operational Hotspot Ranking: Precision@K and Recall@K on holdout shifts.        |
|                                                                                         |
+-----------------------------------------------------------------------------------------+
```

> [!IMPORTANT]
> **Probability Calibration vs. Hotspot Ranking:**
> Superior Brier score does not automatically imply superior top-$k$ hotspot selection. A forecaster can achieve a low Brier score through conservative probabilities near the base rate while failing to prioritize true surge hotspots. Both dimensions must be jointly verified using shift-level bootstrap audits.

---

## 9. Step 8: Tests and Regression Protection

### Full Stack Verification Summary

| Check Suite | Target / Command | Result |
| :--- | :--- | :--- |
| **Backend Test Suite** | `python -m pytest backend/tests/ -v` | **94 PASSED** (66 baseline + 28 Pune ingestion & audit tests) in 15.33s |
| **Deployed Calibrator** | `backend/artifacts/calibrator.joblib` | SHA-256: `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` (**VERIFIED UNCHANGED**) |
| **Deployed Forecaster** | `backend/artifacts/forecaster_catboost.cbm` | SHA-256: `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` (**VERIFIED UNCHANGED**) |
| **TypeScript Typecheck** | `npx tsc --noEmit` | **0 errors** (Exit code 0) |
| **Frontend Linter** | `npm run lint` | **0 errors, 0 warnings** (Exit code 0) |
| **Production Build** | `npm run build` | **Vite build clean** (`dist/` generated cleanly in 678ms) |

---

## 10. Summary of Files Changed, Tests Run, and Next Dependencies

### Files Modified & Created
1. `backend/services/pune_data_readiness.py`:
   - Expanded `PROHIBITED_PII_FIELDS` to include email, contact numbers, PAN, voter ID, and suspect names.
   - Added `PUNE_STATION_VERIFICATION_STATUS` dictionary categorizing the 33 stations into verified core vs. unverified/bifurcated units.
2. `backend/ingestion/pune_ingestion_pipeline.py`:
   - Upgraded deduplication to 256-bit SHA-256 with `dedup_mode` support ("incident" vs "offence").
   - Added Zero FIR cross-station repeated FIR tracking and amended timestamp detection.
   - Upgraded PII detection to vectorized full-dataset scanning across all rows with email, PAN, phone, and Aadhaar patterns.
   - Sanitized exception reporting to eliminate PII leakage.
   - Enhanced `create_chronological_splits` with boundary alignment (`enforce_clean_boundaries`), cross-split FIR leakage detection, and target prevalence auditing.
3. `backend/tests/test_pune_data_ingestion.py`:
   - Expanded from 15 to 28 unit tests covering all deduplication edge cases, privacy scanning, station audits, and anti-leakage splitting.
4. `PUNE_DATA_QUALITY_AND_FEASIBILITY_REPORT.md`:
   - Created this definitive Phase 3 audit and feasibility report.

### Unresolved Risks
1. **Unverified Station Boundaries:** The official GIS polygons for 4 recent bifurcations (`pashan`, `bavdhan`, `alankar`, `wanawadi`) remain unconfirmed without police boundary shapefiles.
2. **Free-Text Geocoding Error:** In real CCTNS FIRs, narrative *Place of Occurrence* descriptions require named entity recognition and fuzzy gazetteer matching, which introduces spatial uncertainty in informal settlements.
3. **Institutional Dependency:** Strata Risk cannot acquire or train on real Pune incident data without an institutional partnership.

### Next Real-World Dependency
Execution of a formal **Memorandum of Understanding (MoU)** with the **Office of the Commissioner of Police (CoP), Pune City**, accompanied by a certified DPDPA 2023 Data Protection Agreement and anonymized CCTNS database export.
