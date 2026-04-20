"""
Schémas Pydantic — définissent la forme des requêtes et réponses de l'API.
Pydantic valide automatiquement les types et génère la doc Swagger.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ── Requêtes ──────────────────────────────────────────────────────────────────

class PredictRequest(BaseModel):
    """Corps d'une requête de prédiction manuelle."""
    symbol: str = Field(..., example="AAPL")
    sma_5: float = Field(..., description="Moyenne mobile sur 5 ticks", example=189.5)
    sma_20: float = Field(..., description="Moyenne mobile sur 20 ticks", example=187.2)
    volatility_20: float = Field(..., description="Écart-type sur 20 ticks", example=1.42)
    price_change_pct: float = Field(..., description="Variation % vs tick précédent", example=0.31)


# ── Réponses ──────────────────────────────────────────────────────────────────

class Prediction(BaseModel):
    """Résultat d'une prédiction."""
    symbol: str
    direction: str          # "UP" ou "DOWN"
    probability_up: float   # probabilité de hausse (0-1)
    model_version: str      # alias du modèle utilisé
    confidence: str         # "high" / "medium" / "low"


class PredictResponse(BaseModel):
    prediction: Prediction
    features_used: dict


class ABTestResponse(BaseModel):
    """Résultat d'un test A/B entre production et staging."""
    symbol: str
    production: Prediction
    staging: Optional[Prediction]
    agreement: bool         # les deux modèles sont-ils d'accord ?


class HealthResponse(BaseModel):
    status: str
    model_production: bool
    model_staging: bool
    redis_online: bool


class InsightResponse(BaseModel):
    """Réponse de l'analyse IA des alertes de drift."""
    symbol: Optional[str]
    n_alerts_analyzed: int
    insight: str
