import json
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models import Match, Team
from app.services import schedule
from app.services.errors import Conflict, ServiceError
from app.store import Store
from app.tournament.templates import DATA_DIR, MAX_TEAMS, MIN_TEAMS, load_template
from tests.factories import EVENT_DATE, find, make_team, seeded


@pytest.mark.parametrize("n_teams", range(MIN_TEAMS, MAX_TEAMS + 1))
def test_every_precomputed_schedule_keeps_the_rules(n_teams: int) -> None:
    data = load_template(n_teams)
    assert sorted(n for nums in data["groups"].values() for n in nums) == list(
        range(1, n_teams + 1)
    )
    games = Counter()
    by_slot = defaultdict(list)
    for game in data["pool"]:
        games.update([game["team_a"], game["team_b"]])
        by_slot[game["slot"]].append(game)
    assert set(games.values()) == {8}  # every team plays exactly 8 group games
    for slot_games in by_slot.values():
        teams = [t for g in slot_games for t in (g["team_a"], g["team_b"])]
        assert len(teams) == len(set(teams))  # nobody plays twice at once
        assert len(slot_games) <= data["courts"]
    for team in range(1, n_teams + 1):
        slots = sorted(
            s for s, gs in by_slot.items() for g in gs if team in (g["team_a"], g["team_b"])
        )
        runs = [b - a for a, b in zip(slots, slots[1:], strict=False)]
        assert all(
            not (x == 1 and y == 1) for x, y in zip(runs, runs[1:], strict=False)
        )  # max 2 in a row
    assert data["group_play_ends"] <= "15:30"
    assert [k["code"] for k in data["knockout"]][-3:] == ["F-1", "F-2", "F-3"]


def test_template_range_and_files() -> None:
    assert len(list(DATA_DIR.glob("teams_*.json"))) == MAX_TEAMS - MIN_TEAMS + 1
    with pytest.raises(ValueError, match="32-42"):
        load_template(43)
    assert json.loads((DATA_DIR / "teams_40.json").read_text())["teams"] == 40


def test_draw_generate_lock_and_clear(client: TestClient, store: Store, admin: dict) -> None:
    for _ in range(34):
        make_team(store)
    make_team(store, checked_in=False)  # not here yet: left out of the draw
    response = client.post("/api/admin/schedule", headers=admin)
    assert response.status_code == 400 and "event date" in response.json()["detail"]
    client.patch(
        "/api/admin/tournament", headers=admin, json={"event_date": EVENT_DATE.isoformat()}
    )
    assert "Draw team numbers" in client.post("/api/admin/schedule", headers=admin).json()["detail"]
    drawn = client.post("/api/admin/draw", headers=admin, json={"seed": 7}).json()
    assert [t["number"] for t in drawn] == list(range(1, 35))
    again = [
        t["id"] for t in client.post("/api/admin/draw", headers=admin, json={"seed": 7}).json()
    ]
    assert again == [t["id"] for t in drawn]  # same seed, same draw
    assert client.post("/api/admin/schedule", headers=admin).json() == {"matches": 136 + 17}
    first = min(store.all(Match), key=lambda m: m.scheduled_at)
    assert first.scheduled_at == datetime(2026, 12, 6, 15, 0, tzinfo=UTC)  # 10:00 AM in Boston
    team = find(store, Team, team_number=1)
    assert team.lunch_start is not None
    summary = client.get("/api/admin/summary", headers=admin).json()
    assert summary["tournament"]["schedule_exists"] and summary["checked_in"] == 34
    assert client.post("/api/admin/draw", headers=admin, json={}).status_code == 409
    date_change = client.patch(
        "/api/admin/tournament", headers=admin, json={"event_date": "2026-12-07"}
    )
    assert date_change.status_code == 400
    assert client.post("/api/admin/schedule/lock", headers=admin, json={"locked": True}).json()[
        "locked"
    ]
    assert client.post("/api/admin/schedule", headers=admin).status_code == 409
    assert client.delete("/api/admin/schedule", headers=admin).status_code == 409
    client.post("/api/admin/schedule/lock", headers=admin, json={"locked": False})
    assert client.delete("/api/admin/schedule", headers=admin).status_code == 204
    assert find(store, Team, team_number=1).lunch_start is None
    lock = client.post("/api/admin/schedule/lock", headers=admin, json={"locked": True})
    assert lock.status_code == 400


def test_draw_needs_32_to_42_checked_in_teams(store: Store) -> None:
    for _ in range(31):
        make_team(store)
    with pytest.raises(ServiceError, match="31 active teams"):
        schedule.draw_numbers(store)


def test_generate_refuses_gaps_in_numbers(store: Store) -> None:
    seeded(store, 32)
    team = find(store, Team, team_number=32)
    team.team_number = 99
    store.save(team)
    with pytest.raises(ServiceError, match="gaps"):
        schedule.generate_schedule(store)


def test_unlock_refused_once_games_started(store: Store) -> None:
    seeded(store, 32)
    match = store.all(Match)[0]
    match.status = "in_progress"
    store.save(match)
    with pytest.raises(ServiceError, match="stays locked"):
        schedule.set_locked(store, False)


def test_court_override(client: TestClient, store: Store, admin: dict) -> None:
    seeded(store, 32)
    match = store.all(Match)[0]
    moved = client.patch(f"/api/admin/matches/{match.id}", headers=admin, json={"court": 9}).json()
    assert moved["court"] == 9
    assert (
        client.patch(
            f"/api/admin/matches/{match.id}", headers=admin, json={"court": 10}
        ).status_code
        == 400
    )
    assert (
        client.patch("/api/admin/matches/99999", headers=admin, json={"court": 1}).status_code
        == 404
    )
    match.status = "completed"
    store.save(match)
    assert (
        client.patch(f"/api/admin/matches/{match.id}", headers=admin, json={"court": 2}).status_code
        == 409
    )


def test_running_behind_shifts_later_games_and_warns(
    client: TestClient, store: Store, admin: dict
) -> None:
    no_schedule = client.post(
        "/api/admin/delays",
        headers=admin,
        json={"minutes": 10, "from_time": "2026-12-06T15:00:00Z"},
    )
    assert no_schedule.status_code == 400
    seeded(store, 40)
    two_pm = datetime(2026, 12, 6, 19, 0, tzinfo=UTC)
    before = {m.id: m.scheduled_at for m in store.all(Match)}
    result = client.post(
        "/api/admin/delays", headers=admin, json={"minutes": 20, "from_time": two_pm.isoformat()}
    ).json()
    after = {m.id: m.scheduled_at for m in store.all(Match)}
    moved = [i for i in before if after[i] != before[i]]
    assert result["moved"] == len(moved) and all(before[i] >= two_pm for i in moved)
    assert all(after[i] - before[i] == timedelta(minutes=20) for i in moved)
    assert any("overlaps Sabha" in w for w in result["warnings"])
    assert any("after 6:40 PM" in w for w in result["warnings"])
    assert client.get("/api/admin/delays", headers=admin).json()[0]["minutes"] == 20
    for bad in ({"minutes": 0}, {"minutes": 500}):
        response = client.post(
            "/api/admin/delays", headers=admin, json={**bad, "from_time": two_pm.isoformat()}
        )
        assert response.status_code == 400
    naive = client.post(
        "/api/admin/delays", headers=admin, json={"minutes": 5, "from_time": "2026-12-06T14:00:00"}
    )
    assert naive.status_code == 400


def test_a_game_that_starts_while_shifting_keeps_its_time(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    seeded(store, 32)
    calls = iter([True])

    def flaky(store: Store, match: Match) -> None:
        if next(calls, False):
            raise Conflict("changed")
        store.save(match)

    monkeypatch.setattr(schedule, "save_match", flaky)
    result = schedule.apply_delay(store, 5, datetime(2026, 12, 6, 15, 0, tzinfo=UTC), "admin")
    assert result["warnings"][-1] == "1 game(s) started while shifting and kept their time"


def test_versions_stop_two_devices_overwriting_each_other(store: Store) -> None:
    seeded(store, 32)
    first, second = store.get(Match, 1), store.get(Match, 1)
    schedule.save_match(store, first)
    with pytest.raises(Conflict, match="another device"):
        schedule.save_match(store, second)
