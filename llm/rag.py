"""
DataPulse — Session 6
RAG (Retrieval-Augmented Generation) — récupère les alertes pertinentes
depuis le fichier JSONL pour les injecter comme contexte dans Claude.

RAG = Retrieval-Augmented Generation
  → au lieu d'entraîner Claude sur nos données, on lui donne
    les données directement dans le prompt (comme un "copier-coller intelligent")
  → il peut ainsi répondre à des questions sur des données qu'il n'a jamais vues
"""

import json
import logging
from pathlib import Path

try:
    from llm.config import ALERTS_FILE, RAG_MAX_ALERTS
except ImportError:
    from config import ALERTS_FILE, RAG_MAX_ALERTS

logger = logging.getLogger(__name__)


def load_alerts(symbol: str | None = None, n: int = RAG_MAX_ALERTS) -> list[dict]:
    """
    Charge les n dernières alertes depuis le fichier JSONL.

    Si symbol est précisé, filtre sur ce symbole.
    Retourne une liste de dicts (chaque dict = une alerte).
    """
    path = Path(ALERTS_FILE)
    if not path.exists():
        logger.warning("Fichier d'alertes introuvable : %s", ALERTS_FILE)
        return []

    lines = path.read_text().strip().split("\n")
    alerts = []
    for line in lines:
        if not line:
            continue
        try:
            alert = json.loads(line)
            alerts.append(alert)
        except json.JSONDecodeError:
            continue

    if symbol:
        alerts = [a for a in alerts if a.get("symbol") == symbol.upper()]

    return alerts[-n:]


def format_alerts_for_prompt(alerts: list[dict]) -> str:
    """
    Formate les alertes en texte structuré pour le prompt Claude.

    Chaque alerte devient un bloc lisible avec les infos clés.
    """
    if not alerts:
        return "Aucune alerte disponible pour ce symbole."

    lines = []
    for i, alert in enumerate(alerts, 1):
        level = alert.get("level", "unknown").upper()
        symbol = alert.get("symbol", "?")
        timestamp = alert.get("timestamp", "?")
        drift_share = alert.get("drift_share", 0)
        features_drifted = alert.get("features_drifted", [])
        message = alert.get("message", "")

        lines.append(
            f"[{i}] {timestamp} | {symbol} | Niveau: {level}\n"
            f"    Drift share: {drift_share:.1%} des features\n"
            f"    Features impactées: {', '.join(features_drifted) if features_drifted else 'aucune'}\n"
            f"    Message: {message}"
        )

    return "\n\n".join(lines)


def get_context_for_symbol(symbol: str | None = None) -> str:
    """
    Point d'entrée principal du RAG.
    Retourne le contexte formaté pour injecter dans le prompt.
    """
    alerts = load_alerts(symbol=symbol)
    context = format_alerts_for_prompt(alerts)

    n = len(alerts)
    scope = f"pour {symbol}" if symbol else "toutes les actions"
    logger.info("RAG: %d alertes récupérées %s", n, scope)

    return context, n
