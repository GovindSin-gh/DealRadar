import os
import pathlib

os.environ["DATABASE_URL"] = "sqlite:///./test_dealradar.db"
os.environ["GROQ_API_KEY"] = ""
os.environ["RATE_LIMIT_PER_HOUR"] = "1000"
os.environ["WATCH_LIMIT_PER_HOUR"] = "1000"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
    pathlib.Path("test_dealradar.db").unlink(missing_ok=True)
