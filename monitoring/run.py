"""
DataPulse — Session 5
Point d'entrée du monitoring — lance une analyse de drift complète.

Usage :
  python monitoring/run.py                    # tous les symboles
  python monitoring/run.py --symbol AAPL      # un symbole spécifique
  python monitoring/run.py --simulate-drift   # simule un drift pour tester les alertes
"""

import argparse
import logging
import sys

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

try:
    from monitoring.drift_detector import DriftDetector, _generate_synthetic_data
    from monitoring.reporter import save_html_report, save_json_summary
    from monitoring.alerts import evaluate_and_alert, get_alert_summary
    from monitoring.config import MONITORED_FEATURES
except ImportError:
    from drift_detector import DriftDetector, _generate_synthetic_data
    from reporter import save_html_report, save_json_summary
    from alerts import evaluate_and_alert, get_alert_summary
    from config import MONITORED_FEATURES

logger = logging.getLogger(__name__)

SYMBOLS = ["AAPL", "GOOG", "MSFT", "AMZN", "TSLA", "NVDA"]


def run_synthetic(symbol: str, simulate_drift: bool) -> None:
    """Lance une analyse sur données synthétiques (demo / test)."""
    detector = DriftDetector()

    reference = _generate_synthetic_data(200, drift=False)
    current   = _generate_synthetic_data(100, drift=simulate_drift)

    result = detector.run(symbol, reference, current)

    html_path = save_html_report(result)
    json_path = save_json_summary(result)
    level = evaluate_and_alert(result)

    print(f"\n{result.summary()}")
    print(f"\nRapport HTML : {html_path}")
    print(f"Résumé JSON  : {json_path}")
    print(f"Niveau alerte: {level.upper()}")


def run_from_duckdb(symbol: str) -> None:
    """Lance une analyse depuis les données réelles DuckDB."""
    detector = DriftDetector()
    result = detector.run_from_duckdb(symbol)

    if result is None:
        logger.warning("Pas assez de données pour %s — utilise --simulate-drift pour tester", symbol)
        return

    save_html_report(result)
    save_json_summary(result)
    level = evaluate_and_alert(result)

    print(f"\n{result.summary()}")
    print(f"\nNiveau alerte: {level.upper()}")


def main():
    parser = argparse.ArgumentParser(description="DataPulse — Monitoring drift")
    parser.add_argument("--symbol", default=None, help="Symbole à analyser (défaut: tous)")
    parser.add_argument("--simulate-drift", action="store_true",
                        help="Simule un drift pour tester le système d'alertes")
    args = parser.parse_args()

    symbols = [args.symbol.upper()] if args.symbol else SYMBOLS

    for symbol in symbols:
        logger.info("Analyse drift pour %s...", symbol)
        if args.simulate_drift or True:  # fallback synthétique si DuckDB insuffisant
            try:
                run_from_duckdb(symbol)
            except Exception:
                run_synthetic(symbol, args.simulate_drift)
        logger.info("─" * 60)

    summary = get_alert_summary()
    print(f"\nRésumé alertes : {summary}")


if __name__ == "__main__":
    main()
