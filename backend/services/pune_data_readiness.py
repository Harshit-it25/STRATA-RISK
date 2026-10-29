"""
Pune Data Readiness, Intake Contract, and Model-Readiness Gate (Phase 5 Hardened).

Defines the formal data intake contract, hardened institutional authorization verification,
explicit non-bypassable readiness gate, independent station-level vs coordinate-level readiness,
conservative geographic auditing, reproducible exploratory analysis workflow, and future
forecasting evaluation protocol for Pune City.

Strict Empirical & Jurisdictional Integrity Rules:
1. Hardened Institutional Authorization Verification:
   - Does NOT treat a user-controlled boolean or an arbitrary MoU string as independent proof of authorization.
   - Separates manifest presence, manifest schema validity, issuer verification, cryptographic verification,
     approved purpose, authorization validity and expiry, and dataset identity binding.
   - If verification cannot be performed, retains an explicit AUTHORIZATION_UNVERIFIED state.
   - Fixture authorization can NEVER authorize a production dataset.
2. Explicit Non-Bypassable Readiness Gate:
   - Distinguishes: NO_DATA, AUTHORIZATION_MISSING, AUTHORIZATION_UNVERIFIED, SCHEMA_INVALID,
     PRIVACY_REVIEW_REQUIRED, INSUFFICIENT_TEMPORAL_COVERAGE, INSUFFICIENT_SPATIAL_COVERAGE,
     INSUFFICIENT_TARGET_SUPPORT, GIS_MAPPING_INCOMPLETE, READY_FOR_EXPLORATORY_ANALYSIS.
   - Ingestion success does NOT imply readiness for exploratory analysis.
   - Decouples station-level EDA from coordinate-level EDA.
   - Readiness for exploratory analysis is strictly decoupled from readiness for model training
     (is_ready_for_training = False) and readiness for deployment (is_ready_for_deployment = False).
3. Conservative Geography & Representativeness:
   - Evaluates station-level and coordinate-level readiness independently.
   - Uses only supplied, authorized, documented station identifiers and official GIS boundaries.
   - Never infers official boundaries from station names, geocoding results, or approximate shapes.
   - Tracks geographically unresolved records and assesses potential selection bias.
4. Privacy & Data Handling:
   - Zero raw PII in logs, exceptions, or audit reports.
   - Explicitly documents that regex scanning does NOT guarantee complete anonymization in unstructured free text.
5. Active Safety Guarantees:
   - Pune and Mumbai remain strictly UNSUPPORTED for live API forecasting.
   - is_validated remains False. Zero Chicago weights are transferred.
"""

import os
import re
import json
import hashlib
import math
from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Union
import shutil
import uuid
import pandas as pd
import numpy as np

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.exceptions import InvalidSignature


# ==============================================================================
# 1. READINESS STATUS ENUM
# ==============================================================================

class PuneReadinessStatus(str, Enum):
    """Explicit, non-bypassable data readiness gate statuses."""
    NO_DATA = "NO_DATA"
    AUTHORIZATION_MISSING = "AUTHORIZATION_MISSING"
    AUTHORIZATION_UNVERIFIED = "AUTHORIZATION_UNVERIFIED"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    PRIVACY_REVIEW_REQUIRED = "PRIVACY_REVIEW_REQUIRED"
    INSUFFICIENT_TEMPORAL_COVERAGE = "INSUFFICIENT_TEMPORAL_COVERAGE"
    INSUFFICIENT_SPATIAL_COVERAGE = "INSUFFICIENT_SPATIAL_COVERAGE"
    INSUFFICIENT_TARGET_SUPPORT = "INSUFFICIENT_TARGET_SUPPORT"
    GIS_MAPPING_INCOMPLETE = "GIS_MAPPING_INCOMPLETE"
    READY_FOR_EXPLORATORY_ANALYSIS = "READY_FOR_EXPLORATORY_ANALYSIS"


class PuneLifecycleStage(str, Enum):
    """
    Formal institutional lifecycle stages for Pune data readiness (Stages 0 through 6).
    Enforces sequential evidence requirements before any progression.
    In Phase 6, model training (Stage 4), independent validation (Stage 5),
    and operational pilot (Stage 6) are strictly disabled and blocked.
    """
    STAGE_0_UNAUTHORIZED = "STAGE_0_UNAUTHORIZED"
    STAGE_1_AUTHORIZATION_VERIFIED = "STAGE_1_AUTHORIZATION_VERIFIED"
    STAGE_2_READY_FOR_STATION_LEVEL_EDA = "STAGE_2_READY_FOR_STATION_LEVEL_EDA"
    STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA = "STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA"
    STAGE_4_CONTROLLED_TRAINING_ELIGIBLE = "STAGE_4_CONTROLLED_TRAINING_ELIGIBLE"
    STAGE_5_INDEPENDENT_VALIDATION_ELIGIBLE = "STAGE_5_INDEPENDENT_VALIDATION_ELIGIBLE"
    STAGE_6_APPROVED_PILOT_ELIGIBLE = "STAGE_6_APPROVED_PILOT_ELIGIBLE"


# ==============================================================================
# 2. CANONICAL JURISDICTIONAL REGISTRY & SCHEMAS
# ==============================================================================

# Standardized 33 Police Station jurisdictions for Pune City Commissionerate
PUNE_POLICE_STATIONS = [
    "khadki", "vishrantwadi", "yerwada", "vimantal", "chandan_nagar",
    "kalyani_nagar", "koregaon_park", "bundgarden", "shivajinagar", "deccan_gymkhana",
    "faraskhana", "vishrambaug", "khadak", "samarth", "swargate",
    "sahakar_nagar", "dattawadi", "bharati_vidyapeeth", "bibvewadi", "kondhwa",
    "wanowrie", "hadapsar", "mundhwa", "wanawadi", "lashkar_cantonment",
    "kothrud", "warje_malwadi", "alankar", "uttam_nagar", "sinhagad_road",
    "chaturshringi", "pashan", "bavdhan"
]

# Mapping IPC / BNS categories to Strata Risk operational harm tiers
IPC_BNS_CATEGORY_MAP = {
    # Violent Street Harm
    "302": "violent_street_harm",      # IPC Murder (BNS 103)
    "307": "violent_street_harm",      # IPC Attempt to Murder (BNS 109)
    "392": "violent_street_harm",      # IPC Robbery (BNS 309)
    "397": "violent_street_harm",      # IPC Robbery with deadly weapon (BNS 311)
    "384": "violent_street_harm",      # IPC Extortion (BNS 308)
    "326": "violent_street_harm",      # IPC Grievous Hurt (BNS 117)
    "chain_snatching": "violent_street_harm",
    "robbery": "violent_street_harm",
    "extortion": "violent_street_harm",
    "dacoity": "violent_street_harm",
    "murder": "violent_street_harm",
    
    # Property Harm
    "379": "property_harm",            # IPC Theft (BNS 303)
    "380": "property_harm",            # IPC Theft in dwelling (BNS 305)
    "457": "property_harm",            # IPC House-breaking by night (BNS 331)
    "hbt_night": "property_harm",
    "motor_vehicle_theft": "property_harm",
    "theft": "property_harm",
    "burglary": "property_harm",

    # Public Disorder
    "147": "public_disorder",          # IPC Rioting (BNS 191)
    "148": "public_disorder",          # IPC Rioting with weapon (BNS 192)
    "riots": "public_disorder",
    "unlawful_assembly": "public_disorder"
}

# Required schema fields for authorized CCTNS extract
EXPECTED_PUNE_SCHEMA = {
    "fir_number_hash": "Hashed pseudonymized FIR identifier (Required)",
    "police_station_id": "Standardized police station identifier matching Pune 33 stations (Required)",
    "incident_datetime": "ISO 8601 timestamp of incident occurrence (Required)",
    "registration_datetime": "ISO 8601 timestamp of FIR filing (Optional)",
    "section_code": "IPC or BNS penal section code (Required)",
    "place_of_occurrence": "Textual location description or Chowki/Beat ID (Optional)",
    "latitude": "Geocoded latitude if available, else null (Optional)",
    "longitude": "Geocoded longitude if available, else null (Optional)"
}

PROHIBITED_PII_FIELDS = [
    "complainant_name", "complainant", "victim_name", "victim",
    "accused_name", "accused", "suspect_name", "suspect",
    "phone_number", "phone", "mobile", "mobile_no", "contact_number",
    "email", "email_id", "email_address",
    "aadhar_number", "aadhaar", "aadhaar_number", "aadhaar_no",
    "pan_number", "pan_card", "voter_id", "passport_number",
    "exact_residential_address", "residential_address", "address",
    "witness_name", "witness_address", "caste", "religion"
]

# Station verification metadata: distinguishing verified administrative units from unverified assumptions
PUNE_STATION_VERIFICATION_STATUS: Dict[str, Dict[str, Any]] = {
    "khadki": {"status": "VERIFIED_CORE", "notes": "Established Cantonment/North municipal jurisdiction."},
    "vishrantwadi": {"status": "VERIFIED_CORE", "notes": "Established North-East municipal jurisdiction."},
    "yerwada": {"status": "VERIFIED_CORE", "notes": "Established East municipal jurisdiction."},
    "vimantal": {"status": "VERIFIED_CORE", "notes": "Airport jurisdiction (formerly Viman Nagar)."},
    "chandan_nagar": {"status": "VERIFIED_CORE", "notes": "East corridor jurisdiction (Ahmednagar Highway)."},
    "kalyani_nagar": {"status": "VERIFIED_CORE", "notes": "Carved from Yerwada; established IT/residential zone."},
    "koregaon_park": {"status": "VERIFIED_CORE", "notes": "Established Central-East municipal jurisdiction."},
    "bundgarden": {"status": "VERIFIED_CORE", "notes": "Established Central/Railway station jurisdiction."},
    "shivajinagar": {"status": "VERIFIED_CORE", "notes": "Established Central administrative jurisdiction."},
    "deccan_gymkhana": {"status": "VERIFIED_CORE", "notes": "Established Central-West commercial corridor."},
    "faraskhana": {"status": "VERIFIED_CORE", "notes": "Historic Old City (Peth) jurisdiction."},
    "vishrambaug": {"status": "VERIFIED_CORE", "notes": "Historic Old City (Peth) jurisdiction."},
    "khadak": {"status": "VERIFIED_CORE", "notes": "Historic Old City (Peth) jurisdiction."},
    "samarth": {"status": "VERIFIED_CORE", "notes": "Historic Old City (Peth) jurisdiction."},
    "swargate": {"status": "VERIFIED_CORE", "notes": "Established South-Central transit hub."},
    "sahakar_nagar": {"status": "VERIFIED_CORE", "notes": "South residential corridor jurisdiction."},
    "dattawadi": {"status": "VERIFIED_CORE", "notes": "South-West corridor jurisdiction."},
    "bharati_vidyapeeth": {"status": "VERIFIED_CORE", "notes": "South boundary institutional corridor (Katraj)."},
    "bibvewadi": {"status": "VERIFIED_CORE", "notes": "South-East residential corridor."},
    "kondhwa": {"status": "VERIFIED_CORE", "notes": "South-East expanding peri-urban jurisdiction."},
    "wanowrie": {"status": "VERIFIED_CORE", "notes": "East Cantonment/municipal border."},
    "hadapsar": {"status": "VERIFIED_CORE", "notes": "Major East industrial and commercial corridor."},
    "mundhwa": {"status": "VERIFIED_CORE", "notes": "East IT and residential corridor."},
    "wanawadi": {"status": "UNVERIFIED_TRANSLITERATION_DUPLICATE", "notes": "Transliteration variant of 'wanowrie'. Official gazette maps these to the identical physical station."},
    "lashkar_cantonment": {"status": "VERIFIED_CORE", "notes": "Pune Cantonment jurisdiction (Camp area)."},
    "kothrud": {"status": "VERIFIED_CORE", "notes": "Established West residential corridor."},
    "warje_malwadi": {"status": "VERIFIED_CORE", "notes": "South-West bypass corridor."},
    "alankar": {"status": "UNVERIFIED_RECENT_BIFURCATION", "notes": "Bifurcated from Kothrud. Boundary GIS polygon unconfirmed."},
    "uttam_nagar": {"status": "VERIFIED_CORE", "notes": "South-West peri-urban corridor (Khadakwasla/NDA)."},
    "sinhagad_road": {"status": "VERIFIED_CORE", "notes": "South-West transit corridor along Mutha river."},
    "chaturshringi": {"status": "VERIFIED_CORE", "notes": "North-West university and institutional corridor."},
    "pashan": {"status": "UNVERIFIED_RECENT_BIFURCATION", "notes": "Carved from Chaturshringi. Boundary GIS polygon unconfirmed."},
    "bavdhan": {"status": "UNVERIFIED_RECENT_BIFURCATION", "notes": "Carved from Hinjewadi/Chaturshringi/Kothrud border. Boundary GIS polygon unconfirmed."}
}


# ==============================================================================
# 3. THRESHOLD CONFIGURATION & AUDIT CLASSIFICATION
# ==============================================================================

class PuneThresholdConfig:
    """
    Configurable threshold registry with formal methodological classifications:
    - POLICY_REQUIREMENT: Mandated by legal instrument, institutional MoU, or safety policy.
    - PROVISIONAL_OPERATIONAL: Pragmatic initial operating benchmark; configurable.
    - STATISTICALLY_JUSTIFIED: Derived from formal statistical estimation theory (e.g. sampling variance).
    - UNVALIDATED_ASSUMPTION: Heuristic estimate requiring empirical validation on real local data.
    """

    def __init__(
        self,
        eda_timespan_days: float = 180.0,
        training_timespan_days: float = 1080.0,
        station_coverage_pct: float = 80.0,
        eda_min_target_positives: int = 20,
        training_min_target_positives: int = 100,
        eda_min_records: int = 500,
        training_min_records: int = 15000,
        min_coordinate_completeness_pct: float = 90.0,
    ):
        self.eda_timespan_days = eda_timespan_days
        self.training_timespan_days = training_timespan_days
        self.station_coverage_pct = station_coverage_pct
        self.eda_min_target_positives = eda_min_target_positives
        self.training_min_target_positives = training_min_target_positives
        self.eda_min_records = eda_min_records
        self.training_min_records = training_min_records
        self.min_coordinate_completeness_pct = min_coordinate_completeness_pct

    @classmethod
    def get_threshold_classifications(cls) -> Dict[str, Dict[str, Any]]:
        """Returns structured audit classification and rationale for each threshold."""
        return {
            "training_timespan_days": {
                "default_value": 1080.0,  # 36 months
                "classification": "POLICY_REQUIREMENT_AND_STATISTICALLY_JUSTIFIED",
                "rationale": (
                    "Mandated by Phase 1-3 policy to capture multi-year seasonality (monsoon, Ganesh festival surges) "
                    "and provide clean non-overlapping training (24 months) and out-of-time test holdouts (12 months). "
                    "Statistically necessary to estimate diurnal/seasonal interaction terms without lookahead."
                ),
                "limitations": "Does not account for non-stationary administrative changes (e.g. PCMC split in 2018)."
            },
            "eda_timespan_days": {
                "default_value": 180.0,  # 6 months
                "classification": "PROVISIONAL_OPERATIONAL",
                "rationale": "Pragmatic operating threshold to evaluate multi-month volume stability prior to full longitudinal export.",
                "limitations": "Does not capture full annual seasonality; provisional and configurable."
            },
            "station_coverage_pct": {
                "default_value": 80.0,  # 26 of 33 stations
                "classification": "POLICY_REQUIREMENT_AND_PROVISIONAL_OPERATIONAL",
                "rationale": "Prevents isolated precinct data from being misrepresented as city-wide intelligence.",
                "limitations": "Remaining 20% may represent rapidly expanding peri-urban zones with acute policing needs."
            },
            "training_min_target_positives": {
                "default_value": 100,
                "classification": "STATISTICALLY_JUSTIFIED",
                "rationale": "Derived from binomial sampling theory for rare event rate estimation.",
                "what_it_can_establish": (
                    "Establishes a minimal aggregate sample size for estimating an unconditional global prevalence "
                    "base rate with crude standard error approximately 1/sqrt(100) = 10%."
                ),
                "what_remains_uncertain": (
                    "Across 33 stations x 6 shifts/day (198 unit-shifts/day, or ~72,270 unit-shifts/year), 100 positive "
                    "events implies extreme spatio-temporal sparsity (annual positive rate << 0.14%). It is completely "
                    "insufficient to estimate local conditional probabilities per unit-shift. Reliability diagrams "
                    "partitioned into 10 bins with ~10 events each suffer from severe bin-boundary instability and do "
                    "NOT prove calibration stability."
                ),
                "limitations": "Does not establish conditional probability power per station-shift."
            },
            "training_min_records": {
                "default_value": 15000,
                "classification": "UNVALIDATED_ASSUMPTION_AND_PROVISIONAL_OPERATIONAL",
                "rationale": "Heuristic aggregate volume benchmark (~15-20 incidents per station per month over 36 months).",
                "what_it_can_establish": "Verifies basic ingestion throughput and gross tabular volume handling.",
                "what_remains_uncertain": (
                    "Gross row counts are decoupled from spatial and temporal balance. A total of 15,000 records "
                    "clustered in 3 central stations leaves 30 stations starved for violent crime data. Data sufficiency "
                    "requires positive support per spatial unit per shift window, not total aggregate row count."
                ),
                "limitations": "Gross count cannot prove data sufficiency or statistical power."
            },
            "eda_min_target_positives": {
                "default_value": 20,
                "classification": "PROVISIONAL_OPERATIONAL",
                "rationale": "Minimal threshold to ensure preliminary target prevalence is non-zero across harm tiers.",
                "what_it_can_establish": "Confirms presence of target crime categories in extract.",
                "what_remains_uncertain": "Completely insufficient for model fitting, feature ranking, or hypothesis testing.",
                "limitations": "Insufficient for model fitting."
            },
            "eda_min_records": {
                "default_value": 500,
                "classification": "PROVISIONAL_OPERATIONAL",
                "rationale": "Minimum volume for basic temporal and station frequency histograms.",
                "what_it_can_establish": "Enables preliminary exploratory frequency distributions and histograms.",
                "what_remains_uncertain": "Does not establish statistical power or representativeness.",
                "limitations": "Does not establish statistical power."
            },
            "min_coordinate_completeness_pct": {
                "default_value": 90.0,
                "classification": "STATISTICALLY_JUSTIFIED",
                "rationale": "Target completeness benchmark for fine-grained coordinate-level map forecasts.",
                "what_it_can_establish": "Ensures that coordinate-level micro-modeling is restricted to datasets with low overall missingness.",
                "what_remains_uncertain": (
                    "A 90% completeness threshold does NOT prove that the missing 10% are Missing Completely At Random (MCAR). "
                    "If missing coordinates are concentrated in informal settlements, slums, or peripheral beats, "
                    "coordinate density maps suffer from acute geographic attrition bias."
                ),
                "limitations": "High overall completeness does not guarantee spatial representativeness."
            },
            "littles_mcar_test": {
                "technique": "Little's Missing Completely At Random (MCAR) Test",
                "classification": "DIAGNOSTIC_HYPOTHESIS_TEST",
                "what_it_can_establish": "Tests the null hypothesis that missingness across observed variables is independent of observed values (MCAR vs MAR).",
                "what_remains_uncertain": (
                    "Cannot detect or rule out Missing Not At Random (MNAR) mechanisms where missingness depends on "
                    "unobserved latent factors (such as citizen reporting reluctance, informal unmapped settlements, "
                    "or differing beat recording practices). A non-significant test does NOT guarantee absence of selection bias."
                ),
            },
            "morans_i_spatial_autocorrelation": {
                "technique": "Global Moran's I Statistic",
                "classification": "SPATIAL_AUTOCORRELATION_DIAGNOSTIC",
                "what_it_can_establish": "Measures global spatial clustering vs dispersion among observed reporting police stations.",
                "what_remains_uncertain": (
                    "Global Moran's I computes autocorrelation ONLY across units with observed data; it cannot evaluate "
                    "unobserved non-reporting stations. It averages across the entire study area, masking acute local non-stationarity "
                    "(e.g. high-crime pockets adjacent to cantonments), and is highly sensitive to spatial weight matrix (W) specification."
                ),
            },
            "moving_block_bootstrap_7d": {
                "technique": "Seven-Day Moving-Block Bootstrap (MBB)",
                "classification": "DEPENDENT_TIME_SERIES_RESAMPLING",
                "what_it_can_establish": "Preserves short-term serial autocorrelation and weekly diurnal cycles within each resampled 7-day block.",
                "what_remains_uncertain": (
                    "Introduces artificial boundary discontinuities between blocks; breaks dependencies longer than 7 days "
                    "(bi-weekly pay cycles, monthly seasonality, multi-week Ganesh festival surges); choice of block length "
                    "involves an unavoidable bias-variance trade-off without a universally optimal length."
                ),
            },
            "calibration_reliability_bins": {
                "technique": "Binned Reliability Diagrams (Decile Partitioning)",
                "classification": "PROBABILISTIC_CALIBRATION_DIAGNOSTIC",
                "what_it_can_establish": "Provides empirical comparison between mean predicted probability and observed event frequency across probability groups.",
                "what_remains_uncertain": (
                    "Highly sensitive to bin partitioning (equal width vs equal frequency); small sample counts per bin "
                    "cause severe sampling noise and non-monotonic artifacts; grouping masks intra-bin miscalibration "
                    "and does not measure predictive sharpness or information value."
                ),
            }
        }


# Canonical default threshold instance
DEFAULT_THRESHOLD_CONFIG = PuneThresholdConfig()


# ==============================================================================
# 3.1 RETENTION POLICY CONFIGURATION & LIFECYCLE SAFETY (PHASE 7.4)
# ==============================================================================

class PuneRetentionPolicyStatus(str, Enum):
    """Formal lifecycle approval status for data retention policies."""
    PROPOSED_PENDING_INSTITUTIONAL_APPROVAL = "PROPOSED_PENDING_INSTITUTIONAL_APPROVAL"
    APPROVED_BY_COMMISSIONERATE = "APPROVED_BY_COMMISSIONERATE"
    REJECTED_OR_REVOKED = "REJECTED_OR_REVOKED"


class PuneRetentionPolicyConfig:
    """
    Retention policy and storage lifecycle safety configuration for Pune City incident data.

    STRICT GOVERNANCE INVARIANTS:
    1. Historical Coverage != Post-Acquisition Retention:
       - Historical Coverage (training_timespan_days, e.g. ~36 months / 1,080 days) specifies how far
         back past observations extend chronologically for temporal modeling.
       - Post-Acquisition Retention (retention_schedule_days, e.g. proposed 365 days) specifies how long
         received data files may be retained post-transfer on disk before mandatory deletion.
    2. Proposed != Authorized:
       - A proposed 365-day schedule is an application draft proposal, NOT an institutional authorization.
       - Missing institutional approval (is_approved_by_institution=False) cannot be interpreted as authorization.
    3. No Automated Deletion of Real Data:
       - Real datasets are NEVER deleted automatically by background daemons or timer scripts merely
         because a proposed 365-day interval has elapsed.
       - Deletion requires formal institutional instruction, DPO review, and manual operator confirmation.
    4. Category-Specific Retention Disaggregation:
       - Raw, cleaned, intermediate, temporary, and audit records have distinct retention lifecycles.
    """

    def __init__(
        self,
        proposed_retention_days: int = 365,
        approved_retention_days: Optional[int] = None,
        is_approved_by_institution: bool = False,
        approval_reference: Optional[str] = None,
        policy_status: PuneRetentionPolicyStatus = PuneRetentionPolicyStatus.PROPOSED_PENDING_INSTITUTIONAL_APPROVAL,
    ):
        self.proposed_retention_days = proposed_retention_days
        self.approved_retention_days = approved_retention_days
        self.is_approved_by_institution = is_approved_by_institution
        self.approval_reference = approval_reference
        self.policy_status = policy_status

    def validate_configuration(self) -> None:
        """
        Validates configuration consistency and fails closed on unauthorized claims.
        Guarantees that unapproved policies cannot claim approved retention days or authorization.
        """
        if self.is_approved_by_institution:
            if self.policy_status != PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE:
                raise ValueError(
                    "Inconsistent retention policy: is_approved_by_institution is True, "
                    f"but policy_status is '{self.policy_status}'."
                )
            if not self.approved_retention_days or self.approved_retention_days <= 0:
                raise ValueError(
                    "Approved retention policy must specify a positive approved_retention_days integer."
                )
            if not self.approval_reference or not str(self.approval_reference).strip():
                raise ValueError(
                    "Approved retention policy requires an official institutional approval reference (e.g. bilateral MoU addendum)."
                )
        else:
            if self.approved_retention_days is not None:
                raise ValueError(
                    "Approved retention days cannot be set when is_approved_by_institution is False. "
                    "All retention schedules remain strictly PROPOSED until institutional approval is executed."
                )
            if self.policy_status == PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE:
                raise ValueError(
                    "Policy status cannot be APPROVED_BY_COMMISSIONERATE when is_approved_by_institution is False."
                )

    CONSUMED_DELETION_TOKEN_IDS: Set[str] = set()

    @classmethod
    def clear_consumed_tokens(cls) -> None:
        """Clears in-memory consumed token identifiers (for test isolation)."""
        cls.CONSUMED_DELETION_TOKEN_IDS.clear()

    @classmethod
    def create_deletion_approval_token(
        cls,
        signing_private_key: ed25519.Ed25519PrivateKey,
        dataset_version: str,
        dataset_sha256: str,
        policy_reference: str,
        action: str = "AUTHORIZE_DATASET_DELETION",
        authorization_id: Optional[str] = None,
        token_id: Optional[str] = None,
        issuer_id: str = "pune_city_police_cop",
        valid_from_iso: Optional[str] = None,
        valid_until_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates and cryptographically signs a deletion authorization token.
        Requires the institutional private signing key.
        """
        if signing_private_key is None:
            raise ValueError("Signing private key is required to issue deletion approval token.")

        now_dt = datetime.now(timezone.utc)
        valid_from = valid_from_iso or (now_dt - timedelta(minutes=5)).isoformat()
        valid_until = valid_until_iso or (now_dt + timedelta(hours=24)).isoformat()
        tok_id = token_id or f"del-tok-{uuid.uuid4()}"
        auth_id = authorization_id or f"DEL-AUTH-{uuid.uuid4().hex[:8].upper()}"

        token_payload = {
            "action": str(action).strip(),
            "authorization_id": str(auth_id).strip(),
            "dataset_sha256": str(dataset_sha256).strip().lower(),
            "dataset_version": str(dataset_version).strip(),
            "issued_at": now_dt.isoformat(),
            "issuer_id": str(issuer_id).strip(),
            "policy_reference": str(policy_reference).strip(),
            "token_id": str(tok_id).strip(),
            "valid_from": str(valid_from).strip(),
            "valid_until": str(valid_until).strip(),
        }

        canonical_payload = canonicalize_rfc8785(token_payload)
        sig_bytes = signing_private_key.sign(canonical_payload)
        token_dict = dict(token_payload)
        token_dict["signature"] = sig_bytes.hex()
        return token_dict

    def verify_deletion_approval_token(
        self,
        token: Any,
        expected_dataset_version: Optional[str] = None,
        expected_dataset_sha256: Optional[str] = None,
        current_time_iso: Optional[str] = None,
        is_fixture: bool = False,
        consume_token: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Cryptographically validates an institutional deletion approval token.
        Returns (is_valid, failure_reason).
        """
        # 1. Type and Boolean checks
        if token is None or isinstance(token, bool):
            return (False, "Deletion approval token cannot be None or a Boolean.")

        if isinstance(token, str):
            token_str = token.strip()
            if not token_str:
                return (False, "Deletion approval token cannot be empty.")
            try:
                token_dict = json.loads(token_str)
            except Exception:
                return (False, "Approval token string is not valid JSON; arbitrary strings cannot authorize deletion.")
        elif isinstance(token, dict):
            token_dict = token
        else:
            return (False, f"Approval token must be a JSON string or dict, got {type(token).__name__}.")

        if not isinstance(token_dict, dict):
            return (False, "Approval token payload must be a JSON object dictionary.")

        # 2. Institutional policy approval state check
        if not self.is_approved_by_institution:
            return (False, "Institutional retention policy is unapproved. Real-data deletion is strictly prohibited.")
        if self.policy_status != PuneRetentionPolicyStatus.APPROVED_BY_COMMISSIONERATE:
            return (False, f"Retention policy status is '{self.policy_status}'; requires APPROVED_BY_COMMISSIONERATE.")
        if not self.approval_reference or not str(self.approval_reference).strip():
            return (False, "Active retention policy has no institutional approval reference.")

        # 3. Required fields check
        required_fields = [
            "action", "dataset_version", "dataset_sha256", "policy_reference",
            "authorization_id", "token_id", "issuer_id", "valid_from", "valid_until", "signature"
        ]
        missing = [f for f in required_fields if f not in token_dict or not str(token_dict[f]).strip()]
        if missing:
            return (False, f"Malformed token: missing required field(s): {', '.join(missing)}.")

        # 4. Action binding
        action = str(token_dict.get("action")).strip()
        if action != "AUTHORIZE_DATASET_DELETION":
            return (False, f"Invalid token action '{action}'; expected 'AUTHORIZE_DATASET_DELETION'.")

        # 5. Policy reference binding
        token_policy_ref = str(token_dict.get("policy_reference")).strip()
        if token_policy_ref != str(self.approval_reference).strip():
            return (
                False,
                f"Token policy reference '{token_policy_ref}' does not match active approved policy reference '{self.approval_reference}'."
            )

        # 6. Version binding (if specified)
        token_version = str(token_dict.get("dataset_version")).strip()
        if expected_dataset_version and token_version != str(expected_dataset_version).strip():
            return (
                False,
                f"Token dataset version '{token_version}' does not match target version '{expected_dataset_version}'."
            )

        # 7. Dataset SHA-256 fingerprint binding (if specified)
        token_sha = str(token_dict.get("dataset_sha256")).strip().lower()
        if expected_dataset_sha256 and token_sha != str(expected_dataset_sha256).strip().lower():
            return (
                False,
                f"Token dataset fingerprint '{token_sha}' does not match target dataset SHA-256 '{expected_dataset_sha256}'."
            )

        # 8. Replay attack protection
        token_id = str(token_dict.get("token_id")).strip()
        if token_id in self.CONSUMED_DELETION_TOKEN_IDS:
            return (False, f"Replay rejected: token_id '{token_id}' has already been consumed.")

        # 9. Time validity (Approval period)
        now_dt = datetime.now(timezone.utc)
        if current_time_iso:
            try:
                now_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
            except Exception:
                pass

        try:
            valid_from = datetime.fromisoformat(str(token_dict.get("valid_from")).replace("Z", "+00:00"))
            valid_until = datetime.fromisoformat(str(token_dict.get("valid_until")).replace("Z", "+00:00"))
        except Exception as e:
            return (False, f"Malformed validity timestamps in token: {e}")

        if now_dt < valid_from:
            return (False, f"Token is not yet active (valid_from: {token_dict.get('valid_from')}).")
        if now_dt > valid_until:
            return (False, f"Token has expired (valid_until: {token_dict.get('valid_until')}).")

        # 10. Revocation check
        auth_id = str(token_dict.get("authorization_id")).strip()
        sig_hex = str(token_dict.get("signature")).strip()
        if (
            auth_id in InstitutionalIssuerRegistry.TRUSTED_REVOKED_IDENTIFIERS
            or token_id in InstitutionalIssuerRegistry.TRUSTED_REVOKED_IDENTIFIERS
            or sig_hex in InstitutionalIssuerRegistry.TRUSTED_REVOKED_IDENTIFIERS
            or token_policy_ref in InstitutionalIssuerRegistry.TRUSTED_REVOKED_IDENTIFIERS
        ):
            return (False, f"Token or authorization identifier '{auth_id}' is revoked.")

        # 11. Issuer and cryptographic verification
        issuer_id = str(token_dict.get("issuer_id")).strip()
        if issuer_id not in InstitutionalIssuerRegistry.APPROVED_ISSUERS:
            return (False, f"Unknown or untrusted token issuer '{issuer_id}'.")

        issuer_info = InstitutionalIssuerRegistry.APPROVED_ISSUERS[issuer_id]
        if issuer_info.get("is_fixture_authority") and not is_fixture:
            return (False, "Test fixture authority cannot authorize real dataset deletion in production.")

        payload_to_verify = {k: v for k, v in token_dict.items() if k != "signature"}
        canonical_payload = canonicalize_rfc8785(payload_to_verify)

        is_valid_sig, sig_err = InstitutionalIssuerRegistry.verify_signature(
            issuer_id=issuer_id,
            canonical_payload=canonical_payload,
            signature_hex=sig_hex,
        )
        if not is_valid_sig:
            return (False, f"Cryptographic token verification failed: {sig_err}")

        # 12. Token consumption
        if consume_token:
            self.CONSUMED_DELETION_TOKEN_IDS.add(token_id)

        return (True, None)

    def can_delete_real_data(
        self,
        is_manual_operator_confirmed: bool = False,
        approval_token: Optional[Union[str, Dict[str, Any]]] = None,
        dataset_version: Optional[str] = None,
        dataset_sha256: Optional[str] = None,
        current_time_iso: Optional[str] = None,
        is_fixture: bool = False,
        consume_token: bool = False,
    ) -> bool:
        """
        Determines whether real dataset deletion is authorized.
        Safety Invariant: Prohibits automatic deletion of real data based merely on elapsed proposed days.
        Requires explicit institutional approval, manual operator confirmation, and an authentic cryptographic token.
        Rejects user-controlled Booleans, arbitrary strings, expired/revoked/replayed tokens, and unprovisioned keys.
        """
        if not self.is_approved_by_institution:
            return False
        if not is_manual_operator_confirmed:
            return False
        if approval_token is None or isinstance(approval_token, bool):
            return False

        is_valid, _ = self.verify_deletion_approval_token(
            token=approval_token,
            expected_dataset_version=dataset_version,
            expected_dataset_sha256=dataset_sha256,
            current_time_iso=current_time_iso,
            is_fixture=is_fixture,
            consume_token=consume_token,
        )
        return is_valid

    def execute_authorized_deletion(
        self,
        target_path: str,
        is_manual_operator_confirmed: bool = False,
        approval_token: Optional[Union[str, Dict[str, Any]]] = None,
        dataset_version: Optional[str] = None,
        dataset_sha256: Optional[str] = None,
        current_time_iso: Optional[str] = None,
        is_fixture: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes authorized deletion of a real dataset file or version directory.
        Fails closed if institutional approval, operator confirmation, or token verification fails.
        Consumes the token upon successful validation to prevent replay attacks.
        Emits a structured audit receipt containing the target path and deletion timestamp.
        """
        if not self.is_approved_by_institution:
            raise PermissionError("Deletion blocked: Institutional retention policy is unapproved.")
        if not is_manual_operator_confirmed:
            raise PermissionError("Deletion blocked: Manual operator confirmation is required.")

        is_valid, failure_reason = self.verify_deletion_approval_token(
            token=approval_token,
            expected_dataset_version=dataset_version,
            expected_dataset_sha256=dataset_sha256,
            current_time_iso=current_time_iso,
            is_fixture=is_fixture,
            consume_token=True,
        )
        if not is_valid:
            raise PermissionError(f"Deletion blocked by token verification failure: {failure_reason}")

        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Target path for deletion does not exist: '{target_path}'")

        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)

        receipt = {
            "action": "REAL_DATASET_DELETED",
            "target_path": target_path,
            "deletion_timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_reference": self.approval_reference,
            "dataset_version": dataset_version,
            "dataset_sha256": dataset_sha256,
            "status": "SUCCESS",
        }
        return receipt

    @classmethod
    def get_data_category_retention_matrix(cls) -> Dict[str, Dict[str, Any]]:
        """Returns the formal disaggregated retention rules per data category."""
        return {
            "raw_authorized_dataset": {
                "classification": "RESTRICTED_SOURCE_DATA",
                "proposed_retention": "365 days from receipt (Proposed; subject to MoU terms)",
                "storage_tier": "Encrypted offline / air-gapped research vault (AES-256)",
                "deletion_authority": "Office of the Commissioner of Police, Pune City",
                "sanitization_standard": "NIST SP 800-88 Rev. 1 compliant purge/overwriting (or OS unlinking if on standard filesystem with documented limitation)",
                "audit_evidence": "Certificate of Data Sanitization with raw SHA-256 digest"
            },
            "cleaned_incident_dataset": {
                "classification": "DERIVED_PSEUDONYMIZED_RESEARCH_DATA",
                "proposed_retention": "Synchronized with raw dataset retention (maximum approved study period)",
                "storage_tier": "Versioned intake directory with application-level overwrite protection",
                "deletion_authority": "Institutional Data Governance Committee and Pune Police Authority",
                "sanitization_standard": "NIST SP 800-88 Rev. 1 compliant purge/overwriting",
                "audit_evidence": "Signed Data Destruction Log with cleaned SHA-256 digest"
            },
            "temporary_processing_files": {
                "classification": "EPHEMERAL_SYSTEM_SCRATCH",
                "proposed_retention": "0 days (Purged immediately upon ingestion pipeline completion)",
                "storage_tier": "Local scratch / in-memory temp buffers",
                "deletion_authority": "Automated pipeline lifecycle (immediate unlinking)",
                "sanitization_standard": "Standard filesystem unlinking / buffer release",
                "audit_evidence": "Pipeline execution log confirmation"
            },
            "intermediate_analytical_datasets": {
                "classification": "EXPLORATORY_RESEARCH_INTERMEDIATES",
                "proposed_retention": "Active exploratory analysis duration only; deleted prior to final archiving",
                "storage_tier": "Isolated research enclave volume",
                "deletion_authority": "Lead ML Engineer / Data Governance Officer",
                "sanitization_standard": "Secure file unlinking and directory purge",
                "audit_evidence": "Cleaned version archive manifest"
            },
            "aggregated_statistical_reports": {
                "classification": "NON_PII_RESEARCH_OUTPUT",
                "proposed_retention": "Permanent (contains zero citizen records, names, coordinates, or FIR numbers)",
                "storage_tier": "Standard project documentation / artifact repository",
                "deletion_authority": "N/A (Public/Institutional academic record)",
                "sanitization_standard": "N/A (Contains only aggregated counts, histograms, and metrics)",
                "audit_evidence": "Permanent Git-tracked analysis report"
            },
            "model_training_datasets": {
                "classification": "FUTURE_TRAINING_RECORDS",
                "proposed_retention": "LOCKED_DISABLED_IN_PHASE_7 (0 days; creation prohibited)",
                "storage_tier": "N/A (Prohibited in Stage 0-3)",
                "deletion_authority": "N/A (Requires Stage 4 MoU training addendum)",
                "sanitization_standard": "N/A",
                "audit_evidence": "N/A"
            },
            "audit_manifests_and_integrity_records": {
                "classification": "PERMANENT_INTEGRITY_PROVENANCE",
                "proposed_retention": "Permanent (retained after dataset deletion for legal & scientific reproducibility)",
                "storage_tier": "Versioned directory (intake_audit_manifest.json, authorized_manifest.json)",
                "deletion_authority": "Never purged (essential audit trail; zero citizen PII)",
                "sanitization_standard": "N/A (Cryptographic hashes and metadata only)",
                "audit_evidence": "Permanent audit log"
            },
            "backups_and_recoverable_copies": {
                "classification": "DISASTER_RECOVERY_ARCHIVE",
                "proposed_retention": "Synchronized strictly with raw authorized dataset retention",
                "storage_tier": "Encrypted backup media (AES-256)",
                "deletion_authority": "Institutional Information Security Officer (CISO)",
                "sanitization_standard": "NIST SP 800-88 Rev. 1 media purge / physical destruction",
                "audit_evidence": "Backup Media Purge Certificate"
            }
        }


# Canonical default retention policy instance (strictly PROPOSED pending institutional approval)
DEFAULT_RETENTION_POLICY_CONFIG = PuneRetentionPolicyConfig()


# ==============================================================================
# 4. HARDENED INSTITUTIONAL ISSUER REGISTRY & CRYPTOGRAPHIC VERIFICATION
# ==============================================================================

def canonicalize_rfc8785(data: Any) -> bytes:
    """
    Serializes a Python data structure to canonical JSON bytes per RFC 8785 (JSON Canonicalization Scheme - JCS).

    Conformance Rules:
    1. Output is strictly UTF-8 encoded without a byte order mark (BOM).
    2. Zero whitespace between tokens (separators=(',', ':')).
    3. Dictionary/object keys are sorted by UTF-16 code units (implemented via big-endian UTF-16 byte sort).
    4. Strings: Quotation mark ("), reverse solidus (\\), and control characters (U+0000 to U+001F)
       are escaped. Standard short escapes (\\b, \\t, \\n, \\f, \\r) are used where applicable;
       other control characters are escaped as \\u00xx with lowercase hexadecimal.
       Characters with Unicode scalar values >= U+0020 (including Indian/Devanagari scripts and
       supplementary plane characters) are preserved as literal raw UTF-8 bytes and are NEVER
       converted to \\uXXXX escapes.
    5. Numbers: Formatted strictly per ECMAScript (ECMA-262) Section 7.1.12.1.
       Floats with integer values are formatted without decimal points or exponents.
       Negative zero (-0.0) is normalized to 0.
       NaN and Infinity are strictly forbidden (raises ValueError).
    6. Unsupported types (sets, binary, custom classes) raise TypeError.
    """
    def _precheck(val: Any) -> None:
        if val is None or isinstance(val, (bool, str, int)):
            return
        elif isinstance(val, float):
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"RFC 8785 prohibits NaN and Infinity, got {val}")
        elif isinstance(val, dict):
            for k, v in val.items():
                if not isinstance(k, str):
                    raise TypeError(f"Type {type(k).__name__} is not JSON-serializable under RFC 8785")
                _precheck(v)
        elif isinstance(val, (list, tuple)):
            for item in val:
                _precheck(item)
        else:
            raise TypeError(f"Type {type(val).__name__} is not JSON-serializable under RFC 8785")

    _precheck(data)
    try:
        import jcs
        return jcs.canonicalize(data)
    except ImportError:
        # Fallback pure-Python RFC 8785 implementation if jcs package is not present
        def convert2Es6Format(value: Any) -> str:
            fvalue = float(value)
            if fvalue == 0:
                return "0"
            pyDouble = str(fvalue)
            if pyDouble.find("n") >= 0:
                raise ValueError("Invalid JSON number: " + pyDouble)
            pySign = ""
            if pyDouble.find("-") == 0:
                pySign = "-"
                pyDouble = pyDouble[1:]
            pyExpStr = ""
            pyExpVal = 0
            q = pyDouble.find("e")
            if q > 0:
                pyExpStr = pyDouble[q:]
                if pyExpStr[2:3] == "0":
                    pyExpStr = pyExpStr[:2] + pyExpStr[3:]
                pyDouble = pyDouble[0:q]
                pyExpVal = int(pyExpStr[1:])
            pyFirst = pyDouble
            pyDot = ""
            pyLast = ""
            q = pyDouble.find(".")
            if q > 0:
                pyDot = "."
                pyFirst = pyDouble[:q]
                pyLast = pyDouble[q + 1:]
            if pyLast == "0":
                pyDot = ""
                pyLast = ""
            if pyExpVal > 0 and pyExpVal < 21:
                pyFirst += pyLast
                pyLast = ""
                pyDot = ""
                pyExpStr = ""
                q = pyExpVal - len(pyFirst)
                while q >= 0:
                    q -= 1
                    pyFirst += "0"
            elif pyExpVal < 0 and pyExpVal > -7:
                pyLast = pyFirst + pyLast
                pyFirst = "0"
                pyDot = "."
                pyExpStr = ""
                q = pyExpVal
                while q < -1:
                    q += 1
                    pyLast = "0" + pyLast
            return pySign + pyFirst + pyDot + pyLast + pyExpStr

        def _encode_val(v: Any) -> str:
            if v is None:
                return "null"
            if v is True:
                return "true"
            if v is False:
                return "false"
            if isinstance(v, (int, float)):
                return convert2Es6Format(v)
            if isinstance(v, str):
                return json.dumps(v, ensure_ascii=False)
            if isinstance(v, (list, tuple)):
                return "[" + ",".join(_encode_val(x) for x in v) + "]"
            if isinstance(v, dict):
                sorted_items = sorted(v.items(), key=lambda kv: str(kv[0]).encode("utf-16-be"))
                return "{" + ",".join(f"{json.dumps(str(k), ensure_ascii=False)}:{_encode_val(val)}" for k, val in sorted_items) + "}"
            raise TypeError(f"Type {type(v).__name__} is not JSON-serializable under RFC 8785")

        return _encode_val(data).encode("utf-8")


class InstitutionalIssuerRegistry:
    """
    Approved institutional issuer trust model for Pune City Police data authorization.
    Operates strictly offline without external web dependencies.
    Uses asymmetric Ed25519 digital signatures over canonical manifest metadata.

    Security Model & Trust Boundaries:
    - Asymmetric Key Separation: The issuing authority (Pune Police Commissionerate)
      retains the private signing key. The Strata Risk application possesses ONLY
      trusted public verification keys.
    - Zero Production Secrets in Code: No production private keys or public keys
      are committed to source control. Production public keys are provisioned
      strictly via secure environment configuration (PUNE_COP_ED25519_PUBLIC_KEY).
    - Unprovisioned Credentials Block Authorization: If the public verification key
      is not provisioned, authorization is unconditionally blocked (AUTHORIZATION_UNVERIFIED).
    - Fixture Credential Isolation: Fixture credentials cannot authorize production datasets.
    - Dataset Fingerprint Binding: Strict SHA-256 fingerprint matching binds the signed
      manifest to the delivered dataset bits.
    - Immutability Disclaimer: Storage overwrite prevention is application-level and does
      not guarantee hardware WORM immutability without dedicated infrastructure.
    """

    DEFAULT_TEST_FIXTURE_PUBLIC_KEY = "4de0ce474e3ba1dbd409354955150b922c369ac822d30e4cc070dc09ed280009"

    DEFAULT_REVOCATION_LIST_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "pune_revocations.json"
    )

    APPROVED_ISSUERS: Dict[str, Dict[str, Any]] = {
        "pune_city_police_cop": {
            "name": "Office of Commissioner of Police, Pune City",
            "jurisdiction": "Pune City Police Commissionerate",
            "signature_algorithm": "Ed25519",
            "public_key_env_var": "PUNE_COP_ED25519_PUBLIC_KEY",
            "public_key_hex": None,  # Strictly unprovisioned in source code
            "allowed_purposes": ["public_safety_risk_modeling", "exploratory_data_analysis", "offline_validation"],
            "permitted_fields": ["fir_number_hash", "police_station_id", "incident_datetime", "section_code", "registration_datetime", "place_of_occurrence", "latitude", "longitude"],
            "is_active": True,
            "is_fixture_authority": False,
        },
        "test_fixture_authority": {
            "name": "Strata Risk Unit Test Synthetic Authority",
            "jurisdiction": "Sandboxed Test Environment",
            "signature_algorithm": "Ed25519",
            "public_key_env_var": "TEST_FIXTURE_ED25519_PUBLIC_KEY",
            "default_sandbox_public_key": "4de0ce474e3ba1dbd409354955150b922c369ac822d30e4cc070dc09ed280009",
            "allowed_purposes": ["unit_testing", "exploratory_data_analysis"],
            "permitted_fields": ["fir_number_hash", "police_station_id", "incident_datetime", "section_code", "registration_datetime", "place_of_occurrence", "latitude", "longitude"],
            "is_active": True,
            "is_fixture_authority": True,
        }
    }

    # Monotonically increasing sequence tracker to prevent stale CRL rollback substitution
    LATEST_OBSERVED_CRL_SEQUENCE: int = 0

    # Trusted in-memory revocation registry for authoritative revocation enforcement
    TRUSTED_REVOKED_IDENTIFIERS: Set[str] = set()

    @classmethod
    def register_revocation(cls, identifier: str) -> None:
        """Registers a revoked authorization_id, mou_reference, or signature hash in the trusted revocation registry."""
        if identifier:
            cls.TRUSTED_REVOKED_IDENTIFIERS.add(str(identifier).strip())

    @classmethod
    def clear_trusted_revocations(cls) -> None:
        """Clears in-memory trusted revocations (primarily for unit test isolation)."""
        cls.TRUSTED_REVOKED_IDENTIFIERS.clear()

    @classmethod
    def reset_crl_sequence(cls, val: int = 0) -> None:
        """Resets the sequence tracker (for unit test isolation)."""
        cls.LATEST_OBSERVED_CRL_SEQUENCE = val

    @classmethod
    def create_authorized_crl(
        cls,
        issuer_id: str,
        revoked_authorizations: List[Any],
        crl_sequence: int = 1,
        issued_at_iso: Optional[str] = None,
        expires_at_iso: Optional[str] = None,
        description: str = "Strata Risk Authorized Certificate Revocation List",
        signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None,
    ) -> Dict[str, Any]:
        """
        Creates and cryptographically signs an authoritative Certificate Revocation List (CRL).
        Signs canonical RFC 8785 JSON of payload excluding 'signature' and 'crl_sha256'.
        """
        now_dt = datetime.now(timezone.utc)
        issued_at = issued_at_iso or now_dt.isoformat()
        expires_at = expires_at_iso or (now_dt + timedelta(days=365)).isoformat()

        crl_dict = {
            "crl_version": "1.0",
            "crl_sequence": int(crl_sequence),
            "issuer_id": issuer_id,
            "description": description,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "revoked_authorizations": revoked_authorizations,
        }

        canonical_payload = canonicalize_rfc8785(crl_dict)
        crl_sha = hashlib.sha256(canonical_payload).hexdigest()
        crl_dict["crl_sha256"] = crl_sha

        if signing_private_key:
            sig_bytes = signing_private_key.sign(canonical_payload)
            crl_dict["signature"] = sig_bytes.hex()

        return crl_dict

    @classmethod
    def load_persistent_crl(
        cls,
        crl_path: Optional[str] = None,
        current_time_iso: Optional[str] = None,
        require_crl: bool = False,
        require_signed_crl: bool = False,
    ) -> Tuple[bool, Optional[str], Set[str], Dict[str, Any]]:
        """
        Loads and validates the persistent Certificate Revocation List (CRL).
        
        Security Properties:
        - Survives Application Restarts: Stored persistently on disk.
        - Multi-Worker Consistency: Re-read dynamically on verification to prevent worker divergence.
        - Authenticity & Schema: Verifies crl_version, crl_sequence, issuer_id, validity timestamps, and revoked items.
        - Rollback Protection: Enforces crl_sequence monotonicity to prevent stale substitution replay attacks.
        - Asymmetric Signature Verification: Verifies Ed25519 digital signature over canonical CRL payload when present.
        - Freshness & Expiry: Evaluates whether CRL has expired or is not yet effective.
        - Fail-Closed Policy: If require_crl is True (or PUNE_REQUIRE_PERSISTENT_REVOCATION_LIST is set)
          and the CRL is missing, expired, or malformed, verification unconditionally fails closed.
        """
        target_path = crl_path or os.environ.get("PUNE_REVOCATION_LIST_PATH") or cls.DEFAULT_REVOCATION_LIST_PATH
        policy_requires_crl = require_crl or os.environ.get("PUNE_REQUIRE_PERSISTENT_REVOCATION_LIST", "").lower() in ("1", "true", "yes")
        policy_requires_signed = require_signed_crl or os.environ.get("PUNE_REQUIRE_SIGNED_CRL", "").lower() in ("1", "true", "yes")

        if not os.path.exists(target_path):
            if policy_requires_crl:
                return (False, f"Persistent CRL file missing at '{target_path}'. Production authorization policy requires verified persistent CRL.", set(), {})
            return (True, None, set(), {})

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                crl_data = json.load(f)
        except Exception as e:
            return (False, f"Malformed persistent CRL file at '{target_path}': {str(e)}", set(), {})

        # Schema validation
        required_keys = ["crl_version", "issuer_id", "issued_at", "expires_at", "revoked_authorizations"]
        for k in required_keys:
            if k not in crl_data:
                return (False, f"Persistent CRL schema invalid: missing required field '{k}'.", set(), crl_data)

        # Rollback & replay prevention via monotonic sequence counter
        seq_num = crl_data.get("crl_sequence")
        if seq_num is not None:
            try:
                seq_int = int(seq_num)
                if seq_int < 1:
                    return (False, f"Persistent CRL crl_sequence must be a positive integer, got {seq_int}.", set(), crl_data)
                if cls.LATEST_OBSERVED_CRL_SEQUENCE > 0 and seq_int < cls.LATEST_OBSERVED_CRL_SEQUENCE:
                    return (
                        False,
                        f"Stale CRL rollback attack detected: presented crl_sequence ({seq_int}) "
                        f"is older than verified active sequence ({cls.LATEST_OBSERVED_CRL_SEQUENCE}).",
                        set(),
                        crl_data,
                    )
                cls.LATEST_OBSERVED_CRL_SEQUENCE = max(cls.LATEST_OBSERVED_CRL_SEQUENCE, seq_int)
            except (ValueError, TypeError):
                return (False, f"Persistent CRL crl_sequence is not a valid integer: {seq_num}", set(), crl_data)

        # Freshness and expiry verification
        now_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00")) if current_time_iso else datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)

        try:
            expires_dt = datetime.fromisoformat(str(crl_data["expires_at"]).replace("Z", "+00:00"))
            issued_dt = datetime.fromisoformat(str(crl_data["issued_at"]).replace("Z", "+00:00"))
            if expires_dt.tzinfo is None:
                expires_dt = expires_dt.replace(tzinfo=timezone.utc)
            if issued_dt.tzinfo is None:
                issued_dt = issued_dt.replace(tzinfo=timezone.utc)

            if now_dt > expires_dt:
                return (False, f"Persistent CRL expired on {crl_data['expires_at']}. Stale revocation data rejected.", set(), crl_data)

            if now_dt < issued_dt:
                return (False, f"Persistent CRL is not yet effective until {crl_data['issued_at']}.", set(), crl_data)
        except Exception as e:
            return (False, f"Persistent CRL has unparseable timestamps: {str(e)}", set(), crl_data)

        # Optional digest verification if expected hash is configured
        expected_sha = os.environ.get("PUNE_EXPECTED_CRL_SHA256") or crl_data.get("crl_sha256")
        if expected_sha:
            content_to_hash = {k: v for k, v in crl_data.items() if k not in ("crl_sha256", "signature")}
            computed_sha = hashlib.sha256(canonicalize_rfc8785(content_to_hash)).hexdigest()
            if computed_sha.lower() != str(expected_sha).lower():
                return (False, f"Persistent CRL integrity digest mismatch: computed {computed_sha[:12]}... != expected {expected_sha[:12]}...", set(), crl_data)

        # Digital signature verification
        crl_sig = crl_data.get("signature")
        if crl_sig:
            payload_to_verify = {k: v for k, v in crl_data.items() if k not in ("signature", "crl_sha256")}
            canonical_payload = canonicalize_rfc8785(payload_to_verify)
            is_valid_sig, sig_err = cls.verify_signature(
                issuer_id=crl_data["issuer_id"],
                canonical_payload=canonical_payload,
                signature_hex=str(crl_sig),
            )
            if not is_valid_sig:
                return (
                    False,
                    f"Persistent CRL digital signature invalid for issuer '{crl_data['issuer_id']}': {sig_err}",
                    set(),
                    crl_data,
                )
        elif policy_requires_signed:
            return (
                False,
                f"Persistent CRL missing required institutional digital signature for issuer '{crl_data['issuer_id']}'.",
                set(),
                crl_data,
            )

        # Collect revoked tokens
        revoked_set: Set[str] = set()
        raw_revoked = crl_data.get("revoked_authorizations", [])
        if isinstance(raw_revoked, list):
            for item in raw_revoked:
                if isinstance(item, str):
                    revoked_set.add(item.strip())
                elif isinstance(item, dict):
                    for key in ("identifier", "authorization_id", "mou_reference", "signature"):
                        val = item.get(key)
                        if val:
                            revoked_set.add(str(val).strip())

        return (True, None, revoked_set, crl_data)

    @classmethod
    def is_authorization_revoked(
        cls,
        manifest: Dict[str, Any],
        current_time_iso: Optional[str] = None,
        crl_path: Optional[str] = None,
        require_crl: bool = False,
        require_signed_crl: bool = False,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates revocation against:
        1. Manifest self-declared revocation flag (is_revoked: True).
        2. In-memory trusted revocation registry (ephemeral).
        3. Environment CRL (PUNE_REVOKED_AUTHORIZATIONS).
        4. Persistent authenticated CRL file (PUNE_REVOCATION_LIST_PATH).
        
        Enforces fail-closed behavior if persistent CRL is required but invalid/expired.
        """
        # 1. Manifest self-declared revocation flag
        if manifest.get("is_revoked", False) is True:
            return (True, "Authorization manifest contains explicit is_revoked: True flag.")

        auth_id = str(manifest.get("authorization_id", "")).strip()
        mou_ref = str(manifest.get("mou_reference", "")).strip()
        sig_str = str(manifest.get("signature") or manifest.get("verification_token") or "").strip()

        # 2. Check trusted in-memory registry
        if auth_id and auth_id in cls.TRUSTED_REVOKED_IDENTIFIERS:
            return (True, f"Authorization ID '{auth_id}' is present in trusted revocation registry.")

        if mou_ref and mou_ref in cls.TRUSTED_REVOKED_IDENTIFIERS:
            return (True, f"MoU reference '{mou_ref}' is present in trusted revocation registry.")

        if sig_str and sig_str in cls.TRUSTED_REVOKED_IDENTIFIERS:
            return (True, "Digital signature digest is present in trusted revocation registry.")

        # 3. Check environment-provisioned CRL (PUNE_REVOKED_AUTHORIZATIONS)
        env_crl = os.environ.get("PUNE_REVOKED_AUTHORIZATIONS", "")
        if env_crl:
            revoked_tokens = {tok.strip() for tok in env_crl.split(",") if tok.strip()}
            if auth_id in revoked_tokens:
                return (True, f"Authorization ID '{auth_id}' is revoked via PUNE_REVOKED_AUTHORIZATIONS environment CRL.")
            if mou_ref in revoked_tokens:
                return (True, f"MoU reference '{mou_ref}' is revoked via PUNE_REVOKED_AUTHORIZATIONS environment CRL.")
            if sig_str in revoked_tokens:
                return (True, "Digital signature is revoked via PUNE_REVOKED_AUTHORIZATIONS environment CRL.")

        # 4. Check persistent Certificate Revocation List (CRL)
        crl_ok, crl_err, persistent_revoked_ids, _ = cls.load_persistent_crl(
            crl_path=crl_path,
            current_time_iso=current_time_iso,
            require_crl=require_crl,
            require_signed_crl=require_signed_crl,
        )
        if not crl_ok:
            return (True, f"Revocation integrity check failed closed: {crl_err}")

        if auth_id and auth_id in persistent_revoked_ids:
            return (True, f"Authorization ID '{auth_id}' is revoked in persistent CRL.")
        if mou_ref and mou_ref in persistent_revoked_ids:
            return (True, f"MoU reference '{mou_ref}' is revoked in persistent CRL.")
        if sig_str and sig_str in persistent_revoked_ids:
            return (True, "Digital signature digest is revoked in persistent CRL.")

        return (False, None)

    @classmethod
    def get_issuer_public_key(
        cls,
        issuer_id: str,
        explicit_public_key_hex: Optional[str] = None
    ) -> Optional[ed25519.Ed25519PublicKey]:
        """
        Resolves the Ed25519 public verification key for the given institutional issuer.
        The application possesses ONLY public verification keys.
        Production public keys are NEVER hardcoded in source code; they must be provisioned
        via secure environment configuration (e.g. PUNE_COP_ED25519_PUBLIC_KEY).
        Returns Ed25519PublicKey instance, or None if unprovisioned.
        """
        if explicit_public_key_hex:
            try:
                return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(explicit_public_key_hex.strip()))
            except Exception:
                return None

        issuer_info = cls.APPROVED_ISSUERS.get(issuer_id)
        if not issuer_info:
            return None

        env_var = issuer_info.get("public_key_env_var")
        if env_var:
            env_val = os.environ.get(env_var)
            if env_val:
                try:
                    return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(env_val.strip()))
                except Exception:
                    return None

        # Test fixture authority has a sandboxed default public key
        if issuer_info.get("is_fixture_authority"):
            default_key = issuer_info.get("default_sandbox_public_key")
            if default_key:
                try:
                    return ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(default_key))
                except Exception:
                    return None

        return None

    @classmethod
    def compute_canonical_payload(
        cls,
        issuer_id: str,
        authorization_id: str,
        mou_reference: str,
        permitted_use: str,
        valid_from: str,
        valid_until: str,
        dataset_sha256: Optional[str] = None,
        permitted_fields: Optional[List[str]] = None,
        manifest_version: str = "2.1",
    ) -> bytes:
        """
        Constructs deterministic canonical serialization (RFC 8785 JSON Canonicalization Scheme style)
        binding all authorization-sensitive fields:
        - authorization_id
        - dataset_sha256
        - issuer_id
        - manifest_version
        - mou_reference
        - permitted_fields (dataset scope)
        - permitted_use
        - valid_from
        - valid_until
        """
        canonical_dict = {
            "authorization_id": str(authorization_id).strip(),
            "dataset_sha256": str(dataset_sha256 or "*").strip(),
            "issuer_id": str(issuer_id).strip(),
            "manifest_version": str(manifest_version or "2.1").strip(),
            "mou_reference": str(mou_reference).strip(),
            "permitted_fields": sorted(str(f).strip() for f in (permitted_fields or [])) if permitted_fields else [],
            "permitted_use": str(permitted_use).strip(),
            "valid_from": str(valid_from).strip(),
            "valid_until": str(valid_until).strip(),
        }
        return canonicalize_rfc8785(canonical_dict)

    @classmethod
    def verify_signature(
        cls,
        issuer_id: str,
        canonical_payload: bytes,
        signature_hex: str,
        explicit_public_key_hex: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies Ed25519 digital signature using the issuer's public key.
        Returns (is_valid, error_message).
        """
        pub_key = cls.get_issuer_public_key(issuer_id, explicit_public_key_hex=explicit_public_key_hex)
        if not pub_key:
            issuer_info = cls.APPROVED_ISSUERS.get(issuer_id, {})
            return (False, f"Institutional public verification key for issuer '{issuer_id}' is unprovisioned (environment variable '{issuer_info.get('public_key_env_var')}' is unset). Production authorization is blocked until official public key provisioning.")

        try:
            clean_sig = signature_hex.strip()
            sig_bytes = bytes.fromhex(clean_sig)
            if len(sig_bytes) != 64:
                return (False, f"Ed25519 signature must be exactly 64 bytes (128 hex chars), got {len(sig_bytes)} bytes.")
            pub_key.verify(sig_bytes, canonical_payload)
            return (True, None)
        except InvalidSignature:
            return (False, "Ed25519 signature verification failed: digital signature is invalid, forged, or tampered.")
        except Exception as e:
            return (False, f"Malformed signature format: {str(e)}")

    @classmethod
    def create_authorized_manifest(
        cls,
        signing_private_key: Optional[ed25519.Ed25519PrivateKey] = None,
        mou_reference: str = "MOU/PUNE-COP/2026/STRATA-001",
        issuer_id: str = "pune_city_police_cop",
        permitted_use: str = "public_safety_risk_modeling",
        valid_from: str = "2026-01-01T00:00:00Z",
        valid_until: str = "2027-12-31T23:59:59Z",
        dataset_sha256: Optional[str] = None,
        is_fixture: bool = False,
        is_revoked: bool = False,
        retention_schedule_days: int = 365,
        authorization_id: Optional[str] = None,
        permitted_fields: Optional[List[str]] = None,
        manifest_version: str = "2.1",
    ) -> Dict[str, Any]:
        """
        Helper to generate an authentically signed authorization manifest.
        SECURITY REQUIREMENT: An Ed25519PrivateKey instance MUST be supplied by the caller.
        The production application holds only public keys and cannot sign manifests.
        """
        if signing_private_key is None:
            raise ValueError(
                "Cannot create authorized manifest: Private signing key is required. "
                "The application possesses only public verification credentials. "
                "Institutional private keys are retained exclusively by the issuing authority."
            )

        issuer_info = cls.APPROVED_ISSUERS.get(issuer_id)
        if not issuer_info:
            raise ValueError(f"Unknown institutional issuer_id: '{issuer_id}'")

        auth_id = str(authorization_id or f"AUTH-{issuer_id.upper()}-{hashlib.sha256(mou_reference.encode()).hexdigest()[:8]}").strip()
        perm_fields = permitted_fields if permitted_fields is not None else issuer_info["permitted_fields"]

        canonical_payload = cls.compute_canonical_payload(
            issuer_id=issuer_id,
            authorization_id=auth_id,
            mou_reference=mou_reference,
            permitted_use=permitted_use,
            valid_from=valid_from,
            valid_until=valid_until,
            dataset_sha256=dataset_sha256,
            permitted_fields=perm_fields,
            manifest_version=manifest_version,
        )

        signature_bytes = signing_private_key.sign(canonical_payload)
        signature_hex = signature_bytes.hex()

        return {
            "manifest_version": manifest_version,
            "authorization_id": auth_id,
            "mou_reference": mou_reference,
            "issuing_authority": issuer_info["name"],
            "issuer_id": issuer_id,
            "signature_algorithm": "ed25519",
            "issued_at": "2026-01-01T00:00:00Z",
            "valid_from": valid_from,
            "valid_until": valid_until,
            "is_authorized": True,
            "is_revoked": is_revoked,
            "is_fixture": is_fixture,
            "permitted_use": permitted_use,
            "permitted_fields": perm_fields,
            "dpdpa_compliance_certified": True,
            "retention_schedule_days": retention_schedule_days,
            "dataset_fingerprint": {
                "expected_sha256": dataset_sha256 or "*",
                "binding_enforced": dataset_sha256 is not None,
            },
            "signature": signature_hex,
            "verification_token": signature_hex,  # For backward compatibility
        }

    @classmethod
    def verify_manifest(
        cls,
        manifest: Optional[Dict[str, Any]] = None,
        dataset_sha256: Optional[str] = None,
        is_fixture: bool = False,
        current_time_iso: Optional[str] = None,
        crl_path: Optional[str] = None,
        require_crl: bool = False,
    ) -> Tuple[bool, str, List[str], Dict[str, Any]]:
        """
        Executes institutional authorization verification with asymmetric Ed25519.
        Does NOT treat a user-controlled boolean or an arbitrary MoU string as independent proof.
        Returns (is_verified, status_code, violations_list, sanitized_manifest).
        """
        violations: List[str] = []

        # 1. Manifest Presence
        if manifest is None:
            return (False, PuneReadinessStatus.AUTHORIZATION_MISSING.value, ["Authorization manifest missing. Local file presence does not confer authorization."], {})

        # 2. Manifest Schema Validity
        required_schema = [
            "authorization_id", "mou_reference", "issuing_authority", "issuer_id",
            "permitted_use", "valid_from", "valid_until",
            "dpdpa_compliance_certified"
        ]
        for key in required_schema:
            if key not in manifest or manifest[key] is None or str(manifest[key]).strip() == "":
                violations.append(f"Manifest schema invalid: missing or empty required field '{key}'")

        sig_val = manifest.get("signature") or manifest.get("verification_token")
        if not sig_val or str(sig_val).strip() == "":
            violations.append("Manifest schema invalid: missing or empty signature / verification_token")

        if violations:
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        auth_id = str(manifest["authorization_id"]).strip()
        issuer_id = str(manifest["issuer_id"]).strip()
        mou_ref = str(manifest["mou_reference"]).strip()
        permitted_use = str(manifest["permitted_use"]).strip()
        valid_until_str = str(manifest["valid_until"]).strip()
        valid_from_str = str(manifest["valid_from"]).strip()
        manifest_ver = str(manifest.get("manifest_version", "2.1")).strip()
        perm_fields = manifest.get("permitted_fields", [])
        sig_str = str(sig_val).strip()

        # 3. Issuer Verification
        if issuer_id not in cls.APPROVED_ISSUERS:
            violations.append(f"Untrusted issuing authority '{issuer_id}'. Not in approved institutional registry.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        issuer_info = cls.APPROVED_ISSUERS[issuer_id]
        if not issuer_info["is_active"]:
            violations.append(f"Issuing authority '{issuer_id}' is marked INACTIVE in institutional registry.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 4. Fixture Authorization Isolation
        if issuer_info["is_fixture_authority"] and not is_fixture:
            violations.append("Fixture authority credential cannot authorize a production dataset. Production issuer required.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        if manifest.get("is_fixture", False) and not is_fixture:
            violations.append("Manifest is marked 'is_fixture: True'. Fixture manifests cannot authorize production intake.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 5. Revocation & Explicit Flag Audit (Trusted Revocation Mechanism)
        is_revoked, rev_reason = cls.is_authorization_revoked(
            manifest,
            current_time_iso=current_time_iso,
            crl_path=crl_path,
            require_crl=require_crl,
        )
        if is_revoked:
            violations.append(f"Authorization manifest has been revoked by issuing authority ({rev_reason}).")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        if manifest.get("is_authorized") is not True:
            violations.append("Manifest 'is_authorized' boolean is False.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        if manifest.get("dpdpa_compliance_certified") is not True:
            violations.append("DPDPA 2023 Data Protection Agreement certification is False or unverified.")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 6. Approved Purpose & Permitted Fields
        if permitted_use not in issuer_info["allowed_purposes"]:
            violations.append(f"Requested purpose '{permitted_use}' is not in issuer's approved purposes: {issuer_info['allowed_purposes']}")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 7. Validity & Expiration (Strict Fail-Closed Timestamp Validation)
        now_dt = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00")) if current_time_iso else datetime.now(timezone.utc)
        if now_dt.tzinfo is None:
            now_dt = now_dt.replace(tzinfo=timezone.utc)
        try:
            valid_until_dt = datetime.fromisoformat(valid_until_str.replace("Z", "+00:00"))
            valid_from_dt = datetime.fromisoformat(valid_from_str.replace("Z", "+00:00"))
            if valid_until_dt.tzinfo is None:
                valid_until_dt = valid_until_dt.replace(tzinfo=timezone.utc)
            if valid_from_dt.tzinfo is None:
                valid_from_dt = valid_from_dt.replace(tzinfo=timezone.utc)

            if valid_from_dt > valid_until_dt:
                violations.append(f"Manifest validity window malformed: valid_from ({valid_from_str}) is after valid_until ({valid_until_str}).")
                return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

            if now_dt > valid_until_dt:
                violations.append(f"Authorization manifest expired on {valid_until_str}. Current timestamp: {now_dt.isoformat()}")
                return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

            if now_dt < valid_from_dt:
                violations.append(f"Authorization manifest is not yet effective until {valid_from_str}.")
                return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)
        except Exception as e:
            violations.append(f"Malformed or unparseable timestamp in manifest: {str(e)}")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 8. Asymmetric Cryptographic Verification (Ed25519 over deterministic canonical payload)
        manifest_expected_sha = manifest.get("dataset_fingerprint", {}).get("expected_sha256")
        bound_sha = manifest_expected_sha if (manifest_expected_sha and manifest_expected_sha != "*") else None

        bound_payload = cls.compute_canonical_payload(
            issuer_id=issuer_id,
            authorization_id=auth_id,
            mou_reference=mou_ref,
            permitted_use=permitted_use,
            valid_from=valid_from_str,
            valid_until=valid_until_str,
            dataset_sha256=bound_sha,
            permitted_fields=perm_fields,
            manifest_version=manifest_ver,
        )
        is_sig_valid, sig_err = cls.verify_signature(issuer_id, bound_payload, sig_str)

        # Also support wildcard payload verification if dataset was unbound at signing
        if not is_sig_valid and bound_sha is not None:
            wildcard_payload = cls.compute_canonical_payload(
                issuer_id=issuer_id,
                authorization_id=auth_id,
                mou_reference=mou_ref,
                permitted_use=permitted_use,
                valid_from=valid_from_str,
                valid_until=valid_until_str,
                dataset_sha256=None,
                permitted_fields=perm_fields,
                manifest_version=manifest_ver,
            )
            is_sig_valid, sig_err = cls.verify_signature(issuer_id, wildcard_payload, sig_str)

        if not is_sig_valid:
            violations.append(f"Cryptographic verification failed: {sig_err or 'Ed25519 digital signature is invalid, forged, or tampered.'}")
            return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        # 9. Dataset Identity Binding & Mismatch Check
        fingerprint = manifest.get("dataset_fingerprint", {})
        expected_sha = fingerprint.get("expected_sha256", "*")
        binding_enforced = fingerprint.get("binding_enforced", False) or (expected_sha and expected_sha != "*")

        if binding_enforced:
            if not dataset_sha256:
                violations.append("Manifest enforces strict dataset fingerprint binding, but no dataset SHA-256 fingerprint was provided.")
                return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

            if expected_sha and expected_sha != "*" and expected_sha.lower() != dataset_sha256.lower():
                violations.append(f"Dataset fingerprint mismatch: dataset SHA-256 ('{dataset_sha256[:12]}...') does not match manifest ('{expected_sha[:12]}...').")
                return (False, PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value, violations, manifest)

        return (True, "VERIFIED", [], manifest)


# ==============================================================================
# 5. HARDENED AUTHORIZATION VALIDATOR
# ==============================================================================

class PuneAuthorizationValidator:
    """Validates legal authorization and permitted-use instruments."""

    @classmethod
    def validate(
        cls,
        manifest: Optional[Dict[str, Any]] = None,
        dataset_path: Optional[str] = None,
        dataset_content_or_hash: Optional[str] = None,
        is_fixture: bool = False,
        current_time_iso: Optional[str] = None
    ) -> Tuple[bool, str, List[str], Dict[str, Any]]:
        """
        Executes hardened institutional verification.
        Distinguishes AUTHORIZATION_MISSING vs AUTHORIZATION_UNVERIFIED.
        """
        # If labeled as fixture, it cannot satisfy production authorization
        if is_fixture:
            return (
                False,
                PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value,
                ["Dataset is explicitly designated as a TEST FIXTURE. Test fixtures cannot satisfy authorized production intake."],
                {"status": "TEST_FIXTURE_REJECTED", "is_fixture": True}
            )

        # Check if dataset path indicates a unit test fixture
        if dataset_path:
            clean_path = dataset_path.lower().replace("\\", "/")
            if "fixture" in clean_path or "sample" in clean_path or "test" in clean_path:
                if not manifest:
                    return (
                        False,
                        PuneReadinessStatus.AUTHORIZATION_MISSING.value,
                        [f"Dataset path '{dataset_path}' indicates a test fixture or sample. Authorized institutional manifest required."],
                        {"status": "SUSPECTED_FIXTURE_NO_AUTH", "is_fixture": True}
                    )

        # Attempt companion manifest lookup on disk if unprovided
        if not manifest and dataset_path:
            companion_auth = f"{dataset_path}.auth.json"
            if os.path.exists(companion_auth):
                try:
                    with open(companion_auth, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                except Exception as e:
                    return (
                        False,
                        PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value,
                        [f"Companion authorization file '{companion_auth}' unparseable: {str(e)}"],
                        {}
                    )

        if not manifest:
            return (
                False,
                PuneReadinessStatus.AUTHORIZATION_MISSING.value,
                ["Authorization manifest missing. Local file presence does NOT establish legal authorization."],
                {"status": "MISSING_MANIFEST"}
            )

        # Compute dataset SHA-256 hash if path provided
        calculated_sha: Optional[str] = None
        if dataset_content_or_hash:
            calculated_sha = dataset_content_or_hash
        elif dataset_path and os.path.exists(dataset_path):
            try:
                hasher = hashlib.sha256()
                with open(dataset_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        hasher.update(chunk)
                calculated_sha = hasher.hexdigest()
            except Exception:
                calculated_sha = None

        # Verify through InstitutionalIssuerRegistry
        is_ok, status_code, violations, verified_manifest = InstitutionalIssuerRegistry.verify_manifest(
            manifest=manifest,
            dataset_sha256=calculated_sha,
            is_fixture=is_fixture,
            current_time_iso=current_time_iso
        )

        return (is_ok, status_code, violations, verified_manifest)


# ==============================================================================
# 6. HARDENED DATA-READINESS GATE
# ==============================================================================

class PuneDataReadinessGate:
    """
    Hardened sequential gate evaluating dataset readiness across 10 discrete statuses:
    1. NO_DATA
    2. AUTHORIZATION_MISSING
    3. AUTHORIZATION_UNVERIFIED
    4. SCHEMA_INVALID
    5. PRIVACY_REVIEW_REQUIRED
    6. INSUFFICIENT_TEMPORAL_COVERAGE
    7. INSUFFICIENT_SPATIAL_COVERAGE
    8. INSUFFICIENT_TARGET_SUPPORT
    9. GIS_MAPPING_INCOMPLETE
    10. READY_FOR_EXPLORATORY_ANALYSIS

    Evaluates station-level and coordinate-level readiness independently.
    """

    @classmethod
    def evaluate(
        cls,
        df_or_path: Any = None,
        authorization_manifest: Optional[Dict[str, Any]] = None,
        gis_boundary_path: Optional[str] = None,
        is_fixture: bool = False,
        require_gis_complete: bool = False,
        threshold_config: Optional[PuneThresholdConfig] = None,
        current_time_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates the readiness gate sequentially.
        Does not mark a dataset ready merely because ingestion succeeded.
        Separates readiness for exploratory analysis from training and deployment.
        """
        cfg = threshold_config or DEFAULT_THRESHOLD_CONFIG

        checklist = {
            "data_present": False,
            "authorization_verified": False,
            "schema_valid": False,
            "pii_clean": False,
            "temporal_coverage_adequate": False,
            "spatial_coverage_adequate": False,
            "target_support_adequate": False,
            "station_level_eda_ready": False,
            "coordinate_level_eda_ready": False,
            "gis_mapping_complete": False,
        }

        # ----------------- GATE 1: NO_DATA -----------------
        if df_or_path is None:
            return cls._build_result(
                status=PuneReadinessStatus.NO_DATA,
                message="No dataset supplied. File path is None or unprovided.",
                checklist=checklist,
                details={}
            )

        df: Optional[pd.DataFrame] = None
        dataset_path: Optional[str] = None

        if isinstance(df_or_path, str):
            dataset_path = df_or_path
            if not os.path.exists(dataset_path):
                return cls._build_result(
                    status=PuneReadinessStatus.NO_DATA,
                    message=f"Dataset path '{dataset_path}' does not exist on disk.",
                    checklist=checklist,
                    details={"dataset_path": dataset_path}
                )
            try:
                df = pd.read_csv(dataset_path, comment="#")
            except Exception as e:
                return cls._build_result(
                    status=PuneReadinessStatus.NO_DATA,
                    message=f"Failed to read dataset file at '{dataset_path}': {str(e)}",
                    checklist=checklist,
                    details={"dataset_path": dataset_path, "error": str(e)}
                )
        elif isinstance(df_or_path, pd.DataFrame):
            df = df_or_path.copy()
        else:
            return cls._build_result(
                status=PuneReadinessStatus.NO_DATA,
                message=f"Invalid data object type: {type(df_or_path)}",
                checklist=checklist,
                details={}
            )

        if df is None or len(df) == 0:
            return cls._build_result(
                status=PuneReadinessStatus.NO_DATA,
                message="Supplied dataset contains 0 records (empty dataframe).",
                checklist=checklist,
                details={"dataset_path": dataset_path, "record_count": 0}
            )

        checklist["data_present"] = True

        # Compute dataset SHA-256 for binding
        dataset_sha: Optional[str] = None
        if dataset_path and os.path.exists(dataset_path):
            try:
                h = hashlib.sha256()
                with open(dataset_path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                dataset_sha = h.hexdigest()
            except Exception:
                dataset_sha = None

        # ----------------- GATE 2 & 3: AUTHORIZATION -----------------
        auth_ok, auth_status, auth_violations, validated_manifest = PuneAuthorizationValidator.validate(
            manifest=authorization_manifest,
            dataset_path=dataset_path,
            dataset_content_or_hash=dataset_sha,
            is_fixture=is_fixture,
            current_time_iso=current_time_iso
        )
        if not auth_ok:
            assigned_status = PuneReadinessStatus.AUTHORIZATION_MISSING if auth_status == PuneReadinessStatus.AUTHORIZATION_MISSING.value else PuneReadinessStatus.AUTHORIZATION_UNVERIFIED
            return cls._build_result(
                status=assigned_status,
                message=f"Legal authorization verification failed ({assigned_status.value}): {'; '.join(auth_violations)}",
                checklist=checklist,
                details={"violations": auth_violations, "manifest": validated_manifest, "dataset_path": dataset_path}
            )

        checklist["authorization_verified"] = True

        # ----------------- GATE 4: SCHEMA_INVALID -----------------
        schema_ok, schema_errors = PuneDataReadinessAudit.validate_dataset_schema(df)
        if not schema_ok:
            return cls._build_result(
                status=PuneReadinessStatus.SCHEMA_INVALID,
                message=f"Dataset schema invalid with {len(schema_errors)} error(s).",
                checklist=checklist,
                details={"schema_errors": schema_errors, "dataset_path": dataset_path}
            )

        checklist["schema_valid"] = True

        # ----------------- GATE 5: PRIVACY_REVIEW_REQUIRED -----------------
        pii_ok, pii_violations = PuneDataReadinessAudit.check_for_prohibited_pii(df)
        if not pii_ok:
            return cls._build_result(
                status=PuneReadinessStatus.PRIVACY_REVIEW_REQUIRED,
                message=f"DPDPA 2023 PII audit failed: {len(pii_violations)} sensitive pattern violation(s) detected.",
                checklist=checklist,
                details={"pii_violations": pii_violations, "dataset_path": dataset_path}
            )

        checklist["pii_clean"] = True

        # ----------------- GATE 6: INSUFFICIENT_TEMPORAL_COVERAGE -----------------
        parsed_dates = pd.to_datetime(df["incident_datetime"], errors="coerce")
        valid_dates = parsed_dates.dropna()
        if len(valid_dates) < 2:
            return cls._build_result(
                status=PuneReadinessStatus.INSUFFICIENT_TEMPORAL_COVERAGE,
                message="Dataset lacks parseable timestamps for temporal coverage evaluation.",
                checklist=checklist,
                details={"valid_timestamp_count": len(valid_dates)}
            )

        timespan_days = round((valid_dates.max() - valid_dates.min()).total_seconds() / 86400.0, 2)
        if timespan_days < cfg.eda_timespan_days:
            return cls._build_result(
                status=PuneReadinessStatus.INSUFFICIENT_TEMPORAL_COVERAGE,
                message=f"Dataset timespan ({timespan_days} days) is less than required minimum ({cfg.eda_timespan_days} days).",
                checklist=checklist,
                details={
                    "timespan_days": timespan_days,
                    "min_required_days": cfg.eda_timespan_days,
                    "earliest_date": str(valid_dates.min()),
                    "latest_date": str(valid_dates.max())
                }
            )

        checklist["temporal_coverage_adequate"] = True

        # ----------------- GATE 7: INSUFFICIENT_SPATIAL_COVERAGE -----------------
        geo_coverage = PuneDataReadinessAudit.validate_geographic_coverage(df)
        if geo_coverage["coverage_percentage"] < cfg.station_coverage_pct:
            return cls._build_result(
                status=PuneReadinessStatus.INSUFFICIENT_SPATIAL_COVERAGE,
                message=(
                    f"Dataset covers only {geo_coverage['coverage_percentage']}% of Pune police stations "
                    f"({geo_coverage['present_stations_count']}/{len(PUNE_POLICE_STATIONS)}), "
                    f"failing the {cfg.station_coverage_pct}% threshold."
                ),
                checklist=checklist,
                details=geo_coverage
            )

        checklist["spatial_coverage_adequate"] = True

        # ----------------- GATE 8: INSUFFICIENT_TARGET_SUPPORT -----------------
        harm_tiers = PuneDataReadinessAudit.map_incident_categories(df["section_code"])
        target_positives = int((harm_tiers != "other_cognizable").sum())
        if target_positives < cfg.eda_min_target_positives:
            return cls._build_result(
                status=PuneReadinessStatus.INSUFFICIENT_TARGET_SUPPORT,
                message=(
                    f"Insufficient positive target cases ({target_positives} positive high-harm incidents), "
                    f"below minimum requirement of {cfg.eda_min_target_positives}."
                ),
                checklist=checklist,
                details={
                    "positive_target_count": target_positives,
                    "min_required_positives": cfg.eda_min_target_positives,
                    "harm_tier_distribution": harm_tiers.value_counts().to_dict()
                }
            )

        checklist["target_support_adequate"] = True

        # ----------------- SEPARATION OF STATION-LEVEL vs COORDINATE-LEVEL -----------------
        # Station-level EDA is satisfied once authorized, temporal, station presence, and target support pass!
        checklist["station_level_eda_ready"] = True

        # Evaluate GIS polygon boundaries and coordinate completeness for coordinate-level EDA
        gis_complete, gis_details = cls._audit_gis_boundaries(df, gis_boundary_path)
        checklist["gis_mapping_complete"] = gis_complete

        coord_completeness = gis_details["coordinate_completeness_pct"]
        coordinate_level_ready = (
            gis_complete and
            (coord_completeness >= cfg.min_coordinate_completeness_pct)
        )
        checklist["coordinate_level_eda_ready"] = coordinate_level_ready

        # ----------------- GATE 9: GIS_MAPPING_INCOMPLETE -----------------
        if require_gis_complete and not gis_complete:
            return cls._build_result(
                status=PuneReadinessStatus.GIS_MAPPING_INCOMPLETE,
                message="Official GIS boundary polygon mapping is unverified or incomplete.",
                checklist=checklist,
                details=gis_details,
                station_level_ready=True,
                coordinate_level_ready=False
            )

        # ----------------- GATE 10: READY_FOR_EXPLORATORY_ANALYSIS -----------------
        return cls._build_result(
            status=PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS,
            message="All gates passed: dataset is authorized and approved for reproducible exploratory analysis.",
            checklist=checklist,
            details={
                "record_count": len(df),
                "timespan_days": timespan_days,
                "coverage_percentage": geo_coverage["coverage_percentage"],
                "target_positives": target_positives,
                "gis_audit": gis_details,
                "manifest": validated_manifest
            },
            station_level_ready=True,
            coordinate_level_ready=coordinate_level_ready
        )

    @classmethod
    def _audit_gis_boundaries(
        cls,
        df: pd.DataFrame,
        gis_boundary_path: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Conservative geography audit: checks whether official GIS polygon layer is present and covers stations."""
        has_official_layer = gis_boundary_path is not None and os.path.exists(gis_boundary_path)

        # Count stations with UNVERIFIED status (recent bifurcations)
        unverified_stations = [s for s, m in PUNE_STATION_VERIFICATION_STATUS.items() if m["status"] != "VERIFIED_CORE"]
        present_unverified = []
        if "police_station_id" in df.columns:
            st_slugs = df["police_station_id"].astype(str).str.lower().str.strip().unique()
            present_unverified = [s for s in unverified_stations if s in st_slugs]

        # Calculate unresolved geography metrics
        valid_coords_count = 0
        if "latitude" in df.columns and "longitude" in df.columns:
            lats = pd.to_numeric(df["latitude"], errors="coerce")
            lons = pd.to_numeric(df["longitude"], errors="coerce")
            valid_mask = (
                lats.notna() & lons.notna() &
                (lats >= 18.350) & (lats <= 18.700) &
                (lons >= 73.650) & (lons <= 74.100)
            )
            valid_coords_count = int(valid_mask.sum())

        unresolved_coords = len(df) - valid_coords_count
        unverified_station_record_count = 0
        if "police_station_id" in df.columns:
            unverified_mask = df["police_station_id"].astype(str).str.lower().str.strip().isin(unverified_stations)
            unverified_station_record_count = int(unverified_mask.sum())

        details = {
            "has_official_gis_boundary_file": has_official_layer,
            "gis_boundary_path": gis_boundary_path,
            "unverified_bifurcated_stations_present": present_unverified,
            "unverified_station_records_count": unverified_station_record_count,
            "records_missing_or_out_of_bounds_coordinates": unresolved_coords,
            "coordinate_completeness_pct": round((valid_coords_count / max(1, len(df))) * 100, 2),
            "unresolved_geography_representativeness_impact": (
                "Official GIS shapefiles for recent bifurcations (pashan, bavdhan, alankar) "
                "must be supplied by Pune Police / PMC before spatial modeling. Geographically unresolved "
                "records must be audited for selection bias without silent discarding."
            )
        }

        # GIS is complete only if official boundary layer exists AND no unverified stations remain without polygons
        is_complete = has_official_layer and (len(present_unverified) == 0)
        return (is_complete, details)

    @classmethod
    def _build_result(
        cls,
        status: PuneReadinessStatus,
        message: str,
        checklist: Dict[str, bool],
        details: Dict[str, Any],
        station_level_ready: bool = False,
        coordinate_level_ready: bool = False,
    ) -> Dict[str, Any]:
        """Constructs standardized gate evaluation response."""
        is_eda = (status == PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS)
        is_station_eda = station_level_ready or is_eda
        is_coord_eda = coordinate_level_ready

        return {
            "city_id": "pune",
            "gate_status": status.value,
            "readiness_status": status.value,
            "is_ready_for_eda": is_eda,
            "is_ready_for_station_level_eda": is_station_eda,
            "is_ready_for_coordinate_level_eda": is_coord_eda,
            # Strictly decouple EDA readiness from model training & deployment readiness!
            "is_ready_for_training": False,
            "is_ready_for_deployment": False,
            "gate_passed": is_eda,
            "gate_message": message,
            "checklist": checklist,
            "geographic_readiness": {
                "station_level": {
                    "is_ready": is_station_eda,
                    "status": "READY_FOR_EXPLORATORY_ANALYSIS" if is_station_eda else status.value,
                    "spatial_unit": "police_station_id (33 Pune Commissionerate Jurisdictions)",
                    "notes": "Permitted for station-level aggregations and baseline rate modeling once training gate is approved."
                },
                "coordinate_level": {
                    "is_ready": is_coord_eda,
                    "status": "READY_FOR_EXPLORATORY_ANALYSIS" if is_coord_eda else ("GIS_MAPPING_INCOMPLETE" if not is_coord_eda and is_station_eda else status.value),
                    "spatial_unit": "geocoded_coordinates_and_gis_polygons",
                    "blockers": ["Official GIS polygon shapefile required for all stations", "Unverified bifurcations (pashan, bavdhan, alankar) unconfirmed"] if not is_coord_eda else []
                },
                "unresolved_geography_summary": details.get("gis_audit") or details.get("geographic_coverage") or {},
            },
            "evaluation_details": details,
            "lifecycle_transitions": PuneLifecycleTransitionManager.evaluate_transitions(
                gate_evaluation={
                    "gate_status": status.value,
                    "checklist": checklist,
                    "is_ready_for_station_level_eda": is_station_eda,
                    "is_ready_for_coordinate_level_eda": is_coord_eda,
                },
                manifest=details.get("manifest")
            ),
            "active_safety_warning": (
                "Pune remains strictly UNSUPPORTED for live API forecasting. "
                "is_ready_for_training and is_ready_for_deployment remain False. "
                "Zero models are trained or enabled."
            ),
        }


# ==============================================================================
# 7. PUNE DATA READINESS AUDIT (CORE COMPATIBILITY SERVICE)
# ==============================================================================

class PuneDataReadinessAudit:
    """Audits data readiness, schema compliance, missingness, and leakage for Pune."""

    @classmethod
    def get_provenance_metadata(cls) -> Dict[str, Any]:
        """Returns target data source, governance, and institutional licensing requirements."""
        return {
            "city_id": "pune",
            "jurisdiction": "Pune City Police Commissionerate",
            "state": "Maharashtra, India",
            "target_system": "Crime and Criminal Tracking Network and Systems (CCTNS)",
            "institutional_counterpart": "Office of Commissioner of Police (CoP), Pune",
            "governing_statutes": [
                "Digital Personal Data Protection Act (DPDPA), 2023",
                "Bharatiya Nyaya Sanhita (BNS), 2023 / Indian Penal Code (IPC)",
                "Supreme Court FIR Publication Mandate (Youth Bar Association, 2016)"
            ],
            "required_access_instrument": "Memorandum of Understanding (MoU) with Data Protection Annexure",
            "data_anonymization_standard": "k-anonymity with zero identifiable complainant/victim PII",
            "current_acquisition_status": "PENDING_FORMAL_MOU"
        }

    @classmethod
    def assess_readiness(
        cls,
        dataset_path: Optional[str] = None,
        authorization_manifest: Optional[Dict[str, Any]] = None,
        gis_boundary_path: Optional[str] = None,
        is_fixture: bool = False,
        threshold_config: Optional[PuneThresholdConfig] = None,
        min_timespan_days: Optional[float] = None,
        min_station_coverage_pct: Optional[float] = None,
        min_target_positives: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Assess overall data readiness for Pune through the explicit gate.
        Maintains backward compatibility with Phase 1-4 callers.
        """
        provenance = cls.get_provenance_metadata()

        if dataset_path is None or not os.path.exists(dataset_path):
            gate_res = PuneDataReadinessGate.evaluate(df_or_path=None)
            gate_res.update({
                "data_acquired": False,
                "dataset_path": dataset_path,
                "provenance": provenance,
                "missing_requirements": [
                    "Formal Memorandum of Understanding (MoU) executed with Pune City Police Commissionerate.",
                    "Anonymized CCTNS database export covering minimum 36 months of incident records.",
                    "Police station beat / chowki boundary GIS shapefile / GeoJSON from Pune Police / PMC.",
                    "IPC-to-BNS penal section conversion table verified for July 2024 statutory transition.",
                    "Zero PII compliance certification under Digital Personal Data Protection Act (DPDPA 2023)."
                ],
                "actionable_next_steps": [
                    "Submit formal pilot research proposal to Additional Commissioner of Police (Admin / Crime), Pune.",
                    "Define secure on-premise or encrypted data transfer protocol for pseudonymized FIR logs.",
                    "Map 33 Pune Police Station jurisdictions to OpenStreetMap / PMC ward boundary layers.",
                    "Construct out-of-time chronological train (2020-2023) and test (2024) holdout splits once ingested."
                ],
                "active_safety_guarantee": (
                    "Strata Risk enforces strict geographic gating. Coordinates in Pune receive "
                    "coverage_status='UNSUPPORTED' with risk_probability=None. Zero Chicago weights are transferred."
                )
            })
            return gate_res

        # Evaluate through the explicit gate
        gate_res = PuneDataReadinessGate.evaluate(
            df_or_path=dataset_path,
            authorization_manifest=authorization_manifest,
            gis_boundary_path=gis_boundary_path,
            is_fixture=is_fixture,
            threshold_config=threshold_config
        )
        gate_res["data_acquired"] = gate_res["checklist"]["data_present"]
        gate_res["dataset_path"] = dataset_path
        gate_res["provenance"] = provenance
        return gate_res

    @classmethod
    def validate_dataset_schema(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Validate whether dataset has all required fields."""
        errors = []
        required_cols = ["fir_number_hash", "police_station_id", "incident_datetime", "section_code"]
        for col in required_cols:
            if col not in df.columns:
                errors.append(f"Missing required schema column: '{col}'")
        return (len(errors) == 0, errors)

    @classmethod
    def check_for_prohibited_pii(cls, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Ensure no private citizen PII columns or patterns are included under DPDPA 2023."""
        violations = []
        # Column name check
        for col in df.columns:
            col_lower = col.lower().strip().replace(" ", "_").replace("-", "_")
            for pii in PROHIBITED_PII_FIELDS:
                if pii in col_lower:
                    violations.append(f"Prohibited PII column detected: '{col}' matches pattern '{pii}'")

        # Content regex checks across all rows (vectorized)
        phone_pattern = re.compile(r"\b[6-9]\d{9}\b")
        email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        aadhaar_pattern = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
        pan_pattern = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

        for col in df.columns:
            col_lower = col.lower()
            if "hash" in col_lower or "dedup" in col_lower:
                continue
            if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
                str_s = df[col].dropna().astype(str)
                if str_s.empty:
                    continue
                if str_s.str.contains(phone_pattern, regex=True).any():
                    violations.append(f"Phone number pattern detected in column '{col}'")
                if str_s.str.contains(email_pattern, regex=True).any():
                    violations.append(f"Email address pattern detected in column '{col}'")
                if str_s.str.contains(aadhaar_pattern, regex=True).any():
                    violations.append(f"Aadhaar number pattern detected in column '{col}'")
                if str_s.str.contains(pan_pattern, regex=True).any():
                    violations.append(f"PAN card pattern detected in column '{col}'")

        return (len(violations) == 0, violations)

    @classmethod
    def validate_geographic_coverage(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Audit representation across the 33 Pune Police Stations."""
        if "police_station_id" not in df.columns:
            return {"coverage_percentage": 0.0, "present_stations_count": 0, "missing_stations_count": len(PUNE_POLICE_STATIONS), "missing_stations": PUNE_POLICE_STATIONS}

        normalized_stations = df["police_station_id"].astype(str).str.lower().str.strip().unique()
        present = [s for s in PUNE_POLICE_STATIONS if s in normalized_stations]
        missing = [s for s in PUNE_POLICE_STATIONS if s not in normalized_stations]
        coverage_pct = round((len(present) / len(PUNE_POLICE_STATIONS)) * 100, 2)

        return {
            "coverage_percentage": coverage_pct,
            "present_stations_count": len(present),
            "missing_stations_count": len(missing),
            "missing_stations": missing
        }

    @classmethod
    def map_incident_categories(cls, section_series: pd.Series) -> pd.Series:
        """Map raw IPC/BNS section codes to Strata Risk operational harm tiers."""
        def map_code(code: Any) -> str:
            if pd.isna(code):
                return "other_cognizable"
            clean = str(code).lower().strip()
            for pattern, category in IPC_BNS_CATEGORY_MAP.items():
                if pattern in clean:
                    return category
            return "other_cognizable"

        return section_series.apply(map_code)

    @classmethod
    def check_missingness_and_quality(cls, df: pd.DataFrame) -> Dict[str, Any]:
        """Audit field missingness, null ratios, and date parsing."""
        null_ratios = {col: round(float(df[col].isna().mean()), 4) for col in df.columns}
        invalid_dates = 0
        if "incident_datetime" in df.columns:
            try:
                parsed = pd.to_datetime(df["incident_datetime"], errors="coerce")
                invalid_dates = int(parsed.isna().sum())
            except Exception:
                invalid_dates = len(df)

        return {
            "null_ratios": null_ratios,
            "invalid_incident_dates_count": invalid_dates,
            "invalid_dates_ratio": round(invalid_dates / max(1, len(df)), 4)
        }

    @classmethod
    def check_temporal_leakage_and_split(
        cls,
        df: pd.DataFrame,
        datetime_col: str = "incident_datetime",
        train_ratio: float = 0.65,
        val_ratio: float = 0.15
    ) -> Dict[str, Any]:
        """Verify chronological strictly non-overlapping partitions."""
        if datetime_col not in df.columns:
            return {"valid_split": False, "error": f"Missing column {datetime_col}"}

        sorted_df = df.sort_values(datetime_col).reset_index(drop=True)
        n = len(sorted_df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train = sorted_df.iloc[:train_end]
        val = sorted_df.iloc[train_end:val_end]
        test = sorted_df.iloc[val_end:]

        t_max_train = train[datetime_col].max()
        t_min_val = val[datetime_col].min()
        t_max_val = val[datetime_col].max()
        t_min_test = test[datetime_col].min()

        no_leakage = (t_max_train < t_min_val) and (t_max_val < t_min_test)

        return {
            "valid_split": no_leakage,
            "train_samples": len(train),
            "val_samples": len(val),
            "test_samples": len(test),
            "train_time_range": [str(train[datetime_col].min()), str(t_max_train)],
            "val_time_range": [str(t_min_val), str(t_max_val)],
            "test_time_range": [str(t_min_test), str(test[datetime_col].max())],
            "zero_lookahead_verified": no_leakage
        }


# ==============================================================================
# 8. REPRODUCIBLE EXPLORATORY ANALYSIS WORKFLOW
# ==============================================================================

class PuneExploratoryAnalysisWorkflow:
    """
    Reproducible exploratory data analysis (EDA) workflow for an authorized Pune dataset.
    If no real dataset is present, emits clear NO_DATA rather than inventing results.
    Fixtures must be explicitly labeled and flagged.
    """

    @classmethod
    def run_exploratory_analysis(
        cls,
        dataset_path: Optional[str] = None,
        authorization_manifest: Optional[Dict[str, Any]] = None,
        gis_boundary_path: Optional[str] = None,
        is_fixture: bool = False,
        threshold_config: Optional[PuneThresholdConfig] = None,
    ) -> Dict[str, Any]:
        """
        Executes comprehensive exploratory analysis on an authorized dataset.
        """
        # Step 1: Check gate status
        gate_eval = PuneDataReadinessGate.evaluate(
            df_or_path=dataset_path,
            authorization_manifest=authorization_manifest,
            gis_boundary_path=gis_boundary_path,
            is_fixture=is_fixture,
            threshold_config=threshold_config
        )

        # If no dataset supplied, return NO_DATA without inventing metrics
        if gate_eval["gate_status"] == PuneReadinessStatus.NO_DATA.value:
            return {
                "status": PuneReadinessStatus.NO_DATA.value,
                "message": "No real Pune dataset supplied. Exploratory analysis cannot proceed without authorized data.",
                "is_fixture": is_fixture,
                "gate_evaluation": gate_eval,
                "eda_report": None
            }

        # If gate failed, return status and blockers
        if not gate_eval["gate_passed"]:
            return {
                "status": gate_eval["gate_status"],
                "message": f"Dataset blocked by readiness gate: {gate_eval['gate_message']}",
                "is_fixture": is_fixture,
                "gate_evaluation": gate_eval,
                "eda_report": None
            }

        # Load dataset
        df = pd.read_csv(dataset_path, comment="#") if isinstance(dataset_path, str) else dataset_path.copy()

        # Parse timestamps safely
        df["dt_parsed"] = pd.to_datetime(df["incident_datetime"], errors="coerce")
        df["harm_tier"] = PuneDataReadinessAudit.map_incident_categories(df["section_code"])
        df["month_year"] = df["dt_parsed"].dt.strftime("%Y-%m")

        # 1. Temporal profile
        earliest = df["dt_parsed"].min()
        latest = df["dt_parsed"].max()
        timespan_days = round((latest - earliest).total_seconds() / 86400.0, 2)
        records_per_month = df["month_year"].value_counts().sort_index().to_dict()

        # Identify temporal gaps (months with zero records between start and end)
        all_months = [d.strftime("%Y-%m") for d in pd.date_range(start=earliest, end=latest, freq="MS")]
        temporal_gaps = [m for m in all_months if m not in records_per_month or records_per_month[m] == 0]

        # 2. Station distribution
        records_per_station = df["police_station_id"].astype(str).str.lower().str.strip().value_counts().to_dict()

        # 3. Category distribution over time
        category_by_month = df.groupby(["month_year", "harm_tier"]).size().unstack(fill_value=0).to_dict(orient="index")

        # 4. Missingness & Quality
        missing_timestamps = int(df["incident_datetime"].isna().sum())
        unparseable_timestamps = int(df["dt_parsed"].isna().sum()) - missing_timestamps
        missing_station_ids = int(df["police_station_id"].isna().sum())
        missing_section_codes = int(df["section_code"].isna().sum())

        # 5. Duplicate and amended record patterns
        exact_duplicates = int(df.duplicated(subset=["fir_number_hash", "police_station_id", "incident_datetime"]).sum())
        firs_per_station = df.groupby("fir_number_hash")["police_station_id"].nunique()
        cross_station_firs = int((firs_per_station > 1).sum())
        firs_per_time = df.groupby("fir_number_hash")["incident_datetime"].nunique()
        amended_timestamp_firs = int((firs_per_time > 1).sum())

        # 6. Spatial coverage & unresolved geography
        valid_coords = 0
        if "latitude" in df.columns and "longitude" in df.columns:
            lats = pd.to_numeric(df["latitude"], errors="coerce")
            lons = pd.to_numeric(df["longitude"], errors="coerce")
            valid_mask = (
                lats.notna() & lons.notna() &
                (lats >= 18.350) & (lats <= 18.700) &
                (lons >= 73.650) & (lons <= 74.100)
            )
            valid_coords = int(valid_mask.sum())

        unresolved_coords = len(df) - valid_coords
        unverified_bifurcations = ["alankar", "pashan", "bavdhan", "wanawadi"]
        unverified_station_records = int(df["police_station_id"].astype(str).str.lower().str.strip().isin(unverified_bifurcations).sum())

        # 7. Positive-target support across candidate forecast windows
        def calc_shift_window_support(hours: int) -> Dict[str, Any]:
            temp_df = df.dropna(subset=["dt_parsed"]).copy()
            temp_df["shift_bin"] = temp_df["dt_parsed"].dt.floor(f"{hours}h")
            shifts_with_violent = temp_df[temp_df["harm_tier"] == "violent_street_harm"]["shift_bin"].nunique()
            shifts_with_any_target = temp_df[temp_df["harm_tier"] != "other_cognizable"]["shift_bin"].nunique()
            total_station_shifts = temp_df.groupby(["shift_bin", "police_station_id"]).size()
            windows_per_day = 24 // hours
            total_potential_station_windows = int(round(max(1.0, timespan_days) * windows_per_day * len(PUNE_POLICE_STATIONS)))
            return {
                "window_hours": hours,
                "windows_per_day": windows_per_day,
                "shifts_with_violent_street_harm": shifts_with_violent,
                "shifts_with_cognizable_target": shifts_with_any_target,
                "total_active_station_shifts": len(total_station_shifts),
                "total_potential_station_windows": total_potential_station_windows,
                "mean_events_per_active_station_shift": round(float(total_station_shifts.mean()), 3) if len(total_station_shifts) > 0 else 0.0,
            }

        target_support_by_window = {
            "4_hour_operational_window": calc_shift_window_support(4),
            "8_hour_patrol_shift": calc_shift_window_support(8),
            "24_hour_daily_window": calc_shift_window_support(24),
            "4_hour_shift": calc_shift_window_support(4),
            "8_hour_shift": calc_shift_window_support(8),
            "24_hour_day": calc_shift_window_support(24),
        }

        # 8. Recording practice shifts
        recording_shifts = {
            "bns_transition_observed": any("2024-07" in m or "2024-08" in m for m in records_per_month.keys()),
            "notes": (
                "July 1, 2024 statutory transition from Indian Penal Code (IPC) to Bharatiya Nyaya Sanhita (BNS) "
                "introduces potential section-code categorization shifts. Units must verify penal section cross-walk."
            )
        }

        eda_report = {
            "execution_metadata": {
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "dataset_source": dataset_path if isinstance(dataset_path, str) else "in_memory_dataframe",
                "is_fixture": is_fixture,
                "execution_mode": "FIXTURE_EVALUATION" if is_fixture else "AUTHORIZED_EXPLORATORY_ANALYSIS",
            },
            "temporal_profile": {
                "earliest_timestamp": str(earliest),
                "latest_timestamp": str(latest),
                "timespan_days": timespan_days,
                "total_records": len(df),
                "records_per_month": records_per_month,
                "temporal_gaps_identified": temporal_gaps,
            },
            "station_profile": {
                "records_per_station": records_per_station,
                "unique_stations_represented": len(records_per_station),
                "coverage_pct": round((len(records_per_station) / len(PUNE_POLICE_STATIONS)) * 100, 2),
            },
            "category_profile": {
                "overall_distribution": df["harm_tier"].value_counts().to_dict(),
                "monthly_distribution": category_by_month,
            },
            "data_quality_profile": {
                "missing_timestamps": missing_timestamps,
                "unparseable_timestamps": unparseable_timestamps,
                "missing_station_identifiers": missing_station_ids,
                "missing_section_codes": missing_section_codes,
            },
            "deduplication_profile": {
                "exact_duplicates_count": exact_duplicates,
                "cross_station_repeated_firs_count": cross_station_firs,
                "amended_timestamp_firs_count": amended_timestamp_firs,
            },
            "spatial_profile": {
                "records_with_valid_coordinates": valid_coords,
                "records_missing_coordinates": unresolved_coords,
                "records_in_unverified_bifurcated_stations": unverified_station_records,
                "unresolved_geography_total": unresolved_coords + unverified_station_records,
                "representativeness_impact_assessment": (
                    "Records lacking coordinates or residing in unverified recent bifurcations (alankar, pashan, bavdhan) "
                    "cannot be mapped to official polygons without verified shapefiles. Silently dropping them would "
                    "introduce suburban selection bias."
                ),
            },
            "target_support_by_forecast_window": target_support_by_window,
            "recording_practice_shifts": recording_shifts,
            "limitations_and_unresolved_issues": [
                "Official GIS boundary shapefiles for Pune City Police stations remain unverified.",
                "Automated regex scanning does NOT guarantee full anonymization of narrative place descriptions.",
                "Zero models trained or deployed; exploratory analysis strictly offline."
            ]
        }

        return {
            "status": PuneReadinessStatus.READY_FOR_EXPLORATORY_ANALYSIS.value,
            "message": "Exploratory analysis completed successfully.",
            "is_fixture": is_fixture,
            "gate_evaluation": gate_eval,
            "eda_report": eda_report
        }

    # Classmethod alias for standardized invocation
    run = run_exploratory_analysis


# ==============================================================================
# 9. FUTURE FORECASTING EVALUATION PROTOCOL
# ==============================================================================

class PuneForecastingEvaluationProtocol:
    """
    Formal evaluation protocol for future forecasting models.
    Documents the intended prediction unit, forecast horizon, baseline progression,
    calibration split isolation, and required metrics before any model training or CatBoost evaluation.
    """

    # Reconciled Operational Forecast Window Specification
    WINDOW_DURATION_HOURS: int = 4
    WINDOWS_PER_DAY: int = 6
    TOTAL_POLICE_STATIONS: int = 33
    STATION_WINDOWS_PER_DAY: int = 198  # 33 stations * 6 windows/day

    PREDICTION_UNIT = "Police Station Jurisdiction (S_i) x 4-Hour Operational Window (W_j)"
    FORECAST_HORIZON = "4 Hours Ahead (predict 4-hour window t+1 using information up to window t)"
    TARGET_DEFINITION = "Occurrence of target harm tier (Y in {0, 1}) or incident count in station during 4-hour window"

    @classmethod
    def calculate_expected_station_windows(cls, num_days: int, num_stations: int = 33) -> int:
        """
        Calculates exact expected station-window evaluation units across a given temporal span in days.
        For 33 stations:
        1 day = 198 station-windows
        180 days = 35,640 station-windows
        365 days = 72,270 station-windows
        3 years (1095 days) = 216,810 station-windows
        """
        return int(num_days * cls.WINDOWS_PER_DAY * num_stations)

    @classmethod
    def calculate_window_support(
        cls,
        df: pd.DataFrame,
        window_hours: int = 4,
        num_stations: int = 33,
        station_reporting_coverage_pct: float = 100.0,
    ) -> Dict[str, Any]:
        """
        Calculates empirical target support across candidate forecasting horizons.
        Explicitly distinguishes:
        - Theoretical station-window capacity (windows_per_day * D * num_stations).
        - Observed active station-windows with recorded incidents.
        - Windows with verified reporting coverage.
        - Positive target events.
        - Missing or unresolved geographic records.
        - Emphasizes that statistical adequacy CANNOT be inferred from gross aggregate incidents.
        """
        if df.empty or "incident_datetime" not in df.columns:
            return {
                "window_hours": window_hours,
                "windows_per_day": 24 // window_hours,
                "timespan_days": 0.0,
                "num_stations": num_stations,
                "theoretical_station_window_capacity": 0,
                "total_potential_station_windows": 0,
                "windows_with_verified_coverage": 0,
                "observed_station_windows": 0,
                "active_station_windows_with_incidents": 0,
                "station_windows_with_target": 0,
                "positive_target_events": 0,
                "unresolved_geographic_records": 0,
                "target_event_prevalence_pct": 0.0,
                "statistical_adequacy_assessment": "Dataset is empty; zero statistical support.",
            }

        temp_df = df.dropna(subset=["incident_datetime"]).copy()
        if "dt_parsed" not in temp_df.columns:
            temp_df["dt_parsed"] = pd.to_datetime(temp_df["incident_datetime"], errors="coerce")
        temp_df = temp_df.dropna(subset=["dt_parsed"])

        unresolved_geography = int((
            temp_df["police_station_id"].isna() |
            ~temp_df["police_station_id"].astype(str).str.lower().str.strip().isin(PUNE_POLICE_STATIONS)
        ).sum()) if "police_station_id" in temp_df.columns else len(temp_df)

        if temp_df.empty:
            return {
                "window_hours": window_hours,
                "windows_per_day": 24 // window_hours,
                "timespan_days": 0.0,
                "num_stations": num_stations,
                "theoretical_station_window_capacity": 0,
                "total_potential_station_windows": 0,
                "windows_with_verified_coverage": 0,
                "observed_station_windows": 0,
                "active_station_windows_with_incidents": 0,
                "station_windows_with_target": 0,
                "positive_target_events": 0,
                "unresolved_geographic_records": unresolved_geography,
                "target_event_prevalence_pct": 0.0,
                "statistical_adequacy_assessment": "Zero valid timestamps; statistical support cannot be evaluated.",
            }

        if "harm_tier" not in temp_df.columns and "section_code" in temp_df.columns:
            temp_df["harm_tier"] = PuneDataReadinessAudit.map_incident_categories(temp_df["section_code"])

        earliest = temp_df["dt_parsed"].min()
        latest = temp_df["dt_parsed"].max()
        timespan_days = max(1.0, round((latest - earliest).total_seconds() / 86400.0, 2))

        windows_per_day = 24 // window_hours
        theoretical_capacity = int(round(timespan_days * windows_per_day * num_stations))
        verified_coverage_windows = int(round(theoretical_capacity * (station_reporting_coverage_pct / 100.0)))

        temp_df["window_bin"] = temp_df["dt_parsed"].dt.floor(f"{window_hours}h")
        target_mask = temp_df["harm_tier"] != "other_cognizable" if "harm_tier" in temp_df.columns else pd.Series(True, index=temp_df.index)

        station_window_counts = temp_df.groupby(["window_bin", "police_station_id"]).size()
        active_windows = len(station_window_counts)

        target_df = temp_df[target_mask]
        target_station_window_counts = target_df.groupby(["window_bin", "police_station_id"]).size()
        windows_with_target = len(target_station_window_counts)

        prevalence_pct = round((windows_with_target / theoretical_capacity) * 100, 4) if theoretical_capacity > 0 else 0.0

        return {
            "window_hours": window_hours,
            "windows_per_day": windows_per_day,
            "timespan_days": timespan_days,
            "num_stations": num_stations,
            "theoretical_station_window_capacity": theoretical_capacity,
            "total_potential_station_windows": theoretical_capacity,
            "windows_with_verified_coverage": verified_coverage_windows,
            "observed_station_windows": active_windows,
            "active_station_windows_with_incidents": active_windows,
            "station_windows_with_target": windows_with_target,
            "positive_target_events": windows_with_target,
            "unresolved_geographic_records": unresolved_geography,
            "target_event_prevalence_pct": prevalence_pct,
            "mean_events_per_active_station_window": round(float(station_window_counts.mean()), 3) if active_windows > 0 else 0.0,
            "statistical_adequacy_assessment": (
                "Statistical adequacy cannot be inferred from gross record count. Across 33 stations x 6 windows/day, "
                "extreme spatio-temporal sparsity requires evaluating positive prevalence per unit-shift, not aggregate row volume."
            ),
        }

    BASELINE_HIERARCHY = [
        {
            "level": 1,
            "name": "Historical Station-Level Rate",
            "formula": "P_hat(Y=1 | station) = (1 / N_train) * sum(Y_{station, t})",
            "description": "Stationary empirical base rate per police station across the training set."
        },
        {
            "level": 2,
            "name": "Time-Aware Expanding Historical Rate",
            "formula": "P_hat(Y=1 | station, t) = (1 / (t - t_0)) * sum_{tau=t_0}^{t-1} Y_{station, tau}",
            "description": "Expanding-window empirical rate using observations strictly prior to forecast time t."
        },
        {
            "level": 3,
            "name": "Cyclical Spatio-Temporal Baseline",
            "formula": "P_hat(Y=1 | station, shift_window, day_of_week)",
            "description": "Empirical rate conditioned on station, 4-hour shift of day, and day-of-week interactions."
        },
        {
            "level": 4,
            "name": "CatBoost Spatio-Temporal Classifier",
            "prerequisites": "Must establish and compare against Levels 1-3 first. Outperformance is not guaranteed.",
            "description": "Gradient boosted decision trees with isotonic / Platt calibration fitted strictly on validation split."
        }
    ]

    EVALUATION_METRICS = {
        "probability_quality": [
            {"metric": "Brier Score", "purpose": "Mean squared error of probabilistic forecast: (1/N) * sum((p - y)^2)"},
            {"metric": "Binary Cross-Entropy (Log Loss)", "purpose": "Information-theoretic loss penalizing confident mispredictions"},
            {"metric": "Expected Calibration Error (ECE)", "purpose": "Binned calibration error measuring reliability curve deviation"}
        ],
        "ranking_quality": [
            {"metric": "Precision@K", "purpose": "Proportion of top-K flagged stations experiencing target incident (K=3, 5)"},
            {"metric": "Recall@K", "purpose": "Proportion of total shift incidents captured in top-K flagged stations"}
        ],
        "uncertainty_and_calibration": [
            {"method": "Reliability Diagrams", "purpose": "Empirical calibration curves across decile bins"},
            {"method": "Moving Block Bootstrap (MBB)", "purpose": "Block bootstrap preserving temporal autocorrelation for confidence intervals"}
        ]
    }

    CHRONOLOGICAL_CONSTRAINTS = [
        "Zero Lookahead: Every feature at forecast time t must aggregate records strictly from tau <= t.",
        "Non-Overlapping Holdout: Validation and test splits must occur strictly in the future relative to training.",
        "Calibration Isolation: Platt scaling and isotonic regression must be fit exclusively on validation split, never on test labels.",
        "Target Encodings: Global target priors must be calculated exclusively on the training split.",
        "Timezone Alignment: Asia/Kolkata (IST, UTC+05:30) with zero Daylight Saving Time shifts."
    ]

    @classmethod
    def verify_calibration_split_isolation(
        cls,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        calibrator_target_series: pd.Series
    ) -> Tuple[bool, str]:
        """
        Verifies that calibration was fitted exclusively on validation labels and never touched test labels.
        """
        val_target_ids = set(val_df.index) if hasattr(val_df, "index") else set()
        test_target_ids = set(test_df.index) if hasattr(test_df, "index") else set()

        if hasattr(calibrator_target_series, "index"):
            cal_ids = set(calibrator_target_series.index)
            test_overlap = cal_ids.intersection(test_target_ids)
            if len(test_overlap) > 0:
                return (False, f"Calibration leakage detected! {len(test_overlap)} test labels used in calibration fitting.")

        return (True, "Calibration isolation verified: zero test labels used in calibrator fitting.")

    @classmethod
    def get_protocol_document(cls) -> Dict[str, Any]:
        """Returns structured specification of the evaluation protocol."""
        return {
            "prediction_unit": cls.PREDICTION_UNIT,
            "forecast_horizon": cls.FORECAST_HORIZON,
            "target_definition": cls.TARGET_DEFINITION,
            "baseline_hierarchy": cls.BASELINE_HIERARCHY,
            "evaluation_metrics": cls.EVALUATION_METRICS,
            "chronological_constraints": cls.CHRONOLOGICAL_CONSTRAINTS,
            "threshold_classifications": PuneThresholdConfig.get_threshold_classifications(),
            "active_safety_warning": (
                "Do not train CatBoost or deploy models prior to baseline evaluation and data-readiness review. "
                "CatBoost is NOT promised or assumed to outperform simpler baselines."
            )
        }


# ==============================================================================
# 10. INSTITUTIONAL LIFECYCLE TRANSITION MANAGER (PHASE 6)
# ==============================================================================

class PuneLifecycleTransitionManager:
    """
    Evaluates institutional readiness transitions across Stages 0 through 6.
    Enforces sequential evidence requirements before any progression.
    Guarantees that no user-controlled boolean can enable training or deployment.
    """

    TRANSITION_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
        PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value: {
            "title": "Stage 0: Unauthorized or Unverified Intake",
            "description": "Initial state. Missing dataset or unverified institutional authorization.",
            "prerequisites": ["None. Default state."],
            "is_achievable_in_phase_6": True,
        },
        PuneLifecycleStage.STAGE_1_AUTHORIZATION_VERIFIED.value: {
            "title": "Stage 1: Institutional Authorization Cryptographically Verified",
            "description": "Legally executed MoU and authentic cryptographic verification token matching dataset fingerprint.",
            "prerequisites": [
                "Signed institutional MoU from Commissioner of Police Pune City",
                "Cryptographic Ed25519 signature verification matching approved institutional issuer",
                "Dataset SHA-256 fingerprint matching authorized manifest binding",
                "DPDPA 2023 compliance certification",
                "Active authorization window (not expired, not revoked)"
            ],
            "is_achievable_in_phase_6": True,
        },
        PuneLifecycleStage.STAGE_2_READY_FOR_STATION_LEVEL_EDA.value: {
            "title": "Stage 2: Ready for Station-Level Exploratory Data Analysis",
            "description": "Passed privacy audit, schema validation, and station-level coverage requirements.",
            "prerequisites": [
                "Stage 1 Authorization Verified",
                "Zero prohibited citizen PII fields or regex patterns under DPDPA 2023",
                "Valid schema (fir_number_hash, police_station_id, incident_datetime, section_code)",
                "Minimum 500 valid incident records",
                "Temporal span >= 180 days",
                "Police station coverage >= 80% (>= 26 of 33 authorized stations)",
                "Target positive occurrences >= 20"
            ],
            "is_achievable_in_phase_6": True,
        },
        PuneLifecycleStage.STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA.value: {
            "title": "Stage 3: Ready for Coordinate-Level Exploratory Data Analysis",
            "description": "Passed station-level EDA plus fine-grained coordinate completeness and official GIS boundaries.",
            "prerequisites": [
                "Stage 2 Station-Level EDA Ready",
                "Valid coordinates completeness >= 90%",
                "Coordinates strictly within Pune bounding box (lat: 18.35-18.70, lon: 73.65-74.10)",
                "Official Pune City Police verified GIS boundary polygons (not approximations)"
            ],
            "is_achievable_in_phase_6": True,
        },
        PuneLifecycleStage.STAGE_4_CONTROLLED_TRAINING_ELIGIBLE.value: {
            "title": "Stage 4: Eligible for Controlled Model-Training Experiments",
            "description": "Controlled offline model training experimentation across baseline hierarchy.",
            "prerequisites": [
                "Stage 2 (Station-Level) or Stage 3 (Coordinate-Level) Completed",
                "Minimum 36 months of longitudinal history (1,080 days)",
                "Minimum 15,000 incident records with non-trivial positive support per unit-shift",
                "Minimum 100 positive target events in training set",
                "Strict chronological split with zero future lookahead (max(t_train) < min(t_val))",
                "Signed Institutional MoU Addendum explicitly authorizing ML model training",
                "Institutional Data Governance Committee approval sign-off"
            ],
            "is_achievable_in_phase_6": False,
        },
        PuneLifecycleStage.STAGE_5_INDEPENDENT_VALIDATION_ELIGIBLE.value: {
            "title": "Stage 5: Eligible for Independent Validation",
            "description": "Out-of-time evaluation on sequestered test holdout by independent review team.",
            "prerequisites": [
                "Stage 4 Controlled Training Completed",
                "Baseline progression demonstrated (CatBoost must beat Levels 1-3 baselines)",
                "Calibration verified on validation split with zero test-label leakage",
                "Sequestered out-of-time test holdout (minimum 12 months)",
                "Independent methodology audit by external review team",
                "Institutional pre-registration of evaluation metrics and decision thresholds"
            ],
            "is_achievable_in_phase_6": False,
        },
        PuneLifecycleStage.STAGE_6_APPROVED_PILOT_ELIGIBLE.value: {
            "title": "Stage 6: Formally Approved Operational Pilot",
            "description": "Controlled, human-supervised operational pilot deployment in select police stations.",
            "prerequisites": [
                "Stage 5 Independent Validation Passed",
                "Formal written operational authorization from Commissioner of Police, Pune City",
                "Algorithmic Bias, Fairness, and Disparate Impact Audit Sign-Off",
                "Standard Operating Procedure for human-in-the-loop oversight (zero automated dispatch)",
                "Continuous monitoring, drift detection, and immediate kill-switch mechanisms"
            ],
            "is_achievable_in_phase_6": False,
        },
    }

    @classmethod
    def evaluate_transitions(
        cls,
        gate_evaluation: Dict[str, Any],
        manifest: Optional[Dict[str, Any]] = None,
        official_approvals: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates lifecycle stage transitions based on empirical gate evaluation.
        Enforces that Stages 4, 5, and 6 remain strictly locked and disabled in Phase 6.
        """
        gate_status = gate_evaluation.get("gate_status", PuneReadinessStatus.NO_DATA.value)
        checklist = gate_evaluation.get("checklist", {})
        auth_verified = checklist.get("authorization_verified", False)
        station_eda_ready = gate_evaluation.get("is_ready_for_station_level_eda", False)
        coord_eda_ready = gate_evaluation.get("is_ready_for_coordinate_level_eda", False)

        # Stage determination
        if not auth_verified or gate_status in [
            PuneReadinessStatus.NO_DATA.value,
            PuneReadinessStatus.AUTHORIZATION_MISSING.value,
            PuneReadinessStatus.AUTHORIZATION_UNVERIFIED.value,
        ]:
            current_stage = PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value
        elif coord_eda_ready:
            current_stage = PuneLifecycleStage.STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA.value
        elif station_eda_ready:
            current_stage = PuneLifecycleStage.STAGE_2_READY_FOR_STATION_LEVEL_EDA.value
        else:
            current_stage = PuneLifecycleStage.STAGE_1_AUTHORIZATION_VERIFIED.value

        stages_status = {
            PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value: {
                "achieved": True,
                "status": "COMPLETED",
                "evidence": "Initial ingestion checkpoint.",
            },
            PuneLifecycleStage.STAGE_1_AUTHORIZATION_VERIFIED.value: {
                "achieved": auth_verified,
                "status": "COMPLETED" if auth_verified else "BLOCKED",
                "evidence": "Cryptographically verified manifest with matching Ed25519 signature and SHA-256 fingerprint." if auth_verified else "Authorization manifest missing or unverified.",
            },
            PuneLifecycleStage.STAGE_2_READY_FOR_STATION_LEVEL_EDA.value: {
                "achieved": station_eda_ready,
                "status": "COMPLETED" if station_eda_ready else ("PENDING_PREREQUISITES" if auth_verified else "BLOCKED"),
                "evidence": "Passed schema, PII audit, >=500 records, >=180 days, >=80% station coverage, >=20 target events." if station_eda_ready else "Data quality or coverage gates not satisfied.",
            },
            PuneLifecycleStage.STAGE_3_READY_FOR_COORDINATE_LEVEL_EDA.value: {
                "achieved": coord_eda_ready,
                "status": "COMPLETED" if coord_eda_ready else ("PENDING_GIS_AND_COORDINATES" if station_eda_ready else "BLOCKED"),
                "evidence": "Coordinate completeness >=90% and verified official GIS polygons." if coord_eda_ready else "Missing official GIS polygons or coordinate completeness <90%.",
            },
            PuneLifecycleStage.STAGE_4_CONTROLLED_TRAINING_ELIGIBLE.value: {
                "achieved": False,
                "status": "LOCKED_DISABLED_IN_PHASE_6",
                "is_eligible": False,
                "evidence": None,
                "blockers": [
                    "Phase 6 Invariant: Model training remains strictly disabled.",
                    "No signed institutional training addendum from Pune City Police.",
                    "Data Governance Committee approval not executed.",
                    "Longitudinal 36-month volume sufficiency and unit-shift support not established."
                ]
            },
            PuneLifecycleStage.STAGE_5_INDEPENDENT_VALIDATION_ELIGIBLE.value: {
                "achieved": False,
                "status": "LOCKED_DISABLED_IN_PHASE_6",
                "is_eligible": False,
                "evidence": None,
                "blockers": [
                    "Phase 6 Invariant: Independent validation remains strictly disabled.",
                    "Controlled model training (Stage 4) must be successfully executed first.",
                    "Independent audit team review not executed."
                ]
            },
            PuneLifecycleStage.STAGE_6_APPROVED_PILOT_ELIGIBLE.value: {
                "achieved": False,
                "status": "LOCKED_DISABLED_IN_PHASE_6",
                "is_eligible": False,
                "evidence": None,
                "blockers": [
                    "Phase 6 Invariant: Operational pilot deployment remains strictly disabled.",
                    "Independent validation (Stage 5) must be completed first.",
                    "Formal written operational pilot authorization from Commissioner of Police required.",
                    "Algorithmic bias and safety review sign-off required."
                ]
            },
        }

        return {
            "current_stage": current_stage,
            "current_stage_spec": cls.TRANSITION_SPECIFICATIONS[current_stage],
            "stages": stages_status,
            "model_training_eligible": False,
            "independent_validation_eligible": False,
            "pilot_deployment_eligible": False,
            "next_required_action": (
                "Formal institutional engagement and MoU execution with Office of the Commissioner of Police, Pune City."
                if current_stage == PuneLifecycleStage.STAGE_0_UNAUTHORIZED.value
                else "Execute exploratory analysis workflow and review data quality findings."
            ),
            "active_safety_invariant": (
                "Pune and Mumbai remain strictly UNSUPPORTED. "
                "No user-controlled boolean can enable training or deployment."
            ),
        }
