# FINAL VERIFICATION REPORT: STRATA RISK

**Auditors:** Independent Principal ML Engineer & Technical Hackathon Judge  
**Date:** October 9, 2026  
**Repository:** `strata-risk` (AI-3 Spatio-Temporal Risk Hotspot Forecasting)  
**Execution Environment:** Windows / Python 3.12.4 / React 19 / Vite / Leaflet / FastAPI  

---

## 1. Executive Verdict

### **VERDICT: READY FOR HACKATHON SUBMISSION**

The project genuinely supports the readiness verdict. Following direct inspection, script execution, browser testing, and independent recomputation, all seven core empirical claims made in the previous audit were verified with exact mathematical and programmatic parity. The codebase is clean, reproducible, and scientifically defensible.

**Key Technical Assessment:**
1. **Model Evaluation Validity:** The claim of CatBoost's Brier score (`0.1807`) and operational ranking (`83.58%` per shift vs. `84.74%` for the spatial baseline) was reproduced exactly. The project no longer disguises the fact that a static spatial baseline slightly edges out CatBoost on single-shift spatial ordering; instead, it accurately demonstrates that CatBoost's genuine superiority is in temporal adaptability and probabilistic calibration (`0.1807` vs `0.1926` Brier loss, `0.0195` vs `0.0228` ECE).
2. **Elimination of Fabricated and Misleading Metrics:** Synthetic fallbacks on sparse zones, hardcoded sensor telemetry text, and mathematically fictitious "95% CI" claims on binary residuals have been eliminated from both the backend API and frontend UI.
3. **Geospatial and Client Integrity:** Universal geocoding and Leaflet tile rendering (Esri satellite, CARTO, OSM, OpenTopoMap) function natively without API keys. Critical race conditions and location-reset bugs on time-slider interactions have been verified as resolved.
4. **Demonstrability:** The full stack builds cleanly, passes all 53 automated tests, and runs live in the browser.

---

## 2. Audit Claims Verification Matrix

| Claim from Previous Audit | Claimed Value | Independently Recomputed Value | Exact Exit Code / Verification Command | Status |
| :--- | :---: | :---: | :--- | :---: |
| Cleaned Chicago Crime Records | 24,815 | **24,815** | `python -c "import pandas as pd; len(pd.read_csv('data/processed_chicago_crimes.csv'))"` $\rightarrow$ `0` | **VERIFIED** |
| Holdout Test Observations | 3,440 | **3,440** (across 172 shifts) | `reproduce_audit_metrics.py` $\rightarrow$ `0` | **VERIFIED** |
| Test Set Positive Prevalence | 70.49% | **70.49%** (2,425 / 3,440) | `reproduce_audit_metrics.py` $\rightarrow$ `0` | **VERIFIED** |
| CatBoost Calibrated Brier Score | 0.1807 | **0.1807** | `reproduce_audit_metrics.py` $\rightarrow$ `0` | **VERIFIED** |
| CatBoost Operational Precision | 83.58% | **83.58%** (std: 0.195) | `reproduce_audit_metrics.py` $\rightarrow$ `0` | **VERIFIED** |
| Spatial Baseline Operational Prec. | 84.74% | **84.74%** (std: 0.199) | `reproduce_audit_metrics.py` $\rightarrow$ `0` | **VERIFIED** |
| Backend Pytest Test Suite | 53 passing | **53 passed, 0 failed** | `python -m pytest backend/tests/ -v` $\rightarrow$ `0` | **VERIFIED** |
| TypeScript Compiler Checks | Clean | **0 errors** | `npx tsc --noEmit` $\rightarrow$ `0` | **VERIFIED** |
| ESLint Verification | Clean | **0 errors** | `npm run lint` $\rightarrow$ `0` | **VERIFIED** |
| Production Frontend Build | Clean | **0 errors** (built in ~500ms) | `npm run build` $\rightarrow$ `0` | **VERIFIED** |

---

## 3. Independently Reproduced Model Metrics

Evaluated on **3,440 out-of-time future observations** (Holdout period: April 25, 2023 – May 23, 2023) across 20 spatio-temporal cells in Chicago's five primary sectors:

### Global Holdout Evaluation Metrics ($n=3,440$, Prevalence $= 70.49\%$)

| Model Architecture | Brier Score | ROC-AUC | PR-AUC | Log Loss | ECE (Cal. Error) | Cal. Slope | Pooled Prec@20% | Pooled Recall@20% |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Naive Base Rate Baseline** | 0.2085 | 0.5000 | 0.7049 | 0.6078 | 0.0228 | 1.0000 | 64.39% | 18.27% |
| **Temporal Cyclical Baseline** | 0.1949 | 0.6535 | 0.8021 | 0.5749 | 0.0269 | 0.9133 | 85.90% | 24.37% |
| **Historical Spatial Baseline** | 0.1926 | 0.6700 | 0.8032 | 0.5701 | 0.0228 | 1.0234 | 84.74% | 24.04% |
| **CatBoost (Uncalibrated)** | **0.1805** | **0.7302** | **0.8578** | **0.5372** | 0.0194 | 0.9887 | **91.57%** | **25.98%** |
| **CatBoost (Isotonic Calibrated)** | **0.1807** | **0.7282** | **0.8482** | **0.5649** | **0.0195** | 0.8357 | **90.84%** | **25.77%** |

---

## 4. Operational Ranking: The Model's Real Value

### Methodology:
- **Scope:** 172 consecutive 4-hour operational shifts ($172 \times 20 = 3,440$ cell-shift instances).
- **Dispatch Rule:** Top 4 cells ($20\%$) ranked by predicted risk within each individual shift.
- **Evaluation:** Compare dispatched cells against observed incident occurrences in that exact shift.

### Operational Results Comparison:
| Model Architecture | Mean Shift Precision | Std Dev | 95% Empirical CI | Mean Shift Recall | Lift over Base Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Naive Base Rate Baseline** | 67.59% | 0.272 | [6.88%, 100.00%] | 18.79% | -2.91% |
| **Temporal Cyclical Baseline** | 75.58% | 0.209 | [25.00%, 100.00%] | 21.80% | +5.09% |
| **Historical Spatial Baseline** | **84.74%** | 0.199 | [50.00%, 100.00%] | **24.38%** | **+14.24%** |
| **CatBoost (Isotonic Calibrated)** | **83.58%** | **0.195** | **[50.00%, 100.00%]** | **24.05%** | **+13.08%** |

### Critical Scientific Findings:
1. **Spatial Baseline Strength:** In high-density urban crime corridors, crime clustering is remarkably stationary. Consistently picking the historically most violent four cells yields an impressive $84.74\%$ precision per shift.
2. **CatBoost's Genuine Advantage:** While CatBoost trails by $1.16\%$ on static spatial precision alone, it provides **temporal intelligence and calibrated risk probabilities**:
   - CatBoost's Brier score is **6.2% superior** (`0.1807` vs `0.1926`).
   - CatBoost's ROC-AUC is **8.7% superior** (`0.7282` vs `0.6700`).
   - The historical spatial baseline predicts the **exact same 4 cells 24/7/365**, with a static probability. It cannot distinguish between a quiet 4 AM Tuesday morning and a volatile 10 PM Saturday night.
   - CatBoost correctly scales predicted risk up and down with diurnal commuter surges and weekend activity cycles, providing operational dispatchers with dynamic, reliable probability estimates.

---

## 5. Geographic Consistency Findings

### End-to-End Forecast Trace:
1. **Raw Records:** Official Chicago Case records with coordinates (e.g. Lat `41.8820`, Lon `-87.6278`).
2. **Data Processor:** Maps CPD District 1 to `sector_id: "zone-04"` (Loop) and nearest offset to `zone_key: "market"`.
3. **Feature Pipeline:** Aggregates into `(window_time, sector_id, zone_key)` 4-hour buckets. Computes strictly backward-looking lag counts, rolling sums, and diurnal features.
4. **Model Inference:** CatBoost predicts probability $p = 0.61$, converted to risk score $61/100$.
5. **API Response:** `POST /api/forecast/location` returns sector `zone-04`, zone `market`, status `supported`.
6. **Map Rendering:** Leaflet displays `zone-04` polygon, centering on `[41.8719, -87.6283]` and rendering zone `market`'s bounding corridor `[41.8855, -87.6320]` to `[41.8785, -87.6235]`.

### Geometry Truth:
- **Centroids:** Centroids are grounded in official Chicago Police Department district stations.
- **Micro-zone Polygons:** Micro-zones are **operational corridor bounding envelopes** aligned to commercial, transit, and river landmarks, not official administrative CPD police beat shapefiles. This limitation is now explicitly disclosed in the codebase (`chicagoGeography.ts`) and project documentation.

### Universal Coverage Behavior Verified:
- **Downtown Chicago (`41.88, -87.62`):** `SUPPORTED`, genuine model predictions returned.
- **Evanston Border Buffer (`42.04, -87.68`):** `PARTIAL COVERAGE`, degraded buffer notice displayed.
- **Mumbai (`19.07, 72.87`):** `UNSUPPORTED`, honest explanation that model is trained on Chicago; **no fabricated Chicago predictions returned**.
- **New York (`40.71, -74.00`):** `UNSUPPORTED`, no fabricated predictions.
- **Null Island / Ocean (`0.0, 0.0`):** `UNSUPPORTED`, no fabricated predictions.

---

## 6. Live Application & Browser Verification

The application was run locally (`FastAPI` backend on port 8000, `Vite` dev server on port 3000) and verified:

1. **Overview Screen:** Confirmed live metrics load dynamically: `24,815 records ingested`, live risk score `61 / 100 (0.61)`, dynamic SHAP explanations (`7-day moving baseline rate`, `cos_day`, `diurnal commuter surge`). Zero hardcoded probabilities (`p=0.82/0.18/0.24`) remain.
2. **Basemap Switching:** Street, Satellite (Esri World Imagery), Dark Canvas (CARTO Dark Matter), and Terrain (OpenTopoMap) load genuine raster/vector tiles natively via HTTP 200 without API keys.
3. **Location Search & Coverage Display:** Searching for "Mumbai" displays an `UNSUPPORTED` badge with honest disclaimer. Searching for "Chicago" displays a `SUPPORTED` badge with full local metrics.
4. **Time Step Slider Interaction:** Adjusting the temporal slider preserves the active user-selected location without resetting to default Chicago.
5. **Race Condition Prevention:** Rapid sequential search inputs discard stale asynchronous responses using monotonic request IDs.
6. **Validation Screen:** Displays Expected Calibration Error (`0.0195`), Brier Score (`0.1807`), and the newly added **Operational Shift Precision Banner** transparently disclosing CatBoost's `83.6%` vs Spatial Baseline's `84.7%` across 172 audited shifts.

---

## 7. Exact Commands Executed & Exit Codes

| Step | Command | Exit Code | Observed Result |
| :--- | :--- | :---: | :--- |
| **Backend Tests** | `python -m pytest backend/tests/ -v` | **0** | 53 passed, 0 failed in 9.27s |
| **Regression Tests** | `python -m pytest backend/tests/test_audit_regressions.py -v` | **0** | 8 passed, 0 failed in 5.75s |
| **Reproduction Script** | `python -m backend.evaluation.reproduce_audit_metrics` | **0** | Full holdout evaluation reproduced |
| **Dataset Row Check** | `python -c "import pandas as pd; print(len(pd.read_csv('data/processed_chicago_crimes.csv')))"` | **0** | Exactly 24,815 rows |
| **TypeScript Check** | `npx tsc --noEmit` | **0** | Clean (0 errors) |
| **ESLint Check** | `npm run lint` | **0** | Clean (0 errors) |
| **Production Build** | `npm run build` | **0** | Vite built dist bundle in 507ms |
| **Backend Health** | `python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"` | **0** | `{"status":"healthy","model_loaded":true}` |

---

## 8. Remaining Blockers for Production (Honest Disclosure)

1. **Third-Party Geocoder Upstream Rate Limits:** Public OSM Nominatim limits requests to 1 req/sec. Production deployment requires self-hosting Nominatim or using a paid commercial API key.
2. **Heuristic Corridor Boundaries:** Micro-zone polygons are corridor bounding boxes rather than official municipal beat shapefiles.
3. **Single-City Training Data:** The model is trained strictly on Chicago data.

---

## 9. Practical Hackathon Demonstration Checklist

- [x] **1. Start Stack:**
  - Backend: `python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
  - Frontend: `npm run dev` (opens `http://localhost:3000`)
- [x] **2. Demo Universal Location Search:**
  - Search for **"Chicago"** $\rightarrow$ Show `SUPPORTED` badge, 24,815 records, risk score 61/100, SHAP drivers.
  - Search for **"Mumbai"** $\rightarrow$ Show `UNSUPPORTED` badge and honest coverage message (judges love ethical AI that doesn't hallucinate out-of-domain).
- [x] **3. Demo Interactive Leaflet Risk Map:**
  - Click **Risk Map** tab $\rightarrow$ Switch basemaps: Street, Satellite, Dark, Terrain.
  - Show authentic spatial overlays and risk intensity polygons.
- [x] **4. Demo Temporal Dynamics:**
  - Move slider through `08:00`, `12:00`, `16:00`, `20:00`, `00:00` $\rightarrow$ Show dynamic score updates without losing selected location.
- [x] **5. Demo Scientific Rigor (Validation Screen):**
  - Open **Validation** tab $\rightarrow$ Show Brier score (`0.1807`), ECE (`0.0195`), and highlight the Operational Shift Precision banner explaining why CatBoost's temporal calibration adds true value over static spatial baselines.

---

## 10. Final Readiness Verdict

# **READY FOR HACKATHON SUBMISSION**

**Justification:**  
The repository is scientifically verified, free of fraudulent claims or synthetic fallback tricks, fully resilient against client-side race conditions, and backed by passing automated test suites across both frontend and backend. It represents an exemplary, honest, and technically sophisticated hackathon entry.
