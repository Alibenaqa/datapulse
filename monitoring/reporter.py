"""
Génération de rapports HTML avec Evidently.

Chaque rapport est sauvegardé dans monitoring/reports/
avec un nom horodaté pour garder l'historique.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

try:
    from monitoring.config import REPORTS_DIR
    from monitoring.drift_detector import DriftResult
except ImportError:
    from config import REPORTS_DIR
    from drift_detector import DriftResult

logger = logging.getLogger(__name__)


def save_html_report(result: DriftResult) -> Path:
    """
    Sauvegarde le rapport Evidently en HTML.
    Retourne le chemin du fichier créé.
    """
    if result.report is None:
        raise ValueError("DriftResult ne contient pas de rapport Evidently.")

    reports_dir = Path(REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"drift_{result.symbol}_{ts}.html"
    path = reports_dir / filename

    result.report.save_html(str(path))
    logger.info("Rapport HTML sauvegardé : %s", path)
    return path


def save_json_summary(result: DriftResult) -> Path:
    """
    Sauvegarde un résumé JSON lisible par machine (utile pour la Session 6 / LLM).
    """
    import json

    reports_dir = Path(REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"drift_{result.symbol}_{ts}.json"
    path = reports_dir / filename

    summary = {
        "timestamp": result.timestamp,
        "symbol": result.symbol,
        "dataset_drift": result.dataset_drift,
        "drift_share": result.drift_share,
        "n_features_drifted": result.n_features_drifted,
        "n_features_total": result.n_features_total,
        "reference_size": result.reference_size,
        "current_size": result.current_size,
        "features": result.feature_results,
    }

    path.write_text(json.dumps(summary, indent=2))
    logger.info("Résumé JSON sauvegardé : %s", path)
    return path


def list_reports() -> list[dict]:
    """Liste tous les rapports existants triés par date (le plus récent en premier)."""
    reports_dir = Path(REPORTS_DIR)
    if not reports_dir.exists():
        return []

    reports = []
    for f in sorted(reports_dir.glob("drift_*.html"), reverse=True):
        parts = f.stem.split("_")
        reports.append({
            "file": str(f),
            "symbol": parts[1] if len(parts) > 1 else "unknown",
            "created": f.stat().st_mtime,
        })
    return reports
