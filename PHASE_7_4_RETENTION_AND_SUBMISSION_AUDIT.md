# STRATA RISK — PHASE 7.4 RETENTION POLICY RECONCILIATION & INSTITUTIONAL SUBMISSION AUDIT
**Forensic Audit of Historical Data Coverage, Post-Acquisition Retention Governance, Storage Lifecycles, and Implementation Alignment**

> [!WARNING]
> **AUDIT STATUS: PHASE 7.4 FINALIZED — AWAITING EXTERNAL INSTITUTIONAL ACTION**
> This document audits and reconciles historical data coverage requirements, proposed post-acquisition retention policies, intermediate data lifecycles, and statutory privacy safeguards across the Strata Risk codebase.
> **No Memorandum of Understanding (MoU), data-sharing agreement, cryptographic verification key, or authorized Pune dataset currently exists.**
> Pune and Mumbai remain strictly **UNSUPPORTED** (`is_validated = False`, `NO_DATA` / `STAGE_0_UNAUTHORIZED`).

---

## 1. Section A: Historical Coverage vs. Post-Acquisition Retention Definitions

Prior documentation iterations contained conceptual conflation between the retrospective temporal window of observations requested and the prospective shelf-life of received data files. Phase 7.4 establishes an explicit, permanent distinction:

```
┌────────────────────────────────────────────────────────────────────────┐
│             TEMPORAL COVERAGE vs. POST-ACQUISITION RETENTION           │
├───────────────────────────────────┬────────────────────────────────────┤
│ HISTORICAL DATA COVERAGE          │ POST-ACQUISITION RETENTION         │
│ (Retrospective Observation Span)  │ (Prospective Storage Shelf-Life)   │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Span: ~36 months (1,080 days)   │ • Span: Proposed 365 calendar days │
│ • Direction: Retrospective (past) │ • Direction: Prospective (future)  │
│ • Unit: Incident timestamps (t)   │ • Unit: Storage days from receipt  │
│ • Purpose: Captures annual cycles │ • Purpose: Limits institutional    │
│   monsoons, IPC-to-BNS statutory  │   data exposure and enforces DPDPA │
│   breaks, and baseline drift      │   storage limitation principles    │
│ • Governed by: Statistical power │ • Governed by: Bilateral MoU terms │
│   and evaluation protocol needs   │   and DPO compliance mandate       │
└───────────────────────────────────┴────────────────────────────────────┘
```

### 1.1 Historical Data Coverage Definition
- **Scope:** The chronological elapsed interval between the earliest incident timestamp ($t_{\min}$) and the latest incident timestamp ($t_{\max}$) present in the delivered extract.
- **Requirement Target:** Approximately 36 continuous months (~1,080 calendar days) for controlled model-training evaluation (`STAGE_4_CONTROLLED_TRAINING_ELIGIBLE`), or approximately 6 months (~180 days) for preliminary exploratory data analysis (`STAGE_2_READY_FOR_STATION_LEVEL_EDA`).
- **Function:** Ensures sufficient retrospective observation depth to model quarterly seasonality, monsoon surges, annual festivals, and the July 1, 2024 statutory transition from the Indian Penal Code (IPC) to the Bharatiya Nyaya Sanhita (BNS).
- **Invariant:** Historical coverage describes data content; it does not authorize or dictate post-acquisition storage duration.

### 1.2 Post-Acquisition Retention Schedule Definition
- **Scope:** The duration that received files and derived artifacts are permitted to reside on encrypted institutional research infrastructure following formal transfer.
- **Current Status:** **Strictly PROPOSED (365 calendar days) and SUBJECT TO INSTITUTIONAL APPROVAL.**
- **Governance:** Defined in the draft request package and subject to formal negotiation and ratification in the bilateral research MoU by the Office of the Commissioner of Police, Pune City.
- **Invariant:** A proposed 365-day retention schedule does not constitute authorization to retain data for 365 days or any other interval until the bilateral MoU is executed.

---

## 2. Section B: Retention-Period References Across Project Documentation

The repository was systematically audited for all references to retention, historical coverage, 365 days, and 36 months:

| File Inspected | Prior Text / Assumption | Identified Inconsistency | Phase 7.4 Reconciliation |
| :--- | :--- | :--- | :--- |
| **`INSTITUTIONAL_DATA_REQUEST_PACKAGE.md`** | Referenced 365-day retention as a flat statement without disaggregating categories or clearly separating from 36-month coverage. | Implied a single retention rule for all files and did not detail temporary or backup treatment. | Reconciled: Explicitly separated ~36-month historical coverage from proposed 365-day retention. Disaggregated rules across 8 data categories. Clarified deletion authorities and evidence standards. Labeled `DRAFT — SUBJECT TO INSTITUTIONAL, LEGAL, AND PRIVACY APPROVAL`. |
| **`PUNE_DATA_ACQUISITION_CHECKLIST.md`** | Item G.3 stated "365-Day Retention Schedule & Deletion Protocol". | Did not explicitly note that 365 days is a proposal subject to police approval, or detail intermediate-file purges. | Reconciled: Updated Item G.3 to "Post-Acquisition Retention Schedule & Deletion Protocol", explicitly citing disaggregated categories and manual deletion governance. |
| **`PHASE_7_1_INSTITUTIONAL_HANDOFF.md`** | Line 46 stated that a 365-day purge conflicted with needing 36 months of history, proposing an extended 36-month retention. | Conflated historical observation coverage with storage retention duration. | Reconciled: Decoupled historical coverage (~36 months retrospective span) from post-acquisition retention (proposed 365 days post-transfer shelf-life). Updated Item A-08 and legal questions accordingly. |
| **`PHASE_7_2_HANDOFF_FINALIZATION.md`** | Line 108 referenced "Approval for retaining pseudonymized historical FIR hashes for 36 months". | Conflated 36 months of historical data with 36 months of post-acquisition storage. | Reconciled: Corrected line 108 to specify approval of the proposed post-acquisition retention schedule (proposed 365 days) distinct from retrospective coverage. |
| **`PUNE_AUTHORIZED_DATA_INTAKE_AND_READINESS.md`** | Section 3.6 stated flat 365-day retention and unqualified "cryptographic erasure". | Overstated sanitization capability on standard filesystems; lacked category disaggregation. | Reconciled: Clarified proposed retention status, disaggregated 8 tiers, and distinguished standard filesystem unlinking from hardware media sanitization. |
| **`PHASE_6_AUTHORIZED_DATA_ACQUISITION_PACKAGE.md`** | Line 121 referenced "365-day retention schedule, NIST SP 800-88 sanitization protocols". | Presented 365 days as an established protocol rather than a draft proposal. | Reconciled: Labeled as a proposed post-acquisition schedule subject to institutional approval across 8 data categories. |
| **`backend/services/pune_data_readiness.py`** | Contained `retention_schedule_days: int = 365` default in manifest generator. | Had no configuration class distinguishing proposed from approved retention policies. | Reconciled: Implemented `PuneRetentionPolicyConfig` and `PuneRetentionPolicyStatus`, providing programmatic enforcement of proposed vs approved states and blocking automated deletion. |

---

## 3. Section C: Disaggregated Treatment of Data Categories

To prevent uniform retention over-retention or accidental destruction of essential audit records, data retention is formally disaggregated across eight distinct categories:

```
┌────────────────────────────────────────────────────────────────────────┐
│             EIGHT-CATEGORY DATA RETENTION & LIFECYCLE MATRIX           │
├───────────────────────────────────┬────────────────────────────────────┤
│ 1. Raw Authorized Dataset         │ 5. Aggregated Statistical Reports  │
│    Restricted source data         │    Permanent academic output       │
├───────────────────────────────────┼────────────────────────────────────┤
│ 2. Cleaned Incident Dataset       │ 6. Model-Training Datasets         │
│    Derived pseudonymized research │    Locked / Disabled (0 days)      │
├───────────────────────────────────┼────────────────────────────────────┤
│ 3. Temporary Processing Files     │ 7. Audit Manifests & Records       │
│    Ephemeral scratch (0 days)     │    Permanent integrity provenance  │
├───────────────────────────────────┼────────────────────────────────────┤
│ 4. Intermediate Analytics Data    │ 8. Backups & Recoverable Copies    │
│    Active analysis duration only  │    Synchronized with raw dataset   │
└───────────────────────────────────┴────────────────────────────────────┘
```

| Category | Classification | Proposed Retention | Storage Tier | Deletion Authority | Sanitization Standard | Retained Post-Deletion |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Raw Authorized Dataset** | Restricted Source Data | Proposed 365 days from receipt (Subject to MoU terms) | Encrypted offline research vault (AES-256) | Office of the Commissioner of Police, Pune City | NIST SP 800-88 Rev. 1 media purge / secure overwrite | None (Completely purged) |
| **2. Cleaned Incident Dataset** | Derived Pseudonymized Research Data | Synchronized with raw dataset retention | Versioned directory with application overwrite protection | Institutional Data Governance Committee & Police Authority | Secure file unlinking & volume wipe | None (Completely purged) |
| **3. Temporary Processing Files** | Ephemeral System Scratch | 0 days (Purged immediately upon pipeline completion) | In-memory buffers / OS temp scratch | Automated pipeline lifecycle | Immediate unlinking and buffer purge | None |
| **4. Intermediate Analytical Datasets** | Exploratory Intermediates | Duration of active exploratory analysis only | Isolated research enclave volume | Lead ML Engineer / Governance Officer | Secure directory purge prior to archiving | None |
| **5. Aggregated Statistical Reports** | Non-PII Research Output | Permanent (Contains zero citizen records or FIRs) | Standard project documentation repository | N/A (Academic & governance record) | N/A (Aggregated metrics only) | Permanent report retained |
| **6. Model-Training Datasets** | Future Training Data | **LOCKED / DISABLED (0 days)** | N/A (Prohibited in Stage 0–3) | N/A (Requires Stage 4 MoU addendum) | N/A | N/A |
| **7. Audit Manifests & Integrity Records** | Permanent Integrity Provenance | Permanent (Retained post-deletion for accountability) | Versioned intake directory | Never purged (Essential legal audit trail; zero PII) | N/A (Hashes, schemas, counts only) | Permanent audit manifest (`intake_audit_manifest.json`) |
| **8. Backups & Recoverable Copies** | Disaster Recovery Archive | Synchronized strictly with raw dataset retention | Encrypted backup media (AES-256) | Institutional Chief Information Security Officer (CISO) | NIST SP 800-88 Rev. 1 media destruction / purge | None (Purged simultaneously) |

---

## 4. Section D: Actual Implemented Safeguards vs. Documented Proposals

To eliminate overstated technical claims, actual software-enforced controls are contrasted with documented institutional proposals:

| Safeguard Domain | Documented Institutional Proposal | Actual Implementation in Active Codebase | Disclosed Technical Boundary |
| :--- | :--- | :--- | :--- |
| **Storage Immutability** | "Immutable intake audit manifests and version storage" | Version directory existence check (`os.path.exists -> raise FileExistsError`) in `ingest_authorized_dataset` (lines 640–648). | **Application-Level Overwrite Protection Only.** Does not provide OS-level write-protection or hardware WORM immutability. An OS administrator can modify or delete files unless hosted on hardware WORM or AWS S3 Object Lock. |
| **Integrity Verification** | "Hash-verified tamper-evident audit manifests" | Recomputes raw dataset SHA-256 byte-by-byte and compares to `expected_sha256` in signed manifest. | **Cryptographic Tamper-Evidence Implemented.** Proves file identity; does not prevent physical file deletion. |
| **Anonymization vs Pseudonymization** | "Anonymized CCTNS incident extract" | FIR numbers hashed via salted SHA-256; station names normalized; coordinates truncated to 3 decimal places. | **Pseudonymization Only.** A salted hash is not irreversible anonymization. Dictionary attacks are theoretically possible if salt and sequential FIR registry are compromised. |
| **PII Content Scrubbing** | "100% automated PII elimination under DPDPA 2023" | Vectorized regex scan across all columns and string values for phone numbers, emails, 12-digit Aadhaar, 10-character PAN (`audit_pii`, lines 310–360). | **Structured Pattern Interception Only.** Regex filters intercept standard format tokens, but cannot guarantee 100% removal of contextual identities in unstructured Marathi/English free text. |
| **Cryptographic Authorization** | "Asymmetric Ed25519 authorization verification" | RFC 8785 canonicalizer (`canonicalize_rfc8785`) + `ed25519.Ed25519PublicKey.verify` + persistent CRL validation in `InstitutionalIssuerRegistry`. | **Fully Implemented & Verified.** Application holds no private keys; cannot self-sign. Public key strictly unprovisioned (`None`) in source code. |
| **Retention Policy Enforcement** | "365-day retention schedule with automated deletion" | `PuneRetentionPolicyConfig` class enforces consistency checks and blocks automated deletion (`can_delete_real_data` returns `False`). | **Manual / Operational Deletion Governance.** No automated deletion daemon runs in the background. Real dataset deletion is a human-supervised procedure requiring multi-signature approval. |

---

## 5. Section E: Legal and Privacy Issues Still Awaiting Institutional Approval

The software implementation enforces strict technical gates, but the following legal and privacy issues remain unresolved external dependencies:

1. **DPDPA 2023 Section 17 Research Exemption Determination:**
   - *Status:* **Awaiting Institutional Legal Review.**
   - *Issue:* Section 17 does not automatically grant blanket exemption to public safety research. The Institutional Data Protection Officer (DPO) and Legal Counsel must conduct a formal Data Protection Impact Assessment (DPIA) and certify that data processing is restricted to necessary statistical research with adequate safeguards against individual profiling.
2. **Post-Acquisition Retention Schedule Ratification:**
   - *Status:* **Awaiting Commissionerate Review.**
   - *Issue:* The proposed 365-day retention schedule must be formally reviewed by Pune City Police legal officers to ensure alignment with Maharashtra Police record retention regulations and CCTNS administrative guidelines.
3. **Residual Re-Identification Risk in Geocoded Data:**
   - *Status:* **Awaiting Ethics & Legal Review.**
   - *Issue:* Truncating coordinates to 3 decimal places (~111-meter precision) protects residential doors, but in sparse peripheral beats or rural cantonment perimeters, 111m precision combined with public news reports may narrow re-identification. Legal counsel must approve coordinate release thresholds.
4. **Unstructured Narrative Text Policy:**
   - *Status:* **Awaiting Technical Directorate Agreement.**
   - *Issue:* Because regex token scanning cannot guarantee zero identity leakage in vernacular free text, institutional counsel must decide whether `place_of_occurrence` should be restricted strictly to pre-defined categorical codes or omitted entirely.

---

## 6. Section F: Retention Policy Configuration & Actual Behavior

Phase 7.4 introduced the formal [`PuneRetentionPolicyConfig`](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/pune_data_readiness.py#L360-L460) safety abstraction to eliminate policy ambiguity:

### 6.1 State Separation Architecture
- `policy_status`: Strictly defaults to `PROPOSED_PENDING_INSTITUTIONAL_APPROVAL`.
- `is_approved_by_institution`: Strictly defaults to `False`.
- `proposed_retention_days`: Configured as 365 days (application proposal).
- `approved_retention_days`: Strictly `None` until an executed approval reference is supplied.

### 6.2 Fail-Closed Configuration Validation
The method `validate_configuration()` enforces:
1. If `is_approved_by_institution == False`:
   - Setting `approved_retention_days` raises `ValueError` ("Approved retention days cannot be set when is_approved_by_institution is False").
   - Setting `policy_status == APPROVED_BY_COMMISSIONERATE` raises `ValueError`.
2. If `is_approved_by_institution == True`:
   - Omitting `approval_reference` raises `ValueError`.
   - Setting `approved_retention_days <= 0` raises `ValueError`.
   - Setting `policy_status != APPROVED_BY_COMMISSIONERATE` raises `ValueError`.

### 6.3 Prevention of Automated Deletion of Real Data
The method `can_delete_real_data(is_manual_operator_confirmed, approval_token)` enforces:
- If `is_approved_by_institution == False`: Returns `False` (unapproved policy cannot authorize deletion).
- If `is_manual_operator_confirmed == False`: Returns `False` (**automated background deletion is strictly prohibited**).
- If `approval_token` is missing or empty: Returns `False`.
- Real dataset deletion is strictly a human-supervised operational action.

---

## 7. Section G: Files Changed and Reason for Each Change

| File Path | Change Category | Rationale & Purpose |
| :--- | :--- | :--- |
| [`backend/services/pune_data_readiness.py`](file:///c:/Users/harsh/Downloads/strata-risk/backend/services/pune_data_readiness.py) | Code Hardening | Added `PuneRetentionPolicyStatus`, `PuneRetentionPolicyConfig`, and `DEFAULT_RETENTION_POLICY_CONFIG` to programmatically separate proposed from approved retention, prevent automated real-data deletion, and define the 8-category retention matrix. |
| [`backend/tests/test_phase_7_4_retention_policy.py`](file:///c:/Users/harsh/Downloads/strata-risk/backend/tests/test_phase_7_4_retention_policy.py) | Test Suite Expansion | Added 7 unit tests verifying default unapproved status, historical coverage vs retention decoupling, fail-closed validation on inconsistent policies, automated deletion blocking, and 8-category matrix coverage. |
| [`INSTITUTIONAL_DATA_REQUEST_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/INSTITUTIONAL_DATA_REQUEST_PACKAGE.md) | Governance Documentation | Updated title and headers to `DRAFT — SUBJECT TO INSTITUTIONAL, LEGAL, AND PRIVACY APPROVAL`. Decoupled ~36-month historical coverage from proposed 365-day retention. Detailed 8 data categories, deletion authorities, and DPDPA Section 17 legal and residual risk disclosures. Kept sign-offs blank. |
| [`PUNE_DATA_ACQUISITION_CHECKLIST.md`](file:///c:/Users/harsh/Downloads/strata-risk/PUNE_DATA_ACQUISITION_CHECKLIST.md) | Governance Documentation | Updated Item G.1 (DPDPA non-automatic exemption) and Item G.3 (Post-Acquisition Retention Schedule & Deletion Protocol, citing 8 tiers and manual deletion governance). |
| [`PHASE_7_1_INSTITUTIONAL_HANDOFF.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_7_1_INSTITUTIONAL_HANDOFF.md) | Technical Documentation | Corrected line 46, Item A-08, and question 214 to eliminate historical coverage vs retention conflation. |
| [`PHASE_7_2_HANDOFF_FINALIZATION.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_7_2_HANDOFF_FINALIZATION.md) | Technical Documentation | Corrected line 108 to clarify post-acquisition retention schedule approval distinct from ~36 months historical coverage. |
| [`PUNE_AUTHORIZED_DATA_INTAKE_AND_READINESS.md`](file:///c:/Users/harsh/Downloads/strata-risk/PUNE_AUTHORIZED_DATA_INTAKE_AND_READINESS.md) | Technical Documentation | Updated Section 3.6 to clarify proposed retention status, 8 data categories, and manual deletion governance. |
| [`PHASE_6_AUTHORIZED_DATA_ACQUISITION_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/PHASE_6_AUTHORIZED_DATA_ACQUISITION_PACKAGE.md) | Technical Documentation | Updated line 121 to reflect proposed post-acquisition retention schedule across 8 data tiers. |

---

## 8. Section H: Verification & Regression Protection Results

The complete test suite, static typechecker, linter, and build pipeline were executed to confirm total system stability:

| Verification Stage | Command Line | Result | Detail |
| :--- | :--- | :---: | :--- |
| **Backend Unit & Integration Suite** | `python -m pytest backend/tests/ -v` | **203 PASSED** | 100% pass rate in 15.80s (196 baseline + 7 Phase 7.4 tests), 0 warnings |
| **TypeScript Static Analysis** | `npx tsc --noEmit` | **PASSED** | 0 type errors, clean exit code 0 |
| **Frontend Linter** | `npm run lint` | **PASSED** | Clean exit code 0 |
| **Production Bundle Build** | `npm run build` | **PASSED** | Vite bundle built cleanly in 548ms |

### Canonical Chicago Production Artifact Cryptographic Hashes

Bit-level SHA-256 digests were recomputed and verified bit-identical to established repository baselines:

```
forecaster_catboost.cbm:
  Expected: 8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96
  Actual:   8A9FF0EC1D7EF8E5D60EEECA633C40EBAB423CE9CAD7A241CC45F2BEEFAC4A96  ==> MATCH (100% Bit-Identical)

calibrator.joblib:
  Expected: 8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D
  Actual:   8646328A284D513B7DB78967BFF660EA9A8DD174372DA109CF8DEF3D31C2594D  ==> MATCH (100% Bit-Identical)

model_metadata.json:
  Expected: B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407
  Actual:   B7A3A06EF6B823D0D87E93011E7AFCF07710A84AE13D94784761917643EDA407  ==> MATCH (100% Bit-Identical)
```

---

## 9. Section I: Outstanding Dependencies

The project is technically prepared but remains strictly blocked by the following external real-world dependencies:

1. **Bilateral Research MoU Execution:** Formal negotiation and execution by institutional leadership and the Commissioner of Police, Pune City. **(No MoU exists.)**
2. **DPDPA Section 17 Research Exemption Review:** Formal evaluation and sign-off by Institutional Legal Counsel and Data Protection Officer. **(No legal certification exists.)**
3. **Institutional Ed25519 Public Verification Key Delivery:** Receipt and environment injection of `PUNE_COP_ED25519_PUBLIC_KEY`. **(Currently unprovisioned in source code.)**
4. **Authorized Historical Incident Extract Delivery:** Formal delivery of a ~36-month (or provisional 6-month) CCTNS incident extract accompanied by an Ed25519-signed manifest matching the extract's SHA-256 fingerprint. **(No authorized dataset exists.)**
5. **CCTNS Server Transmission & Downtime Logs:** Release of station transmission records to verify reporting coverage. **(No logs exist.)**
6. **Authoritative GIS Boundary Shapefiles:** Release of official administrative polygon layers for all 33 stations (specifically verifying *Pashan*, *Bavdhan*, and *Alankar*). **(No official GIS layers exist.)**

---

## 10. Next Immediate Action

> [!IMPORTANT]
> All software engineering, data-governance hardening, and retention policy reconciliations are complete and verified.
> **The next required real-world action is formal internal review of [`INSTITUTIONAL_DATA_REQUEST_PACKAGE.md`](file:///c:/Users/harsh/Downloads/strata-risk/INSTITUTIONAL_DATA_REQUEST_PACKAGE.md) by Institutional Legal Counsel and the Data Protection Officer, followed by submission to the Office of the Commissioner of Police, Pune City.**
> Until bilateral authorization and authentic credentials are delivered, all Pune models, training pipelines, and deployment endpoints remain strictly **DISABLED**.
