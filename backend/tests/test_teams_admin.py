import pytest
from fastapi.testclient import TestClient

from app.models import Player
from app.services.errors import ServiceError
from app.services.teams import admin_update_team
from app.services.tournament import get_tournament
from app.store import Store
from tests.factories import make_player, make_team


def test_admin_creates_edits_and_deletes_teams(
    client: TestClient, store: Store, admin: dict
) -> None:
    a, b = make_player(store), make_player(store, center="South")  # admins may pair across centers
    created = client.post(
        "/api/admin/teams",
        headers=admin,
        json={"name": "Dinkers", "password": "pass", "player_ids": [a.id, b.id]},
    )
    assert created.status_code == 201
    team = created.json()
    assert team["status"] == "active" and team["checked_in"] is False
    c = make_player(store)
    patched = client.patch(
        f"/api/admin/teams/{team['id']}",
        headers=admin,
        json={
            "name": "Dinkers United",
            "checked_in": True,
            "player_ids": [a.id, c.id],
            "password": "newpass",
        },
    ).json()
    assert patched["name"] == "Dinkers United" and patched["checked_in"] is True
    assert {p["id"] for p in patched["players"]} == {a.id, c.id}
    assert store.get(Player, b.id).team_id is None
    login = client.post(
        "/api/auth/team-login", json={"team_name": "dinkers united", "password": "newpass"}
    )
    assert login.status_code == 200
    renamed = client.patch(
        f"/api/admin/teams/{team['id']}", headers=admin, json={"name": "DINKERS UNITED"}
    )
    assert renamed.json()["name"] == "DINKERS UNITED"
    assert len(client.get("/api/admin/teams", headers=admin).json()) == 1
    assert client.delete(f"/api/admin/teams/{team['id']}", headers=admin).status_code == 204
    assert store.get(Player, a.id).team_id is None
    assert client.delete(f"/api/admin/teams/{team['id']}", headers=admin).status_code == 404


def test_team_rules(client: TestClient, store: Store, admin: dict) -> None:
    existing = make_team(store, name="First")
    a, b = make_player(store), make_player(store)
    body = {"name": "Second", "password": "pass", "player_ids": [a.id, a.id]}
    assert client.post("/api/admin/teams", headers=admin, json=body).status_code == 400
    body["player_ids"] = [a.id, next(p.id for p in store.all(Player) if p.team_id == existing.id)]
    response = client.post("/api/admin/teams", headers=admin, json=body)
    assert response.status_code == 409 and "another team" in response.json()["detail"]
    body["player_ids"] = [a.id, b.id]
    body["status"] = "maybe"
    assert client.post("/api/admin/teams", headers=admin, json=body).status_code == 400
    assert (
        client.patch(
            f"/api/admin/teams/{existing.id}", headers=admin, json={"name": "second"}
        ).status_code
        == 200
    )
    other = make_team(store, name="Third")
    clash = client.patch(f"/api/admin/teams/{other.id}", headers=admin, json={"name": "SECOND"})
    assert clash.status_code == 409


def test_team_cap_waitlist_and_status_changes(
    client: TestClient, store: Store, admin: dict
) -> None:
    tournament = get_tournament(store)
    tournament.team_cap = 1
    store.save(tournament)
    make_team(store)
    a, b = make_player(store), make_player(store)
    waiting = client.post(
        "/api/admin/teams",
        headers=admin,
        json={"name": "Late", "password": "pass", "player_ids": [a.id, b.id]},
    ).json()
    assert waiting["status"] == "waitlist"
    full = client.patch(
        f"/api/admin/teams/{waiting['id']}", headers=admin, json={"status": "active"}
    )
    assert full.status_code == 409 and "full" in full.json()["detail"]
    same = client.patch(
        f"/api/admin/teams/{waiting['id']}", headers=admin, json={"status": "waitlist"}
    )
    assert same.status_code == 200


def test_numbered_teams_keep_their_status(store: Store) -> None:
    team = make_team(store)
    team.team_number = 1
    store.save(team)
    with pytest.raises(ServiceError, match="Clear the schedule"):
        admin_update_team(store, team.id, status="withdrawn")
    from app.services.teams import admin_delete_team

    with pytest.raises(ServiceError, match="Withdraw it instead"):
        admin_delete_team(store, team.id)


def test_admin_sees_and_cancels_pending_requests(
    client: TestClient, store: Store, admin: dict
) -> None:
    a, b = make_player(store), make_player(store)
    client.post(
        "/api/registration/requests",
        json={
            "from_player_id": a.id,
            "to_player_id": b.id,
            "team_name": "Pending",
            "password": "pass",
        },
    )
    pending = client.get("/api/admin/requests", headers=admin).json()
    assert [r["team_name"] for r in pending] == ["Pending"]
    cancelled = client.post(f"/api/admin/requests/{pending[0]['id']}/cancel", headers=admin)
    assert cancelled.json()["status"] == "cancelled"
    assert client.post("/api/admin/requests/999/cancel", headers=admin).status_code == 404
