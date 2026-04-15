"""
Préparation des données d'entraînement.

Deux sources possibles :
1. DuckDB (données réelles issues du feature pipeline Session 2)
2. Générateur synthétique (marche aléatoire) si pas assez de données réelles

Variable cible : direction du prochain tick
  1 → prix suivant > prix actuel  (hausse)
  0 → prix suivant <= prix actuel (baisse/stable)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from feature_store.features import FeatureEngine
from ml.config import FEATURE_COLS, DUCKDB_PATH, SYNTHETIC_TICKS, TEST_SIZE

logger = logging.getLogger(__name__)


def _generate_synthetic(n_ticks: int, symbol: str = "SYNTHETIC") -> pd.DataFrame:
    """
    Génère n_ticks de données synthétiques via marche aléatoire gaussienne.
    Retourne un DataFrame avec les features + target déjà calculés.
    """
    engine = FeatureEngine()
    rows = []
    price = 200.0

    for i in range(n_ticks + 1):  # +1 pour calculer la target du dernier tick
        change = np.random.normal(0, 0.005)
        price = round(price * (1 + change), 4)
        tick = {
            "symbol": symbol,
            "price": price,
            "volume": int(np.random.randint(100, 5000)),
            "timestamp": f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00",
        }
        fv = engine.process(tick)
        rows.append(fv.to_dict())

    df = pd.DataFrame(rows)

    # Target : 1 si le prix du prochain tick est supérieur au prix actuel
    df["next_price"] = df["price"].shift(-1)
    df["target"] = (df["next_price"] > df["price"]).astype(int)

    # Supprimer la dernière ligne (pas de next_price) et les lignes sans features complètes
    df = df.dropna(subset=FEATURE_COLS + ["target"])
    df = df.drop(columns=["next_price"])

    return df.reset_index(drop=True)


def load_from_duckdb(symbol: str | None = None) -> pd.DataFrame | None:
    """
    Charge les données depuis DuckDB (feature store Session 2).
    Retourne None si le fichier n'existe pas ou s'il y a moins de 100 lignes.
    """
    if not Path(DUCKDB_PATH).exists():
        return None

    import duckdb
    con = duckdb.connect(DUCKDB_PATH, read_only=True)

    where = f"WHERE symbol = '{symbol}'" if symbol else ""
    df = con.execute(f"""
        SELECT symbol, timestamp, price, volume, {', '.join(FEATURE_COLS)}
        FROM features
        {where}
        ORDER BY symbol, timestamp
    """).df()
    con.close()

    if len(df) < 100:
        return None

    # Calcul de la target par symbole (shift dans chaque groupe)
    df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    df["next_price"] = df.groupby("symbol")["price"].shift(-1)
    df["target"] = (df["next_price"] > df["price"]).astype(int)
    df = df.dropna(subset=FEATURE_COLS + ["target"])
    df = df.drop(columns=["next_price"])

    return df.reset_index(drop=True)


def get_training_data(symbol: str | None = None) -> pd.DataFrame:
    """
    Point d'entrée principal. Tente DuckDB d'abord, fallback sur synthétique.
    """
    df = load_from_duckdb(symbol)

    if df is not None:
        logger.info("Données chargées depuis DuckDB : %d lignes", len(df))
    else:
        logger.info(
            "Pas assez de données dans DuckDB — génération de %d ticks synthétiques",
            SYNTHETIC_TICKS,
        )
        df = _generate_synthetic(SYNTHETIC_TICKS)
        logger.info("Données synthétiques générées : %d lignes", len(df))

    return df


def train_test_split_temporal(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split temporel : les derniers TEST_SIZE% de lignes pour le test.
    On n'utilise PAS sklearn train_test_split pour éviter le data leakage.
    """
    cutoff = int(len(df) * (1 - TEST_SIZE))
    return df.iloc[:cutoff].copy(), df.iloc[cutoff:].copy()
