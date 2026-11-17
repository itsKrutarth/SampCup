from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import PartnerRequest, Team
from app.services.tournament import get_tournament
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


def test_players_pick_a_partner_and_the_partner_accepts(client: TestClient, db: Session) -> None:
    a, b, c = make_player(db), make_player(db), make_player(db)
    make_player(db, center="South")
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
    assert db.get(PartnerRequest, third.json()["id"]).status == "cancelled"
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


def test_request_rules(client: TestClient, db: Session) -> None:
    a, b, c, d = (make_player(db) for _ in range(4))
    south = make_player(db, center="South")
    teamed = make_team(db, name="Taken Name").players[0]
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


def test_answers_must_come_from_the_right_player(client: TestClient, db: Session) -> None:
    a, b = make_player(db), make_player(db)
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
    client: TestClient, db: Session
) -> None:
    a, b, c = make_player(db), make_player(db), make_player(db)
    first = ask(client, a.id, b.id).json()["id"]
    team = make_team(db)
    db.get(type(c), c.id).team_id = team.id
    db.get(type(a), a.id).team_id = team.id
    db.commit()
    assert answer(client, first, "accept", b.id).status_code == 409


def test_teams_past_the_cap_go_on_the_waitlist(client: TestClient, db: Session) -> None:
    get_tournament(db).team_cap = 1
    db.commit()
    make_team(db)
    a, b = make_player(db), make_player(db)
    request_id = ask(client, a.id, b.id).json()["id"]
    assert answer(client, request_id, "accept", b.id).json()["status"] == "waitlist"


def test_closed_registration_refuses_new_requests_and_accepts(
    client: TestClient, db: Session
) -> None:
    a, b, c, d = (make_player(db) for _ in range(4))
    request_id = ask(client, a.id, b.id).json()["id"]
    get_tournament(db).registration_open = False
    db.commit()
    assert ask(client, c.id, d.id, name="Late").status_code == 409
    assert answer(client, request_id, "accept", b.id).status_code == 409
    assert db.query(Team).count() == 0


def test_request_spam_is_rate_limited(client: TestClient, db: Session) -> None:
    a = make_player(db)
    codes = {ask(client, a.id, a.id).status_code for _ in range(31)}
    assert codes == {400, 429}
