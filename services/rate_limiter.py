
import os
from pathlib import Path

from dotenv import load_dotenv
from slowapi import Limiter
from slowapi.util import get_remote_address


# Load the project's .env for local development.
# Existing environment variables are not overwritten.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Use Redis when configured; otherwise keep local development working.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
RATE_LIMIT_STORAGE = REDIS_URL or "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=RATE_LIMIT_STORAGE,
    headers_enabled=True,
)
