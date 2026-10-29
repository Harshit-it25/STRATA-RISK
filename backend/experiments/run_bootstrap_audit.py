import json
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.linear_model import LogisticRegression
from catboost import CatBoostClassifier
import joblib

from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline
from backend.models.baselines import HistoricalSpatialBaseline

def run_bootstrap_audit(n_replicates: int = 5000, seed: int = 42):
    print("=" * 80)
    print("STRATA RISK — SHIFT-LEVEL PAIRED BOOTSTRAP ROBUSTNESS AUDIT")
    print(f"Replicates: {n_replicates} | Random Seed: {seed}")
    print("=" * 80)

    # 1. Pipeline and data loading
    pipeline = SpatioTemporalDataPipeline()
    raw_df = pd.read_csv("data/processed_chicago_crimes.csv")
    clean_df = pipeline.validate_raw_data(raw_df)
    grid_df = pipeline.build_spatio_temporal_grid(clean_df)
    feature_df = pipeline.generate_features_and_targets(grid_df)

    train_df, val_df, test_df = pipeline.split_chronological(feature_df, train_frac=0.65, val_frac=0.15)
    
    unique_shifts = sorted(test_df["window_time"].unique())
    n_shifts = len(unique_shifts)
    print(f"Holdout Test Shifts: {n_shifts} ({test_df['window_time'].min()} to {test_df['window_time'].max()})")
    print(f"Total Test Observations: {len(test_df)} (Cells per shift: {len(test_df) // n_shifts})")

    y_train = train_df["target_event"].values.astype(int)
    y_val = val_df["target_event"].values.astype(int)
    y_test = test_df["target_event"].values.astype(int)

    # 2. Models
    # A) Historical Spatial Baseline (fitted strictly on train_df)
    spatial_baseline = HistoricalSpatialBaseline(prior_weight=5.0).fit(train_df)
    p_test_spatial = spatial_baseline.predict_proba(test_df)

    # B) CatBoost Model
    model = CatBoostClassifier()
    model.load_model("backend/artifacts/forecaster_catboost.cbm")
    with open("backend/artifacts/model_metadata.json", "r") as f:
        meta = json.load(f)
    feature_cols = meta["feature_columns"]

    p_val_raw = model.predict_proba(val_df[feature_cols])[:, 1]
    p_test_raw = model.predict_proba(test_df[feature_cols])[:, 1]

    # C) Isotonic Calibrator (deployed artifact)
    iso_cal = joblib.load("backend/artifacts/calibrator.joblib")
    p_test_iso = np.clip(iso_cal.predict(p_test_raw), 0.0, 1.0)

    # D) Platt Calibrator (Logit, C=1.0 fitted strictly on validation)
    eps = 1e-12
    p_val_raw_clipped = np.clip(p_val_raw, eps, 1 - eps)
    p_test_raw_clipped = np.clip(p_test_raw, eps, 1 - eps)
    logits_val = np.log(p_val_raw_clipped / (1 - p_val_raw_clipped)).reshape(-1, 1)
    logits_test = np.log(p_test_raw_clipped / (1 - p_test_raw_clipped)).reshape(-1, 1)

    lr_logit = LogisticRegression(solver="lbfgs", C=1.0, random_state=42)
    lr_logit.fit(logits_val, y_val)
    p_test_platt = lr_logit.predict_proba(logits_test)[:, 1]

    models = {
        "spatial": p_test_spatial,
        "raw": p_test_raw,
        "iso": p_test_iso,
        "platt": p_test_platt,
    }

    # Verify predictions are finite and in [0, 1]
    for m_name, probs in models.items():
        assert np.all(np.isfinite(probs)), f"{m_name} contains non-finite probabilities"
        assert np.all((probs >= 0.0) & (probs <= 1.0)), f"{m_name} contains out-of-bound probabilities"

    # 3. Compute per-shift metrics matrix
    # Map shift string/timestamp to shift index 0..171
    shift_to_idx = {s: i for i, s in enumerate(unique_shifts)}
    test_shift_indices = test_df["window_time"].map(shift_to_idx).values

    # Pre-aggregate shift-level metrics for fast vectorized bootstrap
    # For each shift i in 0..171:
    #   - brier: mean (p - y)^2 in that shift
    #   - logloss: mean -[y log p + (1-y) log(1-p)] in that shift
    #   - prec@4: sum(y in top 4) / 4
    #   - recall@4: sum(y in top 4) / sum(y in shift) if sum(y) > 0 else NaN
    shift_metrics = {m: {
        "brier": np.zeros(n_shifts),
        "logloss": np.zeros(n_shifts),
        "prec4": np.zeros(n_shifts),
        "rec4": np.zeros(n_shifts),
        "positives": np.zeros(n_shifts),
        "count": np.zeros(n_shifts),
    } for m in models}

    eps_ll = 1e-15
    for s_idx, s_val in enumerate(unique_shifts):
        mask = (test_shift_indices == s_idx)
        y_shift = y_test[mask]
        n_pos = np.sum(y_shift)
        n_cells = len(y_shift)
        k = min(4, n_cells)

        for m_name, probs in models.items():
            p_shift = probs[mask]
            
            # Brier
            shift_metrics[m_name]["brier"][s_idx] = np.mean((p_shift - y_shift) ** 2)
            
            # Log loss
            p_clipped = np.clip(p_shift, eps_ll, 1 - eps_ll)
            ll = -np.mean(y_shift * np.log(p_clipped) + (1 - y_shift) * np.log(1 - p_clipped))
            shift_metrics[m_name]["logloss"][s_idx] = ll
            
            # Precision@4 and Recall@4
            # Stable tie handling using stable sort (order preserved)
            top_k_indices = np.argsort(-p_shift, kind="stable")[:k]
            pos_in_top = np.sum(y_shift[top_k_indices])
            shift_metrics[m_name]["prec4"][s_idx] = pos_in_top / k
            shift_metrics[m_name]["rec4"][s_idx] = (pos_in_top / n_pos) if n_pos > 0 else np.nan
            shift_metrics[m_name]["positives"][s_idx] = n_pos
            shift_metrics[m_name]["count"][s_idx] = n_cells

    # Print Point Estimates (Observed on Holdout)
    print("\nOBSERVED POINT ESTIMATES (All 172 shifts):")
    print(f"{'Model':<28} | {'Brier':<7} | {'LogLoss':<7} | {'Prec@4':<8} | {'Recall@4':<8}")
    print("-" * 65)
    for m_name in models:
        br = np.mean(shift_metrics[m_name]["brier"])
        ll = np.mean(shift_metrics[m_name]["logloss"])
        p4 = np.mean(shift_metrics[m_name]["prec4"])
        r4 = np.nanmean(shift_metrics[m_name]["rec4"])
        print(f"{m_name:<28} | {br:<7.4f} | {ll:<7.4f} | {p4:<8.2%} | {r4:<8.2%}")

    # 4. Bootstrap Resampling of Shifts (B = 5,000)
    rng = np.random.default_rng(seed)
    # Generate B sample indices with replacement: shape (n_replicates, n_shifts)
    bootstrap_shift_indices = rng.choice(n_shifts, size=(n_replicates, n_shifts), replace=True)

    boot_results = {m: {
        "brier": np.zeros(n_replicates),
        "logloss": np.zeros(n_replicates),
        "prec4": np.zeros(n_replicates),
        "rec4": np.zeros(n_replicates)
    } for m in models}

    for b in range(n_replicates):
        b_idx = bootstrap_shift_indices[b]
        for m_name in models:
            boot_results[m_name]["brier"][b] = np.mean(shift_metrics[m_name]["brier"][b_idx])
            boot_results[m_name]["logloss"][b] = np.mean(shift_metrics[m_name]["logloss"][b_idx])
            boot_results[m_name]["prec4"][b] = np.mean(shift_metrics[m_name]["prec4"][b_idx])
            boot_results[m_name]["rec4"][b] = np.nanmean(shift_metrics[m_name]["rec4"][b_idx])

    # 5. Paired Differences for each replicate
    diff_brier_iso_platt = boot_results["iso"]["brier"] - boot_results["platt"]["brier"]
    diff_logloss_iso_platt = boot_results["iso"]["logloss"] - boot_results["platt"]["logloss"]

    diff_prec4_iso_spatial = boot_results["iso"]["prec4"] - boot_results["spatial"]["prec4"]
    diff_prec4_platt_spatial = boot_results["platt"]["prec4"] - boot_results["spatial"]["prec4"]
    diff_prec4_raw_spatial = boot_results["raw"]["prec4"] - boot_results["spatial"]["prec4"]

    diff_rec4_iso_spatial = boot_results["iso"]["rec4"] - boot_results["spatial"]["rec4"]
    diff_rec4_platt_spatial = boot_results["platt"]["rec4"] - boot_results["spatial"]["rec4"]

    # Differences between CatBoost and Spatial Baseline on Brier / LogLoss
    diff_brier_iso_spatial = boot_results["iso"]["brier"] - boot_results["spatial"]["brier"]
    diff_brier_platt_spatial = boot_results["platt"]["brier"] - boot_results["spatial"]["brier"]
    diff_logloss_iso_spatial = boot_results["iso"]["logloss"] - boot_results["spatial"]["logloss"]

    # 6. Compute 95% Percentile Confidence Intervals
    def get_ci(arr):
        return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))

    print("\n" + "=" * 95)
    print("BOOTSTRAP 95% PERCENTILE CONFIDENCE INTERVALS (5,000 Shift Replicates)")
    print("=" * 95)
    print(f"{'Model':<25} | {'Metric':<10} | {'Point Est':<10} | {'95% CI Lower':<12} | {'95% CI Upper':<12}")
    print("-" * 95)

    summary_stats = {}
    for m_name in models:
        summary_stats[m_name] = {}
        for metric in ["brier", "logloss", "prec4", "rec4"]:
            point = float(np.mean(shift_metrics[m_name][metric]) if metric != "rec4" else np.nanmean(shift_metrics[m_name][metric]))
            lo, hi = get_ci(boot_results[m_name][metric])
            summary_stats[m_name][metric] = {"point": point, "ci_lower": lo, "ci_upper": hi}
            fmt_pt = f"{point:.4f}" if "prec" not in metric and "rec" not in metric else f"{point:.2%}"
            fmt_lo = f"{lo:.4f}" if "prec" not in metric and "rec" not in metric else f"{lo:.2%}"
            fmt_hi = f"{hi:.4f}" if "prec" not in metric and "rec" not in metric else f"{hi:.2%}"
            print(f"{m_name:<25} | {metric:<10} | {fmt_pt:<10} | {fmt_lo:<12} | {fmt_hi:<12}")

    print("\n" + "=" * 95)
    print("PAIRED BOOTSTRAP DIFFERENCES & HYPOTHESIS TESTS (95% CI)")
    print("=" * 95)
    paired_tests = [
        ("Brier (Isotonic - Platt)", diff_brier_iso_platt, False),
        ("Log Loss (Isotonic - Platt)", diff_logloss_iso_platt, False),
        ("Brier (Isotonic - Spatial)", diff_brier_iso_spatial, False),
        ("Brier (Platt - Spatial)", diff_brier_platt_spatial, False),
        ("Log Loss (Isotonic - Spatial)", diff_logloss_iso_spatial, False),
        ("Precision@4 (Isotonic - Spatial)", diff_prec4_iso_spatial, True),
        ("Precision@4 (Platt - Spatial)", diff_prec4_platt_spatial, True),
        ("Precision@4 (Raw - Spatial)", diff_prec4_raw_spatial, True),
        ("Recall@4 (Isotonic - Spatial)", diff_rec4_iso_spatial, True),
        ("Recall@4 (Platt - Spatial)", diff_rec4_platt_spatial, True),
    ]

    paired_summary = {}
    print(f"{'Comparison':<35} | {'Mean Diff':<11} | {'95% CI Lower':<12} | {'95% CI Upper':<12} | {'p-value (2-sided)':<18}")
    print("-" * 95)
    for name, diff_arr, is_pct in paired_tests:
        mean_diff = float(np.mean(diff_arr))
        lo, hi = get_ci(diff_arr)
        # 2-sided empirical p-value: 2 * min(P(diff <= 0), P(diff >= 0))
        p_val = float(2 * min(np.mean(diff_arr <= 0), np.mean(diff_arr >= 0)))
        p_val = min(1.0, p_val)
        paired_summary[name] = {"mean": mean_diff, "ci_lower": lo, "ci_upper": hi, "p_value": p_val}

        fmt_m = f"{mean_diff:+.2%}" if is_pct else f"{mean_diff:+.6f}"
        fmt_lo = f"{lo:+.2%}" if is_pct else f"{lo:+.6f}"
        fmt_hi = f"{hi:+.2%}" if is_pct else f"{hi:+.6f}"
        p_str = f"{p_val:.4f}" if p_val >= 0.0001 else "< 0.0001"
        print(f"{name:<35} | {fmt_m:<11} | {fmt_lo:<12} | {fmt_hi:<12} | {p_str:<18}")

    # Output JSON of audit results for documentation
    out_obj = {
        "bootstrap_replicates": n_replicates,
        "random_seed": seed,
        "n_shifts": n_shifts,
        "n_observations": len(test_df),
        "model_summary": summary_stats,
        "paired_differences": paired_summary
    }
    with open("backend/artifacts/statistical_robustness_results.json", "w", encoding="utf-8") as f:
        json.dump(out_obj, f, indent=2)

    print("\nResults exported to backend/artifacts/statistical_robustness_results.json")
    return out_obj

if __name__ == "__main__":
    run_bootstrap_audit(n_replicates=5000, seed=42)
