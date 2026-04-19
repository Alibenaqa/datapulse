import os
from dotenv import load_dotenv

load_dotenv()

# Répertoire des rapports HTML générés
REPORTS_DIR = os.getenv("REPORTS_DIR", "monitoring/reports")

# DuckDB — même base que le feature store
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/feature_store.duckdb")

# Features surveillées
MONITORED_FEATURES = ["sma_5", "sma_20", "volatility_20", "price_change_pct"]

# Seuils d'alerte
# p-value : si < 0.05, la distribution a significativement changé (test statistique)
DRIFT_P_VALUE_THRESHOLD = float(os.getenv("DRIFT_P_VALUE_THRESHOLD", "0.05"))

# % de features en drift pour déclencher une alerte globale
DRIFT_SHARE_THRESHOLD = float(os.getenv("DRIFT_SHARE_THRESHOLD", "0.5"))

# Taille minimale du dataset de référence pour faire le test
MIN_REFERENCE_SIZE = int(os.getenv("MIN_REFERENCE_SIZE", "100"))

# Taille minimale du dataset courant
MIN_CURRENT_SIZE = int(os.getenv("MIN_CURRENT_SIZE", "50"))
