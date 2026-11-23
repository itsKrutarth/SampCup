"""The app takes back what the backup sheet recorded while it was down (/admin/sheet-import)."""

import datetime as dt

from fastapi.testclient import TestClient

from app.models import Match, ScoreAudit, Team
from app.services.sheet_import import venue_time
from app.store import Store
from tests.factories import seeded

NY = "America/New_York"


def numbers(store: Store, match: Match) -> tuple[int | None, int | None]:
    teams = {t.id: t.team_number for t in store.all(Team)}
    return teams.get(match.team_a_id), teams.get(match.team_b_id)  # type: ignore[arg-type]


def send(client: TestClient, admin: dict, *games: dict):
    return client.post("/api/admin/sheet-import", headers=admin, json={"games": list(games)})


def test_venue_times_from_the_sheet() -> None:
    day = dt.datetime(2026, 12, 6, 15, tzinfo=dt.UTC)  # 10:00 AM in West Boylston
    at = lambda h, m: dt.datetime(2026, 12, 6, h, m, tzinfo=dt.UTC)  # noqa: E731
    assert venue_time("10:15 AM", day, NY) == at(15, 15)
    assert venue_time("4:30 pm", day, NY) == at(21, 30)
    assert venue_time("4:30", day, NY) == at(21, 30)  # no AM/PM: the afternoon
    assert venue_time("9:05", day, NY) == at(14, 5)  # ...or the morning
    assert venue_time("12:10 PM", day, NY) == at(17, 10)
    for nonsense in ("", "13:00", "0:30 AM", "noon", "10:75"):
        assert venue_time(nonsense, day, NY) is None


def test_results_times_and_courts_come_back_from_the_sheet(
    client: TestClient, store: Store, admin: dict
) -> None:
    seeded(store, 32)
    games = sorted(store.all(Match), key=lambda m: (m.scheduled_at, m.court))
    first, moved, other = games[0], games[20], games[30]
    a, b = numbers(store, first)
    report = send(
        client,
        admin,
        {"code": first.code, "team_a": a, "team_b": b, "score_a": 11, "score_b": 7}
        | {"end_reason": "reached_11", "seconds": 510},
        {"code": moved.code, "time": "4:45 PM", "court": 9},
        {"code": "G999", "score_a": 11, "score_b": 0, "end_reason": "forfeit"},
        {"code": other.code, "team_a": 1, "team_b": 2, "score_a": 11, "score_b": 3}
        | {"end_reason": "reached_11", "seconds": 400},
        {"code": games[40].code, "time": "", "court": games[40].court},  # nothing changed
    ).json()
    outcome = {r["code"]: r for r in report["games"]}
    assert outcome[first.code] == {"code": first.code, "applied": ["result"], "skipped": None}
    assert outcome[moved.code]["applied"] == ["court 9", "new time"]
    assert outcome["G999"]["skipped"] == "no such game in the app"
    assert "other teams" in outcome[other.code]["skipped"]
    assert outcome[games[40].code]["skipped"] == "nothing to take"
    assert set(report["taken"]) == {first.code, moved.code, games[40].code}
    assert {r["code"] for r in report["skipped"]} == {"G999", other.code}

    played = store.get(Match, first.id)
    assert played.status == "completed" and played.seconds == 510 and played.score_a == 11
    assert played.ended_at - played.started_at == dt.timedelta(seconds=510)
    audit = [x for x in store.all(ScoreAudit) if x.match_id == first.id]
    assert [x.action for x in audit] == ["import"] and audit[0].reason == "From the backup sheet"
    shifted = store.get(Match, moved.id)
    assert shifted.court == 9 and shifted.scheduled_at == dt.datetime(
        2026, 12, 6, 21, 45, tzinfo=dt.UTC
    ).replace(day=shifted.scheduled_at.day)

    # sent again: already in the app; a different score or game time is a correction
    again = send(
        client,
        admin,
        {"code": first.code, "team_a": a, "team_b": b, "score_a": 11, "score_b": 7}
        | {"end_reason": "reached_11", "seconds": 510},
    ).json()
    assert again["taken"] == [first.code] and again["skipped"] == []
    fixed = send(
        client,
        admin,
        {"code": first.code, "team_a": a, "team_b": b, "score_a": 11, "score_b": 9}
        | {"end_reason": "reached_11", "seconds": 540},
    ).json()
    assert fixed["games"][0]["applied"] == ["result corrected"]
    corrected = store.get(Match, first.id)
    assert (corrected.score_b, corrected.seconds) == (9, 540)
    # an impossible result is reported, not saved
    bad = send(
        client,
        admin,
        {"code": games[1].code, "team_a": numbers(store, games[1])[0]}
        | {"team_b": numbers(store, games[1])[1], "score_a": 11, "score_b": 11}
        | {"end_reason": "reached_11"},
    ).json()
    assert "winner" in bad["skipped"][0]["skipped"]


def test_knockout_games_wait_for_their_teams_and_only_admins_import(
    client: TestClient, store: Store, admin: dict, judge: dict
) -> None:
    seeded(store, 32)
    r16 = next(m for m in store.all(Match) if m.code == "R16-1")
    report = send(
        client,
        admin,
        {"code": "R16-1", "team_a": 1, "team_b": 2, "score_a": 11, "score_b": 5}
        | {"end_reason": "reached_11"},
    ).json()
    assert report["skipped"][0]["skipped"] == "the app does not know this game's teams yet"
    assert store.get(Match, r16.id).status == "scheduled"
    assert send(client, judge, {"code": "R16-1"}).status_code == 403
    too_many = {"games": [{"code": "G001"}] * 301}
    assert client.post("/api/admin/sheet-import", headers=admin, json=too_many).status_code == 422


def test_the_backup_sheet_link_is_a_google_sheet(client: TestClient, admin: dict) -> None:
    link = "https://docs.google.com/spreadsheets/d/abc123/edit"
    saved = client.patch("/api/admin/tournament", headers=admin, json={"backup_sheet_url": link})
    assert saved.json()["tournament"]["backup_sheet_url"] == link
    for bad in ("javascript:alert(1)", "https://evil.example/sheet", "http://docs.google.com/x"):
        refused = client.patch(
            "/api/admin/tournament", headers=admin, json={"backup_sheet_url": bad}
        )
        assert refused.status_code == 422, bad
    cleared = client.patch("/api/admin/tournament", headers=admin, json={"backup_sheet_url": ""})
    assert cleared.json()["tournament"]["backup_sheet_url"] == ""
    assert "backup_sheet_url" not in client.get("/api/public/overview").json()["tournament"]
