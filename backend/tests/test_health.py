from unittest.mock import MagicMock

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.main import app
from app.store import Store, get_store


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_database_answers(client: TestClient) -> None:
    assert client.get("/api/ready").json() == {"status": "ready"}


def test_ready_when_database_is_down(client: TestClient) -> None:
    table = MagicMock()
    table.get_item.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException"}}, "GetItem"
    )
    app.dependency_overrides[get_store] = lambda: Store(table)
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
