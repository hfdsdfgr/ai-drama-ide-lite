"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client
