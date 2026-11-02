from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_answers(client: TestClient) -> None:
    def in_memory_db() -> Iterator[Session]:
        with Session(create_engine("sqlite://")) as session:
            yield session

    app.dependency_overrides[get_db] = in_memory_db
    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_when_database_is_down(client: TestClient) -> None:
    broken = MagicMock(spec=Session)
    broken.execute.side_effect = OperationalError("SELECT 1", {}, Exception("connection refused"))
    app.dependency_overrides[get_db] = lambda: broken
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
