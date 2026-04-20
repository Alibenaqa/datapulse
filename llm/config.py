"""
DataPulse — Session 6
Configuration du module LLM (Claude API).
"""

import os

# Modèle Claude à utiliser
ANTHROPIC_MODEL = "claude-opus-4-6"

# Clé API — à définir dans la variable d'environnement ANTHROPIC_API_KEY
# (ou dans un fichier .env à la racine du projet)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Chemin vers le fichier d'alertes généré par le monitoring
ALERTS_FILE = "monitoring/reports/alerts.jsonl"

# Nombre max d'alertes à injecter dans le contexte RAG
RAG_MAX_ALERTS = 20

# Nombre max de tokens dans la réponse Claude
MAX_TOKENS = 1024
