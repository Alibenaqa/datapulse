import os
from dotenv import load_dotenv

load_dotenv()

# Redis (online store)
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_FEATURE_TTL = int(os.getenv("REDIS_FEATURE_TTL", "3600"))  # 1h

# DuckDB (offline store)
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/feature_store.duckdb")

# Feature engineering
WINDOW_SHORT = 5    # SMA courte
WINDOW_LONG = 20    # SMA longue + volatilité
# Taille du buffer de prix gardé en mémoire par symbole pour calculer les features
PRICE_BUFFER_SIZE = 50
