"""
DataPulse — Session 2
Feature Pipeline : Kafka → FeatureEngine → OnlineStore (Redis) + OfflineStore (DuckDB)

Ce pipeline tourne en parallèle du consumer Session 1 :
  - Session 1 consumer  → persiste les ticks bruts en JSONL
  - Ce pipeline         → calcule les features et les stocke dans Redis + DuckDB
"""

import logging
import signal
import sys
import time

from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

from config import REDIS_HOST, REDIS_PORT
from features import FeatureEngine
from online_store import OnlineFeatureStore
from offline_store import OfflineFeatureStore

# Kafka
import os
from dotenv import load_dotenv
load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_STOCKS = os.getenv("KAFKA_TOPIC_STOCKS", "stock-prices")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Log tous les 20 ticks pour ne pas noyer le terminal
LOG_EVERY_N = 20


def create_consumer(retries: int = 5, delay: int = 3) -> KafkaConsumer:
    import json
    for attempt in range(1, retries + 1):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC_STOCKS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id="datapulse-feature-pipeline",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
            )
            logger.info("Pipeline connecté à Kafka")
            return consumer
        except NoBrokersAvailable:
            logger.warning("Kafka indisponible, tentative %d/%d...", attempt, retries)
            time.sleep(delay)
    logger.error("Impossible de se connecter à Kafka.")
    sys.exit(1)


def run():
    engine = FeatureEngine()
    online = OnlineFeatureStore()
    offline = OfflineFeatureStore()

    consumer = create_consumer()

    running = True
    tick_count = 0

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Arrêt du pipeline...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Feature pipeline démarré — topic: %s", KAFKA_TOPIC_STOCKS)

    try:
        for message in consumer:
            if not running:
                break

            tick = message.value
            fv = engine.process(tick)

            online.write(fv)
            offline.write(fv)

            tick_count += 1
            if tick_count % LOG_EVERY_N == 0:
                stats = offline.stats()
                logger.info(
                    "[%d ticks] %s → prix=%.2f sma5=%s sma20=%s vol20=%s | DuckDB: %d lignes",
                    tick_count,
                    fv.symbol,
                    fv.price,
                    f"{fv.sma_5:.2f}" if fv.sma_5 else "—",
                    f"{fv.sma_20:.2f}" if fv.sma_20 else "—",
                    f"{fv.volatility_20:.4f}" if fv.volatility_20 else "—",
                    stats["total_rows"],
                )

    finally:
        offline.close()
        consumer.close()
        logger.info("Pipeline fermé. %d ticks traités.", tick_count)


if __name__ == "__main__":
    run()
