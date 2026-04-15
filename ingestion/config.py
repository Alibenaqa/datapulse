import os
from dotenv import load_dotenv

load_dotenv()

# Kafka
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_STOCKS = os.getenv("KAFKA_TOPIC_STOCKS", "stock-prices")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "datapulse-consumers")

# Producer
PRODUCE_INTERVAL_SECONDS = float(os.getenv("PRODUCE_INTERVAL_SECONDS", "1.0"))

# Symbols à simuler
STOCK_SYMBOLS = ["AAPL", "GOOG", "MSFT", "AMZN", "TSLA", "NVDA"]

# Persistence
DATA_RAW_PATH = os.getenv("DATA_RAW_PATH", "data/raw")
