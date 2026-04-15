"""
Online Feature Store — Redis.

Stratégie de stockage :
  - Clé : features:{symbol}  →  Hash Redis avec tous les champs du FeatureVector
  - TTL : 1h (configurable) pour éviter des données périmées en prod
  - Time series : on garde aussi les N derniers vecteurs dans une liste
    features:history:{symbol}  →  List Redis (LPUSH + LTRIM)
"""

import json
import logging

import redis

try:
    from feature_store.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_FEATURE_TTL
    from feature_store.features import FeatureVector
except ImportError:
    from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_FEATURE_TTL
    from features import FeatureVector

logger = logging.getLogger(__name__)

HISTORY_MAX_LEN = 100  # derniers vecteurs gardés par symbole


class OnlineFeatureStore:

    def __init__(self):
        self._client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
        )
        self._client.ping()
        logger.info("OnlineFeatureStore connecté à Redis %s:%d", REDIS_HOST, REDIS_PORT)

    def write(self, fv: FeatureVector) -> None:
        """Écrit le FeatureVector dans Redis (hash + historique)."""
        data = {k: str(v) for k, v in fv.to_dict().items()}

        pipe = self._client.pipeline()

        # Hash "latest" — mise à jour atomique
        key_latest = f"features:{fv.symbol}"
        pipe.hset(key_latest, mapping=data)
        pipe.expire(key_latest, REDIS_FEATURE_TTL)

        # Historique en liste (dernier en tête)
        key_history = f"features:history:{fv.symbol}"
        pipe.lpush(key_history, json.dumps(fv.to_dict()))
        pipe.ltrim(key_history, 0, HISTORY_MAX_LEN - 1)
        pipe.expire(key_history, REDIS_FEATURE_TTL)

        pipe.execute()

    def get_latest(self, symbol: str) -> dict | None:
        """Retourne les dernières features d'un symbole, ou None si absentes."""
        data = self._client.hgetall(f"features:{symbol}")
        if not data:
            return None
        # Reconvertit les nombres
        result = {}
        for k, v in data.items():
            try:
                result[k] = float(v) if "." in v else int(v)
            except ValueError:
                result[k] = v
        return result

    def get_history(self, symbol: str, n: int = 20) -> list[dict]:
        """Retourne les n derniers FeatureVectors d'un symbole."""
        raw = self._client.lrange(f"features:history:{symbol}", 0, n - 1)
        return [json.loads(r) for r in raw]

    def list_symbols(self) -> list[str]:
        """Retourne tous les symboles présents dans le store."""
        keys = self._client.keys("features:*")
        return sorted({k.split(":")[1] for k in keys if ":history:" not in k})
