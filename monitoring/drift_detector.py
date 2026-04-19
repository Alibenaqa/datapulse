"""
DataPulse — Session 5
Détecteur de data drift avec Evidently.

C'est quoi le data drift ?
──────────────────────────
Le modèle ML a été entraîné sur des données historiques avec
certaines caractéristiques statistiques (distributions des features).
Si les données réelles commencent à ressembler à autre chose
(ex: la volatilité explose suite à une crise), le modèle se dégrade
sans qu'on s'en aperçoive.

Le drift detector compare :
  - Dataset de référence → données d'entraînement (passé "stable")
  - Dataset courant      → données récentes (fenêtre glissante)

Il utilise des tests statistiques pour détecter si les distributions
ont significativement changé.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd
from evidently import ColumnMapping
from evidently.metrics import DataDriftTable, DatasetDriftMetric
from evidently.report import Report

try:
    from monitoring.config import (
        MONITORED_FEATURES,
        DRIFT_P_VALUE_THRESHOLD,
        DRIFT_SHARE_THRESHOLD,
        MIN_REFERENCE_SIZE,
        MIN_CURRENT_SIZE,
    )
except ImportError:
    from config import (
        MONITORED_FEATURES,
        DRIFT_P_VALUE_THRESHOLD,
        DRIFT_SHARE_THRESHOLD,
        MIN_REFERENCE_SIZE,
        MIN_CURRENT_SIZE,
    )

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    """Résultat complet d'une analyse de drift."""
    timestamp: str
    symbol: str
    dataset_drift: bool           # drift global détecté ?
    drift_share: float            # % de features en drift
    n_features_drifted: int
    n_features_total: int
    feature_results: dict         # détail par feature
    reference_size: int
    current_size: int
    report: Optional[object] = field(default=None, repr=False)  # objet Evidently Report

    def summary(self) -> str:
        status = "DRIFT DÉTECTÉ" if self.dataset_drift else "OK"
        lines = [
            f"[{status}] {self.symbol} — {self.timestamp}",
            f"  Features en drift : {self.n_features_drifted}/{self.n_features_total} ({self.drift_share:.0%})",
        ]
        for feat, info in self.feature_results.items():
            flag = "⚠" if info["drifted"] else "✓"
            lines.append(
                f"  {flag} {feat:25s} p={info['p_value']:.4f}  "
                f"méthode={info['stattest']}"
            )
        return "\n".join(lines)


def _load_from_duckdb(symbol: str, limit: int) -> Optional[pd.DataFrame]:
    """Charge les features depuis DuckDB, triées par timestamp."""
    try:
        import duckdb
        from monitoring.config import DUCKDB_PATH
    except ImportError:
        import duckdb
        from config import DUCKDB_PATH

    try:
        con = duckdb.connect(DUCKDB_PATH, read_only=True)
        cols = ", ".join(MONITORED_FEATURES)
        df = con.execute(f"""
            SELECT {cols}
            FROM features
            WHERE symbol = ?
              AND sma_5 IS NOT NULL
              AND sma_20 IS NOT NULL
            ORDER BY timestamp
            LIMIT {limit}
        """, [symbol]).df()
        con.close()
        return df if len(df) >= 10 else None
    except Exception as e:
        logger.warning("Impossible de charger depuis DuckDB : %s", e)
        return None


def _generate_synthetic_data(n: int, drift: bool = False) -> pd.DataFrame:
    """
    Génère des données synthétiques pour les tests.
    Si drift=True, simule un changement de distribution (ex: crise de marché).
    """
    np.random.seed(42 if not drift else 99)

    if not drift:
        # Distribution normale — marché calme
        return pd.DataFrame({
            "sma_5":            np.random.normal(190, 2, n),
            "sma_20":           np.random.normal(188, 3, n),
            "volatility_20":    np.abs(np.random.normal(1.5, 0.3, n)),
            "price_change_pct": np.random.normal(0, 0.5, n),
        })
    else:
        # Distribution très différente — simule une crise (volatilité x3, trend baissier)
        return pd.DataFrame({
            "sma_5":            np.random.normal(160, 8, n),   # prix beaucoup plus bas
            "sma_20":           np.random.normal(175, 10, n),
            "volatility_20":    np.abs(np.random.normal(5.0, 1.0, n)),  # volatilité x3
            "price_change_pct": np.random.normal(-1.5, 1.0, n),        # trend négatif
        })


class DriftDetector:
    """
    Détecte le data drift entre un dataset de référence et un dataset courant.

    Usage typique :
        detector = DriftDetector()
        result = detector.run("AAPL", reference_df, current_df)
        print(result.summary())
    """

    def run(
        self,
        symbol: str,
        reference: pd.DataFrame,
        current: pd.DataFrame,
    ) -> DriftResult:
        """
        Lance l'analyse de drift entre reference et current.

        Args:
            symbol    : ticker analysé (ex: "AAPL")
            reference : DataFrame des données d'entraînement (stable)
            current   : DataFrame des données récentes (à surveiller)

        Returns:
            DriftResult avec tous les détails
        """
        if len(reference) < MIN_REFERENCE_SIZE:
            raise ValueError(
                f"Dataset de référence trop petit : {len(reference)} < {MIN_REFERENCE_SIZE}"
            )
        if len(current) < MIN_CURRENT_SIZE:
            raise ValueError(
                f"Dataset courant trop petit : {len(current)} < {MIN_CURRENT_SIZE}"
            )

        # Garder seulement les features surveillées
        ref = reference[MONITORED_FEATURES].copy()
        cur = current[MONITORED_FEATURES].copy()

        # Rapport Evidently
        report = Report(metrics=[
            DatasetDriftMetric(stattest_threshold=DRIFT_P_VALUE_THRESHOLD),
            DataDriftTable(stattest_threshold=DRIFT_P_VALUE_THRESHOLD),
        ])

        column_mapping = ColumnMapping(numerical_features=MONITORED_FEATURES)
        report.run(reference_data=ref, current_data=cur, column_mapping=column_mapping)

        # Extraire les résultats
        report_dict = report.as_dict()
        dataset_metric = report_dict["metrics"][0]["result"]
        table_metric   = report_dict["metrics"][1]["result"]

        # Détail par feature
        feature_results = {}
        for feat in MONITORED_FEATURES:
            feat_data = table_metric["drift_by_columns"].get(feat, {})
            feature_results[feat] = {
                "drifted":  feat_data.get("drift_detected", False),
                "p_value":  round(feat_data.get("drift_score", 1.0), 4),
                "stattest": feat_data.get("stattest_name", "unknown"),
            }

        n_drifted = sum(1 for f in feature_results.values() if f["drifted"])

        result = DriftResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            dataset_drift=dataset_metric.get("dataset_drift", False),
            drift_share=dataset_metric.get("share_of_drifted_columns", 0.0),
            n_features_drifted=n_drifted,
            n_features_total=len(MONITORED_FEATURES),
            feature_results=feature_results,
            reference_size=len(ref),
            current_size=len(cur),
            report=report,
        )

        logger.info(result.summary())
        return result

    def run_from_duckdb(
        self,
        symbol: str,
        reference_size: int = 500,
        current_size: int = 100,
    ) -> Optional[DriftResult]:
        """
        Charge automatiquement depuis DuckDB et lance l'analyse.
        Les premiers reference_size ticks = référence.
        Les derniers current_size ticks = fenêtre courante.
        """
        df = _load_from_duckdb(symbol, reference_size + current_size)
        if df is None or len(df) < MIN_REFERENCE_SIZE + MIN_CURRENT_SIZE:
            logger.warning(
                "Pas assez de données dans DuckDB pour %s (%d lignes)",
                symbol, len(df) if df is not None else 0,
            )
            return None

        reference = df.iloc[:reference_size]
        current = df.iloc[-current_size:]
        return self.run(symbol, reference, current)
