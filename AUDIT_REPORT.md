# STRATA RISK — ADVERSARIAL TECHNICAL AUDIT REPORT

**Date:** October 9, 2026  
**Auditor Roles:** Principal Software Engineer, Senior ML Researcher, Geospatial Engineer, Security Engineer, SRE, QA Lead  
**Repository:** `strata-risk`  
**Execution Context:** Windows / Python 3.12.4 / React 19 / Vite / Tailwind v4 / Leaflet  

---

## 1. Executive Summary & Brutal Verdict

**VERDICT: NOT READY (for Production) / HACKATHON READY (with Verified Repairs)**

Strata Risk exhibits impressive engineering foundations: a real FastAPI backend, a real CatBoost forecasting engine trained on 24,815 official City of Chicago incident records, and a newly implemented interactive Leaflet map using authentic Esri, OpenStreetMap, and CARTO tiles.

However, an adversarial forensic audit reveals **critical scientific, state management, and geospatial defects**:
1. **Misleading Machine Learning Evaluation:** The reported **91.42% Precision@Top-20%** was calculated by globally sorting all 3,440 test predictions across 172 time slices simultaneously, rather than evaluating operational per-shift dispatch. Evaluated at the true operational scope ($k=4$ cells per 4-hour shift), CatBoost achieves **83.58% precision**, which is actually **lower than the Historical Spatial Baseline (84.74%)**.
2. **Statistically Arbitrary Uncertainty:** The claimed **"±8.3 pts (95% empirical CI)"** is mathematically fictitious—it was produced by multiplying the residual standard deviation by 1.96 and an arbitrary scaling factor of 10.
3. **State Corruption Bug in Frontend:** Changing the forecast time slider (`selectedTime`) triggers an effect in `BackendContext.tsx` that calls `fetchLocationForecast(DEFAULT_LOCATION)`, wiping out any active user-selected location (e.g., Mumbai, London, or custom coordinates) and silently reverting to Chicago.
4. **Race Conditions in Universal Forecasting:** Multiple asynchronous location searches lack sequencing or cancellation; slow earlier responses overwrite newer ones.
5. **Fabricated Probabilities on Sparse Zones:** In `forecasting_service.py`, sparse zones with `None` probability are silently assigned an arbitrary probability of `0.28` and a risk score of `28`.
6. **Hardcoded Model Bypass:** Sector `zone-12` and micro-zone `east` are unconditionally hardcoded to return synthetic "sensor telemetry below 35%" text, bypassing CatBoost model inference entirely, despite Chicago having zero IoT sensors.
7. **Static Hardcoded Values in Overview Screen:** `OverviewScreen.tsx` displays static hardcoded probabilities (`p=0.82`, `p=0.18`, `p=0.24`) in an SVG preview card regardless of model predictions.
8. **Marker Popup Stale State:** Moving the map marker in `InteractiveRiskMap.tsx` updates coordinates but never updates the popup content.

---

## 2. Forensic Findings by Severity

### P1 — Major Correctness Defects, Invalid Evaluations & Broken Workflows

#### Finding P1.1: Operational per-timestep ranking is 83.58%, NOT 91.42%; CatBoost does NOT outperform spatial baseline on operational per-timestep ranking
- **Severity:** P1 (Scientific / Evaluation Validity)
- **Files:** `backend/evaluation/benchmark_runner.py` (lines 60-85), `README.md` (lines 75-85), `backend/artifacts/validation_metrics.json`
- **Evidence & Reproduction:**
  Running `compute_hotspot_ranking_metrics` pools all 3,440 test observations across 172 time slices:
  ```python
  # Benchmark runner code:
  k = max(1, int(round(n * top_k_pct)))  # 688 globally
  top_k_indices = np.argsort(-y_prob)[:k]
  ```
  Independent per-timestep evaluation ($k=4$ top cells out of 20 at each 4-hour shift across all 172 intervals):
  - **CatBoost Forecaster (Operational Mean):** `83.58%`
  - **Historical Spatial Baseline (Operational Mean):** `84.74%`
  - **Temporal Baseline (Operational Mean):** `75.58%`
  - **Global Pooled Sort (Claimed):** `91.42%`
- **Root Cause:** Global sorting exploits time-of-week base-rate differences across the entire 40-day test set (picking peak weekend shifts) rather than solving the operational spatial allocation problem at each operational window.
- **Remediation:** Report both Global Pooled Top-20% and Operational Per-Shift Top-20% explicitly; document that CatBoost's advantage lies in temporal adaptability and probabilistic Brier calibration, not spatial prioritization over the static spatial baseline.

#### Finding P1.2: Statistically Arbitrary "±8.3 pts (95% empirical CI)" Uncertainty Band
- **Severity:** P1 (Scientific Validity)
- **Files:** `backend/evaluation/benchmark_runner.py` (lines 155-164), `backend/artifacts/validation_metrics.json` (line 34)
- **Evidence:**
  ```python
  residuals = y_val_true - p_val
  residual_std = float(np.std(residuals)) # 0.425
  score_uncertainty_pts = round(float(1.96 * residual_std * 10), 1) # 8.3
  ```
- **Root Cause:** Probability residuals are on $[0, 1]$. To convert to a 0-100 scale, the multiplier is 100, which would yield $\pm 83.3$ points. Multiplying by 10 was an arbitrary scaling trick to make the output look like a plausible $\pm 8.3$ points. Binary residuals are non-Gaussian.
- **Remediation:** Remove misleading "95% empirical CI" claim. Define uncertainty truthfully as the empirical mean absolute calibration error (MACE / ECE) or standard error of predicted probability.

#### Finding P1.3: Changing Forecast Time Slider Wipes Out Active Location Selection
- **Severity:** P1 (Broken Core User Workflow)
- **Files:** `src/context/BackendContext.tsx` (lines 182-216, 331-338)
- **Evidence:**
  In `BackendContext.tsx`:
  ```tsx
  useEffect(() => {
    checkConnection();
    fetchForecast();
    fetchLocationForecast(DEFAULT_LOCATION); // LINE 334!
    fetchMap();
    fetchModelHealth();
    fetchValidation();
  }, [checkConnection, fetchForecast, fetchLocationForecast, fetchMap, fetchModelHealth, fetchValidation]);
  ```
  `fetchLocationForecast` depends on `[selectedTime, selectedDate, selectedSector.id]`. When `selectedTime` changes, `fetchLocationForecast` is recreated, triggering this `useEffect`, which calls `fetchLocationForecast(DEFAULT_LOCATION)` (Chicago District 001).
- **Reproduction:**
  1. Search for Mumbai. Location status shows `UNSUPPORTED`.
  2. Click `16:00` or `08:00` on the temporal simulation timeline.
  3. The location forecast card immediately flips back to Downtown Chicago!
- **Remediation:** Decouple initial mount execution from parameter changes. Use `selectedLocationRef` or a dedicated effect that passes `selectedLocation` rather than hardcoding `DEFAULT_LOCATION`.

#### Finding P1.4: Race Condition in Universal Location Forecasting
- **Severity:** P1 (State Synchronization)
- **Files:** `src/context/BackendContext.tsx` (lines 182-216)
- **Evidence:** `fetchLocationForecast` does not maintain a request sequence ID or AbortController.
- **Reproduction:** Selecting Location A (slow network / remote reverse geocode) and immediately selecting Location B (fast local hit) causes Location A's delayed response to overwrite Location B.
- **Remediation:** Add an incrementing `requestId` ref in `BackendContext` and discard responses if the response does not match the active request ID.

#### Finding P1.5: Fabricated Risk Probability (0.28) and Score (28) on Sparse Zones
- **Severity:** P1 (Data Integrity / Ethical Violation)
- **Files:** `backend/services/forecasting_service.py` (lines 511-515)
- **Evidence:**
  ```python
  raw_prob = zone_forecast.get("prob")
  prob = float(raw_prob) if raw_prob is not None else 0.28
  score = zone_forecast.get("score")
  score_int = int(score) if isinstance(score, int) else int(round(prob * 100))
  ```
  When `raw_prob` is `None` (sparse zone), it silently manufactures `0.28` probability and `28` score.
- **Remediation:** Allow `risk_probability` and `risk_score_100` to be `None` in the response payload when data is sparse, with `risk_level: "SPARSE"`.

#### Finding P1.6: Hardcoded Model Bypass for Chicago Sector 12 and Zone East
- **Severity:** P1 (Model Ingestion Integrity)
- **Files:** `backend/services/forecasting_service.py` (lines 208-232)
- **Evidence:**
  ```python
  is_sparse = (sector_id == "zone-12" or zone_key == "east")
  if is_sparse:
      reasons = [
          "Sensor telemetry coverage below 35% statistical confidence threshold.",
          ...
      ]
      return { ... "score": "--", "level": "Sparse", ... }
  ```
- **Root Cause:** Synthetic artifact leftover. Chicago has crime records in District 009 (`zone-12`) and in `east`, and Chicago has no IoT acoustic sensors.
- **Remediation:** Query the CatBoost model dynamically; only mark as Sparse if historical data volume is genuinely below minimum threshold ($N < 5$). Remove fictional sensor telemetry text.

#### Finding P1.7: Hardcoded Static Probabilities in `OverviewScreen.tsx`
- **Severity:** P1 (UI Truthfulness)
- **Files:** `src/components/OverviewScreen.tsx` (lines 365-412)
- **Evidence:** Static SVG tooltip displays: `Market Road p=0.82`, `Riverside Esplanade p=0.18`, `Sector 4 Logistics p=0.24`.
- **Root Cause:** Legacy mock values never connected to `forecast` data.
- **Remediation:** Connect the overview mini-preview directly to `forecast.time_step.zones` or active location forecast data.

---

### P2 — Geospatial, Reliability, Performance & Security Defects

#### Finding P2.1: Hand-Drawn Polygons vs Voronoi Cluster Ingestion Mismatch
- **Severity:** P2 (Geospatial Inconsistency)
- **Files:** `src/data/chicagoGeography.ts`, `backend/ingestion/chicago_processor.py`
- **Evidence:** `chicago_processor.py` assigns crimes using a Euclidean distance to 4 centroid offsets. `chicagoGeography.ts` uses hand-drawn rectangles around State/Michigan, Union Station, and Wacker Drive.
- **Impact:** Polygons are geometric approximations, not legal CPD beat boundaries.
- **Remediation:** Add explicit documentation in UI and code that micro-zones are heuristic operational approximations.

#### Finding P2.2: Unhandled Model NaN / Infinity Exception in Forecasting Service
- **Severity:** P2 (Runtime Reliability)
- **Files:** `backend/services/forecasting_service.py` (line 252)
- **Evidence:** `score = int(round(prob * 100))`. If `prob` is NaN, Python raises `ValueError: cannot convert float NaN to integer`, producing HTTP 500.
- **Remediation:** Add `math.isnan(prob)` / `math.isinf(prob)` guards with safe fallback.

#### Finding P2.3: Insecure CORS Configuration
- **Severity:** P2 (Security)
- **Files:** `backend/main.py` (lines 49-54)
- **Evidence:** `CORSMiddleware` configured with `allow_origins=["*"]` and `allow_credentials=True`.
- **Remediation:** Set `allow_credentials=False` when wildcard origins are used.

#### Finding P2.4: Marker Popup Content Never Updates on Map Move
- **Severity:** P2 (Usability)
- **Files:** `src/components/map/InteractiveRiskMap.tsx` (lines 152-154)
- **Evidence:** When `selectedLocation` updates, `setLatLng` is called on `markerRef.current`, but `setPopupContent` is never called.
- **Remediation:** Call `markerRef.current.setPopupContent(...)` when `selectedLocation` changes.

#### Finding P2.5: Potential Undefined Crash in `CompareScreen.tsx`
- **Severity:** P2 (Runtime Crash)
- **Files:** `src/components/CompareScreen.tsx` (lines 100-101)
- **Evidence:** `timeA.zones[key]` will throw if `timeline` is empty during loading.
- **Remediation:** Add optional chaining and fallback empty object.

---

### P3 — Minor Usability, Cleanup & Dead Code

#### Finding P3.1: Dead State in `OverviewScreen.tsx`
- **Files:** `src/components/OverviewScreen.tsx` (lines 24-31)
- **Evidence:** `selectedPreviewSector`, `tooltipFlash`, `handleSelectSector` are never used.

#### Finding P3.2: Synthetic Fallback Numbers Hardcoded in `ValidationScreen.tsx`
- **Files:** `src/components/ValidationScreen.tsx` (lines 251-285)
- **Evidence:** If validation metrics keys are missing, fallback displays old synthetic numbers (`0.1249`, `0.8932`).

---

## 3. Machine Learning Audit Summary

| Metric | Claimed (README/JSON) | Independently Recomputed (Holdout Test) | Operational Per-Shift ($k=4$) | Audit Verdict |
| :--- | :---: | :---: | :---: | :---: |
| **Brier Score** | `0.1807` | `0.1807` | N/A | **REPRODUCED** |
| **ROC-AUC** | `0.7282` | `0.7282` | N/A | **REPRODUCED** |
| **PR-AUC** | `0.8482` | `0.8482` | N/A | **REPRODUCED** (Base rate: 70.49%) |
| **ECE** | `0.0195` | `0.0195` | N/A | **REPRODUCED** |
| **Precision@Top-20%** | `91.42%` | `91.42%` (Global pooled) | **`83.58%`** | **MISLEADING EVALUATION** |
| **Spatial Baseline Prec@20%** | `84.74%` | `84.74%` (Global pooled) | **`84.74%`** | **CatBoost lower by 1.16%** |
| **Uncertainty Band** | `±8.3 pts (95% CI)` | `0.425 residual std` | Arbitrary $\times 10$ | **STATISTICALLY INVALID** |
