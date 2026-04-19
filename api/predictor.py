"""
Predictor — charge les modèles depuis MLflow et expose une fonction predict().

Les modèles sont chargés une seule fois au démarrage de l'API (singleton)
pour éviter de relire le disque à chaque requête.
"""

import logging
import numpy as np

from ml.config import FEATURE_COLS
from ml.registry import load_production_model, load_staging_model
from api.schemas import Prediction

logger = logging.getLogger(__name__)

FEATURE_ORDER = FEATURE_COLS  # ["sma_5", "sma_20", "volatility_20", "price_change_pct"]


def _confidence(proba: float) -> str:
    """Traduit une probabilité en niveau de confiance lisible."""
    if proba >= 0.65 or proba <= 0.35:
        return "high"
    if proba >= 0.55 or proba <= 0.45:
        return "medium"
    return "low"


class ModelStore:
    """
    Singleton qui maintient les modèles en mémoire.
    Appelé une fois au démarrage via le lifespan FastAPI.
    """

    def __init__(self):
        self._production = None
        self._staging = None

    def load(self):
        logger.info("Chargement des modèles depuis MLflow...")
        self._production = load_production_model()
        self._staging = load_staging_model()

        if self._production:
            logger.info("Modèle production chargé")
        else:
            logger.warning("Aucun modèle production disponible")

        if self._staging:
            logger.info("Modèle staging chargé")

    @property
    def has_production(self) -> bool:
        return self._production is not None

    @property
    def has_staging(self) -> bool:
        return self._staging is not None

    def _predict_with(self, model, features: dict, alias: str) -> Prediction:
        symbol = features.get("symbol", "UNKNOWN")
        X = np.array([[features[f] for f in FEATURE_ORDER]])
        direction_int = model.predict(X)[0]
        proba_up = model.predict_proba(X)[0][1]

        return Prediction(
            symbol=symbol,
            direction="UP" if direction_int == 1 else "DOWN",
            probability_up=round(float(proba_up), 4),
            model_version=alias,
            confidence=_confidence(proba_up),
        )

    def predict_production(self, features: dict) -> Prediction:
        if not self._production:
            raise RuntimeError("Aucun modèle production chargé.")
        return self._predict_with(self._production, features, "production")

    def predict_staging(self, features: dict) -> Prediction | None:
        if not self._staging:
            return None
        return self._predict_with(self._staging, features, "staging")


# Instance globale partagée par l'application FastAPI
model_store = ModelStore()
