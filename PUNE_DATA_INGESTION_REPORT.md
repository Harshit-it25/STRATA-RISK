# STRATA RISK — PHASE 2: PUNE DATA ACQUISITION & INGESTION REPORT
## Auditable Ingestion Engine, Source Provenance, Anti-Leakage Controls, and Data Quality Verification

**Document Identifier:** `PUNE_DATA_INGESTION_REPORT.md`  
**Author:** Principal ML Systems Engineer & Geospatial Data Pipeline Architect  
**Date:** October 12, 2026  
**Status:** Ingestion Pipeline Validated — City Remains UNSUPPORTED  
**Scope:** Phase 2 data acquisition, validation, normalization, anti-leakage splitting, and test verification for a future Pune City forecasting model.

---

## 1. Executive Summary

In Phase 2 of the India-First Architecture migration, Strata Risk has implemented a dedicated, auditable **Pune Data Ingestion Pipeline** (`backend/ingestion/pune_ingestion_pipeline.py`) engineered to process historical incident logs from the Pune City Police Commissionerate while strictly upholding empirical integrity.

### Core Architecture & Safety Principles
1. **Zero Synthetic Records:** No synthetic incident records have been generated or ingested for production use. Only explicit, isolated test fixtures (`fixtures/sample_pune_cctns_fixture.csv`, `fixtures/malformed_pune_cctns_fixture.csv`) are utilized for pipeline software unit tests.
2. **Zero Model Training / Live Inference:** No Pune forecasting model has been trained, fitted, or deployed. Pune remains explicitly registered as `UNSUPPORTED` in `CITY_REGISTRY` (`backend/config/city_config.py`).
3. **Chicago Production Isolation:** The Chicago CatBoost forecasting engine (`forecaster_catboost.cbm`, SHA-256: `8a9ff0ec...`) and isotonic calibrator (`calibrator.joblib`, SHA-256: `8646328a...`) remain 100% frozen, validated, and unaffected. Zero cross-city weights are transferred.
4. **Zero Silent Imputation:** Missing coordinates, incident timestamps, or police station identifiers are never silently synthesized or defaulted.
5. **Strict PII Protection (DPDPA 2023):** Citizen personal information (victim names, complainant names, phone numbers, Aadhaar numbers, residential addresses) triggers immediate pipeline rejection (`PIIViolationError`).
6. **Chronological Anti-Leakage:** Split functions enforce $\max(t_{\text{train}}) < \min(t_{\text{val}}) < \min(t_{\text{test}})$, preventing temporal lookahead.

---

## 2. Data Source Discovery & Forensic Verification

Official open data repositories, state law enforcement portals, and municipal registries were inspected to assess actual data availability for Pune City.

```
                    PUNE DATA PROVENANCE & ACCESS TOPOLOGY
                    
  National / State Repository (NCRB / Maharashtra CCTNS)
  ├── citizen.mahapolice.gov.in: Single FIR lookup (90-day rolling window)
  ├── SC Mandate (Youth Bar Association, 2016): Masks sensitive offenses (POCSO, rape)
  └── Format: Scanned Marathi/English PDFs with citizen PII; bulk export prohibited
  
  City Administration (Pune City Police Commissionerate: punepolice.gov.in)
  ├── Jurisdiction: 33 Police Stations across 2 Regions and 5 Zones (~331 km²)
  ├── Internal System: CCTNS backend & "My Safe Pune" patrol logging
  └── Public Availability: Press releases and annual totals only; bulk machine-readable feed NON-PUBLIC
  
  Municipal Open Data (Pune Municipal Corporation: opendata.pmc.gov.in)
  ├── Focus: Civic infrastructure (solid waste, road networks, ward boundaries, water)
  └── Incident Data: Zero crime or police incident records published
```

### Forensic Data Attributes Table

| Dimension | Pune Police Reality | Ingestion Requirement | Strata Risk Ingestion Handling |
| :--- | :--- | :--- | :--- |
| **Source & Provenance** | Office of Commissioner of Police (CoP), Pune / Maharashtra CCTNS. | Formal institutional Memorandum of Understanding (MoU) with Data Protection Annexure. | Logged in `audit_report["source_provenance"]`. Dataset rejected without valid provenance. |
| **License & Permitted Use** | Government Official Copyright; restricted internal state records. | Authorized research/operational data-sharing license under DPDPA 2023. | Enforces non-PII verification; tracks legal statute (`DPDPA 2023 / BNS 2023`). |
| **Available Fields** | Pseudonymized FIR ID, Police Station Name, Incident Date/Time, Filing Date/Time, Section Code, Place of Occurrence. | Mandatory: `fir_number_hash`, `police_station_id`, `incident_datetime`, `section_code`. | Schema validated via `validate_schema()`; rejects datasets missing mandatory fields. |
| **Temporal Coverage** | Registration timestamp exact to minute; incident occurrence often estimated or interval-based. | Continuous 36+ months required for seasonal and shift-level baseline estimation. | Normalizes to ISO 8601 (`Asia/Kolkata`); drops invalid timestamps; tracks duration. |
| **Geographic Granularity** | 33 standardized Police Stations; text place descriptions; sporadic GPS. | Standardized police station jurisdictional mapping; validated coordinate bounds. | Rejects unmapped stations; normalizes aliases; validates coords within $(18.35-18.70^\circ\text{N}, 73.65-74.10^\circ\text{E})$. |
| **Missingness & Limitations** | Coordinates frequently missing in older records; FIR narratives require NLP geocoding. | Explicit handling; zero silent fabrication of coordinates or times. | Coordinates set to NaN if missing or out-of-bounds; completeness tracked in audit report. |

> [!IMPORTANT]
> **Data Portal Reality Check:** Neither `punepolice.gov.in` nor `opendata.pmc.gov.in` provides a downloadable, public, incident-level crime CSV/JSON. Claims of "freely available Pune crime data" are false. Production modeling requires an executed institutional MoU with the Pune City Police Commissionerate.

---

## 3. Ingestion Pipeline Architecture (`backend/ingestion/pune_ingestion_pipeline.py`)

The pipeline implements an end-to-end cleaning, normalization, auditing, and splitting engine:

```
+-----------------------------------------------------------------------------------+
|                        PUNE DATA INGESTION PIPELINE FLOW                          |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  Raw CCTNS Extract                                                                |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 1: PII Audit (DPDPA 2023)]                                                 |
|  ├── Check column names against PROHIBITED_PII_FIELDS                             |
|  └── Regex scan string columns for 10-digit mobile & 12-digit Aadhaar patterns    |
|         ├── [Violation] ──> Raise PIIViolationError                               |
|         └── [Compliant] ──> Proceed                                               |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 2: Schema Validation]                                                      |
|  └── Verify mandatory fields: fir_number_hash, police_station_id,                  |
|       incident_datetime, section_code                                             |
|         ├── [Missing Column] ──> Raise SchemaValidationError                      |
|         └── [Valid Schema] ──> Proceed                                            |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 3: Timestamp Normalization & Drop Auditing]                                |
|  ├── Parse incident_datetime via pd.to_datetime                                   |
|  └── Nulls / Blanks / Unparseables dropped & counted                              |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 4: Police Station Jurisdictional Validation]                               |
|  ├── Strip suffixes ("Police Station", "PS", etc.)                                |
|  ├── Match against 33 Pune Police Stations + alias dictionary                     |
|  └── Unmapped / Foreign stations dropped (NO silent default mapping!)            |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 5: Non-PII Cryptographic Deduplication]                                    |
|  ├── SHA-256(fir_number_hash | police_station_id | incident_datetime_iso)[:16]    |
|  └── Drop duplicate hashes; count duplicate records                               |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 6: IPC / BNS Harm Tier Cross-Walk]                                        |
|  ├── Map penal sections to: violent_street_harm, property_harm, public_disorder   |
|  └── Fallback unmapped sections to: other_cognizable                              |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 7: Geographic Coordinate Validation]                                       |
|  ├── Bounds check: Lat (18.350, 18.700), Lon (73.650, 74.100)                     |
|  ├── Out-of-bounds coords reset to NaN & counted                                  |
|  └── Missing coords preserved as NaN (NO silent coordinate synthesis!)             |
|         │                                                                         |
|         ▼                                                                         |
|  [Step 8: Audit Report & Sequestered Output Generation]                           |
|  └── Emits Cleaned DataFrame + Detailed JSON Audit Report                         |
|                                                                                   |
+-----------------------------------------------------------------------------------+
```

### Jurisdictional Police Stations (33 Units)
The 33 official police stations of the Pune City Police Commissionerate are enforced:
- `khadki`, `vishrantwadi`, `yerwada`, `vimantal`, `chandan_nagar`, `kalyani_nagar`, `koregaon_park`, `bundgarden`, `shivajinagar`, `deccan_gymkhana`
- `faraskhana`, `vishrambaug`, `khadak`, `samarth`, `swargate`, `sahakar_nagar`, `dattawadi`, `bharati_vidyapeeth`, `bibvewadi`, `kondhwa`
- `wanowrie`, `hadapsar`, `mundhwa`, `wanawadi`, `lashkar_cantonment`, `kothrud`, `warje_malwadi`, `alankar`, `uttam_nagar`, `sinhagad_road`
- `chaturshringi`, `pashan`, `bavdhan`

### IPC / BNS Operational Harm Cross-Walk
Penal sections are normalized into four operational tiers:
- **`violent_street_harm`:** IPC 302/307 (Murder/Attempt), IPC 392/397 (Robbery), IPC 384 (Extortion), IPC 326 (Grievous Hurt) $\rightarrow$ BNS 103, 109, 309, 311, 308, 117.
- **`property_harm`:** IPC 379/380 (Theft/Dwelling Theft), IPC 457 (Night House-breaking) $\rightarrow$ BNS 303, 305, 331.
- **`public_disorder`:** IPC 147/148 (Rioting/Armed Rioting) $\rightarrow$ BNS 191, 192.
- **`other_cognizable`:** Other IPC/BNS sections or non-fatal/non-street complaints.

---

## 4. Leakage Prevention & Anti-Lookahead Guarantee

To eliminate temporal data leakage:
1. **Chronological Splitting (`create_chronological_splits`):**
   - Observations are ordered strictly by normalized incident occurrence timestamp.
   - Partitions: Training ($65\%$), Validation ($15\%$), Holdout Test ($20\%$).
   - Rigorous non-overlap assertion:
     $$\max(t_{\text{train}}) < \min(t_{\text{val}}) \quad \text{and} \quad \max(t_{\text{val}}) < \min(t_{\text{test}})$$
   - If timestamps span across a split boundary, the pipeline detects temporal overlap and flags leakage.
2. **Strict Causal Feature Generation ($t < \text{forecast}$):**
   - Feature engineering for shift window $t$ can only aggregate incident counts strictly from $t - \Delta$ where $\Delta > 0$.
   - Zero lookahead bias: contemporaneous shift records are never included in lag feature calculation.
3. **Quarantine of Test Labels:**
   - Test labels are never used to select features, fit calibrators (isotonic or Platt), or tune hyper-parameters.

---

## 5. Verification Test Suite Results

A comprehensive unit test suite was implemented in `backend/tests/test_pune_data_ingestion.py` covering all 8 specified test dimensions:

| Test ID | Test Function | Verified Behavior | Status |
| :--- | :--- | :--- | :--- |
| **T1** | `test_valid_cctns_fixture_ingestion_and_audit` | Full 20-record fixture ingestion, 100% retention, complete audit metadata generation | **PASSED** |
| **T2** | `test_missing_mandatory_schema_columns` | Raises `SchemaValidationError` when required columns are absent | **PASSED** |
| **T3** | `test_non_pii_deduplication` | Deduplicates records on SHA-256 non-PII hash; drops exact duplicate while retaining valid separate incidents | **PASSED** |
| **T4** | `test_missing_and_invalid_timestamps_handling` | Cleanly drops missing, null, or malformed timestamps; increments drop reason breakdown | **PASSED** |
| **T5** | `test_invalid_police_station_rejection` | Rejects out-of-jurisdiction stations (Chicago, unknown); zero silent default assignment | **PASSED** |
| **T6** | `test_police_station_alias_normalization` | Normalizes aliases ("deccan", "chaturshrungi", "cantonment", "warje malwadi ps") to canonical IDs | **PASSED** |
| **T7** | `test_prohibited_pii_columns_rejection` | Detects citizen PII columns (`victim_name`, `phone_number`, `aadhaar_number`) and raises `PIIViolationError` | **PASSED** |
| **T8** | `test_prohibited_pii_value_detection` | Detects embedded phone numbers in free-text fields under DPDPA 2023 | **PASSED** |
| **T9** | `test_category_mapping_ipc_bns` | Maps IPC sections to harm tiers; falls back gracefully to `other_cognizable` for unmapped codes | **PASSED** |
| **T10** | `test_chronological_splits_zero_leakage` | Verifies $\max(t_{\text{train}}) < \min(t_{\text{val}}) < \min(t_{\text{test}})$ on ordered incident time series | **PASSED** |
| **T11** | `test_chronological_split_detects_leakage` | Detects overlapping boundary timestamps and reports `temporal_leakage_detected: True` | **PASSED** |
| **T12** | `test_empty_dataset_rejection` | Rejects empty DataFrame (0 records) with `InsufficientDataError` | **PASSED** |
| **T13** | `test_insufficient_volume_flagging` | Flags datasets with $< 500$ records as `INSUFFICIENT_VOLUME` with active safety warning | **PASSED** |
| **T14** | `test_coordinate_handling_zero_imputation` | Preserves missing coords as NaN; resets out-of-bounds coords to NaN; never invents coordinates | **PASSED** |
| **T15** | `test_malformed_fixture_pipeline_run` | Processes malformed fixture, cleanly dropping duplicate, invalid station, and invalid date | **PASSED** |

---

## 6. End-to-End System Verification

All components were executed across the entire stack:

```
[System Verification Results]
1. Backend Tests:
   Command: python -m pytest backend/tests/ -v
   Result: 81 PASSED in 12.75s (66 baseline tests + 15 Pune ingestion tests)

2. Production Model Artifacts:
   calibrator.joblib SHA-256: 8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d (VERIFIED)
   forecaster_catboost.cbm SHA-256: 8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96 (VERIFIED)

3. Frontend TypeScript Compilation:
   Command: npx tsc --noEmit
   Result: 0 errors (Exit code: 0)

4. Frontend Code Linting:
   Command: npm run lint
   Result: 0 warnings, 0 errors (Exit code: 0)

5. Frontend Production Bundle Build:
   Command: npm run build
   Result: Vite build successful (dist/index.html, dist/assets/index-ag61WDRr.css, dist/assets/index-D9WieoB_.js)
```

---

## 7. Limitations & Next Steps

### Current Operational Status
- **Pune Coverage Status:** Remains `UNSUPPORTED`.
- **API Response:** Queries for Pune coordinates safely return `status: "unsupported"`, `forecast: None`, `model: None`, and explicit limitations.
- **Model Training:** Zero models have been trained or deployed for Pune.

### Required Prerequisites for Phase 3 (Pune Model Training & Calibration)
1. **Institutional Agreement:** Finalize and execute a formal MoU with the Pune City Police Commissionerate.
2. **Authorized CCTNS Extract:** Acquire minimum 36 months of pseudonymized incident records ($N \ge 10,000$) verified free of citizen PII.
3. **GIS Boundary Ingestion:** Ingest official GIS polygon boundaries for the 33 Pune Police Station jurisdictions and municipal chowkis.
4. **Offline Model Exploration:** Train a localized CatBoost model on Pune historical data using strict chronological splits (e.g. 2021–2023 train, 2024 holdout test).
5. **Independent Calibration Audit:** Evaluate Brier score, ECE, log loss, and Precision@K on holdout test shifts before enabling live API predictions.
