import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.api.deps import login_limiter, registration_limiter
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.auth import create_staff

# CI points this at Postgres; locally the tests use in-memory SQLite.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def engine() -> Iterator[Engine]:
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
    else:
        engine = create_engine(
            "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    login_limiter.reset()
    registration_limiter.reset()
    yield TestClient(app)
    app.dependency_overrides.clear()


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/staff-login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


@pytest.fixture
def admin(client: TestClient, db: Session) -> dict[str, str]:
    create_staff(db, "admin", "admin-password", "admin", "Admin")
    return login(client, "admin", "admin-password")


@pytest.fixture
def judge(client: TestClient, db: Session) -> dict[str, str]:
    create_staff(db, "judge1", "1234", "judge", "Judge One", court=1)
    return login(client, "judge1", "1234")
