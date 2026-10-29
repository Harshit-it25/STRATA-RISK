# STRATA RISK — PUNE AUTHORIZED DATA INTAKE RUNBOOK (PHASE 7.3)
**Operational Step-by-Step Execution Guide for Receiving and Validating Authorized Incident Data**

> [!WARNING]
> **OPERATIONAL STATUS: STANDBY — NO REAL DATA RECEIVED**
> This runbook is a technical operating procedure for authorized data engineers.
> It defines the exact sequential protocol to execute **if and when** an authentic, authorized dataset is received from the Pune City Police Commissionerate.
> **No authorized dataset or cryptographic key currently exists.** Pune remains `UNSUPPORTED`.

---

## Operating Environment & Execution Model Note

> [!IMPORTANT]
> **Implementation Mechanism:** The Strata Risk intake infrastructure is implemented as modular Python classes and functions within `backend.ingestion.pune_ingestion_pipeline`, `backend.services.pune_data_readiness`, and `backend.pipeline.pune_spatiotemporal_pipeline`.
> **No Standalone Shell CLI Exists:** Operations are executed using dedicated Python scripts or interactive Python sessions in the project virtual environment. The runbook provides exact Python execution snippets reflecting the actual codebase.

---

## Pre-Requisites & Operator Checklist

Before commencing dataset ingestion, the operator must verify:
1. Virtual environment is active with all locked dependencies installed:
   ```bash
   pip install -r backend/requirements-lock.txt
   ```
2. The Commissionerate's official Ed25519 public verification key (32-byte hex string) is set in the shell environment:
   ```bash
   # Linux / macOS
   export PUNE_COP_ED25519_PUBLIC_KEY="<32_BYTE_HEX_KEY_PROVIDED_BY_PUNE_POLICE>"
   
   # Windows PowerShell
   $env:PUNE_COP_ED25519_PUBLIC_KEY="<32_BYTE_HEX_KEY_PROVIDED_BY_PUNE_POLICE>"
   ```
   *(Note: Never hardcode public keys into git-tracked files or Python modules.)*
3. The raw extract and signed authorization manifest are placed in the staging directory:
   - Raw dataset: `backend/data/staging/pune_raw_extract.csv` (or `.parquet`)
   - Signed manifest: `backend/data/staging/pune_raw_extract.csv.auth.json`

---

## Step 1: Verify Transfer Authorization & Custody Handover

**Objective:** Confirm legal provenance before opening the dataset file.
- Inspect the physical/digital Chain of Custody Handover Form.
- Verify countersignatures of the Pune Police Liaison Officer and the Institutional Transfer Officer.
- Verify that the handover date falls within the bilateral MoU validity period.
- **Fail-Closed Condition:** If custody paperwork is missing, halt immediately. Do not mount or open the storage media.

---

## Step 2: Record Source Provenance

**Objective:** Document intake parameters in the institutional audit log.
- Record:
  - Source Organization: Office of the Commissioner of Police, Pune City
  - Transfer Protocol: Secure SFTP / Encrypted Hardware Token
  - Receiving Operator Identity: `<Operator Name / ID>`
  - Intake Timestamp: Current UTC timestamp
  - Staging File Path: `backend/data/staging/pune_raw_extract.csv`

---

## Step 3: Calculate the Raw Dataset SHA-256 Fingerprint

**Objective:** Establish bit-for-bit file integrity prior to any parsing.

Execute via PowerShell or Python:
```python
import hashlib

raw_path = "backend/data/staging/pune_raw_extract.csv"
hasher = hashlib.sha256()
with open(raw_path, "rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
        hasher.update(chunk)
raw_sha256 = hasher.hexdigest()
print(f"Raw Dataset SHA-256: {raw_sha256}")
```

Record `raw_sha256` in the operator logbook.

---

## Step 4: Verify Ed25519 Asymmetric Signature & Dataset Binding

**Objective:** Prove mathematically that the manifest was signed by Pune City Police and is bound to this exact raw file.

Execute in Python:
```python
import json
from backend.services.pune_data_readiness import PuneAuthorizationValidator

manifest_path = "backend/data/staging/pune_raw_extract.csv.auth.json"
with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

is_verified, status_code, violations, validated_manifest = PuneAuthorizationValidator.validate(
    manifest=manifest,
    dataset_path=raw_path,
    dataset_content_or_hash=raw_sha256,
    is_fixture=False  # Strictly False for real production data
)

print(f"Verified: {is_verified}")
print(f"Status Code: {status_code}")
if not is_verified:
    print(f"Violations: {violations}")
    raise RuntimeError(f"Intake aborted: {violations}")
```

**Under the Hood:**
1. Loads `PUNE_COP_ED25519_PUBLIC_KEY` from environment.
2. Canonicalizes the manifest using RFC 8785 JSON Canonicalization Scheme (excluding `signature` and `manifest_sha256`).
3. Verifies the Ed25519 digital signature against the canonical byte stream.
4. Asserts `manifest["dataset_fingerprint"]["expected_sha256"] == raw_sha256`.
5. Confirms `is_fixture == False` and issuer is `pune_city_police_cop`.

---

## Step 5: Verify Revocation Status via Persistent CRL

**Objective:** Ensure the authorization identifier has not been revoked by the Commissionerate.

Execute in Python:
```python
from backend.services.pune_data_readiness import InstitutionalIssuerRegistry

is_valid, reason, revoked_ids, crl_meta = InstitutionalIssuerRegistry.load_persistent_crl(
    require_crl=True,
    require_signed_crl=True
)

if not is_valid:
    raise RuntimeError(f"CRL check failed: {reason}")

auth_id = manifest.get("authorization_id")
mou_ref = manifest.get("mou_reference")

if auth_id in revoked_ids or mou_ref in revoked_ids:
    raise RuntimeError(f"Authorization revoked! ID: {auth_id}, MoU: {mou_ref}")

print("CRL verification successful: Authorization is active.")
```

---

## Step 6: Validate Permitted Schema

**Objective:** Enforce presence of mandatory core fields and reject unauthorized columns.

Execute via `PuneDataIngestionPipeline.validate_schema`:
```python
import pandas as pd
from backend.ingestion.pune_ingestion_pipeline import PuneDataIngestionPipeline

df_raw = pd.read_csv(raw_path)
pipeline = PuneDataIngestionPipeline()

# Validates mandatory core fields: fir_number_hash, police_station_id, incident_datetime, section_code
is_schema_valid, schema_issues = pipeline.validate_schema(df_raw)

if not is_schema_valid:
    raise ValueError(f"Schema validation failed: {schema_issues}")

print("Schema validation passed.")
```

---

## Step 7: Screen for Prohibited Personal Information (DPDPA 2023 Audit)

**Objective:** Perform a 100% full-content vectorized regex scan for citizen personal data.

Execute via `PuneDataIngestionPipeline.audit_pii`:
```python
# Scans all columns and string values for phone numbers, emails, Aadhaar, PAN cards, etc.
is_clean, pii_issues = pipeline.audit_pii(df_raw)

if not is_clean:
    # Fails closed without printing citizen data to logs
    raise ValueError(f"PII Violation detected: {len(pii_issues)} columns flagged. Intake aborted.")

print("PII scan clean: 0 prohibited citizen attributes detected.")
```

---

## Step 8: Validate Station Identifiers and Harm Mappings

**Objective:** Normalize station names to the canonical 33 Pune stations and map penal sections to operational harm tiers.

Execute in Python:
```python
from backend.services.pune_data_readiness import PUNE_POLICE_STATIONS, PUNE_STATION_VERIFICATION_STATUS

# Check station normalizations
df_raw["station_normalized"] = df_raw["police_station_id"].apply(PuneDataIngestionPipeline.normalize_station_id)
unmapped = df_raw[~df_raw["station_normalized"].isin(PUNE_POLICE_STATIONS)]

if len(unmapped) > 0:
    print(f"Warning: {len(unmapped)} records contain unmapped station IDs.")

# Check penal section mappings (IPC / BNS)
from backend.services.pune_data_readiness import PuneDataReadinessAudit
harm_tiers = PuneDataReadinessAudit.map_incident_categories(df_raw["section_code"])
print(f"Harm tier distribution:\n{harm_tiers.value_counts()}")
```

---

## Step 9: Validate Timestamps and Point-in-Time Availability Fields

**Objective:** Audit incident occurrence timestamps, FIR registration delays, and potential clerical anomalies.

Execute in Python:
```python
# Normalize incident timestamps
df_raw["dt_incident"] = df_raw["incident_datetime"].apply(pipeline.normalize_timestamp)
invalid_ts_count = df_raw["dt_incident"].isna().sum()
print(f"Invalid incident timestamps: {invalid_ts_count}")

# Audit registration timestamps if present
if "registration_datetime" in df_raw.columns:
    df_raw["dt_reg"] = df_raw["registration_datetime"].apply(pipeline.normalize_timestamp)
    # Check for inverted timestamps (t_fir < t_incident)
    inverted_mask = (df_raw["dt_reg"].notna() & df_raw["dt_incident"].notna() & (df_raw["dt_reg"] < df_raw["dt_incident"]))
    print(f"Clerical anomaly (inverted timestamps): {inverted_mask.sum()} records")
```

---

## Step 10: Establish Reporting-Coverage Classifications

**Objective:** Ingest operational metadata to classify station-windows into the 5-state taxonomy.

Execute via `PuneFourHourSpatiotemporalPipeline`:
```python
from backend.pipeline.pune_spatiotemporal_pipeline import PuneFourHourSpatiotemporalPipeline

spatio_pipeline = PuneFourHourSpatiotemporalPipeline()

# Aggregate incidents onto 4-hour lattice and classify coverage
grid_df, coverage_audit = spatio_pipeline.aggregate_incidents(
    df_cleaned=df_raw[df_raw["dt_incident"].notna()],
    target_harm_tiers=["violent_street_harm"],
    require_coverage_evidence=True  # Strictly True to prevent zero fabrication
)

print("Observation Coverage Breakdown:")
print(f"- Verified Observed Incidents (Y = 1): {coverage_audit['verified_observed_incidents']}")
print(f"- Verified Observed Zeros (Y = 0): {coverage_audit['verified_observed_zeros']}")
print(f"- Unknown Coverage (Y = NaN): {coverage_audit['unknown_coverage_windows']}")
print(f"- Incomplete Extract (Y = NaN): {coverage_audit['incomplete_extract_windows']}")
print(f"- Not Operational (Y = NaN): {coverage_audit['not_operational_windows']}")
```

---

## Step 11: Execute Versioned Ingestion & Verify Output Integrity

**Objective:** Ingest the authorized dataset into an immutable version directory and generate audit manifests.

Execute `PuneDataIngestionPipeline.ingest_authorized_dataset`:
```python
destination_dir = "backend/data/pune_authorized"
version_tag = "1.0"  # Increment to '1.1' or '2.0' for new intakes

cleaned_df, intake_audit = PuneDataIngestionPipeline.ingest_authorized_dataset(
    raw_dataset_path=raw_path,
    manifest_path=manifest_path,
    destination_root_dir=destination_dir,
    version=version_tag,
    source_name="Pune City Police Commissionerate CCTNS Extract",
    is_fixture=False
)

print(f"Ingestion successful into: {intake_audit['version_directory']}")
print(f"Cleaned incidents SHA-256: {intake_audit['output_fingerprint']['cleaned_file_sha256']}")
print(f"Retention rate: {intake_audit['aggregate_retention_and_rejection_counts']['retention_rate_pct']}%")
```

**Storage Verification:**
- Confirm `backend/data/pune_authorized/v1.0/cleaned_incidents.csv` exists.
- Confirm `backend/data/pune_authorized/v1.0/authorized_manifest.json` exists.
- Confirm `backend/data/pune_authorized/v1.0/intake_audit_manifest.json` exists.
- Verify that attempting to re-run with version `1.0` raises `FileExistsError` (application overwrite prevention).

---

## Step 12: Generate Aggregated Data-Quality and Readiness Report

**Objective:** Evaluate formal readiness gates and compile the exploratory analysis report.

Execute `PuneDataReadinessAudit.evaluate_readiness`:
```python
from backend.services.pune_data_readiness import PuneDataReadinessAudit, PuneThresholdConfig

readiness_result = PuneDataReadinessAudit.evaluate_readiness(
    df=cleaned_df,
    manifest=intake_audit,
    gis_boundary_path=None,  # Provide path to GeoJSON/Shapefile if supplied
    config=PuneThresholdConfig(),
    require_gis_complete=False  # False evaluates station-level readiness
)

print(f"Readiness Gate Status: {readiness_result.status.value}")
print(f"Message: {readiness_result.message}")
print(f"Station-Level Ready: {readiness_result.is_station_level_ready}")
print(f"Coordinate-Level Ready: {readiness_result.is_coordinate_level_ready}")
```

Next, run the automated EDA pipeline to produce the full audit document:
```python
eda_output_path = f"backend/data/pune_authorized/v{version_tag}/eda_quality_report.json"

eda_report = PuneDataReadinessAudit.run_pune_eda_pipeline(
    cleaned_dataset_path=f"backend/data/pune_authorized/v{version_tag}/cleaned_incidents.csv",
    manifest_path=f"backend/data/pune_authorized/v{version_tag}/authorized_manifest.json",
    gis_boundary_path=None,
    output_report_path=eda_output_path
)

print(f"EDA Quality Report generated at: {eda_output_path}")
```

---

## Step 13: Record Formal Acceptance or Rejection Decision

**Objective:** Formalize human-in-the-loop governance sign-off.

1. **If Gate Status == `READY_FOR_EXPLORATORY_ANALYSIS`:**
   - Complete and countersign the **Data Acceptance Protocol Form**.
   - Transition lifecycle state to `STAGE_2_READY_FOR_STATION_LEVEL_EDA` (or `STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA` if GIS boundaries are complete).
   - Archive raw extract in encrypted offline vault.
   - Authorize researchers to execute read-only exploratory analysis.
   - **Remind team:** Model training (`STAGE_4`) remains strictly disabled until formal Stage 4 review.

2. **If Gate Status != `READY_FOR_EXPLORATORY_ANALYSIS`:**
   - Document specific failure code (e.g. `INSUFFICIENT_TEMPORAL_COVERAGE`, `INSUFFICIENT_TARGET_SUPPORT`).
   - Move version directory to `backend/data/quarantine/`.
   - Issue formal Deficit Notice to the Commissionerate Technical Directorate.
   - Do NOT proceed to exploratory analysis or model training.
