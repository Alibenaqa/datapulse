"""
DataPulse — Session 3
Pipeline d'entraînement ML avec MLflow tracking.

Modèle : RandomForestClassifier
Tâche  : prédire la direction du prochain tick (hausse/baisse)
"""

import logging
import sys
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from ml.config import (
    MLFLOW_TRACKING_URI,
    MLFLOW_EXPERIMENT_NAME,
    REGISTERED_MODEL_NAME,
    FEATURE_COLS,
    RF_N_ESTIMATORS,
    RF_MAX_DEPTH,
    RF_MIN_SAMPLES_LEAF,
    RF_RANDOM_STATE,
    STAGING_ACCURACY_THRESHOLD,
)
from ml.data_prep import get_training_data, train_test_split_temporal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def compute_metrics(y_true, y_pred, y_proba) -> dict:
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_true, y_proba), 4),
    }


def train(symbol: str | None = None) -> tuple[str, dict]:
    """
    Lance un run MLflow complet : chargement → entraînement → évaluation → log.

    Retourne (run_id, metrics).
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    # 1. Données
    df = get_training_data(symbol)
    train_df, test_df = train_test_split_temporal(df)

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df["target"].values
    X_test  = test_df[FEATURE_COLS].values
    y_test  = test_df["target"].values

    logger.info(
        "Dataset — train: %d lignes, test: %d lignes | target balance: %.1f%% hausse",
        len(train_df), len(test_df), y_train.mean() * 100,
    )

    # 2. Entraînement dans un run MLflow
    with mlflow.start_run() as run:
        run_id = run.info.run_id

        # Params
        params = {
            "n_estimators": RF_N_ESTIMATORS,
            "max_depth": RF_MAX_DEPTH,
            "min_samples_leaf": RF_MIN_SAMPLES_LEAF,
            "random_state": RF_RANDOM_STATE,
            "features": ",".join(FEATURE_COLS),
            "train_size": len(train_df),
            "test_size": len(test_df),
            "symbol": symbol or "all",
        }
        mlflow.log_params(params)

        # Modèle
        model = RandomForestClassifier(
            n_estimators=RF_N_ESTIMATORS,
            max_depth=RF_MAX_DEPTH,
            min_samples_leaf=RF_MIN_SAMPLES_LEAF,
            random_state=RF_RANDOM_STATE,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        # Évaluation
        y_pred  = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        metrics = compute_metrics(y_test, y_pred, y_proba)
        mlflow.log_metrics(metrics)

        # Feature importances
        importances = dict(zip(FEATURE_COLS, model.feature_importances_.round(4)))
        mlflow.log_metrics({f"importance_{k}": v for k, v in importances.items()})

        # Artefact modèle
        mlflow.sklearn.log_model(
            model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME,
            input_example=X_train[:5],
        )

        logger.info("Run MLflow %s", run_id)
        logger.info(
            "Métriques — accuracy=%.4f  f1=%.4f  roc_auc=%.4f",
            metrics["accuracy"], metrics["f1"], metrics["roc_auc"],
        )
        logger.info("Feature importances : %s", importances)

        # Tag de qualité
        passes_threshold = metrics["accuracy"] >= STAGING_ACCURACY_THRESHOLD
        mlflow.set_tag("ready_for_staging", str(passes_threshold))
        mlflow.set_tag("symbol", symbol or "all")

        if passes_threshold:
            logger.info(
                "Seuil atteint (%.4f >= %.2f) — modèle prêt pour Staging",
                metrics["accuracy"], STAGING_ACCURACY_THRESHOLD,
            )
        else:
            logger.warning(
                "Seuil non atteint (%.4f < %.2f)",
                metrics["accuracy"], STAGING_ACCURACY_THRESHOLD,
            )

    return run_id, metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Entraîner le modèle DataPulse")
    parser.add_argument("--symbol", default=None, help="Symbole à entraîner (défaut: tous)")
    args = parser.parse_args()

    run_id, metrics = train(args.symbol)
    print(f"\nRun ID : {run_id}")
    print("Métriques finales :")
    for k, v in metrics.items():
        print(f"  {k:15s} {v:.4f}")
