"""
Feature engineering — calcul à partir d'un buffer de prix en mémoire.

Toutes les fonctions sont pures (pas d'I/O) pour faciliter les tests.
"""

import math
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Optional

from config import WINDOW_SHORT, WINDOW_LONG, PRICE_BUFFER_SIZE


@dataclass
class FeatureVector:
    """Ensemble de features calculées pour un tick donné."""
    symbol: str
    timestamp: str
    price: float
    volume: int
    # Features dérivées
    sma_5: Optional[float] = None
    sma_20: Optional[float] = None
    volatility_20: Optional[float] = None   # écart-type sur 20 ticks
    price_change_pct: Optional[float] = None  # variation vs tick précédent

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


class SymbolBuffer:
    """
    Buffer glissant de prix pour un symbole.
    Maintient les N derniers prix pour calculer les features en O(1).
    """

    def __init__(self, maxlen: int = PRICE_BUFFER_SIZE):
        self._prices: deque[float] = deque(maxlen=maxlen)

    def push(self, price: float) -> None:
        self._prices.append(price)

    def sma(self, window: int) -> Optional[float]:
        if len(self._prices) < window:
            return None
        tail = list(self._prices)[-window:]
        return round(sum(tail) / window, 4)

    def volatility(self, window: int) -> Optional[float]:
        if len(self._prices) < window:
            return None
        tail = list(self._prices)[-window:]
        mean = sum(tail) / window
        variance = sum((p - mean) ** 2 for p in tail) / window
        return round(math.sqrt(variance), 4)

    def price_change_pct(self) -> Optional[float]:
        if len(self._prices) < 2:
            return None
        prev, curr = self._prices[-2], self._prices[-1]
        if prev == 0:
            return None
        return round((curr - prev) / prev * 100, 4)


class FeatureEngine:
    """
    Maintient un buffer par symbole et produit un FeatureVector à chaque tick.
    Stateful — à instancier une fois et réutiliser dans le pipeline.
    """

    def __init__(self):
        self._buffers: dict[str, SymbolBuffer] = {}

    def process(self, tick: dict) -> FeatureVector:
        symbol = tick["symbol"]

        if symbol not in self._buffers:
            self._buffers[symbol] = SymbolBuffer()

        buf = self._buffers[symbol]
        buf.push(tick["price"])

        return FeatureVector(
            symbol=symbol,
            timestamp=tick["timestamp"],
            price=tick["price"],
            volume=tick["volume"],
            sma_5=buf.sma(WINDOW_SHORT),
            sma_20=buf.sma(WINDOW_LONG),
            volatility_20=buf.volatility(WINDOW_LONG),
            price_change_pct=buf.price_change_pct(),
        )
