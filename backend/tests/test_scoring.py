import datetime as dt

import pytest
from fastapi.testclient import TestClient

from app.models import Match, ScoreAudit
from app.services import scoring
from app.services.auth import create_staff
from app.store import ConflictError, Store
from tests.conftest import login
from tests.factories import find, seeded


@pytest.fixture
def game(store: Store) -> Match:
    seeded(store, 32)
    return min((m for m in store.all(Match) if m.court == 1), key=lambda m: m.scheduled_at)


def act(client: TestClient, headers: dict, match: Match, action: str, **body: object):
    return client.post(
        f"/api/judge/matches/{match.id}/{action}", headers=headers, json=body or None
    )


def test_judge_plays_a_game_to_11(
    client: TestClient, store: Store, judge: dict, game: Match
) -> None:
    board = client.get("/api/judge/matches", headers=judge).json()
    assert board["court"] == 1 and board["current"]["id"] == game.id
    assert act(client, judge, game, "score", score_a=1, score_b=0).status_code == 409
    started = act(client, judge, game, "start").json()
    assert started["status"] == "in_progress" and started["score_a"] == 0
    assert act(client, judge, game, "start").json()["status"] == "in_progress"  # retry is harmless
    assert act(client, judge, game, "score", score_a=5, score_b=3).json()["score_a"] == 5
    assert act(client, judge, game, "score", score_a=12, score_b=3).status_code == 400
    final = act(
        client, judge, game, "finish", score_a=11, score_b=7, end_reason="reached_11"
    ).json()
    assert final["status"] == "completed" and final["winner_id"] == game.team_a_id
    assert final["seconds"] < 720
    again = act(client, judge, game, "finish", score_a=11, score_b=7, end_reason="reached_11")
    assert again.status_code == 200  # offline retry of the same result
    other = act(client, judge, game, "finish", score_a=11, score_b=8, end_reason="reached_11")
    assert other.status_code == 409
    assert act(client, judge, game, "start").status_code == 409
    actions = [a.action for a in store.all(ScoreAudit) if a.match_id == game.id]
    assert actions == ["start", "final"]


def test_clock_endings(client: TestClient, store: Store, judge: dict, game: Match) -> None:
    act(client, judge, game, "start")
    tied = act(client, judge, game, "finish", score_a=8, score_b=8, end_reason="clock_lead")
    assert tied.status_code == 400 and "sudden-death" in tied.json()["detail"]
    final = act(
        client,
        judge,
        game,
        "finish",
        score_a=8,
        score_b=8,
        end_reason="clock_lead",
        sudden_death_winner="b",
    ).json()
    assert (final["score_a"], final["score_b"], final["end_reason"]) == (8, 9, "sudden_death")
    assert final["seconds"] == 720 and final["winner_id"] == game.team_b_id


def test_finish_without_start_and_impossible_scores(
    client: TestClient, store: Store, judge: dict, game: Match
) -> None:
    bad = act(client, judge, game, "finish", score_a=11, score_b=11, end_reason="reached_11")
    assert bad.status_code == 400 and "tied" in bad.json()["detail"]
    assert (
        act(client, judge, game, "finish", score_a=11, score_b=0, end_reason="forfeit").status_code
        == 400
    )
    lead = act(client, judge, game, "finish", score_a=9, score_b=4, end_reason="clock_lead").json()
    assert lead["status"] == "completed" and lead["seconds"] == 720


def test_forfeit(client: TestClient, store: Store, judge: dict, game: Match) -> None:
    assert act(client, judge, game, "forfeit", winner="c").status_code == 400
    result = act(client, judge, game, "forfeit", winner="b").json()
    assert (result["score_a"], result["score_b"], result["end_reason"]) == (0, 11, "forfeit")
    assert act(client, judge, game, "forfeit", winner="a").status_code == 409


def test_judges_stay_on_their_court(
    client: TestClient, store: Store, judge: dict, game: Match
) -> None:
    elsewhere = min((m for m in store.all(Match) if m.court == 2), key=lambda m: m.scheduled_at)
    response = act(client, judge, elsewhere, "start")
    assert response.status_code == 400 and "court 1" in response.json()["detail"]
    create_staff(store, "floater", "1234", "judge")
    floater = login(client, "floater", "1234")
    assert act(client, floater, elsewhere, "start").status_code == 200
    board = client.get("/api/judge/matches?court=2", headers=floater).json()
    assert board["court"] == 2 and board["current"]["id"] == elsewhere.id
    assert client.get("/api/judge/matches", headers=floater).json()["court"] is None
    missing = client.post("/api/judge/matches/99999/start", headers=floater)
    assert missing.status_code == 404


def test_knockout_games_wait_for_their_teams_and_earlier_rounds(
    client: TestClient, store: Store, admin: dict, game: Match
) -> None:
    r16 = find(store, Match, code="R16-1")
    response = act(client, admin, r16, "start")
    assert response.status_code == 409 and "not known" in response.json()["detail"]
    assert act(client, admin, r16, "forfeit", winner="a").status_code == 409
    f2 = find(store, Match, code="F-2")
    f2.team_a_id, f2.team_b_id = game.team_a_id, game.team_b_id
    store.save(f2)
    response = act(client, admin, f2, "start")
    assert response.status_code == 409 and "Finish F-1 first" in response.json()["detail"]


def test_admin_corrections_and_resets(
    client: TestClient, store: Store, admin: dict, judge: dict, game: Match
) -> None:
    url = f"/api/admin/matches/{game.id}"
    body = {
        "score_a": 7,
        "score_b": 11,
        "end_reason": "reached_11",
        "reason": "judge swapped teams",
    }
    assert client.post(f"{url}/correct", headers=admin, json=body).status_code == 409
    act(client, judge, game, "finish", score_a=11, score_b=7, end_reason="reached_11")
    assert (
        client.post(f"{url}/correct", headers=admin, json={**body, "reason": " "}).status_code
        == 400
    )
    assert (
        client.post(f"{url}/correct", headers=admin, json={**body, "score_a": 11}).status_code
        == 400
    )
    fixed = client.post(f"{url}/correct", headers=admin, json={**body, "seconds": 500}).json()
    assert fixed["winner_id"] == game.team_b_id and fixed["seconds"] == 500
    keep = client.post(
        f"{url}/correct", headers=admin, json={**body, "score_b": 11, "score_a": 9}
    ).json()
    assert keep["seconds"] == 500  # seconds kept when not given
    assert client.post(f"{url}/reset", headers=admin, json={"reason": ""}).status_code == 400
    reset = client.post(f"{url}/reset", headers=admin, json={"reason": "wrong game"}).json()
    assert reset["status"] == "scheduled" and reset["score_a"] is None
    assert (
        client.post(f"{url}/reset", headers=admin, json={"reason": "again"}).json()["status"]
        == "scheduled"
    )
    log = client.get("/api/admin/audit", headers=admin).json()
    assert [entry["action"] for entry in log] == ["reset", "correct", "correct", "final", "start"]
    assert log[1]["reason"] == "judge swapped teams"


def test_bracket_refresh_retries_after_a_clash(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, 32)
    for match in store.all(Match):
        if match.phase == "group":
            match.status, match.score_a, match.score_b = "completed", 11, 3
            match.end_reason, match.seconds, match.winner_id = "reached_11", 400, match.team_a_id
            store.save(match)
    real_save = store.save
    clashes = iter([True])

    def clashing(record: object, **kw: object) -> None:
        if kw.get("version") is not None and next(clashes, False):
            raise ConflictError("clash")
        real_save(record, **kw)

    monkeypatch.setattr(store, "save", clashing)
    assert scoring.refresh_bracket(store) == []
    assert find(store, Match, code="R16-1").team_a_id is not None


def test_bracket_refresh_gives_up_politely(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        scoring,
        "_bracket_changes",
        lambda store: (
            [
                Match(
                    id=1,
                    code="X",
                    phase="knockout",
                    round_label="x",
                    court=1,
                    scheduled_at=dt.datetime.now(dt.UTC),
                )
            ],
            [],
        ),
    )
    assert scoring.refresh_bracket(store, attempts=2) == [
        "The bracket is busy; it updates with the next result"
    ]
