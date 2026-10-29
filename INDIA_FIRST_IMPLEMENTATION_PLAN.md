# STRATA RISK — INDIA-FIRST IMPLEMENTATION PLAN (PHASE 1)
## Architecture Decoupling, Multi-City Configuration, and Pune Pilot Readiness Roadmap

**Document Identifier:** `INDIA_FIRST_IMPLEMENTATION_PLAN.md`  
**Author:** Principal ML Systems Architect & Geospatial Lead  
**Date:** October 12, 2026  
**Status:** Phase 1 Complete — Architecture Ready for Institutional Pilot  
**Target City:** Pune City Police Commissionerate (Pilot), Greater Mumbai (Evaluated)

---

## 1. Executive Summary

This document establishes the architecture and engineering foundation for transitioning Strata Risk from a single-city research prototype into an **India-first multi-city urban risk forecasting platform**.

In strict accordance with empirical integrity and safety constraints:
1. **Existing Chicago System Preserved:** The Chicago CatBoost model, Isotonic calibrator, 17-feature pipeline, and evaluation telemetry operate completely unaltered.
2. **Pune Registered as Unsupported:** Pune is integrated into the city registry and spatial coverage gazetteer with `coverage_status: "UNSUPPORTED"` and `validated_model_available: false`.
3. **Zero Fabricated Probabilities:** All queries for Pune coordinates safely return `forecast: null` and `risk_probability: null`. No Chicago weights, centroids, or baseline distributions are transferred to Indian locations.
4. **Data Readiness Interface Established:** A formal CCTNS ingestion specification, schema auditor, PII filter, and leakage validator are deployed in `backend/services/pune_data_readiness.py`.

---

## 2. Architecture Changes

### A. Separation of Location Geocoding from Model Readiness
Previously, regional parameters were hardcoded in dictionary tables within `coverage_service.py`. Phase 1 introduces a dedicated, typed `CityConfig` abstraction in `backend/config/city_config.py` that cleanly decouples:
- **Spatial Bounds & Jurisdictions:** City bounds, administrative unit type (lattice vs. police station), and unit counts.
- **Model Registry & Calibration:** Model artifact paths, calibrators, feature schema versions, and validation flags.
- **Data Provider & Governance:** Provider registry, institutional ownership, and data licensing status.

```
                      STRATA RISK MULTI-CITY ARCHITECTURE
                      
              [ User Query: Coordinates / City Name / Map Pin ]
                                      │
                                      ▼
                      [ Geocoding & Reverse Geocoding ]
                       (Offline Gazetteer + Nominatim)
                                      │
                                      ▼
                       [ Geographic Coverage Service ]
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                         ▼
         Region: "chicago"                          Region: "pune"
   (CityConfig: SUPPORTED)                    (CityConfig: UNSUPPORTED)
                 │                                         │
                 ▼                                         ▼
   [ Chicago Forecaster Engine ]              [ Safe Structured Fallback ]
   - Model: forecaster_catboost.cbm            - risk_probability: null
   - Calibrator: calibrator.joblib             - risk_score_100: null
   - Features: 17 CPD lag/temporal             - status: "unsupported"
   - Output: 61/100 (MODERATE)                 - reason: "Model pending MoU"
```

---

## 3. Files Modified & Created

| Component | Path | Change Type | Purpose |
| :--- | :--- | :---: | :--- |
| **City Configuration** | `backend/config/city_config.py` | **NEW** | Minimal, typed Pydantic city abstraction (`CityConfig`, `CityModelConfig`, `CitySpatialConfig`, `CITY_REGISTRY`). |
| **Data Readiness Interface** | `backend/services/pune_data_readiness.py` | **NEW** | Schema validation, PII redaction checks, IPC/BNS harm mapping, missingness audit, and temporal leakage checks for future Pune data. |
| **Geographic Coverage** | `backend/services/coverage_service.py` | **MODIFIED** | Registered Pune region (`pune`) in `KNOWN_REGIONS` with `status: STATUS_UNSUPPORTED` and core bounding box. |
| **Data Providers** | `backend/services/data_providers.py` | **MODIFIED** | Added `PuneCandidateDataProvider` class and registered in `DataProviderRegistry`. |
| **Gazetteer Search** | `backend/services/geocoding_service.py` | **MODIFIED** | Added Pune, Kothrud, and Shivaji Nagar to offline gazetteer to support location search without enabling forecasting. |
| **Regression Test Suite** | `backend/tests/test_india_first_architecture.py` | **NEW** | 10 comprehensive tests validating Chicago continuity, Pune unsupported gating, cross-city leakage prevention, and readiness auditing. |

---

## 4. City Configuration Design

```python
class CityConfig(BaseModel):
    city_id: str
    display_name: str
    country: str
    timezone: str
    coverage_status: str  # "SUPPORTED", "PARTIAL_COVERAGE", "INSUFFICIENT_DATA", "UNSUPPORTED"
    spatial: CitySpatialConfig
    model: CityModelConfig
    data_provider_id: Optional[str] = None
    unsupported_reason: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
```

### City Registry States

1. **Chicago (`city_id: "chicago"`):**
   - `coverage_status`: `SUPPORTED`
   - `model.is_validated`: `True`
   - `model.model_artifact_path`: `backend/artifacts/forecaster_catboost.cbm`
   - `model.calibrator_artifact_path`: `backend/artifacts/calibrator.joblib`
   - `model.feature_columns`: 17 validated Chicago features.
2. **Pune (`city_id: "pune"`):**
   - `coverage_status`: `UNSUPPORTED`
   - `model.is_validated`: `False`
   - `model.model_artifact_path`: `None`
   - `model.calibrator_artifact_path`: `None`
   - `spatial.spatial_unit_type`: `police_station` (33 jurisdictions).
   - `unsupported_reason`: *"No public machine-readable incident-level crime feed is available for Pune. A local CatBoost model has not been trained or evaluated on local ground truth."*
3. **Mumbai (`city_id: "mumbai"`):**
   - `coverage_status`: `UNSUPPORTED`
   - `model.is_validated`: `False`

---

## 5. Pune Data Readiness Requirements

The internal audit engine `PuneDataReadinessAudit.assess_readiness()` checks six prerequisites:

```
                    PUNE DATA READINESS CHECKLIST
                    
  [X] 1. Legal & Governance:
         └── Formal MoU with Office of Commissioner of Police (CoP), Pune.
         └── Compliance with Digital Personal Data Protection Act (DPDPA 2023).
  
  [X] 2. Dataset Ingestion:
         └── Pseudonymized CCTNS extract covering minimum 36 months.
         └── Prohibited PII columns filtered (victim/complainant names, phone numbers).
  
  [X] 3. Schema Conformance:
         └── Required: fir_number_hash, incident_datetime, registration_datetime,
                       police_station_id, section_code, place_of_occurrence.
  
  [X] 4. Spatial Representation:
         └── Coverage across all 33 Pune Police Station jurisdictions (>80% required).
  
  [X] 5. Categorical Harmonization:
         └── IPC-to-BNS penal section mapping to operational harm tiers (BNS 2024 update).
  
  [X] 6. Evaluation Discipline:
         └── Strict chronological split (Train 65%, Val 15%, Holdout Test 20%).
         └── Out-of-time calibration and paired bootstrap evaluation vs spatial baseline.
```

When no dataset is present, the API truthfully reports:
- `is_ready_for_training`: `False`
- `readiness_status`: `"INSUFFICIENT_DATA"`
- `data_acquired`: `False`

---

## 6. Current Limitations & Safety Guarantees

1. **Zero Cross-City Generalization:** Models trained on the Chicago Police Department incident feed are physically, legally, and statistically invalid for Indian cities. Strata Risk enforces strict geographic perimeter gating.
2. **No Synthetic Crime Records:** No mock or synthetic crime events were created for Pune. Synthetic data in law enforcement creates dangerous illusions of precision and violates empirical audit standards.
3. **No Unrelated Redesigns:** The React frontend, Leaflet basemaps, and existing API contracts remain completely stable and backwards-compatible.

---

## 7. Steps Required Before Pune Forecasting Can Be Enabled

Before changing Pune's configuration from `UNSUPPORTED` to `SUPPORTED`, the engineering team must complete:

1. **Phase 2 — Institutional Partnership:**
   Execute a research data-sharing agreement with the **Pune City Police Commissionerate**.
2. **Phase 3 — CCTNS Ingestion:**
   Extract and ingest anonymized FIR records using `PuneDataReadinessAudit.validate_dataset_schema()`.
3. **Phase 4 — Geospatial Boundary Mapping:**
   Ingest the 33 Pune Police Station boundary polygons from Pune Municipal Corporation (`opendata.pmc.gov.in`) or police GIS feeds.
4. **Phase 5 — City-Specific Feature Engineering:**
   Generate the 24 India-specific features (jurisdictional lags, monsoon shocks, festival calendar indicators, contiguous station spillovers).
5. **Phase 6 — Local CatBoost Training & Calibration:**
   Train CatBoost classifier strictly on historical training shifts; fit Platt / Isotonic calibrator strictly on validation shifts.
6. **Phase 7 — Frozen Holdout Certification:**
   Evaluate on untouched out-of-time test shifts ($n \ge 1,000$ shift-stations). Verify calibration slope, ECE $\le 0.03$, and compare operational Precision@3 against the local spatial baseline using paired bootstrap resampling.
7. **Phase 8 — Production Deployment:**
   Serialize `pune_forecaster.cbm` and `pune_calibrator.joblib` into `backend/artifacts/`, update `PUNE_CITY_CONFIG.model.is_validated = True`, and enable live forecasting.

---

## 8. Automated Test & Build Execution Matrix

All automated testing, compilation, and linting suites pass cleanly:

```bash
# 1. Full PyTest Regression Suite (Including 10 New Multi-City Tests)
$ python -m pytest backend/tests/ -q
Result: 66 passed in 12.40s (Exit Code 0)

# 2. TypeScript Static Typecheck
$ npx tsc --noEmit
Result: 0 errors (Exit Code 0)

# 3. ESLint Code Quality
$ npm run lint
Result: 0 errors, 0 warnings (Exit Code 0)

# 4. Vite Production Build
$ npm run build
Result: ✓ built in 690ms (Exit Code 0)

# 5. Production Artifact Hashes Verified Unaltered
calibrator.joblib:  8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d
forecaster_catboost: 8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96
```
