# STRATA RISK — INDIA URBAN RISK FORECASTING FEASIBILITY REPORT
## Data Discovery, Spatial-Temporal Granularity Audit, Model Architecture, and City Recommendation for Mumbai and Pune

**Document Identifier:** `INDIA_CITY_DATA_FEASIBILITY.md`  
**Author:** Principal ML Systems Engineer, Geospatial Data Architect & Policy Auditor  
**Date:** October 12, 2026  
**Status:** Strategic Feasibility Assessment & Engineering Roadmap  
**Scope:** Feasibility analysis for transitioning Strata Risk from Chicago-only research to an India-first urban risk forecasting platform (focusing on Greater Mumbai and Pune City).

---

## 1. Executive Summary & Verdict

Strata Risk’s core engineering value lies in **honest, leak-free, empirically calibrated spatio-temporal risk forecasting**. The existing production implementation was trained and evaluated on 24,815 incident records from the Chicago Police Department, utilizing a 20-cell lattice across 172 four-hour test shifts ($n=3,440$).

A comprehensive forensic investigation was conducted into the official public data landscape in India, specifically investigating open government portals (`data.gov.in`, `smartcities.data.gov.in`, `opendata.pmc.gov.in`), state police platforms (`citizen.mahapolice.gov.in`, `mahapolice.gov.in`), municipal portals, and national repositories (NCRB).

### Core Audit Verdict
1. **Public Open Data Reality:**
   **Neither Mumbai nor Pune currently provides an open, publicly downloadable, incident-level crime dataset with temporal timestamps and geographic coordinates.**
   - Open datasets hosted on official portals (`data.gov.in`, `opencity.in`, Mumbai Police website) consist exclusively of **annual and monthly aggregate tabular summaries** (e.g., 20–30 rows of city-wide counts by IPC crime category).
   - The National Crime Records Bureau (NCRB) publishes annual retrospective compilations aggregated to the entire city level with a 1-to-2 year publication lag.
   - The Maharashtra CCTNS citizen portal (`citizen.mahapolice.gov.in`) is an individual FIR status retrieval interface restricted to a rolling 90-day window, excludes sensitive offenses (POCSO, sexual offenses) per Supreme Court mandate (*Youth Bar Association of India v. Union of India*, 2016), outputs unstructured scanned/typed Marathi PDFs with personally identifiable information (PII), and prohibits automated bulk extraction.
2. **Operational Status:**
   **Neither Indian city can be declared "model-supported" at this time.** Under Strata Risk’s core design principles, fabricating risk scores or transferring Chicago-trained model weights to Indian coordinates is strictly prohibited. The system must continue returning `coverage_status: "unsupported"` and `risk_probability: None` for Mumbai and Pune queries.
3. **Recommended First Pilot City:**
   If institutional access is pursued via a formal Memorandum of Understanding (MoU) with state law enforcement, **Pune City is the recommended first deployment partner**. Pune possesses a more manageable geographic scale (~33 police stations vs. 94 in Mumbai), existing police GIS initiatives (*"My Safe Pune"*), an active civic open data store (`opendata.pmc.gov.in`), and established academic research precedents.

---

## 2. Task 1: Public Data Discovery (Mumbai vs. Pune)

To evaluate data availability without relying on assumptions or portal existence, official public endpoints, downloadable files, and legislative frameworks were inspected directly.

```
                    INDIAN OPEN CRIME DATA LANDSCAPE
                    
  National Level (NCRB / OGD Platform: data.gov.in)
  └── Format: Annual PDF reports / High-level CSV tables
  └── Granularity: Whole-City / Whole-State aggregates (1-year lag)
  └── Coordinates: NONE | Shift Timestamps: NONE
  
  State Level (Maharashtra Police / CCTNS: citizen.mahapolice.gov.in)
  └── Format: Individual FIR PDF search (Marathi / English)
  └── Granularity: Police Station narrative text (90-day search window)
  └── Restrictions: Sensitive crimes masked (SC 2016), PII protected (DPDPA 2023)
  └── Coordinates: NONE (requires text NLP geocoding)
  
  City Portals (Mumbai Police / Pune City Police / PMC Open Data)
  └── Mumbai Police: Monthly comparative statement tables (Counts per IPC head)
  └── Pune City Police: Citizen services (Lost & Found), no public crime database
  └── PMC Open Data: Civic municipal data only (Solid waste, water, transport)
```

### Detailed Data Discovery Matrix

| Data Dimension | Greater Mumbai Police (`mumbaipolice.gov.in`) | Pune City Police (`punepolice.gov.in`) | National / State Aggregators (NCRB / CCTNS) |
| :--- | :--- | :--- | :--- |
| **Incident-Level Raw Feed** | **NOT AVAILABLE.** Only monthly aggregate statements published. | **NOT AVAILABLE.** No public incident-level registry. | **NOT AVAILABLE.** CCTNS internal only; public access restricted to 1-by-1 lookup. |
| **Date & Time Fields** | Monthly and annual aggregates only (e.g., "July 2024", "Year 2023"). | Press release dates only; no public micro-level time fields. | NCRB: Calendar year totals. CCTNS: FIR registration date/time (narrative text). |
| **Spatial Coordinates** | **NONE.** No latitude, longitude, ward, or police station columns in open files. | **NONE.** Internal geotagging (*My Safe Pune*) is strictly non-public. | NCRB: City-wide. CCTNS: Police station name and descriptive "Place of Occurrence" text. |
| **Incident Categorization** | IPC / BNS categories (Murder, Robbery, Theft, HBT Night, Hurt, Rape, Molestation). | Standard IPC / BNS crime heads. | Standardized NCRB crime classification (Violent, Property, Women, SLL). |
| **Historical Depth** | Sporadic monthly statements; OpenCity has 2022–2023 summaries. | Annual crime review totals published in press briefings. | Continuous annual reports (1953–present), but annual resolution only. |
| **Update Frequency** | Monthly PDF/XLSX release with 30–60 day lag. | Ad-hoc / Annual press release. | Annual release with 12–24 month lag. |
| **Licensing & Access** | OpenCity lists "Public Domain" for aggregate tables; police PDFs lack formal open license. | Official Government Copyright; no machine-readable open data license. | NCRB: Open Government Data (OGD) License (aggregates only). |
| **Privacy Restrictions** | None on aggregates (no PII present). | High internal classification. | Strict legal protection: DPDPA 2023, IPC Section 228A, SC 2016 FIR masking guidelines. |

### Direct Inspection of Downloaded Mumbai Crime Data
Inspection of the actual CSV file published as `"IPC Crimes for 2022 and 2023"` on `data.opencity.in` (Resource ID `18e13d1a-678e-4caa-96e5-2b585826f1f1`, downloaded and verified from OpenCity) revealed:
```csv
Crime Heads,2023 Registered,2023 Detected,%Age Detection - 2023,2022 Registered,2022 Detected,%Age Detected 2022
Murder,123,118,96,133,129,97
Robbery,642,628,98,846,727,86
H.B.T.Night.,"1,073",757,71,"1,375",837,61
Thefts.,"6,675","2,835",42,"14,805","3,244",22
M.V.Thefts.,"2,671","1,564",59,"3,058","1,588",52
Total IPC,"45,869","34,991",76,"70,367","47,866",68
```
- **Total records:** Exactly 19 rows.
- **Content:** City-wide annual category counts.
- **Suitability for ML:** Zero spatial attributes, zero shift timestamps, zero incident records. Cannot train or evaluate a spatial-temporal model.

---

## 3. Task 2: Feasibility Comparison (Mumbai vs. Pune)

A comparative evaluation was performed across six criteria required for machine learning forecasting feasibility:

```
+-----------------------------------------------------------------------------------------+
|                              FEASIBILITY SCORECARD                                      |
+----------------------------------+-----------------------+------------------------------+
| Dimension                        | Greater Mumbai        | Pune City                    |
+----------------------------------+-----------------------+------------------------------+
| 1. Public Temporal Granularity   | Monthly / Annual      | Annual / Ad-hoc              |
| 2. Public Spatial Granularity    | City-wide aggregate   | City-wide aggregate          |
| 3. Administrative Police Units   | 94 Police Stations    | 33 Police Stations           |
| 4. Municipal GIS Open Data       | MCGM (Limited GIS)    | PMC Open Data Store (Active) |
| 5. Internal Geotagged Precedent  | Mumbai Safe City CCTV | "My Safe Pune" Patrol App    |
| 6. Academic Research Precedents  | Sporadic (KDE/Ward)   | Moderate (FIR Spatial GIS)   |
| 7. Public Holdout Evaluation     | IMPOSSIBLE            | IMPOSSIBLE                   |
| 8. Institutional Feasibility     | Complex (Multi-agency)| High (Single Commissionerate)|
+----------------------------------+-----------------------+------------------------------+
```

### Detailed Evaluation of Feasibility Dimensions

#### 1. Temporal Granularity
- **Chicago Baseline:** Exact incident occurrence timestamp (minute-level precision), enabling aggregation into 4-hour non-overlapping shifts ($t_0, t_1, \dots$).
- **Mumbai (Public):** Monthly totals (e.g., July 2024). Shift-level or diurnal variations (night vs. day surges) are completely obscured.
- **Pune (Public):** Annual totals. No shift, day-of-week, or hourly data available publicly.
- **Institutional Potential:** Both cities record exact incident registration timestamps in internal CCTNS FIR logs, but actual incident occurrence times often have recall delays or estimated intervals (e.g., "occurred between 22:00 and 04:00").

#### 2. Spatial Granularity
- **Chicago Baseline:** Precise GPS coordinates (latitude/longitude rounded to micro-block) binned into standardized lattice cells.
- **Mumbai (Public):** Zero spatial subdivisions in open data. Administratively, Greater Mumbai is partitioned into 5 Police Regions, 13 Zones, and **94 Police Stations** across ~603 km².
- **Pune (Public):** Zero spatial subdivisions in open data. Administratively, Pune City Police Commissionerate is partitioned into 2 Regions, 5 Zones, and **33 Police Stations** across ~331 km² (recently expanded with merged suburban stations).
- **Spatial Address Ambiguity:** Indian FIRs record narrative text for *"Place of Occurrence"* (e.g., *"Near Ganpati Mandir, Sinhagad Road"*). Free-form address text in bilingual Marathi/English requires Named Entity Recognition (NER) and fuzzy gazetteer matching, introducing substantial spatial geocoding error, especially in informal settlements and dense slums (e.g., Dharavi in Mumbai, Kasba Peth in Pune).

#### 3. Historical Depth
- **Chicago Baseline:** 20+ years of continuous, daily-updated incident records on `data.cityofchicago.org`.
- **Mumbai & Pune (Public):** Public reports cover disconnected 1-year or 2-year summaries.
- **Institutional CCTNS:** CCTNS was phased in across Maharashtra between 2013 and 2016. A centralized historical digital archive spanning 2016–2026 exists internally, offering 8–10 years of consistent digital FIR records if institutional access is granted.

#### 4. Missingness, Reporting Biases & Data Quality
- **Non-Registration ("Burking"):** In India, petty property crimes (theft, mobile phone snatching, vehicle theft) frequently go unregistered as formal FIRs, being relegated to non-cognizable (NC) register entries or lost-and-found portal logs.
- **Supreme Court Masking Mandate:** Per the Supreme Court ruling in *Youth Bar Association of India v. Union of India* (2016), FIRs involving sexual offenses, POCSO, and national security are strictly prohibited from public digital portals. Any public-facing scrape or partial export inherently suffers from severe systematic truncation of violent crimes against women.
- **BNS Transition (July 2024):** On July 1, 2024, India replaced the Indian Penal Code (IPC) with the Bharatiya Nyaya Sanhita (BNS). Historical category mappings (e.g., IPC 378/379 Theft vs. BNS 303; IPC 302 Murder vs. BNS 103) require careful cross-walk harmonization across the historical break.

#### 5. Availability of Chronological Evaluation Data
- **Public Feasibility:** Zero independent chronological evaluation data exists in the public domain. It is mathematically impossible to construct a held-out test set ($n=3,440$) for either city using open data.
- **Institutional Feasibility:** Chronological splitting (e.g., 2018–2022 train, 2023 validation, 2024 holdout test) is feasible exclusively with raw CCTNS exports under institutional authorization.

---

## 4. Task 3: Proposed India-Specific Model Architecture

The existing 17-feature Chicago feature schema **cannot transfer unchanged** to an Indian metropolitan area. The physical morphology, administrative policing structures, climate dynamics, and operational dispatch rules differ fundamentally.

### A. Spatial & Temporal Unit Definition

```
               PROPOSED HIERARCHICAL SPATIAL LATTICE
               
   Level 1: Commissionerate Boundary (Mumbai / Pune)
      └── Level 2: Police Zone (Zonal DCP: 5 in Pune, 13 in Mumbai)
           └── Level 3: Police Station Jurisdiction (33 in Pune, 94 in Mumbai) [PRIMARY UNIT]
                └── Level 4: Police Beat / Chowki Polygons (~3–5 per Station) [FUTURE EXPANSION]
```

1. **Spatial Aggregation Unit:**
   - **Primary Unit:** **Police Station Jurisdictions** (33 units in Pune; 94 units in Mumbai).
   - **Why Grid Cells Fail:** Uniform rectangular grid cells (like Chicago's $5 \times 4$ lattice) are poorly suited to Indian urban geography. City boundaries are fragmented by river confluences (Mula-Mutha in Pune), coastal inlets (Mithi River, Mahim Creek in Mumbai), hills, informal settlements, and irregular police jurisdictional boundaries. Police patrol cars (PCR vans / Beat Marshals) are dispatched strictly within designated Police Station beats.
2. **Temporal Aggregation Shift Window:**
   - **Shift Granularity:** **8-hour or 12-hour operational shifts**, replacing Chicago's 4-hour windows.
   - **Shift Definitions:**
     - **Shift 1 (Day / Commute):** 08:00 to 16:00
     - **Shift 2 (Evening / Peak):** 16:00 to 00:00 (Evening market rush, commercial surges)
     - **Shift 3 (Night / Structural):** 00:00 to 08:00 (House Breaking by Night [HBT], warehouse burglaries)

### B. Forecasting Target Formulation
- **Primary Binary Target:**
  $$Y_{i, t+1} \in \{0, 1\}$$
  Indicates whether at least one high-harm cognizable incident occurs in Police Station jurisdiction $i$ during operational shift $t+1$.
- **Target Category Subsets:**
  - **Violent / Street Harm:** Robbery, Extortion, Chain Snatching, Grievous Hurt, Riots.
  - **Property Harm:** House Breaking by Night (HBT Night), Motor Vehicle Theft (MVT).
  - *Omission Rule:* Exclude domestic violence and sensitive personal offenses from automated dispatch scoring to prevent victim-stigmatizing algorithmic surveillance.

### C. India-Specific Feature Engineering (24 Candidate Features)

```
+---------------------------------------------------------------------------------------+
|                       INDIA-SPECIFIC FEATURE PIPELINE                                 |
+--------------------------+------------------------------------------------------------+
| Feature Group            | Candidate Variables                                        |
+--------------------------+------------------------------------------------------------+
| 1. Jurisdictional Lags   | Lag 1 shift count, Lag 2 shifts, Lag 24h count,            |
|                          | Lag 7d same-shift count, 28-day rolling average.           |
| 2. Spatial Contiguity    | Adjacent Police Station Lag (Sum of incidents in shared-   |
|                          | border police stations during shift t).                    |
| 3. Temporal & Diurnal    | Shift type (Day, Evening, Night), Day of week, Weekend.    |
| 4. Calendar & Festivals  | Indian Public Holiday flag, Major Festival Indicators      |
|                          | (Ganesh Festival, Diwali, Navratri, Eid, Dr. Ambedkar      |
|                          | Jayanti) — times of extreme crowd density and market surges|
| 5. Meteorological Shock  | Extreme Rainfall indicator (IMD alert: >65mm/day),         |
|                          | Monsoon season flag (June–September) — critical in Mumbai  |
|                          | waterlogging and Pune transport halts.                     |
| 6. Morphological Priors  | Commercial hub indicator, Major Railway Station presence   |
|                          | (e.g., Pune Junction, Shivaji Nagar, Dadar, CSMT),         |
|                          | Slum cluster share (% slum population in jurisdiction).    |
+--------------------------+------------------------------------------------------------+
```

### D. Baseline Hierarchy & Model Selection
1. **Baseline 1 — Jurisdictional Spatial Prior (Empirical Bayes):**
   Estimates risk strictly from historical police station frequency:
   $$\hat{p}_{i}^{\text{spatial}} = \frac{k_i + m \cdot \bar{p}}{n_i + m}$$
   where $k_i$ is historical incidents in station $i$, $n_i$ is historical shifts, and $m=5.0$ is the shrinkage prior.
2. **Baseline 2 — Time-Aware Expanding Historical Baseline:**
   Dynamically aggregates observations strictly preceding shift $t$ ($t' < t$) to verify stationarity.
3. **Baseline 3 — Shift-Diurnal Historical Baseline:**
   Empirical rate segmented by `(police_station, shift_type, is_weekend)`.
4. **Candidate Model — Calibrated CatBoost Classifier:**
   - Gradient boosted decision trees using the 24 Indian features.
   - Categorical features: `police_station_id`, `police_zone`, `shift_type`.
   - Loss: Binary Logloss with early stopping on validation split.
   - Calibration: Monotonic Isotonic Regression or Platt Scaling fitted strictly on validation predictions.

### E. Partitioning & Evaluation Integrity
- **Chronological Split:**
  - Training Set (65%): e.g., 2018–2022
  - Validation Arena (15%): e.g., 2023
  - Frozen Holdout Test Set (20%): e.g., 2024
- **Operational Ranking Metric:** Top-$k$ Precision per shift (e.g., Precision@3 for Pune across 33 stations; Precision@10 for Mumbai across 94 stations).
- **Probability Metrics:** Brier score, Expected Calibration Error (ECE < 0.03), Log Loss.

### F. Explicit Insufficient-Data Architecture
The backend must enforce strict dataset provenance gating:
```python
if location.city in ["Mumbai", "Pune"]:
    if not local_model_available(location.city):
        return {
            "coverage_status": "unsupported",
            "risk_probability": None,
            "risk_score_100": None,
            "reason": f"Local spatio-temporal model for {location.city} is not yet trained or evaluated. "
                      "Strata Risk does not fabricate synthetic forecasts or transfer foreign model weights."
        }
```

---

## 4. Task 4: City Selection Recommendation & Institutional Access Roadmap

### Final Recommendation: PUNE CITY as the Recommended First Partner

Neither city currently possesses public data to permit deployment today. However, for an institutional pilot partnership, **Pune City is decisively recommended over Mumbai**.

```
+-----------------------------------------------------------------------------------------+
|                  WHY PUNE IS RECOMMENDED OVER MUMBAI AS FIRST CITY                     |
+----------------------------+-----------------------------+------------------------------+
| Factor                     | Greater Mumbai              | Pune City (RECOMMENDED)      |
+----------------------------+-----------------------------+------------------------------+
| Administrative Scale       | 94 Police Stations (Complex)| 33 Police Stations (Tractable|
| Jurisdiction Boundaries    | Dense, multi-corridor,      | Contained river basin, clear |
|                            | extreme island-city layout  | ring road arterial structure |
| Municipal Data Culture     | MCGM portal fragmented      | Active PMC Open Data Store   |
| Police Tech Precedents     | Massive CCTV network        | "My Safe Pune" Mobile Patrol |
| Academic Precedents        | Limited published GIS data  | Multiple published GIS/FIR   |
|                            |                             | studies with CoP support     |
+----------------------------+-----------------------------+------------------------------+
```

### Strategic Rationale for Pune:
1. **Tractable Operational Granularity:**
   Evaluating 33 police station jurisdictions allows a cleaner, statistically reliable top-3 or top-4 operational dispatch ranking protocol ($k=3$ out of 33 corresponds to the top ~10% high-risk stations). Mumbai’s 94 stations present high spatial fragmentation and boundary border-effect noise.
2. **Existing Municipal Data Infrastructure:**
   Pune Municipal Corporation maintains an active open data repository (`opendata.pmc.gov.in`) providing GIS electoral ward boundaries, road networks, and civic infrastructure in GeoJSON/KML format. These civic layers provide rich contextual priors for environmental crime modeling.
3. **Police Innovation Precedent:**
   The Pune City Police has historically piloted tech-driven initiatives, including the *"My Safe Pune"* geotagged patrol monitoring system and dynamic beat deployment.

---

## 5. Institutional Access Roadmap (How to Obtain Real Data)

To transition Strata Risk from research to production in Pune or Mumbai, the project team must execute the following institutional access protocol:

```
                    INSTITUTIONAL DATA ACCESS WORKFLOW
                    
  1. Stakeholder Engagement
     └── Submit formal research proposal to Office of Commissioner of Police (CoP)
     └── Target: Additional Commissioner of Police (Crime / Admin) & State Home Dept.
  
  2. Data Governance & Legal Framework
     └── Sign institutional Non-Disclosure Agreement (NDA) & Memorandum of Understanding (MoU)
     └── Anonymization protocol compliant with Digital Personal Data Protection Act (DPDPA 2023)
  
  3. CCTNS Data Extraction Specification
     └── Query: Registered FIRs across 33 Pune Police Stations (2018–2025)
     └── Fields: FIR Number (Hashed), Date/Time of Incident, Date/Time of Registration,
                 Police Station ID, Beat/Chowki ID, Place of Occurrence (Text),
                 IPC / BNS Section Codes, Accused Known Flag (Binary)
     └── Mandatory Filter: EXCLUDE victim/complainant names, phone numbers, exact addresses,
                           and all Section 376 / POCSO records (per SC guidelines).
  
  4. Geospatial Harmonization
     └── Map police beat narratives to OpenStreetMap / PMC ward polygon lattice.
     └── Validate baseline frequency across 33 stations.
  
  5. Local Model Training & Validation
     └── Train CatBoost forecaster using strictly 2018–2023 data.
     └── Evaluate frozen holdout on 2024 test shifts.
     └── Certify operational precision against historical spatial baseline.
```

---

## 6. Current System Integrity & Production Boundaries

In strict compliance with audit and engineering guidelines:
1. **Production Code & Artifacts Unchanged:**
   - Deployed calibrator: `backend/artifacts/calibrator.joblib`
   - Hash: `SHA256: 8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` (**Verified Unaltered**)
   - Deployed CatBoost model: `backend/artifacts/forecaster_catboost.cbm` (**Verified Unaltered**)
2. **Chicago Model Preserved:**
   The live application continues serving calibrated Chicago predictions with complete training-serving parity.
3. **Indian Location Behavior:**
   Queries for Mumbai (`19.0760, 72.8777`), Pune (`18.5204, 73.8567`), or other Indian cities continue returning honest, structured fallback responses (`coverage_status: "unsupported"`, `risk_probability: None`), preventing fabricated risk outputs.
4. **Regression Test Suite:**
   All 56 automated backend tests, TypeScript typechecks, ESLint rules, and Vite production bundle builds pass with zero errors.

---

## 7. Summary Conclusion

| Assessment Area | Status / Finding |
| :--- | :--- |
| **Public Incident-Level Data (Mumbai)** | **UNAVAILABLE** (Only annual/monthly aggregate tables exist). |
| **Public Incident-Level Data (Pune)** | **UNAVAILABLE** (Only civic municipal data and annual totals exist). |
| **Can Mumbai/Pune be Deployed Today?** | **NO.** Declaring support without local data violates empirical integrity. |
| **Recommended Pilot City** | **PUNE CITY** (via institutional MoU with Commissioner of Police). |
| **Target Administrative Unit** | **33 Police Station Jurisdictions** (8-hour operational shifts). |
| **Next Step** | Formal partnership outreach for anonymized CCTNS extract. |
