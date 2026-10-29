# STRATA RISK — FIX PLAN

**Priority Order:** P1 (Correctness & State Integrity) -> P2 (Reliability, Geospatial, Security) -> P3 (Cleanup)

---

## 1. P1 Repairs (Mandatory Correctness & Integrity)

### Step 1.1: Fix Frontend Location Reset Bug & Race Conditions (`BackendContext.tsx`)
- **Problem:** Changing `selectedTime` or `selectedSector` calls `fetchLocationForecast(DEFAULT_LOCATION)`, wiping out any selected location (e.g. Mumbai). Multiple requests lack sequencing.
- **Fix:**
  - Create `activeLocationRef` to track currently selected location across effect executions.
  - Implement request sequencing with an incrementing `requestId` ref to discard stale responses from out-of-order asynchronous requests.
  - Separate one-time startup health checks from parameter-driven data fetches.
  - When `selectedTime` or `selectedDate` changes, call `fetchLocationForecast(selectedLocation)` rather than `DEFAULT_LOCATION`.

### Step 1.2: Eliminate Fabricated Probabilities on Sparse Zones (`forecasting_service.py`)
- **Problem:** `forecasting_service.py` assigns `0.28` and `28` score when zone probability is `None`.
- **Fix:**
  - If `raw_prob is None`, set `risk_probability: None`, `risk_score_100: None`, and `risk_level: "SPARSE"`.
  - Update `ForecastResult` schema and frontend to handle `null` scores gracefully without rendering fabricated integers.

### Step 1.3: Eliminate Hardcoded Model Bypass for Chicago Sector 12 and Zone East (`forecasting_service.py`)
- **Problem:** Line 208 unconditionally marks `zone-12` and `east` as sparse with fake "sensor telemetry" reasons.
- **Fix:**
  - Check actual empirical data volume ($N < 5$ records) rather than hardcoding zone names.
  - Remove all fictional acoustic sensor references.
  - Allow CatBoost model inference to run for all valid Chicago zones.

### Step 1.4: Fix Static Hardcoded Probabilities in `OverviewScreen.tsx`
- **Problem:** SVG preview displays static `p=0.82`, `p=0.18`, `p=0.24`.
- **Fix:**
  - Bind preview cards directly to active `activeTimeStep.zones` data from `BackendContext`.
  - Dynamically display the live zone name, score, and probability.

### Step 1.5: Fix Misleading ML Evaluation & Uncertainty Claims
- **Problem:** README and validation report claim `91.42% Precision@Top-20%` and `±8.3 pts (95% CI)` without explaining global pooling or arbitrary scaling.
- **Fix:**
  - Update `backend/evaluation/benchmark_runner.py` to calculate both **Global Pooled Precision@Top-20%** and **Operational Per-Shift Precision@Top-20%**.
  - Document that CatBoost's operational per-shift precision is 83.58% vs 84.74% for spatial baseline.
  - Re-label the uncertainty band from "95% empirical CI" to "Empirical Residual Dispersion (±8.3 pts std-index)" with clear documentation of the methodology.
  - Update `README.md` and `validation_metrics.json` accordingly.

---

## 2. P2 Repairs (Reliability, Geospatial, Security)

### Step 2.1: Fix Insecure CORS Configuration (`backend/main.py`)
- **Problem:** `allow_origins=["*"]` with `allow_credentials=True`.
- **Fix:** Set `allow_credentials=False`.

### Step 2.2: Add NaN / Infinity Exception Guards (`forecasting_service.py`)
- **Problem:** `score = int(round(prob * 100))` throws `ValueError` on NaN.
- **Fix:** Add `if math.isnan(prob) or math.isinf(prob): prob = 0.50` with warning log.

### Step 2.3: Fix Marker Popup Content Not Updating (`InteractiveRiskMap.tsx`)
- **Problem:** Moving the marker pin with `setLatLng` does not update the popup content.
- **Fix:** Call `markerRef.current.setPopupContent(...)` with current location details.

### Step 2.4: Add Safe Fallbacks in `CompareScreen.tsx`
- **Problem:** Unchecked access to `timeA.zones[key]` when timeline is empty.
- **Fix:** Guard against undefined `timeA` and `timeB` with default safe objects.

---

## 3. P3 Cleanup

### Step 3.1: Clean Dead Code in `OverviewScreen.tsx`
- Remove unused `selectedPreviewSector`, `tooltipFlash`, `handleSelectSector`.

### Step 3.2: Clean Hardcoded Fallbacks in `ValidationScreen.tsx`
- Replace synthetic default numbers with honest `"—"` indicators when data is pending.

---

## 4. Regression Testing & Verification

1. Run backend unit tests: `python -m pytest backend/tests/ -v`.
2. Add new test cases:
   - Test per-shift operational ranking vs global pooled ranking.
   - Test sparse zone null probability handling in `get_location_forecast`.
   - Test NaN probability handling.
   - Test CORS configuration.
3. Run frontend TypeScript check: `npx tsc --noEmit`.
4. Run frontend linter: `npm run lint`.
5. Run frontend production build: `npm run build`.
6. Verify end-to-end user workflows in browser.
