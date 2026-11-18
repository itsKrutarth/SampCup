"""A whole tournament day through the API: group play, standings, knockout, best-of-3 Final."""

import random

from fastapi.testclient import TestClient

from app.models import Match, Team
from app.services.scoring import refresh_bracket
from app.store import Store
from tests.factories import find, seeded


def play(
    client: TestClient, headers: dict, match: dict, rng: random.Random, winner: str | None = None
) -> dict:
    url = f"/api/judge/matches/{match['id']}"
    kind = rng.random()
    if winner is None and kind < 0.05:
        response = client.post(f"{url}/forfeit", headers=headers, json={"winner": rng.choice("ab")})
        return response.json()
    assert client.post(f"{url}/start", headers=headers).status_code == 200
    winner = winner or rng.choice("ab")
    loser_points = rng.randint(0, 10)
    if kind < 0.2:  # clock ran out, tied: sudden death
        body = {
            "score_a": 7,
            "score_b": 7,
            "end_reason": "clock_lead",
            "sudden_death_winner": winner,
        }
    elif kind < 0.35:  # clock ran out with a leader
        body = {"score_a": 9, "score_b": 6, "end_reason": "clock_lead"}
        if winner == "b":
            body["score_a"], body["score_b"] = 6, 9
    else:
        a, b = (11, loser_points) if winner == "a" else (loser_points, 11)
        body = {"score_a": a, "score_b": b, "end_reason": "reached_11"}
    response = client.post(f"{url}/finish", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_a_whole_tournament_day(client: TestClient, store: Store, admin: dict) -> None:
    rng = random.Random(40)
    assert client.get("/api/public/overview").json()["phase"] == "registration"
    seeded(store, 40)
    overview = client.get("/api/public/overview").json()
    assert (
        overview["phase"] == "scheduled"
        and overview["teams"] == 40
        and len(overview["upcoming"]) == 9
    )

    group_games = client.get("/api/public/schedule").json()
    pool = [m for m in group_games if m["phase"] == "group"]
    assert len(pool) == 160
    play(client, admin, pool[0], rng)
    assert client.get("/api/public/overview").json()["phase"] == "group_play"
    for match in pool[1:]:
        play(client, admin, match, rng)

    standings = client.get("/api/public/standings").json()["groups"]
    assert set(standings) == {"A", "B", "C", "D"}
    for table in standings.values():
        assert table["complete"] and table["played"] == table["total"] == 40
        assert [r["rank"] for r in table["rows"]] == list(range(1, 11))
        assert all(r["played"] == 8 for r in table["rows"])
    knockout = client.get("/api/public/bracket").json()["matches"]
    r16 = {m["code"]: m for m in knockout}
    assert r16["R16-1"]["team_a"]["id"] == standings["A"]["rows"][0]["team_id"]
    assert r16["R16-1"]["team_b"]["id"] == standings["B"]["rows"][3]["team_id"]
    assert (
        r16["R16-1"]["source_a"] == "Group A 1st" and r16["QF-1"]["source_a"] == "Winner of R16-1"
    )

    for code in (
        [f"R16-{i}" for i in range(1, 9)] + [f"QF-{i}" for i in range(1, 5)] + ["SF-1", "SF-2"]
    ):
        match = next(
            m for m in client.get("/api/public/bracket").json()["matches"] if m["code"] == code
        )
        play(client, admin, match, rng)
        if code == "R16-1":
            assert client.get("/api/public/overview").json()["phase"] == "knockout"

    final = {m["code"]: m for m in client.get("/api/public/bracket").json()["matches"]}
    assert final["F-1"]["team_a"] and final["F-1"]["team_b"]
    play(client, admin, final["F-1"], rng, winner="a")
    play(client, admin, final["F-2"], rng, winner="a")
    bracket = client.get("/api/public/bracket").json()
    f3 = next(m for m in bracket["matches"] if m["code"] == "F-3")
    assert f3["status"] == "cancelled"
    assert bracket["champion"]["id"] == final["F-1"]["team_a"]["id"]
    overview = client.get("/api/public/overview").json()
    assert (
        overview["phase"] == "finished" and overview["champion"]["id"] == bracket["champion"]["id"]
    )

    # A late correction to a group game cannot silently change finished knockout games.
    first = pool[0]
    current = next(m for m in client.get("/api/public/schedule").json() if m["id"] == first["id"])
    flipped = {
        "score_a": current["score_b"],
        "score_b": current["score_a"],
        "end_reason": current["end_reason"],
        "reason": "scores were swapped",
    }
    corrected = client.post(
        f"/api/admin/matches/{first['id']}/correct", headers=admin, json=flipped
    ).json()
    assert corrected["winner_id"] != current["winner_id"]

    csv_text = client.get("/api/admin/export/results.csv", headers=admin).text
    assert csv_text.splitlines()[0].startswith("code,round") and len(csv_text.splitlines()) == 178


def test_final_goes_to_game_three_after_a_split(
    client: TestClient, store: Store, admin: dict
) -> None:
    seeded(store, 32)
    sf_winners = store.all(Team)[:2]
    for code, winner in (("SF-1", sf_winners[0]), ("SF-2", sf_winners[1])):
        match = find(store, Match, code=code)
        match.status, match.winner_id = "completed", winner.id
        store.save(match)
    refresh_bracket(store)
    rng = random.Random(1)
    games = {m["code"]: m for m in client.get("/api/public/bracket").json()["matches"]}
    play(client, admin, games["F-1"], rng, winner="a")
    play(client, admin, games["F-2"], rng, winner="b")
    f3 = next(m for m in client.get("/api/public/bracket").json()["matches"] if m["code"] == "F-3")
    assert f3["status"] == "scheduled"
    play(client, admin, f3, rng, winner="b")
    assert client.get("/api/public/bracket").json()["champion"]["id"] == sf_winners[1].id


def test_public_and_team_pages(client: TestClient, store: Store) -> None:
    seeded(store, 32)
    teams = client.get("/api/public/teams").json()
    assert len(teams) == 32 and teams[0]["number"] == 1
    page = client.get("/api/public/teams/1").json()
    assert len(page["matches"]) >= 8 and page["lunch_start"] and page["next_match"]
    assert page["standing"]["rank"] >= 1
    assert client.get("/api/public/teams/99").status_code == 404
    group_a = client.get("/api/public/schedule?group=a").json()
    assert group_a and {m["group"] for m in group_a} == {"A"}
    court_9 = client.get("/api/public/schedule?court=9").json()
    assert {m["court"] for m in court_9} == {9}
    mine = client.get("/api/public/schedule?team=1").json()
    assert len(mine) == len(page["matches"])
    login = client.post(
        "/api/auth/team-login", json={"team_name": page["name"], "password": "demo"}
    ).json()
    me = client.get("/api/team/me", headers={"Authorization": f"Bearer {login['token']}"}).json()
    assert me["number"] == 1 and len(me["players"]) == 2


def test_announcement_banner(client: TestClient, admin: dict) -> None:
    created = client.post(
        "/api/admin/announcements", headers=admin, json={"title": "Lunch is ready"}
    ).json()
    assert [a["title"] for a in client.get("/api/public/overview").json()["announcements"]] == [
        "Lunch is ready"
    ]
    client.patch(
        f"/api/admin/announcements/{created['id']}",
        headers=admin,
        json={"active": False, "body": "x"},
    )
    assert client.get("/api/public/overview").json()["announcements"] == []
    assert len(client.get("/api/admin/announcements", headers=admin).json()) == 1
    assert (
        client.delete(f"/api/admin/announcements/{created['id']}", headers=admin).status_code == 204
    )
    assert (
        client.delete(f"/api/admin/announcements/{created['id']}", headers=admin).status_code == 404
    )


def test_tournament_settings(client: TestClient, admin: dict) -> None:
    defaults = client.get("/api/public/overview").json()["tournament"]
    assert defaults["venue_name"] == "Rt. 12 Pickle" and defaults["age_group"] == "22-35"
    assert defaults["contacts"] == ""
    summary = client.patch(
        "/api/admin/tournament",
        headers=admin,
        json={
            "name": "SAMP Cup Test",
            "registration_open": False,
            "team_cap": 40,
            "contacts": "Organizer: 555-0100",
            "venue_name": "Test Courts",
        },
    ).json()
    assert (
        summary["tournament"]["name"] == "SAMP Cup Test" and summary["tournament"]["team_cap"] == 40
    )
    public = client.get("/api/public/overview").json()["tournament"]
    assert public["contacts"] == "Organizer: 555-0100" and public["venue_name"] == "Test Courts"
    assert client.get("/api/registration/status").json()["open"] is False
    assert (
        client.patch("/api/admin/tournament", headers=admin, json={"team_cap": 50}).status_code
        == 422
    )


def test_correcting_the_final_reopens_game_three(
    client: TestClient, store: Store, admin: dict
) -> None:
    seeded(store, 32)
    a, b = store.all(Team)[:2]
    for code, winner in (("SF-1", a), ("SF-2", b)):
        match = find(store, Match, code=code)
        match.status, match.winner_id = "completed", winner.id
        store.save(match)
    refresh_bracket(store)
    rng = random.Random(2)
    games = {m["code"]: m for m in client.get("/api/public/bracket").json()["matches"]}
    play(client, admin, games["F-1"], rng, winner="a")
    play(client, admin, games["F-2"], rng, winner="a")
    f3 = games["F-3"]
    refused = client.post(
        f"/api/judge/matches/{f3['id']}/finish",
        headers=admin,
        json={"score_a": 11, "score_b": 2, "end_reason": "reached_11"},
    )
    assert refused.status_code == 409 and "cancelled" in refused.json()["detail"]
    fix = {
        "score_a": 4,
        "score_b": 11,
        "end_reason": "reached_11",
        "reason": "wrong winner entered",
    }
    client.post(f"/api/admin/matches/{games['F-2']['id']}/correct", headers=admin, json=fix)
    reopened = next(
        m for m in client.get("/api/public/bracket").json()["matches"] if m["code"] == "F-3"
    )
    assert reopened["status"] == "scheduled"
    assert client.get("/api/public/bracket").json()["champion"] is None


def test_excel_numbers_become_plain_ids() -> None:
    from app.services.players import _text

    assert _text(123456.0) == "123456" and _text(None) == "" and _text("  a  b ") == "a b"
