import pytest
from fastapi.testclient import TestClient

from app.api import registration
from app.models import PartnerRequest, Player, Team
from app.services.tournament import get_tournament
from app.store import Store
from tests.factories import make_player, make_team


def ask(client: TestClient, a: int, b: int, name: str = "Smash Bros", password: str = "pass1"):
    return client.post(
        "/api/registration/requests",
        json={"from_player_id": a, "to_player_id": b, "team_name": name, "password": password},
    )


def answer(client: TestClient, request_id: int, action: str, player_id: int):
    return client.post(
        f"/api/registration/requests/{request_id}/{action}", json={"player_id": player_id}
    )


def test_players_pick_a_partner_and_the_partner_accepts(client: TestClient, store: Store) -> None:
    a, b, c = make_player(store), make_player(store), make_player(store)
    make_player(store, center="South")
    assert client.get("/api/registration/centers").json() == [
        {"center": "North", "players": 3, "on_teams": 0},
        {"center": "South", "players": 1, "on_teams": 0},
    ]
    sent = ask(client, a.id, b.id)
    assert sent.status_code == 201 and sent.json()["to"]["id"] == b.id
    third = ask(client, c.id, b.id, name="Other Team")  # b now has two offers
    states = {
        p["id"]: p["state"] for p in client.get("/api/registration/players?center=North").json()
    }
    assert states == {a.id: "pending", b.id: "pending", c.id: "pending"}
    status = client.get(f"/api/registration/players/{b.id}").json()
    assert [r["team_name"] for r in status["incoming"]] == ["Smash Bros", "Other Team"]

    team = answer(client, sent.json()["id"], "accept", b.id).json()
    assert team["name"] == "Smash Bros" and team["status"] == "active"
    assert {p["id"] for p in team["players"]} == {a.id, b.id}
    assert store.get(PartnerRequest, third.json()["id"]).status == "cancelled"
    status = client.get(f"/api/registration/players/{a.id}").json()
    assert status["team"]["name"] == "Smash Bros" and status["outgoing"] is None
    login = client.post(
        "/api/auth/team-login", json={"team_name": "smash  bros", "password": "pass1"}
    )
    assert login.status_code == 200
    assert client.get("/api/registration/status").json() == {
        "open": True,
        "team_cap": 42,
        "teams": 1,
    }


def test_request_rules(client: TestClient, store: Store) -> None:
    a, b, c, d = (make_player(store) for _ in range(4))
    south = make_player(store, center="South")
    taken = make_team(store, name="Taken Name")
    teamed = next(p for p in store.all(Player) if p.team_id == taken.id)
    checks = [
        (ask(client, a.id, a.id), 400, "someone else"),
        (ask(client, a.id, south.id), 400, "from your center"),
        (ask(client, a.id, teamed.id), 409, "already on a team"),
        (ask(client, a.id, 99999), 404, "Player not found"),
        (ask(client, a.id, b.id, name="x"), 400, "2-40 characters"),
        (ask(client, a.id, b.id, password="abc"), 400, "4-72 characters"),
        (ask(client, a.id, b.id, name="taken  name"), 409, "taken"),
    ]
    for response, code, text in checks:
        assert response.status_code == code and text in response.json()["detail"], response.text
    assert ask(client, a.id, b.id, name="Fresh").status_code == 201
    response = ask(client, a.id, c.id, name="Second")
    assert response.status_code == 409 and "already have a request" in response.json()["detail"]
    response = ask(client, c.id, d.id, name="FRESH")
    assert response.status_code == 409 and "waiting on another request" in response.json()["detail"]


def test_answers_must_come_from_the_right_player(client: TestClient, store: Store) -> None:
    a, b = make_player(store), make_player(store)
    request_id = ask(client, a.id, b.id).json()["id"]
    assert answer(client, request_id, "accept", a.id).status_code == 400
    assert answer(client, request_id, "cancel", b.id).status_code == 400
    assert answer(client, 9999, "accept", b.id).status_code == 404
    assert answer(client, request_id, "decline", b.id).json()["status"] == "declined"
    response = answer(client, request_id, "accept", b.id)
    assert response.status_code == 409 and "already declined" in response.json()["detail"]
    request_id = ask(client, a.id, b.id).json()["id"]
    assert answer(client, request_id, "cancel", a.id).json()["status"] == "cancelled"


def test_accepting_after_one_player_joined_another_team_fails(
    client: TestClient, store: Store
) -> None:
    a, b, c = make_player(store), make_player(store), make_player(store)
    first = ask(client, a.id, b.id).json()["id"]
    team = make_team(store)
    for player in (a, c):
        player.team_id = team.id
        store.save(player)
    assert answer(client, first, "accept", b.id).status_code == 409


def test_teams_past_the_cap_go_on_the_waitlist(client: TestClient, store: Store) -> None:
    tournament = get_tournament(store)
    tournament.team_cap = 1
    store.save(tournament)
    make_team(store)
    a, b = make_player(store), make_player(store)
    request_id = ask(client, a.id, b.id).json()["id"]
    assert answer(client, request_id, "accept", b.id).json()["status"] == "waitlist"


def test_closed_registration_refuses_new_requests_and_accepts(
    client: TestClient, store: Store
) -> None:
    a, b, c, d = (make_player(store) for _ in range(4))
    request_id = ask(client, a.id, b.id).json()["id"]
    tournament = get_tournament(store)
    tournament.registration_open = False
    store.save(tournament)
    assert ask(client, c.id, d.id, name="Late").status_code == 409
    assert answer(client, request_id, "accept", b.id).status_code == 409
    assert store.all(Team) == []


def test_request_spam_is_rate_limited(
    client: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registration, "REGISTRATION_PER_IP", (30, 600))
    a = make_player(store)
    codes = {ask(client, a.id, a.id).status_code for _ in range(31)}
    assert codes == {400, 429}
