"""
Système d'alertes — notifie quand un drift critique est détecté.

Niveaux d'alerte :
  INFO    → tout va bien
  WARNING → drift partiel (quelques features)
  CRITICAL → drift global (majorité des features)

Les alertes sont :
  1. Loggées dans le terminal
  2. Sauvegardées dans monitoring/reports/alerts.jsonl
     (format JSON Lines — une alerte par ligne, lisible par Claude en Session 6)
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    from monitoring.config import REPORTS_DIR, DRIFT_SHARE_THRESHOLD
    from monitoring.drift_detector import DriftResult
except ImportError:
    from config import REPORTS_DIR, DRIFT_SHARE_THRESHOLD
    from drift_detector import DriftResult

logger = logging.getLogger(__name__)

ALERTS_FILE = "monitoring/reports/alerts.jsonl"


def _write_alert(alert: dict) -> None:
    """Écrit une alerte dans le fichier JSONL."""
    path = Path(ALERTS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(alert) + "\n")


def evaluate_and_alert(result: DriftResult) -> str:
    """
    Évalue la sévérité du drift et déclenche l'alerte appropriée.

    Retourne le niveau : "ok", "warning", ou "critical".
    """
    alert = {
        "timestamp": result.timestamp,
        "symbol": result.symbol,
        "dataset_drift": result.dataset_drift,
        "drift_share": result.drift_share,
        "n_features_drifted": result.n_features_drifted,
        "features_drifted": [
            f for f, info in result.feature_results.items() if info["drifted"]
        ],
    }

    if not result.dataset_drift:
        alert["level"] = "ok"
        alert["message"] = f"{result.symbol} — Aucun drift détecté. Modèle stable."
        logger.info(alert["message"])

    elif result.drift_share < DRIFT_SHARE_THRESHOLD:
        alert["level"] = "warning"
        drifted = alert["features_drifted"]
        alert["message"] = (
            f"{result.symbol} — Drift partiel sur {result.n_features_drifted} feature(s) : "
            f"{', '.join(drifted)}. Surveiller."
        )
        logger.warning(alert["message"])

    else:
        alert["level"] = "critical"
        alert["message"] = (
            f"{result.symbol} — DRIFT CRITIQUE : {result.drift_share:.0%} des features "
            f"ont changé de distribution. Réentraînement recommandé."
        )
        logger.critical(alert["message"])

    _write_alert(alert)
    return alert["level"]


def load_alerts(n: int = 50) -> list[dict]:
    """Charge les n dernières alertes depuis le fichier JSONL."""
    path = Path(ALERTS_FILE)
    if not path.exists():
        return []

    lines = path.read_text().strip().split("\n")
    alerts = [json.loads(line) for line in lines if line]
    return alerts[-n:]


def get_alert_summary() -> dict:
    """Résumé statistique des alertes pour le dashboard."""
    alerts = load_alerts(n=1000)
    if not alerts:
        return {"total": 0, "ok": 0, "warning": 0, "critical": 0}

    return {
        "total": len(alerts),
        "ok":       sum(1 for a in alerts if a.get("level") == "ok"),
        "warning":  sum(1 for a in alerts if a.get("level") == "warning"),
        "critical": sum(1 for a in alerts if a.get("level") == "critical"),
        "last_alert": alerts[-1],
    }
