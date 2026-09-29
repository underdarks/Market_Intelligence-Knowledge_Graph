import os

from dotenv import load_dotenv

load_dotenv()

# Neo4j
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
SEC_IDENTITY = os.environ["SEC_IDENTITY"]

# SEC, DART
SEC_RATE_LIMIT_SLEEP = 0.3  # SEC 초당 10회 제한 대응
DART_RATE_LIMIT_SLEEP = 0.3
DART_API_KEY = os.environ["DART_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Mongo
MONGO_USER = os.environ["MONGO_USER"]
MONGO_PASSWORD = os.environ["MONGO_PASSWORD"]
MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@localhost:27017"
MONGO_DB_NAME = "mikg"

# OpenSearch
OPENSEARCH_HOST = os.environ["OPENSEARCH_HOST"]
OPENSEARCH_PORT = os.environ["OPENSEARCH_PORT"]

LLM_GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "http://localhost:8081/v1")
LLM_GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY", "dummy")
