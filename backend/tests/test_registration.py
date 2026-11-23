import pytest
from fastapi.testclient import TestClient

from app.api import registration
from app.models import PartnerRequest, Player, Team
from app.services.tournament import get_tournament
from app.store import Store
from tests.factories import email_of, make_player, make_team, player_headers


def claim(
    client: TestClient, player: Player, username: str = "aarav_p", password: str = "secret1", **kw
):
    body = {
        "first_name": player.first_name,
        "last_name": player.last_name,
        "email": email_of(player.first_name),
        "username": username,
        "password": password,
        **kw,
    }
    return client.post("/api/players/claim", json=body)


def invite(client: TestClient, headers: dict, to: int, name: str = "Smash Bros"):
    return client.post(
        "/api/registration/requests", headers=headers, json={"to_player_id": to, "team_name": name}
    )


def answer(client: TestClient, headers: dict, request_id: int, action: str):
    return client.post(f"/api/registration/requests/{request_id}/{action}", headers=headers)


def test_players_claim_their_account_once(client: TestClient, store: Store) -> None:
    assert client.get("/api/registration/status").json()["loaded"] is False
    a = make_player(store, first="Aarav", center="")  # the center comes from the registration
    assert client.get("/api/registration/status").json()["loaded"] is True
    body = {
        "first_name": f"  {a.first_name.upper()} ",
        "last_name": "tester",
        "email": f" {email_of(a.first_name).upper()} ",
        "username": "Aarav_P",
        "password": "secret1",
    }
    made = client.post("/api/players/claim", json=body)
    assert made.status_code == 201 and made.json()["player"]["first_name"] == a.first_name
    headers = {"Authorization": f"Bearer {made.json()['token']}"}
    me = client.get("/api/player/me", headers=headers).json()
    assert me["team"] is None and me["incoming"] == [] and me["outgoing"] is None
    assert client.get("/api/auth/me", headers=headers).json()["player"]["username"] == "aarav_p"
    again = claim(client, a, username="someone")
    assert again.status_code == 409 and "already has an account" in again.json()["detail"]
    login = client.post(
        "/api/auth/player-login", json={"username": "AARAV_P", "password": "secret1"}
    )
    assert login.status_code == 200
    wrong = client.post(
        "/api/auth/player-login", json={"username": "aarav_p", "password": "nope00"}
    )
    assert wrong.status_code == 401


def test_claim_rules(client: TestClient, store: Store) -> None:
    a, b = make_player(store), make_player(store)
    twin_a = make_player(store, first="Twin")
    no_email = make_player(store, email_key="")  # an old registration without an email
    store.save(
        Player(
            id=store.next_id(Player),
            mis_id="X1",
            first_name=twin_a.first_name,
            last_name="Tester",
            center="South",
            email_key=twin_a.email_key,
        )
    )
    assert claim(client, a, username="taken").status_code == 201
    cases = [
        (claim(client, b, username="taken"), 409, "taken"),
        (claim(client, b, username="no"), 400, "3-30"),
        (claim(client, b, password="short"), 400, "6-72"),
        (claim(client, b, first_name="Nobody"), 404, "couldn't find"),
        (claim(client, b, email="someone.else@example.com"), 404, "couldn't find"),
        (claim(client, b, email=email_of(a.first_name)), 404, "couldn't find"),  # a's email
        (claim(client, b, email=""), 404, "couldn't find"),
        (claim(client, no_email, email=""), 404, "couldn't find"),
        (claim(client, twin_a, username="twin"), 409, "More than one"),
    ]
    for response, code, text in cases:
        assert response.status_code == code and text in response.json()["detail"], response.text


def test_claims_are_rate_limited(
    client: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registration, "REGISTRATION_PER_IP", (3, 600))
    a = make_player(store)
    codes = [claim(client, a, first_name="Wrong").status_code for _ in range(4)]
    assert codes == [404, 404, 404, 429]


def test_invite_then_partner_claims_and_accepts(client: TestClient, store: Store) -> None:
    a, b, c = make_player(store), make_player(store), make_player(store)
    me = player_headers(client, store, a)
    names = {
        p["id"]: p["state"] for p in client.get("/api/registration/players", headers=me).json()
    }
    assert names == {b.id: "free", c.id: "free"}
    sent = invite(client, me, b.id)
    assert sent.status_code == 201 and sent.json()["to"]["id"] == b.id
    third = invite(client, player_headers(client, store, c), b.id, name="Other Team")
    assert client.get("/api/player/me", headers=me).json()["outgoing"]["team_name"] == "Smash Bros"
    made = claim(client, b, username="partner")  # the partner signs up after being invited
    partner = {"Authorization": f"Bearer {made.json()['token']}"}
    waiting = client.get("/api/player/me", headers=partner).json()
    assert [r["team_name"] for r in waiting["incoming"]] == ["Smash Bros", "Other Team"]
    team = answer(client, partner, sent.json()["id"], "accept").json()
    assert team["name"] == "Smash Bros" and {p["id"] for p in team["players"]} == {a.id, b.id}
    assert store.get(PartnerRequest, third.json()["id"]).status == "cancelled"
    page = client.get("/api/player/me", headers=me).json()["team"]
    assert page["name"] == "Smash Bros" and len(page["players"]) == 2
    public = client.get("/api/public/teams").json()
    assert public[0]["players"][0]["name"] in (a.full_name, b.full_name)


def test_request_rules(client: TestClient, store: Store) -> None:
    a, b, c, d = (make_player(store) for _ in range(4))
    south = make_player(store, center="South")
    taken = make_team(store, name="Taken Name")
    teamed = next(p for p in store.all(Player) if p.team_id == taken.id)
    me = player_headers(client, store, a)
    checks = [
        (invite(client, me, a.id), 400, "someone else"),
        (invite(client, me, south.id), 400, "from your center"),
        (invite(client, me, teamed.id), 409, "already on a team"),
        (invite(client, me, 99999), 404, "Player not found"),
        (invite(client, me, b.id, name="x"), 400, "2-40 characters"),
        (invite(client, me, b.id, name="taken  name"), 409, "taken"),
    ]
    # a player without a center (an admin sets it) can't invite anyone, nor be listed
    blank, other_blank = make_player(store, center=""), make_player(store, center="")
    alone = player_headers(client, store, blank)
    checks += [
        (invite(client, alone, other_blank.id), 400, "center isn't set yet"),
        (invite(client, me, blank.id), 400, "from your center"),
    ]
    for response, code, text in checks:
        assert response.status_code == code and text in response.json()["detail"], response.text
    assert client.get("/api/registration/players", headers=alone).json() == []
    listed = client.get("/api/registration/players", headers=me).json()
    assert blank.id not in {p["id"] for p in listed}
    assert invite(client, me, b.id, name="Fresh").status_code == 201
    second = invite(client, me, c.id, name="Second")
    assert second.status_code == 409 and "already have a request" in second.json()["detail"]
    clash = invite(client, player_headers(client, store, c), d.id, name="FRESH")
    assert clash.status_code == 409 and "waiting on another request" in clash.json()["detail"]


def test_answers_must_come_from_the_right_player(client: TestClient, store: Store) -> None:
    a, b = make_player(store), make_player(store)
    sender, partner = player_headers(client, store, a), player_headers(client, store, b)
    request_id = invite(client, sender, b.id).json()["id"]
    assert answer(client, sender, request_id, "accept").status_code == 400
    assert answer(client, partner, request_id, "cancel").status_code == 400
    assert answer(client, partner, 9999, "accept").status_code == 404
    assert answer(client, partner, request_id, "decline").json()["status"] == "declined"
    again = answer(client, partner, request_id, "accept")
    assert again.status_code == 409 and "already declined" in again.json()["detail"]
    request_id = invite(client, sender, b.id).json()["id"]
    assert answer(client, sender, request_id, "cancel").json()["status"] == "cancelled"


def test_accepting_after_joining_another_team_fails(client: TestClient, store: Store) -> None:
    a, b = make_player(store), make_player(store)
    request_id = invite(client, player_headers(client, store, a), b.id).json()["id"]
    partner = player_headers(client, store, b)
    team = make_team(store)
    a.team_id = team.id
    store.save(a)
    assert answer(client, partner, request_id, "accept").status_code == 409


def test_teams_past_the_cap_wait_and_closed_registration_refuses(
    client: TestClient, store: Store
) -> None:
    tournament = get_tournament(store)
    tournament.team_cap = 1
    store.save(tournament)
    make_team(store)
    a, b, c, d = (make_player(store) for _ in range(4))
    request_id = invite(client, player_headers(client, store, a), b.id).json()["id"]
    assert (
        answer(client, player_headers(client, store, b), request_id, "accept").json()["status"]
        == "waitlist"
    )
    pending = invite(client, player_headers(client, store, c), d.id, name="Late").json()["id"]
    tournament.registration_open = False
    store.save(tournament)
    assert invite(client, player_headers(client, store, c), a.id, name="Later").status_code == 409
    assert answer(client, player_headers(client, store, d), pending, "accept").status_code == 409
    status = client.get("/api/registration/status").json()
    assert status == {"open": False, "team_cap": 1, "loaded": True}
    assert len(store.all(Team)) == 2


def test_player_pages_need_a_player_login(client: TestClient, store: Store, admin: dict) -> None:
    assert client.get("/api/registration/players").status_code == 401
    assert client.get("/api/player/me", headers=admin).status_code == 403


def test_admin_sets_and_releases_player_logins(
    client: TestClient, store: Store, admin: dict
) -> None:
    twin = make_player(store, first="Twin")
    url = f"/api/admin/players/{twin.id}/login"
    missing = client.put(url, headers=admin, json={"password": "temp123"})
    assert missing.status_code == 400 and "username" in missing.json()["detail"]
    no_password = client.put(url, headers=admin, json={"username": "twin1"})
    assert no_password.status_code == 400 and "temporary password" in no_password.json()["detail"]
    made = client.put(url, headers=admin, json={"username": "Twin1", "password": "temp123"}).json()
    assert made["username"] == "twin1" and made["must_change_password"] is True
    login = client.post(
        "/api/auth/player-login", json={"username": "twin1", "password": "temp123"}
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}
    blocked = client.get("/api/player/me", headers=headers)
    assert blocked.status_code == 403 and "own password" in blocked.json()["detail"]
    change = "/api/auth/change-password"
    wrong = client.post(
        change, headers=headers, json={"current_password": "x", "new_password": "mine123"}
    )
    assert wrong.status_code == 400
    same = client.post(
        change, headers=headers, json={"current_password": "temp123", "new_password": "temp123"}
    )
    assert same.status_code == 400
    done = client.post(
        change, headers=headers, json={"current_password": "temp123", "new_password": "mine123"}
    )
    assert done.json()["player"]["must_change_password"] is False
    assert client.get("/api/player/me", headers=headers).status_code == 200
    other = make_player(store)
    client.put(
        f"/api/admin/players/{other.id}/login",
        headers=admin,
        json={"username": "other", "password": "temp123"},
    )
    clash = client.put(url, headers=admin, json={"username": "other"})
    assert clash.status_code == 409
    renamed = client.put(url, headers=admin, json={"username": "twin-new"}).json()
    assert renamed["username"] == "twin-new"
    released = client.delete(url, headers=admin).json()
    assert released["username"] is None
    assert client.get("/api/player/me", headers=headers).status_code == 401  # logged out
    assert client.delete(url, headers=admin).json()["username"] is None  # already free
    assert client.put("/api/admin/players/9999/login", headers=admin, json={}).status_code == 404
    reclaim = claim(client, twin, username="twin-again")
    assert reclaim.status_code == 201
