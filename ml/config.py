import os
from dotenv import load_dotenv

load_dotenv()

# MLflow
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "mlruns")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "datapulse-stock-direction")
REGISTERED_MODEL_NAME = "stock-direction-classifier"

# Données
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "data/feature_store.duckdb")

# Features utilisées pour l'entraînement
FEATURE_COLS = ["sma_5", "sma_20", "volatility_20", "price_change_pct"]

# Hyperparamètres du modèle (RandomForest)
RF_N_ESTIMATORS = int(os.getenv("RF_N_ESTIMATORS", "100"))
RF_MAX_DEPTH = int(os.getenv("RF_MAX_DEPTH", "6"))
RF_MIN_SAMPLES_LEAF = int(os.getenv("RF_MIN_SAMPLES_LEAF", "5"))
RF_RANDOM_STATE = 42

# Seuil de performance pour promotion en Staging
STAGING_ACCURACY_THRESHOLD = float(os.getenv("STAGING_ACCURACY_THRESHOLD", "0.52"))

# Nombre de ticks synthétiques à générer pour l'entraînement
SYNTHETIC_TICKS = int(os.getenv("SYNTHETIC_TICKS", "2000"))
TEST_SIZE = 0.2
