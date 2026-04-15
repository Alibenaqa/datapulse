"""
Model Registry — promotion et chargement des modèles depuis MLflow.

MLflow 3.x utilise des aliases à la place des stages (dépréciés).

Aliases utilisés :
  "staging"    → modèle candidat validé, en attente de prod
  "production" → modèle servi par l'API FastAPI (Session 4)
"""

import logging

import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

from ml.config import (
    MLFLOW_TRACKING_URI,
    REGISTERED_MODEL_NAME,
    STAGING_ACCURACY_THRESHOLD,
)

logger = logging.getLogger(__name__)


def get_client() -> MlflowClient:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient()


def promote_to_staging(run_id: str, metrics: dict) -> bool:
    """
    Assigne l'alias 'staging' à la version issue du run_id
    si l'accuracy dépasse le seuil. Retourne True si promu.
    """
    if metrics.get("accuracy", 0) < STAGING_ACCURACY_THRESHOLD:
        logger.warning(
            "Promotion refusée — accuracy %.4f < seuil %.2f",
            metrics["accuracy"], STAGING_ACCURACY_THRESHOLD,
        )
        return False

    client = get_client()
    versions = client.search_model_versions(f"name='{REGISTERED_MODEL_NAME}'")
    matching = [v for v in versions if v.run_id == run_id]

    if not matching:
        logger.error("Aucune version trouvée pour le run %s", run_id)
        return False

    version = matching[0].version
    client.set_registered_model_alias(REGISTERED_MODEL_NAME, "staging", version)
    logger.info(
        "Modèle %s v%s → alias 'staging' (accuracy=%.4f)",
        REGISTERED_MODEL_NAME, version, metrics["accuracy"],
    )
    return True


def promote_to_production(version: str | None = None) -> None:
    """
    Promeut la version 'staging' (ou une version spécifique) vers 'production'.
    """
    client = get_client()

    if version is None:
        try:
            mv = client.get_model_version_by_alias(REGISTERED_MODEL_NAME, "staging")
            version = mv.version
        except Exception:
            logger.error("Aucun alias 'staging' à promouvoir.")
            return

    client.set_registered_model_alias(REGISTERED_MODEL_NAME, "production", version)
    logger.info("Modèle %s v%s → alias 'production'", REGISTERED_MODEL_NAME, version)


def load_production_model():
    """Charge le modèle tagué 'production'."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    uri = f"models:/{REGISTERED_MODEL_NAME}@production"
    try:
        model = mlflow.sklearn.load_model(uri)
        logger.info("Modèle production chargé : %s", uri)
        return model
    except Exception as e:
        logger.warning("Pas de modèle production disponible : %s", e)
        return None


def load_staging_model():
    """Charge le modèle tagué 'staging' (pour A/B testing Session 4)."""
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    uri = f"models:/{REGISTERED_MODEL_NAME}@staging"
    try:
        model = mlflow.sklearn.load_model(uri)
        logger.info("Modèle staging chargé : %s", uri)
        return model
    except Exception as e:
        logger.warning("Pas de modèle staging disponible : %s", e)
        return None


def list_versions() -> list[dict]:
    """Liste toutes les versions avec leurs aliases."""
    client = get_client()
    try:
        versions = client.search_model_versions(f"name='{REGISTERED_MODEL_NAME}'")
        return [
            {
                "version": v.version,
                "aliases": v.aliases,
                "run_id": v.run_id,
                "status": v.status,
            }
            for v in sorted(versions, key=lambda v: int(v.version))
        ]
    except Exception:
        return []
