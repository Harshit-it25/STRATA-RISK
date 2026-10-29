import json
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from catboost import CatBoostClassifier
import joblib

from backend.pipeline.data_pipeline import SpatioTemporalDataPipeline
from backend.models.baselines import HistoricalSpatialBaseline

def run_moving_block_bootstrap(
    block_lengths=[1, 3, 6, 12, 18],
    n_replicates=5000,
    seed=42
):
    print("=" * 85)
    print("STRATA RISK — MOVING-BLOCK BOOTSTRAP (MBB) TEMPORAL SENSITIVITY AUDIT")
    print(f"Replicates: {n_replicates} | Seed: {seed} | Block lengths evaluated: {block_lengths}")
    print("=" * 85)

    pipeline = SpatioTemporalDataPipeline()
    raw_df = pd.read_csv("data/processed_chicago_crimes.csv")
    clean_df = pipeline.validate_raw_data(raw_df)
    grid_df = pipeline.build_spatio_temporal_grid(clean_df)
    feature_df = pipeline.generate_features_and_targets(grid_df)

    train_df, val_df, test_df = pipeline.split_chronological(feature_df, train_frac=0.65, val_frac=0.15)
    
    unique_shifts = sorted(test_df["window_time"].unique())
    n_shifts = len(unique_shifts) # 172
    print(f"Holdout Test Shifts: {n_shifts} ({test_df['window_time'].min()} to {test_df['window_time'].max()})")

    y_val = val_df["target_event"].values.astype(int)
    y_test = test_df["target_event"].values.astype(int)

    # 1. Models
    spatial_baseline = HistoricalSpatialBaseline(prior_weight=5.0).fit(train_df)
    p_test_spatial = spatial_baseline.predict_proba(test_df)

    model = CatBoostClassifier()
    model.load_model("backend/artifacts/forecaster_catboost.cbm")
    with open("backend/artifacts/model_metadata.json", "r") as f:
        meta = json.load(f)
    feature_cols = meta["feature_columns"]

    p_val_raw = model.predict_proba(val_df[feature_cols])[:, 1]
    p_test_raw = model.predict_proba(test_df[feature_cols])[:, 1]

    iso_cal = joblib.load("backend/artifacts/calibrator.joblib")
    p_test_iso = np.clip(iso_cal.predict(p_test_raw), 0.0, 1.0)

    # Platt (Logit, C=1.0 fitted on validation only)
    eps = 1e-12
    p_val_raw_clipped = np.clip(p_val_raw, eps, 1 - eps)
    p_test_raw_clipped = np.clip(p_test_raw, eps, 1 - eps)
    logits_val = np.log(p_val_raw_clipped / (1 - p_val_raw_clipped)).reshape(-1, 1)
    logits_test = np.log(p_test_raw_clipped / (1 - p_test_raw_clipped)).reshape(-1, 1)

    lr_logit = LogisticRegression(solver="lbfgs", C=1.0, random_state=42)
    lr_logit.fit(logits_val, y_val)
    p_test_platt = lr_logit.predict_proba(logits_test)[:, 1]

    # Time-Aware Expanding Historical Baseline (strictly t < forecast window)
    feature_df["has_event"] = (feature_df["incident_count"] > 0).astype(int)
    feature_df["cum_events"] = feature_df.groupby(["sector_id", "zone_key"])["has_event"].cumsum() - feature_df["has_event"]
    feature_df["cum_n"] = feature_df.groupby(["sector_id", "zone_key"]).cumcount()
    global_prior = train_df["target_event"].mean() # 0.6797
    feature_df["expanding_rate"] = (feature_df["cum_events"] + 5.0 * global_prior) / (feature_df["cum_n"] + 5.0)

    # Extract test expanding rate
    _, _, test_expanding_df = pipeline.split_chronological(feature_df, train_frac=0.65, val_frac=0.15)
    p_test_expanding = test_expanding_df["expanding_rate"].values

    models = {
        "spatial": p_test_spatial,
        "expanding_spatial": p_test_expanding,
        "raw": p_test_raw,
        "iso": p_test_iso,
        "platt": p_test_platt,
    }

    shift_to_idx = {s: i for i, s in enumerate(unique_shifts)}
    test_shift_indices = test_df["window_time"].map(shift_to_idx).values

    # Precompute per-shift metrics matrix
    shift_metrics = {m: {
        "brier": np.zeros(n_shifts),
        "logloss": np.zeros(n_shifts),
        "prec4": np.zeros(n_shifts),
        "rec4": np.zeros(n_shifts)
    } for m in models}

    eps_ll = 1e-15
    for s_idx in range(n_shifts):
        mask = (test_shift_indices == s_idx)
        y_shift = y_test[mask]
        n_pos = np.sum(y_shift)
        k = 4

        for m_name, probs in models.items():
            p_shift = probs[mask]
            shift_metrics[m_name]["brier"][s_idx] = np.mean((p_shift - y_shift) ** 2)
            p_clip = np.clip(p_shift, eps_ll, 1 - eps_ll)
            shift_metrics[m_name]["logloss"][s_idx] = -np.mean(y_shift * np.log(p_clip) + (1 - y_shift) * np.log(1 - p_clip))
            
            top_k = np.argsort(-p_shift, kind="stable")[:k]
            pos_top = np.sum(y_shift[top_k])
            shift_metrics[m_name]["prec4"][s_idx] = pos_top / k
            shift_metrics[m_name]["rec4"][s_idx] = (pos_top / n_pos) if n_pos > 0 else np.nan

    def compute_ci_and_p(arr):
        mean_diff = float(np.mean(arr))
        ci_lo = float(np.percentile(arr, 2.5))
        ci_hi = float(np.percentile(arr, 97.5))
        p_val = float(2 * min(np.mean(arr <= 0), np.mean(arr >= 0)))
        p_val = min(1.0, p_val)
        return mean_diff, ci_lo, ci_hi, p_val

    all_results = {}

    for L in block_lengths:
        print(f"\n--- Running MBB for Block Length L = {L} ({L*4} hours) ---")
        rng = np.random.default_rng(seed)
        num_blocks = n_shifts - L + 1
        blocks = [list(range(j, j + L)) for j in range(num_blocks)]
        blocks_needed = int(np.ceil(n_shifts / L))

        # Sample blocks and truncate to n_shifts
        sampled_shifts_matrix = np.zeros((n_replicates, n_shifts), dtype=int)
        for b in range(n_replicates):
            chosen_block_ids = rng.choice(num_blocks, size=blocks_needed, replace=True)
            seq = []
            for blk_id in chosen_block_ids:
                seq.extend(blocks[blk_id])
            sampled_shifts_matrix[b] = seq[:n_shifts]

        # Evaluate bootstrap replicate means
        boot_metrics = {m: {
            "brier": np.zeros(n_replicates),
            "logloss": np.zeros(n_replicates),
            "prec4": np.zeros(n_replicates),
            "rec4": np.zeros(n_replicates)
        } for m in models}

        for m_name in models:
            for b in range(n_replicates):
                s_idx = sampled_shifts_matrix[b]
                boot_metrics[m_name]["brier"][b] = np.mean(shift_metrics[m_name]["brier"][s_idx])
                boot_metrics[m_name]["logloss"][b] = np.mean(shift_metrics[m_name]["logloss"][s_idx])
                boot_metrics[m_name]["prec4"][b] = np.mean(shift_metrics[m_name]["prec4"][s_idx])
                boot_metrics[m_name]["rec4"][b] = np.nanmean(shift_metrics[m_name]["rec4"][s_idx])

        # Paired differences
        diffs = {
            "Brier (Iso - Platt)": boot_metrics["iso"]["brier"] - boot_metrics["platt"]["brier"],
            "Log Loss (Iso - Platt)": boot_metrics["iso"]["logloss"] - boot_metrics["platt"]["logloss"],
            "Brier (Iso - Spatial)": boot_metrics["iso"]["brier"] - boot_metrics["spatial"]["brier"],
            "Brier (Platt - Spatial)": boot_metrics["platt"]["brier"] - boot_metrics["spatial"]["brier"],
            "Log Loss (Iso - Spatial)": boot_metrics["iso"]["logloss"] - boot_metrics["spatial"]["logloss"],
            "Prec@4 (Iso - Spatial)": boot_metrics["iso"]["prec4"] - boot_metrics["spatial"]["prec4"],
            "Prec@4 (Platt - Spatial)": boot_metrics["platt"]["prec4"] - boot_metrics["spatial"]["prec4"],
            "Recall@4 (Iso - Spatial)": boot_metrics["iso"]["rec4"] - boot_metrics["spatial"]["rec4"],
            "Recall@4 (Platt - Spatial)": boot_metrics["platt"]["rec4"] - boot_metrics["spatial"]["rec4"],
            "Prec@4 (Expanding - Static Spatial)": boot_metrics["expanding_spatial"]["prec4"] - boot_metrics["spatial"]["prec4"]
        }

        block_res = {}
        for name, diff_arr in diffs.items():
            mean_d, lo, hi, p = compute_ci_and_p(diff_arr)
            block_res[name] = {"mean": mean_d, "ci_lower": lo, "ci_upper": hi, "p_value": p}

        all_results[f"L={L}"] = block_res

        # Print summary for this L
        print(f"{'Paired Comparison':<35} | {'Mean Diff':<11} | {'95% CI Lower':<12} | {'95% CI Upper':<12} | {'p-value':<10}")
        print("-" * 87)
        for name, r in block_res.items():
            fmt_m = f"{r['mean']:+.2%}" if "Prec" in name or "Recall" in name else f"{r['mean']:+.6f}"
            fmt_lo = f"{r['ci_lower']:+.2%}" if "Prec" in name or "Recall" in name else f"{r['ci_lower']:+.6f}"
            fmt_hi = f"{r['ci_upper']:+.2%}" if "Prec" in name or "Recall" in name else f"{r['ci_upper']:+.6f}"
            p_str = f"{r['p_value']:.4f}" if r['p_value'] >= 0.0001 else "< 0.0001"
            print(f"{name:<35} | {fmt_m:<11} | {fmt_lo:<12} | {fmt_hi:<12} | {p_str:<10}")

    out_file = "backend/artifacts/temporal_mbb_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to {out_file}")
    return all_results

if __name__ == "__main__":
    run_moving_block_bootstrap()
