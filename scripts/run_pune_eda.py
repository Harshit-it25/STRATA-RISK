#!/usr/bin/env python3
"""
Strata Risk — Pune Police Incident Data Readiness & Exploratory Analysis CLI (Phase 6).

Reproducible entrypoint for evaluating data readiness and generating aggregated
exploratory data analysis (EDA) on an authorized Pune incident dataset.

Strict Invariants:
1. Defaults to NO_DATA when no dataset is supplied.
2. Requires institutional authorization verification for production inputs.
3. Explicitly labels fixture runs and never reports fixture metrics as real findings.
4. Produces ONLY aggregated metrics; never exports citizen-level records.
5. Model training and deployment remain strictly disabled (Pune remains UNSUPPORTED).
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Ensure repository root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
from backend.services.pune_data_readiness import (
    PuneReadinessStatus,
    PuneLifecycleStage,
    PuneAuthorizationValidator,
    PuneDataReadinessGate,
    PuneExploratoryAnalysisWorkflow,
    PuneLifecycleTransitionManager,
    InstitutionalIssuerRegistry,
)


def run_eda_pipeline(
    dataset_path: Optional[str] = None,
    manifest_path: Optional[str] = None,
    is_fixture: bool = False,
    output_dir: Optional[str] = None,
    gis_boundary_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the readiness gate and exploratory analysis workflow.
    Returns structured audit result dictionary.
    """
    # 1. Default to NO_DATA when no dataset supplied
    if not dataset_path:
        print("\n" + "=" * 80)
        print("STRATA RISK — PUNE DATA READINESS & EXPLORATORY ANALYSIS")
        print("=" * 80)
        print("STATUS: NO_DATA")
        print("Notice: No dataset path supplied.")
        print("Default behavior: Emitting NO_DATA evaluation.")
        print("Active Safety: Pune remains strictly UNSUPPORTED for forecasting.")
        print("=" * 80 + "\n")

        gate_res = PuneDataReadinessGate.evaluate(df_or_path=None)
        eda_res = PuneExploratoryAnalysisWorkflow.run(None)
        transitions = PuneLifecycleTransitionManager.evaluate_transitions(gate_res)

        return {
            "execution_status": "NO_DATA",
            "is_fixture": False,
            "gate_evaluation": gate_res,
            "eda_evaluation": eda_res,
            "lifecycle_transitions": transitions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Verify dataset existence
    if not os.path.exists(dataset_path):
        raise FileNotFoundError(f"Dataset file not found: '{dataset_path}'")

    # 2. Resolve Authorization Manifest
    manifest_data: Optional[Dict[str, Any]] = None
    if manifest_path and os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    else:
        companion_path = f"{dataset_path}.auth.json"
        if os.path.exists(companion_path):
            with open(companion_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)

    # 3. Authorization Verification
    print("\n" + "=" * 80)
    print("STRATA RISK — PUNE DATA READINESS & EXPLORATORY ANALYSIS")
    print(f"Mode: {'TEST FIXTURE EVALUATION' if is_fixture else 'AUTHORIZED PRODUCTION INTAKE'}")
    print(f"Dataset Path: {dataset_path}")
    print("=" * 80)

    auth_ok, auth_status, violations, verified_manifest = PuneAuthorizationValidator.validate(
        manifest=manifest_data,
        dataset_path=dataset_path,
        is_fixture=is_fixture
    )

    if not auth_ok:
        print(f"\n[AUTHORIZATION BLOCKED: {auth_status}]")
        for v in violations:
            print(f"  - Violation: {v}")
        print("\nActive Safety: Dataset cannot be analyzed without valid institutional authorization.")
        print("Pune remains strictly UNSUPPORTED.\n" + "=" * 80)

        gate_res = PuneDataReadinessGate.evaluate(
            df_or_path=dataset_path,
            authorization_manifest=manifest_data,
            is_fixture=is_fixture
        )
        transitions = PuneLifecycleTransitionManager.evaluate_transitions(gate_res, manifest=manifest_data)

        return {
            "execution_status": "AUTHORIZATION_BLOCKED",
            "auth_status": auth_status,
            "violations": violations,
            "gate_evaluation": gate_res,
            "lifecycle_transitions": transitions,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    print("\n[AUTHORIZATION VERIFIED]")
    print(f"  Authority: {verified_manifest.get('issuing_authority')}")
    print(f"  MoU Reference: {verified_manifest.get('mou_reference')}")
    print(f"  Permitted Use: {verified_manifest.get('permitted_use')}")
    print(f"  DPDPA Certified: {verified_manifest.get('dpdpa_compliance_certified')}")

    # 4. Execute Readiness Gate Evaluation
    gate_eval = PuneDataReadinessGate.evaluate(
        df_or_path=dataset_path,
        authorization_manifest=verified_manifest,
        gis_boundary_path=gis_boundary_path,
        is_fixture=is_fixture
    )

    # 5. Execute Exploratory Analysis Workflow
    eda_eval = PuneExploratoryAnalysisWorkflow.run(
        df_or_path=dataset_path,
        authorization_manifest=verified_manifest,
        gis_boundary_path=gis_boundary_path,
        is_fixture=is_fixture
    )

    # 6. Evaluate Lifecycle Transitions
    transitions = PuneLifecycleTransitionManager.evaluate_transitions(
        gate_evaluation=gate_eval,
        manifest=verified_manifest
    )

    # Prominently warn if fixture
    if is_fixture:
        print("\n" + "!" * 80)
        print("CRITICAL WARNING: TEST FIXTURE EXECUTION")
        print("This run used a test fixture authority and/or fixture data.")
        print("These measurements MUST NOT be reported or represented as real Pune findings!")
        print("!" * 80)

    # Print summary metrics (strictly aggregated, zero PII)
    eda_report = eda_eval.get("eda_report", {})
    records_total = eda_report.get("temporal_profile", {}).get("total_records", 0)
    timespan_days = eda_report.get("temporal_profile", {}).get("timespan_days", 0)
    stations_covered = eda_report.get("station_profile", {}).get("unique_stations_represented", 0)
    coverage_pct = eda_report.get("station_profile", {}).get("coverage_pct", 0)

    print("\n--- AGGREGATED READINESS & EDA FINDINGS ---")
    print(f"Gate Status: {gate_eval.get('gate_status')}")
    print(f"Station-Level EDA Ready: {gate_eval.get('is_ready_for_station_level_eda')}")
    print(f"Coordinate-Level EDA Ready: {gate_eval.get('is_ready_for_coordinate_level_eda')}")
    print(f"Model Training Eligible: {transitions.get('model_training_eligible')} (LOCKED FALSE in Phase 6)")
    print(f"Pilot Deployment Eligible: {transitions.get('pilot_deployment_eligible')} (LOCKED FALSE in Phase 6)")
    print(f"Total Valid Records: {records_total}")
    print(f"Temporal Span: {timespan_days} days")
    print(f"Station Coverage: {stations_covered}/33 ({coverage_pct}%)")

    # Write aggregated output if requested
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        ts_slug = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_file = os.path.join(output_dir, f"eda_summary_{ts_slug}.json")

        summary_payload = {
            "execution_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "dataset_source": os.path.basename(dataset_path),
                "is_fixture": is_fixture,
                "execution_mode": "FIXTURE_EVALUATION" if is_fixture else "AUTHORIZED_EXPLORATORY_ANALYSIS",
            },
            "gate_evaluation": gate_eval,
            "lifecycle_transitions": transitions,
            "eda_report": eda_report,
            "active_safety_invariant": {
                "city_status": "UNSUPPORTED",
                "is_model_ready": False,
                "zero_citizen_records_exported": True,
            }
        }

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)
        print(f"\nAggregated summary report saved to: {out_file}")

    print("\n" + "=" * 80)
    print("COMPLETION: EDA run complete.")
    print("Pune and Mumbai remain strictly UNSUPPORTED.")
    print("=" * 80 + "\n")

    return {
        "execution_status": "SUCCESS",
        "is_fixture": is_fixture,
        "gate_evaluation": gate_eval,
        "eda_evaluation": eda_eval,
        "lifecycle_transitions": transitions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Strata Risk: Pune Police Incident Data Readiness & Exploratory Analysis CLI."
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Path to the Pune incident dataset CSV or Parquet file. Defaults to NO_DATA if omitted."
    )
    parser.add_argument(
        "--manifest-path",
        type=str,
        default=None,
        help="Path to institutional authorization manifest JSON file (optional if companion file exists)."
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Explicitly mark run as a sandboxed test fixture. Never represents results as real Pune data."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Optional directory to write aggregated EDA JSON summary report."
    )
    parser.add_argument(
        "--gis-boundary-path",
        type=str,
        default=None,
        help="Optional path to official Pune City Police GIS boundary GeoJSON/Shapefile."
    )

    args = parser.parse_args()

    try:
        run_eda_pipeline(
            dataset_path=args.dataset_path,
            manifest_path=args.manifest_path,
            is_fixture=args.fixture,
            output_dir=args.output_dir,
            gis_boundary_path=args.gis_boundary_path,
        )
    except Exception as e:
        print(f"\n[FATAL ERROR IN EDA PIPELINE]: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
