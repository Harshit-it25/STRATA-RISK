# STRATA RISK — PUNE DATA ACQUISITION CHECKLIST (PHASE 7.3)
**Comprehensive Intake Governance, Verification Requirements, and Exception Handling Matrix**

> [!WARNING]
> **GOVERNANCE STATUS: DRAFT PENDING INSTITUTIONAL APPROVAL**
> This checklist defines the mandatory technical and legal criteria that must be satisfied before any real-world incident dataset from Pune City Police may be ingested.
> **No institutional approvals, data agreements, cryptographic keys, or authorized datasets currently exist.**
> Pune and Mumbai remain strictly **UNSUPPORTED** in the Strata Risk operational application.

---

## Overview and Audit Purpose

This checklist establishes an auditable, fail-closed verification pipeline for acquiring, evaluating, and ingesting incident records from the Pune City Police Commissionerate. It defines exact evidence standards and system behaviors across ten operational dimensions (Sections A through J).

---

## Section A: Institutional Authorization

### Item A.1: Bilateral Research Memorandum of Understanding (MoU)
- **Why Required:** Establishes the formal legal basis for research data access, defining permitted research purposes, non-commercial restrictions, liability boundaries, and publication rights.
- **Classification:** **Mandatory (Hard Blocker)**
- **Supplying / Approving Authority:** Jointly executed by the Commissioner of Police, Pune City Police Commissionerate, and the Authorized Signatory of the Research Institution.
- **Evidence of Completion:** Countersigned bilateral legal MoU document with institutional seal and registration reference.
- **System Action if Missing:** Complete intake halt. Lifecycle remains at `STAGE_0_UNAUTHORIZED`. No data processing or analysis permitted.

### Item A.2: Institutional Ethics Board / IRB Review
- **Why Required:** Validates public safety algorithmic fairness, protects against discriminatory or disparate impact across socio-demographic groups, and certifies academic research ethics.
- **Classification:** **Subject to Institutional Approval**
- **Supplying / Approving Authority:** Institutional Ethics Review Board / Independent Ethics Committee.
- **Evidence of Completion:** Formal Ethics Approval Certificate or Notice of Exemption citing study protocol ID.
- **System Action if Missing:** Intake blocked pending committee determination.

### Item A.3: Project Charter and Governance Sign-Off
- **Why Required:** Establishes internal accountability, defines named roles (Principal Investigator, Data Protection Officer, Technical Lead), and commits to non-deployment invariants.
- **Classification:** **Mandatory Internal Governance**
- **Supplying / Approving Authority:** Institutional Principal Investigator and Institutional Data Governance Committee.
- **Evidence of Completion:** Executed Project Charter document registered in institutional records.
- **System Action if Missing:** Intake halted.

---

## Section B: Data-Transfer Approval

### Item B.1: Authorized Secure Transfer Channel Agreement
- **Why Required:** Protects incident data in transit against interception, unauthorized reproduction, or eavesdropping.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Information Security Officers of both Pune City Police and Research Institution.
- **Evidence of Completion:** Agreed secure transfer protocol specification (e.g., direct SFTP with public key authentication, physical encrypted media handover with custody log).
- **System Action if Missing:** Rejection of untrusted transfer channels (e.g., unencrypted email, public cloud shares).

### Item B.2: Chain of Custody & Receipt Acknowledgement
- **Why Required:** Documents legal provenance, transfer timestamps, courier/officer identities, and package integrity.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Designated Transfer Officers from Pune City Police and Research Institution.
- **Evidence of Completion:** Signed Chain of Custody Handover Form detailing transfer timestamp, raw file name, file size in bytes, and media serial number.
- **System Action if Missing:** Dataset quarantined; processing disallowed until provenance is attested.

---

## Section C: Incident Dataset Specification

### Item C.1: Mandatory Core Schema Fields
- **Why Required:** Minimum attributes necessary to construct historical spatiotemporal series without identity leakage (`fir_number_hash`, `police_station_id`, `incident_datetime`, `section_code`).
- **Classification:** **Mandatory (Schema Contract)**
- **Supplying / Approving Authority:** Pune Police CCTNS Database Administrator / Export Specialist.
- **Evidence of Completion:** `PuneDataIngestionPipeline.validate_schema` passes with 100% presence of mandatory fields.
- **System Action if Missing:** Pipeline raises `SchemaValidationError` and terminates.

### Item C.2: Temporal Horizon & Continuity
- **Why Required:** Longitudinal volume necessary to model quarterly and seasonal crime variations (monsoons, festivals) without temporal gaps.
- **Classification:** **Policy Requirement** ($\ge 1,080$ days / 36 months for model evaluation; $\ge 180$ days for exploratory analysis).
- **Supplying / Approving Authority:** Pune Police CCTNS Export Specialist.
- **Evidence of Completion:** `PuneDataReadinessAudit.evaluate_readiness` verifies continuous span between min and max valid incident timestamps.
- **System Action if Missing:** Gate returns `INSUFFICIENT_TEMPORAL_COVERAGE`. Dataset rejected for model training; limited to preliminary exploratory auditing if $\ge 180$ days.

### Item C.3: Station Identifier Canonicalization
- **Why Required:** Associates incident records with authoritative municipal jurisdictions across the 33 police stations of Pune City.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Pune Police CCTNS Export Specialist.
- **Evidence of Completion:** 100% of station values mapped to canonical slugs in `PUNE_POLICE_STATIONS` without unmapped silent drops.
- **System Action if Missing:** Unmapped records dropped; if station coverage drops below 80.0% (26 stations), gate returns `INSUFFICIENT_SPATIAL_COVERAGE`.

### Item C.4: Coordinate Range Verification
- **Why Required:** Validates geocoded incident points fall within the official Pune administrative bounding box ($18.350 \le \text{lat} \le 18.700$, $73.650 \le \text{lon} \le 74.100$).
- **Classification:** **Optional for Station-Level; Mandatory for Coordinate-Level**
- **Supplying / Approving Authority:** Pune Police CCTNS / GIS Cell.
- **Evidence of Completion:** Coordinate validation audit reports valid coordinate percentage.
- **System Action if Missing:** Records with missing/out-of-bounds coordinates are retained for station-level modeling, but excluded from micro-spatial analysis. If valid coordinates $< 90\%$, coordinate-level modeling is blocked while station-level modeling remains eligible.

---

## Section D: Station Operational Records

### Item D.1: Station Commissioning and Decommissioning Dates
- **Why Required:** Prevents historical misalignment for newly established or bifurcated stations (e.g. *Pashan*, *Bavdhan*, *Alankar*).
- **Classification:** **Subject to Institutional Supply**
- **Supplying / Approving Authority:** Pune City Police Commissionerate Administration Branch.
- **Evidence of Completion:** Official Government Resolutions (GR) or Commissionerate Office Orders declaring station operational launch dates.
- **System Action if Missing:** Unverified stations are labeled `UNVERIFIED_RECENT_BIFURCATION`; historical windows prior to verified operation are marked `NOT_OPERATIONAL` ($Y = \text{NaN}$).

### Item D.2: Station Jurisdiction Reorganization Log
- **Why Required:** Identifies territorial redistricting (e.g., Chaturshringi territory reassigned to Pashan in 2021) to prevent false trend detection.
- **Classification:** **Optional / Desirable**
- **Supplying / Approving Authority:** Pune City Police Commissionerate.
- **Evidence of Completion:** Jurisdictional gazette notification or administrative boundary shift timeline.
- **System Action if Missing:** Structural break warnings logged; affected stations flagged for sensitivity analysis.

---

## Section E: Reporting-Coverage Evidence

### Item E.1: CCTNS Station Server Transmission Logs
- **Why Required:** Distinguishes genuine zero-crime operational shifts from station offline periods or network server outages.
- **Classification:** **Mandatory for Emitting Zero Labels ($Y = 0$)**
- **Supplying / Approving Authority:** Pune Police CCTNS Technical Directorate / Maharashtra Police Wireless & IT Branch.
- **Evidence of Completion:** Server connection logs, periodic transaction heartbeats, or station transmission status tables.
- **System Action if Missing:** Pipeline enforces `require_coverage_evidence = True`; shifts without positive records are classified as `UNKNOWN_COVERAGE` ($Y = \text{NaN}$) rather than zero incidents ($Y = 0$). Zero-event training labels are never fabricated.

### Item E.2: Station Downtime & Incident Incomplete Extract Markers
- **Why Required:** Identifies known hardware failures, power outages, or data extraction anomalies where records were lost or omitted.
- **Classification:** **Subject to Institutional Availability**
- **Supplying / Approving Authority:** Pune Police CCTNS System Administrator.
- **Evidence of Completion:** Maintenance incident register or downtime schedule.
- **System Action if Missing:** Time windows without verified uptime remain `UNKNOWN_COVERAGE`.

---

## Section F: GIS and Jurisdictional Boundaries

### Item F.1: Authoritative Police Station Jurisdiction Polygons
- **Why Required:** Defines the ground-truth geographic boundaries of the 33 police stations for spatial aggregation and point-in-polygon verification.
- **Classification:** **Mandatory for Spatial Modeling; Optional for Station Aggregate Modeling**
- **Supplying / Approving Authority:** Pune City Police GIS Cell / Pune Municipal Corporation (PMC).
- **Evidence of Completion:** Official vector file (GeoJSON, Shapefile, or GeoPackage) covering all 33 stations with matching attribute identifiers.
- **System Action if Missing:** Readiness gate returns `GIS_MAPPING_INCOMPLETE`. Micro-spatial coordinate modeling is disabled; station-level modeling proceeds independently.

### Item F.2: Police Chowki / Beat Patrol Zone Layers
- **Why Required:** Enables finer sub-station patrol zone spatial analysis.
- **Classification:** **Optional**
- **Supplying / Approving Authority:** Pune City Police Commissionerate.
- **Evidence of Completion:** Sub-station vector boundary layer.
- **System Action if Missing:** Beat-level analysis omitted; station-level remains primary.

---

## Section G: Privacy and Retention Approval

### Item G.1: DPDPA 2023 Section 17 Research Compliance Assessment
- **Why Required:** Legally evaluates whether proposed research processing satisfies statutory conditions under Section 17 of the DPDPA 2023 and establishes whether necessary institutional safeguards against re-identification are satisfied. Research exemption does NOT apply automatically.
- **Classification:** **Mandatory (Subject to Legal & DPO Determination)**
- **Supplying / Approving Authority:** Institutional Data Protection Officer (DPO) and Institutional Legal Counsel.
- **Evidence of Completion:** Formal countersigned DPDPA Compliance Memorandum and Risk Assessment Sign-off.
- **System Action if Missing:** Complete intake halt. Lifecycle remains at `STAGE_0_UNAUTHORIZED`.

### Item G.2: Automated Full-Content PII Screening
- **Why Required:** Enforces automated scanning across 100% of rows and columns for prohibited citizen PII (names, phone numbers, Aadhaar, PAN, private addresses). Acknowledges residual risk in unstructured free-text descriptions.
- **Classification:** **Mandatory (Automated Pipeline Gate)**
- **Supplying / Approving Authority:** Automated `PuneDataIngestionPipeline` PII scanner.
- **Evidence of Completion:** Clean PII audit report across 100% of rows and string columns with 0 violations.
- **System Action if Missing / Failing:** Pipeline raises `PIIViolationError`, halts execution, and immediately purges in-memory records without logging raw citizen values.

### Item G.3: Post-Acquisition Retention Schedule & Cryptographic Deletion Protocol
- **Why Required:** Establishes formal post-acquisition retention boundaries distinct from retrospective historical coverage (~36 months of past crime history vs proposed 365 days post-transfer shelf-life). Disaggregates rules across 8 data tiers (raw, cleaned, temporary, derived, statistical, training, audit manifests, backups).
- **Classification:** **Mandatory (Proposed Schedule Subject to Institutional Ratification)**
- **Supplying / Approving Authority:** Office of the Commissioner of Police, Pune City, and Institutional Information Security Officer (CISO).
- **Evidence of Completion:** Bilateral Data Retention & Sanitization Agreement with explicit decommissioning date, signed approval reference, and cryptographic deletion approval tokens.
- **Cryptographic Deletion Token Requirement:** Real data deletion requires a cryptographically authenticated Ed25519 token bound to action (`AUTHORIZE_DATASET_DELETION`), dataset version, dataset SHA-256 fingerprint, policy reference, and temporal validity window. Arbitrary strings or user-controlled Booleans are strictly rejected. Replayed or revoked tokens fail closed.
- **Failure-Path Cleanup Standard:** Ingestion aborts (PII violation, schema failure, signature mismatch, disk interruption) must rollback and purge partial version directories while strictly preserving authoritative raw data untouched.
- **System Action if Missing / Unapproved:** Real datasets cannot be ingested; automated deletion is strictly disabled (`can_delete_real_data` returns `False`). Real data deletion requires human operator confirmation, institutional sign-off, and cryptographic token verification.

---

## Section H: Cryptographic Authorization Provisioning

### Item H.1: Institutional Ed25519 Public Verification Key Delivery
- **Why Required:** Enables asymmetric verification of delivered authorization manifests without placing the private signing key in the application.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Office of the Commissioner of Police, Pune City.
- **Evidence of Completion:** 32-byte raw hex public verification key securely injected via environment variable (`PUNE_COP_ED25519_PUBLIC_KEY`).
- **System Action if Missing:** `InstitutionalIssuerRegistry` returns `public_key_hex = None`; authorization gate returns `AUTHORIZATION_UNVERIFIED`. Production intake fails closed.

### Item H.2: Signed RFC 8785 Authorization Manifest
- **Why Required:** Cryptographically binds dataset SHA-256 fingerprint, permitted uses, valid dates, and issuing authority in a tamper-evident payload.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Office of the Commissioner of Police, Pune City.
- **Evidence of Completion:** `<dataset_path>.auth.json` containing valid Ed25519 signature over RFC 8785 canonical JSON payload.
- **System Action if Missing / Invalid:** `PuneAuthorizationValidator` returns `is_verified = False`; gate returns `AUTHORIZATION_MISSING` or `AUTHORIZATION_UNVERIFIED`. Intake aborted.

### Item H.3: Certificate Revocation List (CRL) Freshness & Sequence
- **Why Required:** Verifies that the authorization has not been revoked by the Commissionerate prior to processing.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Institutional Security Administrator / Pune Police Authority.
- **Evidence of Completion:** Persistent signed CRL loaded with valid sequence number and unexpired validity timestamp.
- **System Action if Missing / Stale:** If CRL is expired or sequence is rolled back, intake fails closed.

---

## Section I: Data Intake and Integrity Verification

### Item I.1: Bitwise SHA-256 Fingerprint Matching
- **Why Required:** Verifies exact bit-level dataset integrity, proving the file has not been corrupted or tampered with in transit.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Automated `PuneDataIngestionPipeline`.
- **Evidence of Completion:** Recomputed SHA-256 digest matches `manifest["dataset_fingerprint"]["expected_sha256"]` bit-for-bit.
- **System Action if Missing / Mismatch:** Pipeline raises `ValueError` ("Dataset fingerprint mismatch") and aborts.

### Item I.2: Version Directory Overwrite Prevention
- **Why Required:** Prevents accidental re-runs or malicious actors from overwriting historical intake outputs and audit trails.
- **Classification:** **Mandatory (Application Invariant)**
- **Supplying / Approving Authority:** Automated `PuneDataIngestionPipeline`.
- **Evidence of Completion:** Pipeline verifies `destination_root_dir/v{version}` does not exist prior to write.
- **System Action if Missing / Exists:** Pipeline raises `FileExistsError` and halts.

### Item I.3: Intake Audit Manifest Generation
- **Why Required:** Permanently records input/output SHA-256 digests, aggregate retention rates, drop reason distributions, and privacy certifications without citizen data.
- **Classification:** **Mandatory**
- **Supplying / Approving Authority:** Automated `PuneDataIngestionPipeline`.
- **Evidence of Completion:** `intake_audit_manifest.json` written to version directory and verified with standalone SHA-256 hash.
- **System Action if Missing:** Ingestion declared incomplete; version directory quarantined.

---

## Section J: Acceptance or Rejection Decision

### Item J.1: Formal Gate Status Evaluation
- **Why Required:** Determines whether the dataset meets criteria for exploratory analysis (`STAGE_2_READY_FOR_STATION_LEVEL_EDA` or `STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA`).
- **Classification:** **Mandatory Gate Execution**
- **Supplying / Approving Authority:** `PuneDataReadinessAudit.evaluate_readiness`.
- **Evidence of Completion:** Structured readiness audit result returning explicit status enum and checklist booleans.
- **System Action if Status != READY_FOR_EXPLORATORY_ANALYSIS:** Detailed failure reason and checklist deficits recorded in governance log. Processing halted.

### Item J.2: Joint Acceptance Protocol Sign-Off
- **Why Required:** Formal human-in-the-loop sign-off by project leadership before any analytical code is run on the cleaned output.
- **Classification:** **Mandatory Governance Protocol**
- **Supplying / Approving Authority:** Principal Investigator and Lead ML Engineer.
- **Evidence of Completion:** Executed Data Acceptance / Rejection Memorandum citing version directory, raw SHA-256, cleaned SHA-256, and readiness gate status.
- **System Action if Rejected:** Version directory locked/quarantined; formal notice of rejection sent to issuing authority.

---

## Summary Checklist Matrix

| Section | Domain | Total Items | Mandatory Items | Hard Blockers | Current Institutional Status |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **A** | Institutional Authorization | 3 | 2 | 2 | **AWAITING INSTITUTION** |
| **B** | Data-Transfer Approval | 2 | 2 | 2 | **AWAITING INSTITUTION** |
| **C** | Incident Dataset Specification | 4 | 3 | 2 | **SPECIFIED / PREPARED** |
| **D** | Station Operational Records | 2 | 0 | 0 | **AWAITING INSTITUTION** |
| **E** | Reporting-Coverage Evidence | 2 | 1 | 1 | **SPECIFIED / PREPARED** |
| **F** | GIS & Jurisdictional Boundaries | 2 | 1 | 0 | **AWAITING INSTITUTION** |
| **G** | Privacy & Retention Approval | 3 | 3 | 3 | **PREPARED / AUTOMATED** |
| **H** | Cryptographic Authorization | 3 | 3 | 3 | **IMPLEMENTED (UNPROVISIONED)** |
| **I** | Data Intake & Integrity Verification | 3 | 3 | 3 | **IMPLEMENTED & VERIFIED** |
| **J** | Acceptance or Rejection Decision | 2 | 2 | 2 | **IMPLEMENTED & READY** |
