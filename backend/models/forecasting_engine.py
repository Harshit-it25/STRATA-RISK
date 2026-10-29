"""
Candidate Machine Learning Forecasting Engine for Strata Risk.

Implements CatBoost-based spatio-temporal tabular classification and count estimation.
Includes model calibration, feature importance, artifact serialization, and inference.
"""

import os
import json
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from catboost import CatBoostClassifier, Pool
from sklearn.isotonic import IsotonicRegression

class SpatioTemporalForecaster:
    def __init__(
        self,
        iterations: int = 300,
        learning_rate: float = 0.05,
        depth: int = 5,
        random_seed: int = 42
    ):
        self.iterations = iterations
        self.learning_rate = learning_rate
        self.depth = depth
        self.random_seed = random_seed
        self.model: Optional[CatBoostClassifier] = None
        self.calibrator: Optional[IsotonicRegression] = None
        self.feature_columns: List[str] = []
        self.cat_features: List[str] = ["sector_id", "zone_key"]
        self.metadata: Dict[str, Any] = {}

    def fit(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str = "target_event",
        dataset_type: str = "real",
        dataset_name: Optional[str] = None
    ) -> "SpatioTemporalForecaster":
        self.feature_columns = feature_cols
        cat_indices = [self.feature_columns.index(c) for c in self.cat_features if c in self.feature_columns]

        X_train = train_df[self.feature_columns].copy()
        y_train = train_df[target_col].astype(int).values

        X_val = val_df[self.feature_columns].copy()
        y_val = val_df[target_col].astype(int).values

        # CatBoost classifier with logloss objective
        self.model = CatBoostClassifier(
            iterations=self.iterations,
            learning_rate=self.learning_rate,
            depth=self.depth,
            random_seed=self.random_seed,
            eval_metric="Logloss",
            verbose=False,
            cat_features=cat_indices
        )

        train_pool = Pool(X_train, y_train, cat_features=cat_indices)
        val_pool = Pool(X_val, y_val, cat_features=cat_indices)

        self.model.fit(train_pool, eval_set=val_pool, early_stopping_rounds=30, verbose=False)

        # Fit isotonic probability calibrator on validation predictions (strictly post-hoc, zero test leakage)
        raw_val_probs = self.model.predict_proba(X_val)[:, 1]
        self.calibrator = IsotonicRegression(out_of_bounds="clip")
        self.calibrator.fit(raw_val_probs, y_val)

        # Record metadata
        self.metadata = {
            "model_type": "CatBoostClassifier",
            "dataset_type": dataset_type,
            "dataset_name": dataset_name or "Chicago Crimes (ijzp-q8t2) - Proxy Dataset",
            "iterations": self.model.get_best_iteration() or self.iterations,
            "feature_columns": self.feature_columns,
            "cat_features": self.cat_features,
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "calibrated": True,
            "calibration_method": "IsotonicRegression (Validation Fitted)",
            "random_seed": self.random_seed
        }

        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model has not been trained or loaded yet.")
        X = df[self.feature_columns].copy()
        raw_probs = self.model.predict_proba(X)[:, 1]
        if self.calibrator is not None:
            calibrated_probs = np.clip(self.calibrator.predict(raw_probs), 0.0, 1.0)
            return calibrated_probs
        return raw_probs

    def predict(self, df: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(df) >= threshold).astype(int)

    def get_feature_importances(self) -> Dict[str, float]:
        if self.model is None:
            return {}
        importances = self.model.get_feature_importance()
        return {feat: float(imp) for feat, imp in zip(self.feature_columns, importances)}

    def save_artifacts(self, artifact_dir: str = "backend/artifacts") -> None:
        os.makedirs(artifact_dir, exist_ok=True)
        model_path = os.path.join(artifact_dir, "forecaster_catboost.cbm")
        meta_path = os.path.join(artifact_dir, "model_metadata.json")
        cal_path = os.path.join(artifact_dir, "calibrator.joblib")

        if self.model is not None:
            self.model.save_model(model_path)

        if self.calibrator is not None:
            joblib.dump(self.calibrator, cal_path)

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

    def load_artifacts(
        self,
        artifact_dir: str = "backend/artifacts",
        expected_dataset_type: Optional[str] = None
    ) -> "SpatioTemporalForecaster":
        model_path = os.path.join(artifact_dir, "forecaster_catboost.cbm")
        meta_path = os.path.join(artifact_dir, "model_metadata.json")
        cal_path = os.path.join(artifact_dir, "calibrator.joblib")

        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError(f"Model artifacts not found in {artifact_dir}")

        with open(meta_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        # Enforce strict dataset provenance verification
        if expected_dataset_type is not None:
            actual_type = self.metadata.get("dataset_type", "synthetic")
            if actual_type != expected_dataset_type:
                raise RuntimeError(
                    f"Dataset artifact mismatch: Expected '{expected_dataset_type}' model, "
                    f"but artifact was trained on '{actual_type}' data."
                )

        self.feature_columns = self.metadata["feature_columns"]
        self.cat_features = self.metadata["cat_features"]

        self.model = CatBoostClassifier()
        self.model.load_model(model_path)

        if os.path.exists(cal_path):
            try:
                self.calibrator = joblib.load(cal_path)
            except Exception:
                self.calibrator = None
        else:
            self.calibrator = None

        return self
