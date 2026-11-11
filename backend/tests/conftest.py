import os
import pathlib

os.environ["DATABASE_URL"] = "sqlite:///./test_dealradar.db"
# Tests must never touch real services, even if a developer's .env file has real keys.
for _k in ("GROQ_API_KEY", "SMTP_HOST", "MAIL_FROM", "ADMIN_TOKEN"):
    os.environ[_k] = ""
os.environ["LIVE_SCRAPING"] = "false"
os.environ["RATE_LIMIT_PER_HOUR"] = "1000"
os.environ["WATCH_LIMIT_PER_HOUR"] = "1000"
os.environ["DAILY_DELAY_SECONDS"] = "0"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    pathlib.Path("test_dealradar.db").unlink(missing_ok=True)
