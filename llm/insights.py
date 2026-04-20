"""
DataPulse — Session 6
Point d'entrée CLI du module LLM — analyse les alertes de drift
et génère des insights en langage naturel via Claude.

Usage :
  python llm/insights.py                    # analyse toutes les actions
  python llm/insights.py --symbol AAPL      # analyse un symbole spécifique
  python llm/insights.py --no-stream        # attend la réponse complète

Prérequis :
  export ANTHROPIC_API_KEY='sk-ant-...'
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

try:
    from llm.analyzer import analyze_drift_streaming, analyze_drift_full
    from llm.rag import load_alerts
except ImportError:
    from analyzer import analyze_drift_streaming, analyze_drift_full
    from rag import load_alerts


def print_header(symbol: str | None) -> None:
    scope = symbol if symbol else "toutes les actions"
    print("\n" + "═" * 60)
    print(f"  DataPulse AI — Analyse de drift : {scope}")
    print("═" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="DataPulse — LLM Insights")
    parser.add_argument("--symbol", default=None, help="Symbole à analyser (défaut: tous)")
    parser.add_argument("--no-stream", action="store_true", help="Désactive le streaming")
    args = parser.parse_args()

    symbol = args.symbol.upper() if args.symbol else None

    # Vérifie qu'il y a des alertes avant d'appeler Claude
    alerts = load_alerts(symbol=symbol)
    if not alerts:
        print(f"\nAucune alerte trouvée. Lance d'abord :")
        print("  python monitoring/run.py --simulate-drift")
        sys.exit(0)

    print_header(symbol)
    print(f"Contexte : {len(alerts)} alertes récupérées\n")
    print("─" * 60)
    print()

    try:
        if args.no_stream:
            print(analyze_drift_full(symbol))
        else:
            # Streaming : affiche les tokens au fur et à mesure
            for token in analyze_drift_streaming(symbol):
                print(token, end="", flush=True)
            print()  # saut de ligne final

    except ValueError as e:
        print(f"\nErreur de configuration : {e}")
        sys.exit(1)
    except Exception as e:
        logger.error("Erreur lors de l'analyse : %s", e)
        raise

    print("\n" + "─" * 60)
    print("Analyse terminée.")


if __name__ == "__main__":
    main()
