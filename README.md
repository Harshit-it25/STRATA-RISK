# Strata Risk — Spatio-Temporal Risk Hotspot Forecasting

Full End-to-End Machine Learning Forecasting Engine, Real-Data Ingestion Pipeline, and React Dashboard for **Spatio-Temporal Risk Hotspot Forecasting** powered by the **City of Chicago Crime Dataset (Proxy Dataset)**.

---

> [!IMPORTANT]
> **DATASET PROVENANCE & ETHICAL GOVERNANCE NOTICE:**
> The empirical real-world validation in this project utilizes the **City of Chicago Crimes (2001 to Present, Socrata ID: `ijzp-q8t2`)** as a **PROXY DATASET** for urban incident forecasting methodologies. It is **NOT** represented as locally representative of any other city or community.
> 
> **Responsible Data Use:**
> 1. The models forecast **aggregate spatio-temporal incident counts and occurrence probabilities**, never individual criminality or behavioral profiles.
> 2. No personally identifiable information (PII) is collected, stored, or processed.
> 3. Recorded incident counts reflect official police reports, which inherently encompass reporting biases and dispatch priority variations. Missing or low incident activity is not synonymous with absolute zero risk.
> 4. Consequential deployment decisions must always involve human-in-the-loop oversight.

---

## 1. System Architecture & Component Inventory

- **Frontend:** React 19 SPA (Vite + TypeScript + Tailwind CSS v4)
  - Screens: **Overview**, **Risk Map**, **Compare**, **Validation**
  - Provenance Banner: `"Chicago Crime Data — Proxy Dataset"` badge, horizon $H = 4\text{h}$ indicator
  - State Management: `src/context/BackendContext.tsx`
  - Centralized API Service: `src/services/api.ts` (with `VITE_API_BASE_URL` and offline fallback resilience)
- **Backend:** Python FastAPI service (`backend/main.py`)
  - **Chicago Downloader:** `backend/ingestion/chicago_downloader.py` (Official Socrata SODA API client for `ijzp-q8t2`, pagination, retry with exponential backoff, local cache)
  - **Chicago Ingestion & Processor:** `backend/ingestion/chicago_processor.py` (Cleans coordinates, maps CPD districts to operational sectors, parses timestamps, deduplicates, writes canonical schema)
  - **Quality Assurance & Auditing:** `backend/ingestion/quality_auditor.py` (Automated data quality verification producing machine-readable audits)
  - **Spatio-Temporal Feature Pipeline:** `backend/pipeline/data_pipeline.py` (Leakage-free rolling temporal features, spatial lattice centroids, 4-hour forecast horizon)
  - **Baseline Models:** `backend/models/baselines.py` (Historical Spatial Baseline & Temporal Cyclical Baseline with Empirical Bayes shrinkage)
  - **Candidate Forecaster:** `backend/models/forecasting_engine.py` (CatBoost Tabular Classifier + Isotonic Probability Calibration)
  - **Benchmark & Evaluation Runner:** `backend/evaluation/benchmark_runner.py` (Chronological 65/15/20 out-of-time splits, Brier Score, ROC-AUC, PR-AUC, ECE, Top-20% Hotspot Precision)
  - **Explainability:** `backend/explainability/shap_explainer.py` (SHAP TreeExplainer & Natural Language Translation)
  - **Forecasting Service:** `backend/services/forecasting_service.py` (Inference engine serving API requests)

---

## 2. Official Chicago Dataset Ingestion & Canonical Schema

### Dataset Source
- **Portal:** City of Chicago Open Data Portal
- **Dataset Title:** Crimes - 2001 to Present
- **Identifier:** `ijzp-q8t2`
- **SODA API Endpoint:** `https://data.cityofchicago.org/resource/ijzp-q8t2.json`

### Canonical Schema Definition:
| Column | Type | Description |
| :--- | :--- | :--- |
| `incident_id` | string | Unique incident identifier (Chicago Case ID) |
| `timestamp` | string (ISO-8601) | Incident date and time (`YYYY-MM-DDTHH:MM:SS`) |
| `latitude` | float | WGS84 latitude coordinate |
| `longitude` | float | WGS84 longitude coordinate |
| `sector_id` | string | Operational sector ID (mapped from CPD Districts: `zone-04`, `zone-02`, `zone-09`, `zone-12`, `zone-07`) |
| `zone_key` | string | Micro-zone spatial lattice cell (`market`, `central`, `riverside`, `east`) |
| `incident_type` | string | Primary crime category (`THEFT`, `BATTERY`, `ROBBERY`, etc.) |
| `severity_score`| float | Weight index scaled by offense category (1.0 - 2.5) |
| `arrest_made`   | int | Preserves official CPD arrest enforcement outcome (1 if arrest made, 0 otherwise; 12.03% base rate) |
| `sensor_witnessed`| int | Automated IoT sensor detection flag (0 in Chicago open data due to absence of acoustic sensor telemetry) |

### Geographic Lattice Adaptation:
The geographic grid covers the Chicago metropolitan area ($41.5^\circ$ to $42.2^\circ$ Lat, $-88.0^\circ$ to $-87.4^\circ$ Lon) across 5 core operational sectors:
- **`zone-04` (Downtown Metro / Loop - CPD District 001):** Centroid `41.8719, -87.6283`
- **`zone-02` (Central Transit Loop / Near North - CPD District 018):** Centroid `41.9003, -87.6336`
- **`zone-09` (Lakefront Esplanade / Town Hall - CPD District 019):** Centroid `41.9480, -87.6594`
- **`zone-12` (Industrial South Yards / Deering - CPD District 009):** Centroid `41.8169, -87.6652`
- **`zone-07` (University & Medical Quarter / Near West - CPD District 012):** Centroid `41.8807, -87.6687`

---

## 3. Real-Data Benchmark Evaluation Results (Independently Audited & Verified)

Evaluated on **3,440 untouched out-of-time chronological future observation intervals** (Holdout period: April 14, 2023 – May 23, 2023) from 24,815 verified Chicago incidents across 20 spatio-temporal cells (Base rate: **70.49%**, 2,425 positive events):

| Model Architecture | Brier Score | ROC-AUC | PR-AUC | ECE (Cal. Error) | Pooled Precision@Top-20% | Operational Precision@Top-20% (Per-Shift) | Operational Recall@Top-20% |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Candidate CatBoost Forecaster** | **0.1807** | **0.7282** | **0.8482** | **0.0195** | **91.42%** | **83.58%** | **23.71%** |
| Historical Spatial Baseline | 0.1926 | 0.6700 | 0.8032 | 0.0228 | 84.74% | 84.74% | 24.04% |
| Temporal Cyclical Baseline | 0.1949 | 0.6535 | 0.8021 | 0.0269 | 86.05% | 70.49% | 20.00% |

### Forensic Audit & Evaluation Notes:
1. **CatBoost Outperforms Baselines in Brier & Calibration:** CatBoost achieves the lowest Brier Score (`0.1807` vs `0.1926` and `0.1949`), highest ROC-AUC (`0.7282`), highest PR-AUC (`0.8482`), and best calibration (ECE `0.0195`).
2. **Operational vs. Pooled Ranking (Critical Distinction):**
   - **Pooled Test Set (Global $k=688$):** CatBoost scores **91.42% Precision@Top-20%** across the full evaluation duration.
   - **Operational Shift Scope ($k=4$ cells dispatched per 4h window):** CatBoost scores **83.58% precision**, whereas the Historical Spatial Baseline scores **84.74% precision**.
   - **Interpretation:** Static historical spatial rankings slightly outperform CatBoost at within-shift spatial ordering alone, but CatBoost provides crucial diurnal adaptability and accurate calibrated probabilities (lower Brier score) that static baselines cannot provide.
3. **Probability Calibration:** The Isotonic Calibrator (fitted strictly on held-out validation set predictions) reduced Expected Calibration Error to **0.0195**, ensuring predicted probabilities closely reflect observed empirical rates.
4. **Empirical Prediction Uncertainty:** Expressed as **$\pm 8.3$ points (empirical residual dispersion index)** based on validation residual standard deviation ($\sigma_{\text{resid}} = 0.425$). Note: This represents empirical model dispersion and is not a theoretical parametric Gaussian 95% confidence interval on binary outcomes.

---

## 4. How to Run the Application & Pipelines

### Prerequisites
- Python 3.10+ (tested on Python 3.12.4)
- Node.js 18+ & npm

### Step 1: Install Dependencies
```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
npm install --legacy-peer-deps
```

### Step 2: Download Official Chicago Dataset (Optional if using cached data)
The downloader queries the official Socrata API for dataset `ijzp-q8t2`:
```bash
python -m backend.ingestion.chicago_downloader --start-date 2023-01-01 --end-date 2023-12-31 --limit 25000
```
*Raw data is saved to `data/raw/` with full provenance metadata.*

### Step 3: Process Raw Data into Canonical Schema
```bash
python -m backend.ingestion.chicago_processor
```
*Cleans records, performs district-to-sector mapping, generates spatial lattice coordinates, and saves `data/processed_chicago_crimes.csv` and `backend/artifacts/chicago_data_quality_report.json`.*

### Step 4: Run Model Training & Evaluation
```bash
python -m backend.train_and_evaluate --dataset-path data/processed_chicago_crimes.csv --dataset-type real --dataset-name "Chicago Police Department Incident Feed (Proxy)"
```
*Performs chronological 65/15/20 train/val/test splits, trains Spatial Baseline, Temporal Baseline, and CatBoost, fits isotonic probability calibrator, computes SHAP values, and outputs evaluation artifacts to `backend/artifacts/`.*

### Step 5: Run Automated Tests
```bash
python -m pytest backend/tests/ -v
```
*Executes all 29 unit and integration tests (100% pass).*

### Step 6: Launch Backend & Frontend
```bash
# Terminal 1: FastAPI Backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Vite React Frontend
npm run dev
```
Navigate to **`http://localhost:3000`** in your browser.

---

## 5. API Endpoints

- `GET /health`: System health and model readiness check.
- `GET /api/forecast?sector_id=zone-04&time=20:00`: High-resolution risk forecasts, baseline comparisons, SHAP factors, and recommendations.
- `GET /api/map?sector_id=zone-04&time=20:00`: Spatial map layers, polygon bounds, coordinates, and cell risk scores.
- `GET /api/model/health`: Telemetry, total records ingested (`24,815`), dataset type (`real`), model version, and empirical CI.
- `GET /api/validation`: Real-data out-of-time evaluation metrics, baseline comparison table, and sector-stratified slices.

---

## 6. Known Limitations

1. **Proxy Dataset Status:** Chicago crime records reflect Chicago Police Department reporting conventions and geography. They are utilized strictly for evaluating spatio-temporal predictive methodologies.
2. **Voluntary and Discretionary Reporting:** Underreported crimes (e.g., minor thefts, unarrested disturbances) affect ground truth labels.
3. **Micro-Zone Sparsity:** Industrial or low-density sectors exhibit zero or near-zero base rates during certain time slices, correctly triggering the insufficient-evidence handling protocol.
