"""
DataPulse — Session 1
Consumer : lit les ticks depuis Kafka et les persiste en JSON-Lines (JSONL).

Chaque fichier est partitionné par date et par symbole :
  data/raw/AAPL/2026-04-15.jsonl
  data/raw/GOOG/2026-04-15.jsonl
  ...

Format JSONL = une ligne JSON par tick, idéal pour DuckDB en Session 2.
"""

import json
import logging
import os
import signal
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from config import (
    DATA_RAW_PATH,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_CONSUMER_GROUP,
    KAFKA_TOPIC_STOCKS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def create_consumer(retries: int = 5, delay: int = 3) -> KafkaConsumer:
    import time

    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC_STOCKS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_CONSUMER_GROUP,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                key_deserializer=lambda k: k.decode("utf-8") if k else None,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
            )
            logger.info("Consommateur connecté à Kafka sur %s", KAFKA_BOOTSTRAP_SERVERS)
            return consumer
        except NoBrokersAvailable:
            logger.warning(
                "Kafka indisponible, tentative %d/%d dans %ds...",
                attempt,
                retries,
                delay,
            )
            time.sleep(delay)
    logger.error("Impossible de se connecter à Kafka après %d tentatives.", retries)
    sys.exit(1)


def get_output_path(symbol: str, timestamp_iso: str) -> Path:
    """Retourne le chemin JSONL partitionné par symbole et par date."""
    dt = datetime.fromisoformat(timestamp_iso)
    date_str = dt.strftime("%Y-%m-%d")
    directory = Path(DATA_RAW_PATH) / symbol
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{date_str}.jsonl"


def run():
    consumer = create_consumer()

    # Compteurs par symbole pour les stats
    counts: dict[str, int] = defaultdict(int)

    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Arrêt du consommateur...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Consommateur démarré — topic: %s | groupe: %s",
        KAFKA_TOPIC_STOCKS,
        KAFKA_CONSUMER_GROUP,
    )

    # Fichiers ouverts en cache pour éviter les I/O répétés
    file_handles: dict[str, object] = {}

    try:
        for message in consumer:
            if not running:
                break

            tick: dict = message.value
            symbol: str = tick.get("symbol", "UNKNOWN")
            timestamp: str = tick.get("timestamp", datetime.now(timezone.utc).isoformat())

            # Persistence JSONL
            output_path = get_output_path(symbol, timestamp)
            path_key = str(output_path)

            if path_key not in file_handles:
                file_handles[path_key] = open(output_path, "a", encoding="utf-8")
                logger.info("Nouveau fichier ouvert : %s", output_path)

            file_handles[path_key].write(json.dumps(tick) + "\n")
            file_handles[path_key].flush()

            counts[symbol] += 1

            logger.info(
                "Reçu  %s  prix=%.2f  volume=%d  [total %s: %d]",
                symbol,
                tick.get("price", 0),
                tick.get("volume", 0),
                symbol,
                counts[symbol],
            )

    finally:
        for fh in file_handles.values():
            fh.close()
        consumer.close()

        logger.info("Consommateur fermé. Statistiques finales :")
        for symbol, count in sorted(counts.items()):
            logger.info("  %s : %d ticks reçus", symbol, count)


if __name__ == "__main__":
    run()
