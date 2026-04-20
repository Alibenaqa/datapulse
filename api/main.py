"""
DataPulse — Session 4
API FastAPI — sert les prédictions ML en temps réel.

Endpoints :
  GET  /health                  → état de l'API et des modèles
  GET  /symbols                 → symboles disponibles dans Redis
  POST /predict                 → prédiction à partir de features manuelles
  GET  /predict/{symbol}        → prédiction à partir des dernières features Redis
  GET  /ab-test/{symbol}        → compare production vs staging sur un symbole
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from api.predictor import model_store
from api.schemas import (
    PredictRequest,
    PredictResponse,
    ABTestResponse,
    HealthResponse,
    InsightResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan : chargement des modèles au démarrage ───────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    model_store.load()
    yield
    logger.info("API arrêtée.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DataPulse API",
    description="API de prédiction ML temps réel — direction des cours boursiers",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper Redis ──────────────────────────────────────────────────────────────

def _get_redis_store():
    try:
        from feature_store.online_store import OnlineFeatureStore
        return OnlineFeatureStore()
    except Exception:
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Infra"])
def health():
    """Vérifie que l'API, les modèles et Redis sont opérationnels."""
    redis_ok = False
    store = _get_redis_store()
    if store:
        try:
            store._client.ping()
            redis_ok = True
        except Exception:
            pass

    return HealthResponse(
        status="ok",
        model_production=model_store.has_production,
        model_staging=model_store.has_staging,
        redis_online=redis_ok,
    )


@app.get("/symbols", tags=["Data"])
def list_symbols():
    """
    Retourne les symboles disponibles dans le feature store Redis.
    Ces symboles ont des features calculées et prêtes à l'emploi.
    """
    store = _get_redis_store()
    if not store:
        raise HTTPException(503, "Redis indisponible")
    return {"symbols": store.list_symbols()}


@app.post("/predict", response_model=PredictResponse, tags=["Prediction"])
def predict(request: PredictRequest):
    """
    Prédiction à partir de features fournies manuellement.

    Utile pour tester le modèle avec des valeurs arbitraires.
    """
    if not model_store.has_production:
        raise HTTPException(503, "Aucun modèle production disponible.")

    features = request.model_dump()
    pred = model_store.predict_production(features)

    return PredictResponse(
        prediction=pred,
        features_used={k: features[k] for k in ["sma_5", "sma_20", "volatility_20", "price_change_pct"]},
    )


@app.get("/predict/{symbol}", response_model=PredictResponse, tags=["Prediction"])
def predict_symbol(symbol: str):
    """
    Prédiction en temps réel pour un symbole donné.

    Récupère automatiquement les dernières features depuis Redis
    (calculées par le feature pipeline Session 2).
    """
    if not model_store.has_production:
        raise HTTPException(503, "Aucun modèle production disponible.")

    store = _get_redis_store()
    if not store:
        raise HTTPException(503, "Redis indisponible")

    features = store.get_latest(symbol.upper())
    if not features:
        raise HTTPException(
            404,
            f"Aucune feature disponible pour {symbol}. Lance le feature pipeline d'abord.",
        )

    features["symbol"] = symbol.upper()
    pred = model_store.predict_production(features)

    return PredictResponse(
        prediction=pred,
        features_used={k: features.get(k) for k in ["sma_5", "sma_20", "volatility_20", "price_change_pct"]},
    )


@app.get("/ab-test/{symbol}", response_model=ABTestResponse, tags=["A/B Testing"])
def ab_test(symbol: str):
    """
    Compare la prédiction du modèle production vs staging sur un symbole.

    Permet de valider qu'un nouveau modèle (staging) se comporte
    différemment ou mieux que le modèle en production avant de le promouvoir.
    """
    if not model_store.has_production:
        raise HTTPException(503, "Aucun modèle production disponible.")

    store = _get_redis_store()
    if not store:
        raise HTTPException(503, "Redis indisponible")

    features = store.get_latest(symbol.upper())
    if not features:
        raise HTTPException(404, f"Aucune feature disponible pour {symbol}.")

    features["symbol"] = symbol.upper()
    prod_pred = model_store.predict_production(features)
    staging_pred = model_store.predict_staging(features)

    return ABTestResponse(
        symbol=symbol.upper(),
        production=prod_pred,
        staging=staging_pred,
        agreement=staging_pred is not None and prod_pred.direction == staging_pred.direction,
    )


@app.get("/insights/{symbol}", response_model=InsightResponse, tags=["LLM"])
def insights_symbol(symbol: str):
    """
    Analyse IA des alertes de drift pour un symbole via Claude.

    Utilise RAG (Retrieval-Augmented Generation) : récupère les alertes
    du monitoring et demande à Claude de les analyser en langage naturel.

    Prérequis : variable d'environnement ANTHROPIC_API_KEY définie.
    """
    try:
        from llm.analyzer import analyze_drift_full
        from llm.rag import load_alerts
    except ImportError:
        raise HTTPException(503, "Module LLM non disponible.")

    sym = symbol.upper()
    alerts = load_alerts(symbol=sym)

    if not alerts:
        raise HTTPException(
            404,
            f"Aucune alerte trouvée pour {sym}. Lance d'abord : python monitoring/run.py",
        )

    try:
        insight = analyze_drift_full(sym)
    except ValueError as e:
        raise HTTPException(503, str(e))

    return InsightResponse(
        symbol=sym,
        n_alerts_analyzed=len(alerts),
        insight=insight,
    )


@app.get("/insights", response_model=InsightResponse, tags=["LLM"])
def insights_all():
    """
    Analyse IA globale de toutes les alertes de drift (tous les symboles).
    """
    try:
        from llm.analyzer import analyze_drift_full
        from llm.rag import load_alerts
    except ImportError:
        raise HTTPException(503, "Module LLM non disponible.")

    alerts = load_alerts()

    if not alerts:
        raise HTTPException(
            404,
            "Aucune alerte trouvée. Lance d'abord : python monitoring/run.py",
        )

    try:
        insight = analyze_drift_full(symbol=None)
    except ValueError as e:
        raise HTTPException(503, str(e))

    return InsightResponse(
        symbol=None,
        n_alerts_analyzed=len(alerts),
        insight=insight,
    )
