"""
Offline Feature Store — DuckDB.

DuckDB lit directement les fichiers JSONL produits par le consumer (Session 1)
sans ETL intermédiaire. On matérialise aussi une table `features` pour
les requêtes d'entraînement (Session 3).

Schéma :
  raw_ticks   — vue sur les JSONL (lecture directe)
  features    — table persistée avec les FeatureVectors calculés
"""

import logging
from pathlib import Path

import duckdb

try:
    from feature_store.config import DUCKDB_PATH
    from feature_store.features import FeatureVector
except ImportError:
    from config import DUCKDB_PATH
    from features import FeatureVector

logger = logging.getLogger(__name__)

_CREATE_FEATURES_TABLE = """
CREATE TABLE IF NOT EXISTS features (
    symbol          VARCHAR NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    price           DOUBLE NOT NULL,
    volume          INTEGER NOT NULL,
    sma_5           DOUBLE,
    sma_20          DOUBLE,
    volatility_20   DOUBLE,
    price_change_pct DOUBLE,
    PRIMARY KEY (symbol, timestamp)
)
"""

_INSERT_FEATURE = """
INSERT OR IGNORE INTO features VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""


class OfflineFeatureStore:

    def __init__(self):
        Path(DUCKDB_PATH).parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(DUCKDB_PATH)
        self._con.execute(_CREATE_FEATURES_TABLE)
        logger.info("OfflineFeatureStore ouvert : %s", DUCKDB_PATH)

    def write(self, fv: FeatureVector) -> None:
        """Persiste un FeatureVector dans la table features."""
        self._con.execute(_INSERT_FEATURE, [
            fv.symbol,
            fv.timestamp,
            fv.price,
            fv.volume,
            fv.sma_5,
            fv.sma_20,
            fv.volatility_20,
            fv.price_change_pct,
        ])

    def query_raw(self, symbol: str, date: str) -> "duckdb.DuckDBPyRelation":
        """
        Lit les ticks bruts depuis les JSONL sans les charger en mémoire.
        Exemple : store.query_raw('AAPL', '2026-04-15').df()
        """
        jsonl_path = f"data/raw/{symbol}/{date}.jsonl"
        if not Path(jsonl_path).exists():
            raise FileNotFoundError(f"Pas de données pour {symbol} le {date}")
        return self._con.execute(
            f"SELECT * FROM read_json_auto('{jsonl_path}') ORDER BY timestamp"
        )

    def query_features(
        self,
        symbol: str | None = None,
        limit: int = 1000,
    ) -> "duckdb.DuckDBPyRelation":
        """
        Requête sur la table features matérialisée.
        Retourne un objet relation — appelle .df() pour obtenir un DataFrame pandas.
        """
        where = f"WHERE symbol = '{symbol}'" if symbol else ""
        return self._con.execute(
            f"SELECT * FROM features {where} ORDER BY timestamp DESC LIMIT {limit}"
        )

    def get_training_dataset(self, symbol: str) -> "duckdb.DuckDBPyRelation":
        """
        Retourne le dataset complet pour l'entraînement ML (Session 3).
        Exclut les lignes avec des features nulles (fenêtre insuffisante).
        """
        return self._con.execute("""
            SELECT *
            FROM features
            WHERE symbol = ?
              AND sma_5 IS NOT NULL
              AND sma_20 IS NOT NULL
              AND volatility_20 IS NOT NULL
              AND price_change_pct IS NOT NULL
            ORDER BY timestamp
        """, [symbol])

    def stats(self) -> dict:
        """Statistiques rapides du store."""
        row = self._con.execute(
            "SELECT COUNT(*) as total, COUNT(DISTINCT symbol) as symbols FROM features"
        ).fetchone()
        return {"total_rows": row[0], "symbols": row[1]}

    def close(self) -> None:
        self._con.close()
