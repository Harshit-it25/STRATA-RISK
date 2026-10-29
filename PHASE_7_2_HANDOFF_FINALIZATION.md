# STRATA RISK — PHASE 7.2
## INSTITUTIONAL HANDOFF DOCUMENTATION FINALIZATION REPORT

**Date:** 2026-10-12  
**Audit Scope:** Institutional Request Document Finalization, Audit Manifest Terminology Rectification, Data-Readiness Threshold Classification, Timestamp Quality & Availability Bounds, External Dependency Preservation, and Production Artifact Invariance.  
**System Status:**
- **Chicago Live Forecasting:** **SUPPORTED & OPERATIONAL** (Bit-identical model, calibrator, and metadata artifacts).
- **Pune Candidate Pilot:** **UNSUPPORTED** (Data acquisition preparation only; zero model trained; zero forecasts served).
- **Mumbai Candidate Pilot:** **UNSUPPORTED** (Zero model trained; zero weights transferred).

---

## 1. EXECUTIVE SUMMARY

Phase 7.2 finalizes the institutional handoff documentation and reconciles all remaining language, security, and statistical discrepancies across the Strata Risk repository. This phase performs a comprehensive documentation and consistency pass prior to external institutional review:

1. **Audit Manifest Terminology Corrected:** Eliminated unqualified claims of "immutable audit manifests." The documentation now precisely distinguishes between hash-based integrity checking, digital signatures, application-level overwrite protection, and true hardware/cloud Write-Once-Read-Many (WORM) storage.
2. **Operational Thresholds Methodologically Classified:** Classified every numerical threshold enforced by the intake gate into Policy Requirements, Operational Heuristics, or Statistically Justified Criteria. Explicitly recorded that **gross incident volume and aggregate station coverage do not establish statistical sufficiency by themselves**.
3. **Timestamp Quality & Point-in-Time Availability Clarified:** Established explicit semantic definitions for incident occurrence time, FIR registration time, and central system-entry time. Prohibited claiming ground-truth point-in-time availability when source database synchronization timestamps are absent.
4. **Institutional Dependencies & Legal Disclaimers Preserved:** Clearly marked all legal, privacy, retention, and data-access decisions as requiring formal institutional approval. Explicitly stated that **no Memorandum of Understanding (MoU), institutional signing key, or authorized Pune incident dataset currently exists**.
5. **Full Regression Protection Verified:** Executed the complete backend pytest suite (196 tests passed, 0 warnings), TypeScript compiler check (`npx tsc --noEmit`), linter (`npm run lint`), and production build (`npm run build`). Verified that Chicago production model artifacts remain 100% bit-identical to canonical SHA-256 baselines.

---

## 2. SECTION 1: AUDIT OF HANDOFF DOCUMENTS & TERMINOLOGY RECTIFICATION

### 2.1 Documents Audited
The documentation audit inspected:
- [`INSTITUTIONAL_DATA_REQUEST_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/INSTITUTIONAL_DATA_REQUEST_PACKAGE.md)
- [`PHASE_6_AUTHORIZED_DATA_ACQUISITION_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_6_AUTHORIZED_DATA_ACQUISITION_PACKAGE.md)
- [`PUNE_AUTHORIZED_DATA_INTAKE_AND_READINESS.md`](file:///c:/Users/harsh/Downloads/strata-risk/PUNE_AUTHORIZED_DATA_INTAKE_AND_READINESS.md)
- [`PHASE_7_PUNE_DATA_EXPLORATION_REPORT.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_7_PUNE_DATA_EXPLORATION_REPORT.md)
- [`PHASE_7_1_INSTITUTIONAL_HANDOFF.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_7_1_INSTITUTIONAL_HANDOFF.md)

### 2.2 Rectification of Audit Manifest Terminology
Earlier drafts frequently described the intake audit manifest (`intake_audit_manifest.json`) as "immutable." In Phase 7.2, this terminology was formally corrected across [`INSTITUTIONAL_DATA_REQUEST_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/INSTITUTIONAL_DATA_REQUEST_PACKAGE.md#L214-L225) and [`PHASE_7_1_INSTITUTIONAL_HANDOFF.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_7_1_INSTITUTIONAL_HANDOFF.md#L140-L162).

The implementation guarantees are now explicitly stratified into four technical tiers:

| Security & Storage Tier | Implementation Mechanism in Strata Risk | Guarantee Provided | Boundary / Threat Model Limitation |
| :--- | :--- | :--- | :--- |
| **1. Hash-Based Integrity Checking** | SHA-256 hashing of raw input and cleaned output files recorded in audit manifests. | Detects accidental byte-level corruption or file modification. | Does not prevent an attacker from modifying both the file and the hash simultaneously if storage is writable. |
| **2. Cryptographic Digital Signatures** | Asymmetric Ed25519 digital signatures (RFC 8032) evaluated over RFC 8785 canonical JSON bytes. | Mathematically binds the dataset fingerprint to the institutional authority (Pune City Police CoP). | Guarantees origin authenticity and tamper-evidence of the manifest, but does not prevent deletion of the file on disk. |
| **3. Application-Level Overwrite Protection** | Versioned directory creation checks (`raise FileExistsError`) in [`ingest_authorized_dataset`](file:///c:/Users/harsh/Downloads/strata-risk/backend/ingestion/pune_ingestion_pipeline.py#L750-L770). | Prevents software re-runs from silently replacing or mutating previous intake records. | Enforced by application logic only. Operating system administrators, root users, or external scripts can still overwrite files on standard filesystems. |
| **4. Physical / Hardware WORM Immutability** | Dedicated Write-Once-Read-Many media, AWS S3 Object Lock in Compliance Mode, or Azure Immutable Storage. | Prevents any user (including root/administrator) from deleting or altering audit records until retention expiry. | **Not configured on standard developer workstations or local test environments.** Must be provisioned by institutional cloud infrastructure. |

---

## 3. SECTION 2: METHODOLOGICAL CLASSIFICATION OF DATA-READINESS THRESHOLDS

All numerical thresholds enforced by the intake readiness gate ([`PuneThresholdConfig`](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/pune_data_readiness.py#L197-L255)) have been reviewed and classified:

### 3.1 Threshold Classification Matrix

| Threshold Parameter | Configured Value | Formal Methodological Classification | Scientific & Governance Justification | Empirical Limitations & True Sufficiency Requirements |
| :--- | :--- | :--- | :--- | :--- |
| **`training_timespan_days`** | 1,080 days (36 months) | **Policy Requirement** | Required by multi-stage evaluation policy to capture multi-year seasonality (monsoons, annual festivals) and support non-overlapping training (24 mo) and sequestered test holdouts (12 mo). | By itself does not guarantee sufficiency if incident records are sparse, discontinuous, or clustered in narrow intervals. |
| **`eda_timespan_days`** | 180 days (6 months) | **Operational Heuristic** | Pragmatic initial operational window to observe multiple months of data flow, missingness, and registration delay distributions before longitudinal commitment. | Does not capture full annual cycles; purely exploratory. |
| **`station_coverage_pct`** | 80.0% (26 of 33 stations) | **Operational Heuristic** | Enforces city-wide jurisdictional breadth to prevent localized samples from being overgeneralized as city intelligence. | **Aggregate coverage alone does not ensure uniform statistical power.** The 80% threshold can be satisfied by high-volume central precincts while suburban precincts have near-zero reporting. |
| **`training_min_target_positives`** | 100 positive events | **Operational Heuristic** | Traditional machine-learning rule of thumb to discard severely depleted extracts. | **Arithmetic & Theoretical Sparsity Analysis:** 100 positive events across 33 stations over 3 years (1,095 days) represents $100 / (33 \times 3) \approx 1.01$ events per station-year. In a theoretical 4-hour spatiotemporal grid ($33 \text{ stations} \times 6 \text{ windows/day} \times 1,095 \text{ days} = 216,810$ theoretical station-windows, not observed Pune data), 100 distinct positive station-windows represent approximately **0.046%** of theoretical station-window capacity. This calculation is purely theoretical and illustrates extreme sparsity: 100 positive events is an operational heuristic that does **not** establish statistical sufficiency by itself, yielding high metric variance in ROC-AUC/PR-AUC. |
| **`eda_min_target_positives`** | 20 positive events | **Operational Heuristic** | Floor to prevent evaluating completely empty positive classes during exploratory analysis. | Wholly inadequate for reliable statistical estimation or model fitting. |
| **`training_min_records`** | 15,000 records | **Operational Heuristic** | Gross record volume benchmark. | Total volume does not reflect spatiotemporal distribution or reporting completeness. |
| **`eda_min_records`** | 500 records | **Operational Heuristic** | Discards trivial test samples, partial exports, or corrupted database transfers. | Gross record count carries no spatiotemporal granularity. |
| **`min_coordinate_completeness_pct`** | 90.0% | **Policy Requirement** | Protects against suburban and socio-economic selection bias prior to micro-spatial point modeling. | Station-level modeling remains valid if coordinates fall below this threshold. |

### 3.2 Statistical Sufficiency Mandate for Future Reports
> [!IMPORTANT]
> **Core Methodological Invariant:** Gross incident volume and aggregate station coverage **do not establish statistical sufficiency by themselves**.
> 
> When authorized data is delivered, future Phase 7 reports must report:
> 1. Positive target event support broken down by individual police station ($s \in \{1..33\}$) and operational shift ($w \in \{0..5\}$).
> 2. Verified reporting completeness percentages for each individual police station across the full timespan.
> 3. Effective sample sizes under temporal autocorrelation (using moving-block bootstrap or cluster-robust standard errors).

---

## 4. SECTION 3: TIMESTAMP QUALITY, REPORTING DELAYS, AND POINT-IN-TIME AVAILABILITY

### 4.1 Temporal Anatomy of Municipal Police Data
To prevent lookahead leakage in feature engineering, timestamp semantics are explicitly defined:

1. **Incident Occurrence Time ($t_{\text{incident}}$):** Estimated time of incident occurrence.
   - *Quality Limitations:* Often approximate or rounded (e.g. `00:00:00`, `12:00:00`), especially for property theft, night-time house-breaking, or delayed reports where the victim was away.
2. **FIR Registration Time ($t_{\text{fir}}$):** Official administrative timestamp when the FIR was formally entered into the police station general diary or CCTNS ledger.
   - *Quality Limitations:* Subject to human reporting latency ($\Delta t_{\text{reporting}} = t_{\text{fir}} - t_{\text{incident}}$), which can range from minutes (active violent crimes) to days or weeks (financial fraud or unattended theft).
3. **System Entry / Indexing Time ($t_{\text{system}}$):** Timestamp when the record was synchronized, indexed, and made queryable in the central CCTNS database server.
   - *Quality Limitations:* Subject to batch synchronization schedules, station internet downtime, and central server processing delays ($\Delta t_{\text{sync}} = t_{\text{system}} - t_{\text{fir}}$).
4. **Missing Timestamps:** Records lacking $t_{\text{incident}}$ or $t_{\text{fir}}$ cannot support causal feature construction and are quarantined. Timestamps are **never silently imputed**.
5. **Corrected and Anomalous Timestamps:** Records exhibiting inverted timestamps ($t_{\text{fir}} < t_{\text{incident}}$) or future timestamps represent clerical errors. They are flagged and excluded from causal historical predictors.

### 4.2 Point-in-Time Availability Bounds
> [!CRITICAL]
> **Operational Availability Constraint:** True point-in-time causality requires that at forecast timestamp $t$, the feature pipeline only accesses records satisfying:
> $$t_{\text{system}} \le t$$
> If $t_{\text{system}}$ is not recorded or exported in the source CCTNS database, using $t_{\text{fir}}$ alone as a proxy assumes zero database synchronization delay ($\Delta t_{\text{sync}} = 0$).
> 
> Future evaluations must explicitly disclose this assumption and must not claim "exact point-in-time availability" unless true database indexing timestamps are empirically verified.

---

## 5. SECTION 4: PRESERVATION OF UNRESOLVED INSTITUTIONAL QUESTIONS

All legal, privacy, governance, and access decisions are formally designated as requiring external institutional approval:

### 5.1 Institutional & Legal Clearances Requiring Approval
- **Bilateral MoU Execution:** Requires formal negotiation and signing by institutional leadership and the Commissioner of Police, Pune City. **No MoU currently exists.**
- **DPDPA 2023 Research Exemption:** Requires formal review by the Institutional Data Protection Officer to confirm exemption parameters under Section 17 of the Act.
- **Post-Acquisition Retention Schedule:** Approval of the proposed post-acquisition retention schedule (e.g. proposed 365 days) and deletion protocol for received files requires formal institutional consent. (Distinct from retrospective historical coverage of ~36 months).
- **Cryptographic Key Provisioning:** Receipt of the official institutional public verification key (`PUNE_COP_ED25519_PUBLIC_KEY`) via trusted channels. **No production public key is provisioned in the repository.**
- **Authoritative GIS Boundary Shapefiles:** Release of official polygon layers for all 33 stations (specifically including *Pashan*, *Bavdhan*, *Alankar*) requires coordination with Pune Police and Pune Municipal Corporation (PMC).

### 5.2 Explicit Institutional Disclaimer
This documentation pass organizes technical and governance requirements into an auditable handoff package. **It does not imply, represent, or establish that an MoU has been signed, that cryptographic keys have been provisioned, or that an authorized dataset has been received.**

---

## 6. SECTION 5: REGRESSION PROTECTION & ARTIFACT INVARIANCE

### 6.1 Test Suite & Build Verification
The complete test suite and frontend toolchain were executed:
1. **Backend Tests:**
   ```bash
   python -m pytest backend/tests/ -v
   ============================ 196 passed in 16.30s =============================
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
   # vite v8.3.4 built in 526ms (dist output generated cleanly)
   ```

### 6.2 Chicago Production Artifact Hash Invariance
Bit-level SHA-256 cryptographic hashes for the deployed Chicago production models were recalculated:

| Artifact Path | Expected Canonical SHA-256 | Recalculated SHA-256 | Verification Result |
| :--- | :--- | :--- | :--- |
| `backend/artifacts/forecaster_catboost.cbm` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | `8a9ff0ec1d7ef8e5d60eeeca633c40ebab423ce9cad7a241cc45f2beefac4a96` | **BIT-IDENTICAL** |
| `backend/artifacts/calibrator.joblib` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | `8646328a284d513b7db78967bff660ea9a8dd174372da109cf8def3d31c2594d` | **BIT-IDENTICAL** |
| `backend/artifacts/model_metadata.json` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | `b7a3a06ef6b823d0d87e93011e7afcf07710a84ae13d94784761917643eda407` | **BIT-IDENTICAL** |

---

## 7. FINAL CONDITIONS & ATTESTATIONS

1. **Pune and Mumbai Remain Strictly UNSUPPORTED:** Live forecasting remains disabled (`is_validated = False`). No risk scores or predictions are served to users or frontend maps for Indian cities.
2. **Zero Models Trained:** No Pune model has been fitted, trained, or deployed.
3. **Zero Fabricated Records:** No synthetic incidents, coordinates, or station distributions have been manufactured.
4. **Current Status: `NO_DATA` / `STAGE_0_UNAUTHORIZED`:** The project remains at Stage 0 awaiting formal institutional data intake.
5. **Chicago Serving Unaltered:** Chicago live forecasting remains 100% operational with identical production model artifacts, calibrators, and serving APIs.
