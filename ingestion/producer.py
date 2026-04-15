"""
DataPulse — Session 1
Producer : génère des cours boursiers simulés et les publie sur Kafka.

Chaque message est un tick de marché avec :
  - symbol    : ticker (ex: AAPL)
  - price     : cours simulé par marche aléatoire
  - volume    : volume d'échanges simulé
  - timestamp : ISO 8601 UTC
"""

import json
import logging
import random
import signal
import sys
import time
from datetime import datetime, timezone

from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC_STOCKS,
    PRODUCE_INTERVAL_SECONDS,
    STOCK_SYMBOLS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Prix de départ pour chaque symbole
BASE_PRICES: dict[str, float] = {
    "AAPL": 189.50,
    "GOOG": 175.20,
    "MSFT": 420.80,
    "AMZN": 195.60,
    "TSLA": 245.30,
    "NVDA": 875.40,
}


def create_producer(retries: int = 5, delay: int = 3) -> KafkaProducer:
    for attempt in range(1, retries + 1):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8"),
                acks="all",
                retries=3,
            )
            logger.info("Connecté à Kafka sur %s", KAFKA_BOOTSTRAP_SERVERS)
            return producer
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


def simulate_tick(symbol: str, last_price: float) -> dict:
    """Génère un tick de marché via marche aléatoire (±0.5%)."""
    change_pct = random.gauss(0, 0.005)
    new_price = round(last_price * (1 + change_pct), 2)
    volume = random.randint(100, 10_000)
    return {
        "symbol": symbol,
        "price": new_price,
        "volume": volume,
        "change_pct": round(change_pct * 100, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def on_send_success(metadata):
    logger.debug(
        "Envoyé → topic=%s partition=%d offset=%d",
        metadata.topic,
        metadata.partition,
        metadata.offset,
    )


def on_send_error(exc):
    logger.error("Erreur d'envoi Kafka : %s", exc)


def run():
    producer = create_producer()
    prices = dict(BASE_PRICES)

    # Gestion propre du SIGINT / SIGTERM
    running = True

    def shutdown(signum, frame):
        nonlocal running
        logger.info("Arrêt du producteur...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "Producteur démarré — topic: %s | symbols: %s",
        KAFKA_TOPIC_STOCKS,
        ", ".join(STOCK_SYMBOLS),
    )

    while running:
        for symbol in STOCK_SYMBOLS:
            tick = simulate_tick(symbol, prices[symbol])
            prices[symbol] = tick["price"]

            producer.send(
                KAFKA_TOPIC_STOCKS,
                key=symbol,
                value=tick,
            ).add_callback(on_send_success).add_errback(on_send_error)

            logger.info(
                "%s  prix=%.2f  volume=%d  Δ=%.4f%%",
                tick["symbol"],
                tick["price"],
                tick["volume"],
                tick["change_pct"],
            )

        producer.flush()
        time.sleep(PRODUCE_INTERVAL_SECONDS)

    producer.close()
    logger.info("Producteur fermé proprement.")


if __name__ == "__main__":
    run()
