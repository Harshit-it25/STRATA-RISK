# STRATA RISK — INSTITUTIONAL DATA REQUEST PACKAGE (PHASE 7.4)
**Authorized Police Incident Data Request, Governance Specification, and Technical Ingestion Contract**

> [!WARNING]
> **DRAFT — SUBJECT TO INSTITUTIONAL, LEGAL, AND PRIVACY APPROVAL**
> This document package constitutes a formal research proposal and technical data contract submitted for institutional consideration.
> **No Memorandum of Understanding (MoU), data-sharing agreement, cryptographic key, or police database authorization currently exists.**
> Do not represent, imply, or interpret this draft as an executed or active agreement.
> Pune and Mumbai remain strictly **UNSUPPORTED** in the Strata Risk operational application (`is_validated = False`, zero models trained, zero live forecasts exposed).

---

## Document Identification & Administrative Metadata

- **Document Title**: Formal Data-Access Request and Technical Ingestion Specification for Public Safety Risk Analytics
- **Addressed Authority**: Office of the Commissioner of Police, Pune City Police Commissionerate
- **Jurisdiction**: Pune City, Maharashtra, India
- **Applicable Statutory Framework**:
  - Digital Personal Data Protection Act (DPDPA), 2023 (subject to formal review of Section 17 Research & Statistical Exemption provisions by institutional legal counsel)
  - Bharatiya Nyaya Sanhita (BNS), 2023 / Indian Penal Code (IPC), 1860
  - Information Technology Act, 2000 & IT (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011
  - Maharashtra Police Act, 1951
- **Current Document Status**: `DRAFT — SUBJECT TO INSTITUTIONAL, LEGAL, AND PRIVACY APPROVAL`
- **Application Readiness State**: `NO_DATA` / `STAGE_0_UNAUTHORIZED`

---

## 1. Formal Data-Request Cover Letter

```text
[TO BE PRINTED ON OFFICIAL INSTITUTIONAL LETTERHEAD — DRAFT SUBMISSION FOR REVIEW]

Date: [DD/MM/YYYY]
Reference: REQ/STRATA/PUNE-COP/2026/001-DRAFT

To,
The Commissioner of Police,
Office of the Commissioner of Police,
Pune City Police Commissionerate,
2, Sadhu Vaswani Road, Camp,
Pune, Maharashtra 411001.

Subject: Formal Research Data-Access Request for Historical Pseudonymized Incident Records (CCTNS) 
         and Operational Reporting Metadata for Public Safety Risk Modeling Feasibility Research

Respected Commissioner of Police,

We respectfully submit this formal research data request to explore the technical, statistical, 
and operational feasibility of calibrated spatio-temporal public safety risk modeling within 
the jurisdiction of the Pune City Police Commissionerate.

1. PROJECT PURPOSE & RESEARCH SCOPE
Strata Risk is a non-commercial, academic and operational research initiative focused on developing 
transparent, interpretable, and mathematically calibrated risk assessment engines. The primary 
objective is to assist municipal police leadership in objective, evidence-based patrol resource 
allocation and shift scheduling, preventing overburdening of station personnel while ensuring public 
safety responsiveness.

Our modeling framework strictly operates on aggregate administrative units (police station jurisdictions 
and 4-hour operational shifts). The system is mathematically decoupled from individual citizen surveillance, 
suspect tracking, automated charging, or predictive policing directed at individuals or protected communities.

2. PROPOSED FORECASTING UNIT
All predictive signals and statistical evaluations are formulated strictly at the following unit of analysis:
    Police Station Jurisdiction × Four-Hour Operational Shift
in Indian Standard Time (Asia/Kolkata, UTC+05:30), partitioning each calendar day into six uniform shifts:
    - Shift 0: [00:00:00, 04:00:00) IST (Night / Early Morning Shift)
    - Shift 1: [04:00:00, 08:00:00) IST (Dawn / Early Patrol Shift)
    - Shift 2: [08:00:00, 12:00:00) IST (Late Morning / Midday Shift)
    - Shift 3: [12:00:00, 16:00:00) IST (Afternoon Operational Shift)
    - Shift 4: [16:00:00, 20:00:00) IST (Evening Peak Transit Shift)
    - Shift 5: [20:00:00, 24:00:00) IST (Night Patrol Shift)

3. REQUESTED HISTORICAL DATA COVERAGE
To evaluate multi-year seasonal stability, monsoon cycles, and the statutory transition from the 
Indian Penal Code (IPC) to the Bharatiya Nyaya Sanhita (BNS) enacted on July 1, 2024, we respectfully request:
    - Historical Coverage Target: Approximately 36 continuous months (~1,080 calendar days) of historical 
      incident observations covering the 33 recognized police stations of the Pune City Commissionerate.
    - Alternative Provisional Coverage: If a 36-month extract requires extended administrative clearance, 
      a provisional 6-month historical extract (~180 days) to conduct initial exploratory data analysis (EDA), 
      data flow auditing, and reporting completeness verification.
    - Note on Historical Coverage vs Retention: This historical coverage requirement describes the backward 
      temporal span of observations requested. It does not dictate how long received data files will be retained 
      post-transfer. Post-acquisition retention is governed by a distinct proposed schedule subject to your 
      formal approval.

4. STRICT PRIVACY & DATA MINIMIZATION COMMITMENTS
We emphasize our unconditional commitment to data minimization under the DPDPA 2023:
    - ZERO CITIZEN PERSONAL DATA: We do NOT request, and our ingestion pipeline mathematically rejects, 
      complainant names, victim identities, suspect/accused names, witness details, contact phone numbers, 
      residential door addresses, email addresses, or national identification numbers (Aadhaar, PAN, Voter ID).
    - CRYPTOGRAPHIC PSEUDONYMIZATION: FIR registration numbers must be replaced by a one-way salted 
      SHA-256 hash prior to extract transfer.
    - COORDINATE TRUNCATION: Where spatial coordinates are provided, latitude and longitude must be 
      truncated to 3 decimal places (~111-meter precision), preventing micro-locational re-identification.
    - SECURE RESEARCH ENCLAVE: All processing will occur on offline, encrypted, access-controlled research 
      systems physically localized within the Republic of India. No commercial monetization, public API exposure, 
      or automated tactical dispatch will occur.

5. TECHNICAL DELIVERABLES REQUESTED
As detailed in the attached Technical Specification, our research framework requests:
    - Anonymized/pseudonymized historical incident records (CSV or Parquet format).
    - Station operational downtime and transmission logs (to verify reporting coverage).
    - Official GIS jurisdictional boundary polygons for the 33 police stations.
    - Cryptographic authorization manifest binding the extract's SHA-256 digest with your Ed25519 verification key.

We recognize that certain requested fields (e.g. precise geocodes or central database synchronization timestamps) 
may not be recorded or available in your existing CCTNS systems. Our data intake pipeline is specifically 
architected to handle missing optional fields gracefully without failure.

We remain available to present our technical methodology to your technical leadership and to execute a formal 
bilateral Memorandum of Understanding (MoU) containing all necessary governance, audit, and retention terms.

Yours respectfully,

____________________________________________
[Name of Authorized Institutional Signatory]
[Title / Designation, Principal Investigator]
[Institution / University / Research Center Name]
[Official Institutional Email & Contact Details]
```

---

## 2. Proposed Data Dictionary & Field Definitions

The proposed data contract comprises 9 structured fields designed for privacy preservation, reporting auditability, and spatiotemporal aggregation:

| Field Name | Type | Status | Description & Accepted Format | Privacy & Governance Rules |
| :--- | :--- | :--- | :--- | :--- |
| `fir_number_hash` | String (SHA-256) | **Mandatory Core** | One-way salted cryptographic SHA-256 hash of the administrative FIR identifier (64 hex characters). | Raw FIR numbers, ledger sequence IDs, and complainant references strictly excluded. Prevents citizen tracing. |
| `police_station_id` | String | **Mandatory Core** | Lowercase normalized station identifier matching one of Pune's 33 police stations (e.g., `shivajinagar`, `kothrud`, `hadapsar`). | Standard administrative unit. No officer identity, badge number, or chowki beat personnel identifier. |
| `incident_datetime` | ISO 8601 String | **Mandatory Core** | Estimated date and time of incident occurrence (`YYYY-MM-DDTHH:MM:SS`, Asia/Kolkata timezone). | Preserves shift and day-of-week binning. Approximate or rounded for unattended property offenses. |
| `section_code` | String | **Mandatory Core** | Primary penal section under IPC or BNS (e.g., `392`, `379`, `302`, `103`, `309`). | Maps exclusively to aggregated operational harm tiers (violent street harm, property harm). Excludes case diary narratives. |
| `registration_datetime` | ISO 8601 String | **Operational Optional** | Timestamp when FIR was formally registered in station general diary (`YYYY-MM-DDTHH:MM:SS`). | Used to measure human reporting latency ($\Delta t = t_{\text{fir}} - t_{\text{incident}}$) and enforce anti-leakage lag bounds. |
| `system_entry_datetime` | ISO 8601 String | **Operational Optional** | Timestamp when record was synchronized and indexed in central CCTNS database server. | Distinguishes central server indexing latency ($\Delta t_{\text{sync}} = t_{\text{system}} - t_{\text{fir}}$) to verify point-in-time feature validity. |
| `place_of_occurrence` | String | **Operational Optional** | High-level spatial typology code (e.g., `public_road`, `transit_station`, `commercial_market`, `residential_area`). | Scrubbed of specific building names, door numbers, or private property identifiers via automated PII filters. |
| `latitude` | Float | **Spatial Optional** | WGS-84 latitude decimal degree bounded within Pune administrative box ($18.350 \le \text{lat} \le 18.700$). | Truncated to maximum 3 decimal places (~111-meter precision) to prevent residential address identification. |
| `longitude` | Float | **Spatial Optional** | WGS-84 longitude decimal degree bounded within Pune administrative box ($73.650 \le \text{lon} \le 74.100$). | Truncated to maximum 3 decimal places (~111-meter precision). |

---

## 3. Timestamp Quality, Registration Delays, and Availability Bounds

Operational predictive modeling requires mathematically explicit characterization of timestamp semantics:

```
Timeline of a Police Incident Record in CCTNS:
  t_incident                  t_fir                         t_system                    t_forecast
───────●────────────────────────●─────────────────────────────●─────────────────────────────▶
  Occurrence of Offense    Station FIR Logging        CCTNS Central Database        Operational Shift
                           (General Diary Entry)      Indexing & Synchronization    Prediction Horizon
       │                        │                             │
       └── Reporting Latency ───┴── Synchronization Latency ──┘
```

1. **Incident Occurrence Time ($t_{\text{incident}}$):**
   - Estimated moment of incident occurrence.
   - *Limitation:* Frequently approximate or rounded to shift boundaries (e.g., `00:00:00`, `12:00:00`), particularly for unattended theft or nocturnal burglaries.
2. **FIR Registration Time ($t_{\text{fir}}$):**
   - Official administrative timestamp when the FIR was entered into the station register.
   - *Limitation:* Reflects citizen reporting delay and initial verification time. Median and 90th-percentile delays must be quantified.
3. **System Entry / Indexing Time ($t_{\text{system}}$):**
   - Timestamp when the record became indexed and queryable in central Commissionerate database servers.
   - *Limitation:* Accounts for offline station periods, batch upload schedules, and network downtime.
4. **Point-in-Time Availability Boundary:**
   - To prevent temporal lookahead leakage, causal predictors for forecast shift $t_{\text{forecast}}$ must strictly satisfy:
     $$t_{\text{system}} \le t_{\text{forecast}}$$
   - **Operational Assumption Disclosure:** If the Commissionerate cannot provide $t_{\text{system}}$ in the export, using $t_{\text{fir}}$ alone as a feature availability cutoff assumes zero central database synchronization delay ($\Delta t_{\text{sync}} = 0$). This assumption must be disclosed in all evaluation reports and cannot be claimed as exact point-in-time availability.
5. **Timestamp Anomaly Handling:**
   - Records with inverted timestamps ($t_{\text{fir}} < t_{\text{incident}}$) or timestamps set in the future represent clerical recording errors; they are flagged and excluded from causal feature construction.
   - Missing timestamps are never silently imputed.

---

## 4. Required Reporting-Coverage Information

A critical principle of empirical incident modeling is: **an empty incident extract does not imply zero crime occurrences.**

```
       CCTNS Records Received for Station S in Shift W = 0
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
Station Reporting Verified                      Station Reporting Unknown / Offline
  ==> Verified Zero Event (Y = 0)                 ==> Unobserved Window (Y = NaN)
```

To prevent fabricating zero-event training labels during station network outages or server synchronization downtime, the institution is requested to supply:
1. **CCTNS Server Transmission Logs:** Daily or hourly transmission heartbeats indicating when each station was actively connected and transmitting incident records.
2. **Station Operational Downtime Records:** Logs of technical outages, power disruptions, or CCTNS client failures at individual police stations.
3. **Jurisdictional Transition Dates:** Official operational activation dates for newly bifurcated stations (specifically *Pashan*, *Bavdhan*, and *Alankar*), indicating the exact date from which each station independently logged FIRs.

If operational transmission logs cannot be provided, the Strata Risk intake pipeline marks all periods lacking positive records as `UNKNOWN_COVERAGE` ($Y = \text{NaN}$) rather than assuming zero events ($Y = 0$).

---

## 5. Official GIS Jurisdictional Boundary Request

To evaluate spatial consistency and support future micro-spatial point modeling, authoritative vector GIS layers are requested:

1. **Official Police Station Jurisdiction Polygons (Vector):**
   - Format: GeoJSON, ESRI Shapefile (`.shp`, `.shx`, `.dbf`, `.prj`), or GeoPackage (`.gpkg`).
   - Coordinate Reference System (CRS): EPSG:4326 (WGS 84) or EPSG:32643 (UTM Zone 43N).
   - Scope: Polygons for all 33 recognized police stations, with verified boundaries for recent bifurcations:
     - *Pashan* Police Station (bifurcated from Chaturshringi)
     - *Bavdhan* Police Station (bifurcated from Hinjawadi / Kothrud)
     - *Alankar* Police Station (bifurcated from Kothrud)
2. **Police Chowki / Beat Patrol Boundaries:** Sub-station administrative divisions.
3. **Major Transportation & Arterial Road Vectors:** Road centerlines for spatial distance metrics.

---

## 6. Privacy Protection, DPDPA 2023 Review, and Residual Risk Disclosure

### 6.1 DPDPA 2023 Statutory Compliance & Legal Assessment Status
- **No Automatic Exemption:** The research team explicitly clarifies that research provisions under Section 17 of the Digital Personal Data Protection Act (DPDPA), 2023 do **NOT** automatically grant exemption. Application of Section 17 requires formal legal review, data protection impact assessment, and institutional sign-off by the Institutional Data Protection Officer (DPO) and Legal Counsel.
- **Automated PII Screening Gate:** The ingestion pipeline executes a 100% automated scan across all columns and string values. Prohibited personal data (names, phone numbers, email addresses, 12-digit Aadhaar numbers, 10-character PAN cards) triggers an immediate fail-closed pipeline abort.
- **Zero Raw PII in Logs:** Audit manifests and console outputs strictly forbid recording raw citizen identifiers, names, or addresses.
- **Legal Disclaimer:** This technical specification documents software-level controls and data contracts. It does not constitute formal legal advice, statutory certification, or an institutional privacy guarantee.

### 6.2 Residual Privacy, Re-Identification Risks, and Derived-Data Privacy Assessment

> [!IMPORTANT]
> **No Claim of True Anonymization Solely from Identifier Absence:**
> Strata Risk explicitly does NOT claim dataset anonymization merely because direct citizen identifiers (names, addresses, phone numbers) are absent. Data containing pseudonymized IDs, fine-grained timestamps, truncated coordinates, and rare offense codes constitutes **pseudonymized personal data** under DPDPA 2023, subject to residual re-identification and linkage risks.

In accordance with international data protection standards and DPDPA 2023 principles, the residual privacy risks across all data tiers are evaluated:

1. **Pseudonymized FIR Hashes (`fir_number_hash`):**
   - *Status:* Pseudonymized, NOT irreversibly anonymized.
   - *Residual Risk:* If an adversary possesses sequential police station FIR registries ($< 10,000$ FIRs per station-year), precomputed dictionary or rainbow table attacks could invert unsalted or weakly salted hashes.
   - *Implemented Control:* One-way SHA-256 hashing; application code never accesses or stores the private institutional salt.
   - *Institutional Control Requiring Approval:* Institutional DPO review of salting policy and key rotation schedule.

2. **Coordinate Truncation (3 Decimal Places, ~111m):**
   - *Status:* Obfuscated spatial point.
   - *Residual Risk:* While truncation protects exact door numbers, in rural beats or sparsely populated suburban sectors, 111-meter precision combined with public news reports or auxiliary records poses narrow re-identification risks.
   - *Implemented Control:* Enforced 3-decimal rounding (~111m) and bounding box validation ($18.350 \le \text{lat} \le 18.700$, $73.650 \le \text{lon} \le 74.100$).
   - *Institutional Control Requiring Approval:* Institutional decision on whether micro-spatial coordinates are released or replaced with station-only spatial aggregation.

3. **Small-Cell Aggregation & Rare Offense Categories:**
   - *Status:* Spatiotemporal binning risk.
   - *Residual Risk:* Severe violent offenses (e.g., IPC 302 / 307 - homicide, attempt to murder) have low natural frequency ($N \le 1$ in a 4-hour station-window). An observer combining a small cell count ($Y = 1$) with public press coverage can link the statistical event to specific victims or accused persons.
   - *Implemented Control:* High-level mapping into broad operational harm tiers (`violent_street_harm`, `property_harm`, `public_disorder`) rather than publishing raw individual section codes.
   - *Institutional Control Requiring Approval:* Institutional DPO approval of cell-suppression threshold (e.g., suppressing or binning cells where $N < 5$).

4. **Time-and-Location Combinations (Quasi-Identifiers):**
   - *Status:* Combinatorial linkage risk.
   - *Residual Risk:* Combining an exact 4-hour window, station jurisdiction, and offense category creates a unique spatiotemporal signature that can be joined against external administrative or news datasets.
   - *Implemented Control:* Elimination of minute-level precision in aggregated feature representations.
   - *Institutional Control Requiring Approval:* Formal validation of acceptable spatiotemporal granularity by the Institutional Data Governance Committee.

5. **Unstructured Narrative Text (`place_of_occurrence`):**
   - *Status:* Scrubbed via automated regex token filters.
   - *Residual Risk:* Regex scanning intercepts structured tokens (10-digit phones, 12-digit Aadhaar, 10-character PANs), but **cannot guarantee 100% elimination** of contextual identities in unstructured Marathi or English free-text descriptions (e.g., "near Sharma residence").
   - *Implemented Control:* Automated multi-pass regex scanning for Indian PII formats; fail-closed abortion upon detection.
   - *Institutional Control Requiring Approval:* Institutional policy determining whether free-text `place_of_occurrence` should be omitted entirely in favor of predefined categorical typology codes (`public_road`, `transit_hub`, `commercial_market`).

6. **Dataset Fingerprints & Audit Metadata:**
   - *Status:* Permanent provenance metadata.
   - *Residual Risk:* Audit manifests (`intake_audit_manifest.json`) record bitwise SHA-256 fingerprints, station record counts, and category distributions. While these contain zero direct citizen records, station-level rare category totals could theoretically be correlated with annual police blotters.
   - *Implemented Control:* Audit manifests store aggregate category counts across the entire dataset without individual timestamps, names, or micro-locations.
   - *Institutional Control Requiring Approval:* Ratification of permanent retention of non-PII audit manifests post-source deletion.

### 6.3 Governance Boundary: Implemented vs. Approval-Dependent Privacy Controls

| Control Category | Control Description | Implementation Status | Authority Required |
| :--- | :--- | :--- | :--- |
| **Direct PII Scanning** | Multi-pass regex filter for names, phones, Aadhaar, PAN | **Implemented** (Fail-closed in ingestion pipeline) | Operational Verification |
| **Coordinate Truncation** | Rounding to 3 decimal places (~111m precision) | **Implemented** (Pipeline normalization) | Operational Verification |
| **Harm Tier Aggregation** | Mapping 20+ IPC/BNS sections to 3 operational tiers | **Implemented** (`IPC_BNS_CATEGORY_MAP`) | Operational Verification |
| **Station Name Normalization** | Canonical station alias resolution without fuzzy guessing | **Implemented** (33 station whitelist) | Operational Verification |
| **Cryptographic Deletion Tokens** | Ed25519 token bound to version, SHA-256, policy, & expiry | **Implemented** (`verify_deletion_approval_token`) | Operational Verification |
| **Cell Suppression ($N < 5$)** | Suppressing spatiotemporal cells with count $< 5$ | **Proposed / Pending Approval** | Institutional DPO Sign-Off |
| **Narrative Omission** | Replacing free-text `place_of_occurrence` with typology enum | **Proposed / Pending Approval** | Institutional DPO Sign-Off |
| **Institutional Salt Management**| External Commissionerate-managed salt for FIR hashing | **Proposed / Pending Approval** | Commissionerate Technical Team |
| **Post-Acquisition Retention (365d)**| 365-day storage life before mandatory purge | **Proposed / Pending Approval** | Bilateral MoU Execution |
| **Model-Training Data Retention**| Creating and retaining model-training feature matrices | **LOCKED / DISABLED** (Prohibited in Stage 0–3) | Stage 4 Addendum Required |

### 6.4 Proposed Processing Environment
- **Air-Gapped / Isolated Virtual Enclave:** Analysis will take place on dedicated institutional servers with restricted external network egress.
- **Volume Encryption:** Storage volumes encrypted at rest with AES-256.
- **Multi-Factor Authentication (MFA):** Mandatory multi-factor authentication for all authorized researchers.
- **Role-Based Access Control:** Strict role segregation between data governance auditors and modeling engineers.

---

## 7. Data Retention, Storage Tiers, and Deletion Protocol

### 7.1 Historical Coverage vs. Post-Acquisition Retention Schedule
An explicit distinction is maintained between historical observation coverage and post-acquisition data retention:
- **Historical Data Coverage (Proposed Target: ~36 Months / 1,080 Days):** Represents the retrospective time span of past observations requested to assess seasonal cycles and statutory transitions.
- **Post-Acquisition Retention Schedule (Proposed: 365 Calendar Days):** Represents the duration that received files may be retained post-transfer on research infrastructure. **This schedule is strictly PROPOSED and SUBJECT TO INSTITUTIONAL APPROVAL.** The project is not authorized to retain data for 365 days or any other period until formally ratified in the bilateral MoU.

### 7.2 Disaggregated Retention Rules Across Eight Data Categories

Different data categories carry distinct risk profiles and retention lifecycles:

| Data Category | Classification | Proposed Retention Period | Storage Tier | Deletion Authority | Sanitization Standard | Audit Evidence |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Raw Authorized Dataset** | Restricted Source Data | Proposed 365 days post-transfer (Subject to MoU terms) | Encrypted offline research vault (AES-256) | Pune City Police Commissionerate | NIST SP 800-88 Rev. 1 compliant overwrite / media sanitization | Certificate of Data Sanitization with raw SHA-256 |
| **2. Cleaned Incident Dataset** | Derived Pseudonymized Research Data | Synchronized with raw dataset retention | Versioned directory with application overwrite protection | Institutional Data Governance Committee & Police Authority | Secure file unlinking & volume wipe | Signed Destruction Log with cleaned SHA-256 |
| **3. Temporary Processing Files** | Ephemeral System Scratch | 0 days (Purged immediately upon pipeline completion) | Local in-memory / temporary scratch buffer | Automated pipeline lifecycle | Immediate unlinking and buffer purge | Pipeline execution confirmation log |
| **4. Intermediate Analytical Datasets** | Exploratory Intermediates | Duration of active exploratory analysis only | Isolated research enclave volume | Lead ML Engineer / Governance Officer | Secure directory purge prior to version archiving | Cleaned version archive manifest |
| **5. Aggregated Statistical Reports** | Non-PII Research Output | Permanent (Contains zero citizen records, names, or FIRs) | Standard project documentation repository | N/A (Academic & governance record) | N/A (Aggregated metrics only) | Permanent Git-tracked report |
| **6. Model-Training Datasets** | Future Training Data | **LOCKED / DISABLED (0 days)** | N/A (Prohibited in Stage 0–3) | N/A (Requires Stage 4 MoU addendum) | N/A | N/A |
| **7. Audit Manifests & Integrity Records** | Permanent Integrity Provenance | Permanent (Retained post-deletion for accountability) | Versioned intake directory | Never purged (Essential legal audit trail; zero PII) | N/A (Hashes, schemas, counts only) | Permanent intake audit manifest |
| **8. Backups & Recoverable Copies** | Disaster Recovery Archive | Synchronized strictly with raw dataset retention | Encrypted backup media (AES-256) | Institutional Chief Information Security Officer (CISO) | NIST SP 800-88 Rev. 1 media destruction / purge | Backup Purge Certificate |

### 7.3 Deletion, Sanitization, and Decommissioning Procedures
- **Deletion Authority:** Data deletion is authorized jointly by the Office of the Commissioner of Police, Pune City, and the Institutional Data Governance Committee.
- **Trigger Events:** Deletion becomes mandatory upon: (a) expiration of the approved retention window, (b) formal revocation of authorization, or (c) completion of the research project.
- **Scope of Deletion:** All raw extracts, cleaned datasets, temporary files, derived intermediate features, and associated backup media must be purged.
- **Sanitization Mechanism Clarification:**
  - On standard operating system filesystems, application deletion unlinks files from the filesystem table.
  - True cryptographic erasure or secure multi-pass overwriting requires underlying full-disk encryption with key destruction or dedicated hardware media shredding (NIST SP 800-88 Rev. 1).
  - The project does NOT implement an automated background deletion daemon. Real dataset deletion is a human-supervised, multi-signature administrative procedure requiring manual operator verification and written confirmation.
- **Post-Deletion Retained Metadata:** To preserve scientific integrity and legal auditability, intake audit manifests (`intake_audit_manifest.json`) containing cryptographic digests, schema versions, aggregate row counts, and sanitization certificates are retained permanently. These manifests contain zero citizen records or personal identifiers.

---

## 8. Data Provenance and Cryptographic Authorization Requirements

Every dataset delivered by the Commissionerate must be accompanied by an authentic **RFC 8785 JSON Canonicalization Scheme (JCS) Authorization Manifest** cryptographically signed using the Commissionerate's private Ed25519 signing key:

```json
{
  "manifest_version": "2.1",
  "authorization_id": "AUTH-PUNE_COP-2026-001",
  "mou_reference": "MOU/PUNE-COP/2026/STRATA-001",
  "issuing_authority": "Office of Commissioner of Police, Pune City",
  "issuer_id": "pune_city_police_cop",
  "issued_at": "2026-01-01T00:00:00Z",
  "valid_from": "2026-01-01T00:00:00Z",
  "valid_until": "2027-12-31T23:59:59Z",
  "is_authorized": true,
  "is_revoked": false,
  "is_fixture": false,
  "permitted_use": "public_safety_risk_modeling",
  "permitted_fields": [
    "fir_number_hash", "police_station_id", "incident_datetime",
    "section_code", "registration_datetime", "system_entry_datetime",
    "place_of_occurrence", "latitude", "longitude"
  ],
  "dpdpa_compliance_certified": true,
  "retention_schedule_days": 365,
  "dataset_fingerprint": {
    "expected_sha256": "<SHA256_HEX_DIGEST_OF_DELIVERED_DATASET_FILE>",
    "binding_enforced": true
  },
  "signature_algorithm": "ed25519",
  "signature": "<64_BYTE_ED25519_HEX_SIGNATURE>"
}
```

### Cryptographic Guarantees:
1. **Asymmetric Key Isolation:** The Pune City Police Commissionerate retains its private signing key. The Strata Risk application receives only the public verification key via environment variable (`PUNE_COP_ED25519_PUBLIC_KEY`). The application cannot sign or forge authorization manifests.
2. **Canonical Serializer (RFC 8785):** Guarantees bitwise deterministic serialization across operating systems and programming languages.
3. **Dataset Fingerprint Binding:** The SHA-256 hash of the delivered dataset is cryptographically bound into the signed payload. Any byte-level alteration of the dataset immediately invalidates the signature.
4. **Certificate Revocation List (CRL):** Authoritative revocation checks evaluate sequence freshness and revocation status before any data processing.

---

## 9. Expected Technical Deliverables from the Institution

The project team requests the following formal technical deliverables upon institutional approval:

| Deliverable ID | Technical Deliverable | Accepted Formats | Criticality |
| :--- | :--- | :--- | :--- |
| **DEL-01** | Historical Incident Extract | CSV (UTF-8) or Apache Parquet | **Mandatory** |
| **DEL-02** | Signed Cryptographic Authorization Manifest | JSON (`.auth.json`) signed with Ed25519 | **Mandatory** |
| **DEL-03** | Commissionerate Ed25519 Public Verification Key | 32-byte Raw Hex String via Secure Channel | **Mandatory** |
| **DEL-04** | Official Police Station GIS Jurisdictional Boundaries | GeoJSON, Shapefile, or GeoPackage | Highly Recommended |
| **DEL-05** | Station Operational & CCTNS Transmission Logs | CSV or Structured Text Logs | Highly Recommended |
| **DEL-06** | Historical Jurisdictional Reorganization Timeline | PDF or Structured Table | Recommended |

*Acknowledgment of Data Constraints:* The research team explicitly recognizes that the Commissionerate may not maintain or release every optional deliverable. The Strata Risk ingestion pipeline is designed with graceful degradation: station-level modeling proceeds if coordinates are absent, and latency assumptions are formally documented if central system-entry timestamps are unrecorded.

---

## 10. Methodological Classification of Operational Thresholds

To maintain empirical rigor, all numerical thresholds enforced by the Strata Risk intake gate are explicitly classified:

| Threshold Parameter | Value | Methodological Classification | Scientific & Governance Rationale | Limitations & True Sufficiency Rules |
| :--- | :--- | :--- | :--- | :--- |
| **`training_timespan_days`** | 1,080 days (36 mo) | **Policy Requirement** | Captures multi-year seasonality (monsoons, festivals) and supports non-overlapping train/val/test splits. | Gross timespan does not guarantee statistical sufficiency if data is fragmented. |
| **`eda_timespan_days`** | 180 days (6 mo) | **Operational Heuristic** | Pragmatic initial window to audit data flow, missingness, and registration delay distributions. | Insufficient to capture full annual cycles; purely exploratory. |
| **`station_coverage_pct`** | 80.0% (26/33 stations) | **Operational Heuristic** | Enforces city-wide jurisdictional breadth to prevent localized samples from being overgeneralized. | Aggregate coverage alone does not ensure uniform statistical power; central stations may mask suburban gaps. |
| **`training_min_target_positives`** | 100 events | **Operational Heuristic** | Pragmatic initial floor to discard severely depleted extracts. | **Arithmetic & Theoretical Sparsity:** 100 events across 33 stations over 3 years (1,095 days) equates to $100 / (33 \times 3) \approx 1.01$ events per station-year. In a theoretical 4-hour spatiotemporal lattice ($33 \times 6 \times 1,095 = 216,810$ theoretical station-windows, not observed Pune data), 100 distinct positive windows represent approximately **0.046%** of theoretical window capacity. This theoretical calculation highlights extreme sparsity; 100 events is an operational heuristic that does NOT establish statistical sufficiency by itself. Support and reporting completeness must be empirically evaluated per station and shift. |
| **`eda_min_target_positives`** | 20 events | **Operational Heuristic** | Floor to prevent evaluating completely empty positive classes during exploratory analysis. | Wholly inadequate for statistical estimation or model training. |
| **`min_coordinate_completeness_pct`** | 90.0% | **Policy Requirement** | Guards against suburban and socio-economic selection bias prior to micro-spatial modeling. | Station-level modeling remains valid if coordinates fall below this threshold. |

> [!CRITICAL]
> **Statistical Sufficiency Notice:** Gross record counts and aggregate station coverage **do not establish statistical sufficiency by themselves**. All future evaluations must report positive event support and reporting completeness broken down by individual police station and operational time shift.

---

## 11. Contact, Governance, and Approval Sign-Off Fields

Before submission to Pune City Police, this package must be completed and signed by the institutional project team:

### 11.1 Project Leadership & Principal Investigator
- **Principal Investigator Name**: __________________________________________________
- **Institutional Designation**: __________________________________________________
- **Department / Faculty**: __________________________________________________
- **Institution Name**: __________________________________________________
- **Official Email**: __________________________________________________
- **Signature & Date**: __________________________________________________

### 11.2 Data Governance & Privacy Officer
- **Officer Name**: __________________________________________________
- **Designation**: __________________________________________________
- **DPDPA 2023 Assessment Completed**: [ ] YES  [ ] PENDING
- **Signature & Date**: __________________________________________________

### 11.3 Institutional Legal Counsel
- **Counsel Name / Firm**: __________________________________________________
- **Draft MoU Terms Reviewed**: [ ] YES  [ ] PENDING
- **Signature & Date**: __________________________________________________

### 11.4 Information Security Officer (CISO)
- **CISO Name**: __________________________________________________
- **Enclave Security Audit Certified**: [ ] YES  [ ] PENDING
- **Signature & Date**: __________________________________________________

---

## 12. Next Immediate Action

> [!IMPORTANT]
> The next real-world action required to advance this initiative is **formal institutional review of this package followed by submission to the Office of the Commissioner of Police, Pune City**.
> Until an executed bilateral MoU and authentic cryptographic credentials are provided, all Pune models, training pipelines, and deployment endpoints remain strictly **DISABLED**.
