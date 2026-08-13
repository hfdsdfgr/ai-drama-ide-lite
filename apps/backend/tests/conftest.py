"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.secret_store import MemorySecretStore


@pytest.fixture()
def client(tmp_path):
    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    store = MemorySecretStore()
    with TestClient(create_app(settings=settings, secret_store=store)) as test_client:
        yield test_client
