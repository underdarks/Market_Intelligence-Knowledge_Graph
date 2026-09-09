import os

from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ["NEO4J_USER"]
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
SEC_IDENTITY = os.environ["SEC_IDENTITY"]

SEC_RATE_LIMIT_SLEEP = 0.3  # SEC 초당 10회 제한 대응
DART_RATE_LIMIT_SLEEP = 0.3
DART_API_KEY = os.environ["DART_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
