from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models import Session
from app.services.auth import create_staff, update_staff
from app.services.errors import ServiceError
from app.store import Store
from tests.conftest import login
from tests.factories import make_team


def team_login(client: TestClient, name: str, password: str = "pass"):
    return client.post("/api/auth/team-login", json={"team_name": name, "password": password})


def test_team_login_and_my_team_page(client: TestClient, store: Store) -> None:
    team = make_team(store, name="Net Ninjas")
    response = team_login(client, "NET NINJAS")
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["kind"] == "team" and me["team"]["name"] == "Net Ninjas"
    page = client.get("/api/team/me", headers=headers).json()
    assert page["name"] == "Net Ninjas" and len(page["players"]) == 2 and page["matches"] == []
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert team.id


def test_wrong_team_password_unknown_team_and_withdrawn_team(
    client: TestClient, store: Store
) -> None:
    make_team(store, name="Gone", status="withdrawn")
    make_team(store, name="Here")
    assert team_login(client, "Here", "nope").status_code == 401
    assert team_login(client, "Nobody").status_code == 401
    response = team_login(client, "Gone")
    assert response.status_code == 401 and "withdrawn" in response.json()["detail"]


def test_staff_login_roles_and_guards(
    client: TestClient, store: Store, admin: dict, judge: dict
) -> None:
    assert client.get("/api/auth/me", headers=judge).json()["user"]["role"] == "judge"
    assert client.get("/api/admin/summary", headers=judge).status_code == 403
    assert client.get("/api/admin/summary", headers=admin).status_code == 200
    assert client.get("/api/team/me", headers=admin).status_code == 403
    team_token = team_login(client, make_team(store).name).json()["token"]
    team_headers = {"Authorization": f"Bearer {team_token}"}
    assert client.get("/api/judge/matches", headers=team_headers).status_code == 403
    assert client.get("/api/judge/matches", headers={"Authorization": "Basic x"}).status_code == 401
    bad = client.post("/api/auth/staff-login", json={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401


def test_expired_sessions_are_refused(client: TestClient, store: Store, admin: dict) -> None:
    for session in store.all(Session):
        session.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        store.save(session)
    assert client.get("/api/auth/me", headers=admin).status_code == 401


def test_logins_are_rate_limited(client: TestClient) -> None:
    codes = [team_login(client, "x").status_code for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


def test_staff_accounts(client: TestClient, store: Store, admin: dict) -> None:
    created = client.post(
        "/api/admin/staff",
        headers=admin,
        json={"username": "Court-3", "password": "4321", "role": "judge", "court": 3},
    ).json()
    assert created["username"] == "court-3" and created["display_name"] == "court-3"
    judge_headers = login(client, "court-3", "4321")
    moved = client.patch(
        f"/api/admin/staff/{created['id']}", headers=admin, json={"court": 5}
    ).json()
    assert moved["court"] == 5
    cleared = client.patch(
        f"/api/admin/staff/{created['id']}",
        headers=admin,
        json={"clear_court": True, "display_name": "Floater"},
    ).json()
    assert cleared["court"] is None and cleared["display_name"] == "Floater"
    off = client.patch(f"/api/admin/staff/{created['id']}", headers=admin, json={"active": False})
    assert off.json()["active"] is False
    assert client.get("/api/auth/me", headers=judge_headers).status_code == 401  # sessions ended
    me = client.get("/api/auth/me", headers=admin).json()["user"]["id"]
    assert (
        client.patch(f"/api/admin/staff/{me}", headers=admin, json={"active": False}).status_code
        == 400
    )
    assert len(client.get("/api/admin/staff", headers=admin).json()) == 2
    assert client.patch("/api/admin/staff/999", headers=admin, json={}).status_code == 404


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"username": "bad name!", "password": "12345678", "role": "admin"}, "Username"),
        ({"username": "x", "password": "12345678", "role": "boss"}, "Role"),
        ({"username": "x", "password": "1234", "role": "judge", "court": 10}, "Court"),
        ({"username": "x", "password": "short", "role": "admin"}, "8 characters"),
        ({"username": "x", "password": "123", "role": "judge"}, "at least 4"),
        ({"username": "admin", "password": "12345678", "role": "admin"}, "taken"),
    ],
)
def test_staff_rules(store: Store, kwargs: dict, message: str) -> None:
    create_staff(store, "admin", "admin-password", "admin")
    with pytest.raises(ServiceError, match=message):
        create_staff(store, **kwargs)


def test_staff_password_change(store: Store) -> None:
    user = create_staff(store, "judge9", "1234", "judge")
    with pytest.raises(ServiceError, match="too short"):
        update_staff(store, user.id, password="1")
    assert update_staff(store, user.id, password="5678").password_hash != ""
