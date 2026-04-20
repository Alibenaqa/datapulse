"""
DataPulse — Session 6
Analyseur IA — envoie les alertes de drift à Claude pour obtenir
des insights en langage naturel.

Techniques utilisées :
  - Streaming     : Claude répond mot par mot (pas d'attente)
  - Prompt caching: le system prompt est mis en cache côté Anthropic
                    (économise des tokens sur des appels répétés)
  - Adaptive thinking: Claude "réfléchit" avant de répondre
                       (meilleure qualité d'analyse)
"""

import logging
from typing import Iterator

import anthropic

try:
    from llm.config import ANTHROPIC_MODEL, ANTHROPIC_API_KEY, MAX_TOKENS
    from llm.rag import get_context_for_symbol
except ImportError:
    from config import ANTHROPIC_MODEL, ANTHROPIC_API_KEY, MAX_TOKENS
    from rag import get_context_for_symbol

logger = logging.getLogger(__name__)

# ── System prompt (mis en cache côté Anthropic) ───────────────────────────────
# Ce texte est stable — il ne change pas entre les appels.
# Avec prompt caching, Anthropic le garde en mémoire pendant 5 minutes
# → les appels répétés coûtent moins cher en tokens.

SYSTEM_PROMPT = """Tu es DataPulse AI, un assistant expert en MLOps et surveillance de modèles ML financiers.

Tu analyses des alertes de drift de données pour des modèles de prédiction boursière.
Ces modèles prédisent si le prix d'une action va monter (UP) ou descendre (DOWN).

Contexte technique :
- Les features surveillées sont : sma_5 (moyenne mobile 5 ticks), sma_20 (moyenne mobile 20 ticks),
  volatility_20 (volatilité sur 20 ticks), price_change_pct (variation de prix en %)
- Un "drift" signifie que la distribution statistique d'une feature a changé
  par rapport à la période de référence (données d'entraînement)
- Drift WARNING : quelques features ont changé → surveiller
- Drift CRITICAL : majorité des features ont changé → réentraîner le modèle

Ton rôle :
1. Analyser les alertes reçues et expliquer ce qu'elles signifient en termes métier
2. Identifier les patterns (quelles features driftent souvent ? depuis quand ?)
3. Évaluer le risque pour les prédictions ML
4. Recommander des actions concrètes (réentraîner, surveiller, ignorer)

Réponds en français, de façon claire et structurée. Utilise des bullet points.
Sois précis mais accessible — le lecteur comprend la finance mais pas forcément le ML."""


def analyze_drift_streaming(symbol: str | None = None) -> Iterator[str]:
    """
    Analyse les alertes de drift via Claude et retourne les tokens en streaming.

    Usage :
        for token in analyze_drift_streaming("AAPL"):
            print(token, end="", flush=True)
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY non définie. "
            "Exporte-la : export ANTHROPIC_API_KEY='sk-ant-...'"
        )

    # ── Étape 1 : RAG — récupération du contexte ──────────────────────────────
    context, n_alerts = get_context_for_symbol(symbol)

    if n_alerts == 0:
        yield "Aucune alerte disponible pour ce symbole. Lance d'abord : python monitoring/run.py"
        return

    scope = f"pour {symbol}" if symbol else "pour toutes les actions"
    user_message = f"""Voici les {n_alerts} dernières alertes de drift {scope} :

---
{context}
---

Analyse ces alertes et fournis :
1. Un résumé de la situation actuelle
2. Les features les plus à risque
3. L'évaluation du risque global pour les prédictions ML
4. Tes recommandations concrètes"""

    # ── Étape 2 : Appel Claude avec streaming + prompt caching ───────────────
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    logger.info("Envoi à Claude (%s) — %d alertes en contexte", ANTHROPIC_MODEL, n_alerts)

    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                # Prompt caching : ce bloc est mis en cache 5 min chez Anthropic
                # Les appels répétés économisent ~90% des tokens du system prompt
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def analyze_drift_full(symbol: str | None = None) -> str:
    """
    Version non-streaming — attend la réponse complète et la retourne.
    Utilisée par l'endpoint FastAPI.
    """
    return "".join(analyze_drift_streaming(symbol))
