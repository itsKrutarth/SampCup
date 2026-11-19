from collections.abc import Iterator
from datetime import UTC, datetime

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.main import app
from app.services import scoring
from app.services.auth import create_staff
from app.store import Store, create_table, get_store


@pytest.fixture(autouse=True)
def fake_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never touch a real AWS account from tests."""
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


AFTER_THE_DAY = datetime(2026, 12, 7, 6, tzinfo=UTC)


def set_clock(monkeypatch: pytest.MonkeyPatch, at: datetime) -> None:
    """Run the scoring clock from `at` (it keeps ticking, so game times stay real)."""
    shift = at - datetime.now(UTC)
    monkeypatch.setattr(scoring, "now", lambda: datetime.now(UTC) + shift)


@pytest.fixture(autouse=True)
def tournament_over(monkeypatch: pytest.MonkeyPatch) -> None:
    """Games start only at their time, so by default every test day's games are due."""
    set_clock(monkeypatch, AFTER_THE_DAY)


@pytest.fixture
def store() -> Iterator[Store]:
    with mock_aws():
        yield Store(create_table(boto3.resource("dynamodb", region_name="us-east-1"), "test"))


@pytest.fixture
def client(store: Store) -> Iterator[TestClient]:
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/staff-login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def admin(client: TestClient, store: Store) -> dict[str, str]:
    create_staff(store, "admin", "admin-password", "admin", "Admin")
    return login(client, "admin", "admin-password")


@pytest.fixture
def judge(client: TestClient, store: Store) -> dict[str, str]:
    create_staff(store, "judge1", "1234", "judge", "Judge One", court=1)
    return login(client, "judge1", "1234")
