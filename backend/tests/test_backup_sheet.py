"""The backup Google Sheet (tools/backup-sheet/Code.gs) agrees with the app.

The sheet's logic is plain JavaScript under "Pure logic", so node runs it here: its group
ranking against ranking.py, and its manual mode against a whole simulated day in the app.
"""

import json
import random
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.store import Store
from app.tournament.ranking import STEPS, rank_teams
from tests.factories import seeded
from tests.test_full_day import play

CODE = Path(__file__).resolve().parents[2] / "tools" / "backup-sheet" / "Code.gs"
FAKE_GOOGLE = Path(__file__).with_name("fake_google_sheet.js")
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node runs the sheet's script")
STATUS = {"scheduled": "scheduled", "in_progress": "playing", "completed": "done"}
STATUS["cancelled"] = "not needed"

# Loads Code.gs, then either ranks groups or plays manual mode on the Schedule tab exactly
# as the sheet would hold it after copying the app (every cell as text).
HARNESS = r"""
const fs = require('fs')
const vm = require('vm')
const names = 'rankGroup, scheduleRows, teamRows, recomputeAll, importPayload, bracketGrid, ' +
  'courtsGrid'
const sheet = vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8') + `\n;({ ${names} })`, {})
// the venue time as the real sheet shows it (Apps Script: "h:mm a" at the venue)
const venueTime = (iso) => new Date(iso).toLocaleTimeString('en-US',
  { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }).replace(/\s/g, ' ')
const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const asShown = (row) => Object.fromEntries(Object.entries(row).map(
  ([k, v]) => [k, v === null || v === undefined ? '' : String(v)]))
const teamsOf = (teams) => sheet.teamRows(teams, (iso) => iso).map(
  (t) => ({ number: t[0] === '' ? null : Number(t[0]), name: t[1], group: t[2] }))
let out
if (input.rank) {
  out = input.rank.map((c) => sheet.rankGroup(c.teams, c.games))
} else if (input.rest_of_the_day) {
  // The app is down: organizers type every game left as it is played (every third won by
  // team B), recomputing after each round so the knockout teams appear, then send the sheet.
  const teams = teamsOf(input.teams)
  let rows = sheet.scheduleRows(input.schedule, venueTime).map(asShown)
  for (let round = 0; round < 12; round++) {
    let typed = 0
    const done = (code) => rows.some((x) => x.Game === code && x.Status === 'done')
    rows.forEach((r, i) => {
      if (['done', 'not needed'].includes(r.Status) || !r['Team A #'] || !r['Team B #']) return
      if ((r.Game === 'F-2' && !done('F-1')) || (r.Game === 'F-3' && !done('F-2'))) return
      const bWins = i % 3 === 0
      Object.assign(r, { 'Score A': bWins ? '6' : '11', 'Score B': bWins ? '11' : '7',
        'How it ended': 'reached 11', 'Game time': '8:30', 'Changed in sheet': 'yes' })
      typed++
    })
    out = sheet.recomputeAll(teams, rows)
    rows = out.rows.map(asShown)
    if (!typed) break
  }
  out.payload = sheet.importPayload(rows)
  out.bracket = sheet.bracketGrid(rows)
  out.courts = sheet.courtsGrid(rows)
} else {
  const rows = sheet.scheduleRows(input.schedule, (iso) => iso).map(asShown)
  for (const r of rows) {
    const typed = input.typed[r.Game]
    if (typed) Object.assign(r, typed)
    else if (r['From A'] && r.Status !== 'done' && r.Status !== 'playing') {
      // a knockout game not under way: the sheet must work out its teams itself
      r['Team A #'] = ''
      r['Team B #'] = ''
      r['Team A'] = r['From A']
      r['Team B'] = r['From B']
    }
  }
  out = sheet.recomputeAll(teamsOf(input.teams), rows)
}
process.stdout.write(JSON.stringify(out))
"""


def sheet(payload: dict) -> object:
    done = subprocess.run(  # noqa: S603 - our own script, run by node
        [NODE, "-e", HARNESS, str(CODE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def blocks(rows: list[dict], team: str) -> list[tuple]:
    """Each row on its own, except teams the app placed by drawing lots: their order is
    random in the app and by number in the sheet, so they are compared as a set."""
    grouped: list[list[dict]] = []
    for row in rows:
        if row["decided_by"] == "random draw" and grouped:
            grouped[-1].append(row)
        else:
            grouped.append([row])
    return [
        (
            sorted(r["rank"] for r in block),
            sorted(
                (r[team], r["wins"], r["points_for"], r["avg_seconds"], r["points_against"])
                for r in block
            ),
            sorted(r["decided_by"] for r in block),
        )
        for block in grouped
    ]


def random_group(rng: random.Random) -> tuple[list[int], list[dict]]:
    teams = rng.sample(range(1, 43), rng.randint(2, 6))
    pairs = [(a, b) for a in teams for b in teams if a < b]
    games = []
    for a, b in rng.sample(pairs, rng.randint(0, len(pairs))) * rng.choice([1, 1, 2]):
        reason = rng.choice(["reached_11"] * 3 + ["clock_lead", "sudden_death"])
        reason = "forfeit" if rng.random() < 0.05 else reason
        won = rng.random() < 0.5
        score, seconds = {
            "reached_11": ((11, rng.choice([3, 5, 9])), rng.choice([400, 401, 402, 403, 500, 800])),
            "clock_lead": ((9, 6), 720),
            "sudden_death": ((8, 7), 720),
            "forfeit": ((11, 0), 720),
        }[reason]
        sa, sb = score if won else score[::-1]
        games.append(
            {"team_a": a, "team_b": b, "score_a": sa, "score_b": sb}
            | {"end_reason": reason, "seconds": seconds}
        )
    return teams, games


def game(a: int, b: int, sa: int, sb: int, seconds: int) -> dict:
    result = {"score_a": sa, "score_b": sb, "end_reason": "reached_11", "seconds": seconds}
    return {"team_a": a, "team_b": b} | result


def test_the_sheet_ranks_groups_like_the_app() -> None:
    rng = random.Random(2026)
    cases = [random_group(rng) for _ in range(3000)]
    # Python rounds an average of exactly 154.25 s to 154.2 (to even): team 1 (617 s over 4
    # games) then ties team 2 (771 s over 5) on time and goes ahead on points allowed.
    cases.append(
        (
            [1, 2, 3, 4, 5, 6, 7],
            [
                game(1, 3, 11, 5, 150),
                game(1, 4, 11, 5, 150),
                game(1, 5, 5, 11, 158),
                game(1, 6, 5, 11, 159),
                game(2, 3, 11, 3, 154),
                game(2, 4, 11, 3, 154),
                game(2, 5, 3, 11, 154),
                game(2, 6, 3, 11, 154),
                game(2, 7, 4, 11, 155),
            ],
        )
    )
    app = [rank_teams(teams, games) for teams, games in cases]
    mine = sheet({"rank": [{"teams": t, "games": g} for t, g in cases]})
    for expected, got in zip(app, mine, strict=True):
        assert blocks(got, "team") == blocks(expected, "team")
    steps = Counter(r["decided_by"] for table in app for r in table)
    assert all(steps[step] for step in STEPS), steps  # every rule was exercised
    last = {r["team"]: r for r in app[-1]}
    assert last[1]["rank"] < last[2]["rank"] and last[2]["decided_by"] == "points allowed"


def check_against_app(client: TestClient, typed: dict | None = None) -> dict:
    """Recompute the sheet from the app's own data and compare everything with the app."""
    schedule = client.get("/api/public/schedule").json()
    teams = client.get("/api/public/teams").json()
    out = sheet({"schedule": schedule, "teams": teams, "typed": typed or {}})
    for group, table in client.get("/api/public/standings").json()["groups"].items():
        mine = out["standings"][group]
        assert (mine["complete"], mine["played"], mine["total"]) == (
            table["complete"],
            table["played"],
            table["total"],
        )
        assert blocks(mine["rows"], "team_number") == blocks(table["rows"], "team_number")
        assert [r["played"] for r in mine["rows"]] == [r["played"] for r in table["rows"]]
    if typed:
        return out
    rows = {r["Game"]: r for r in out["rows"]}
    for m in schedule:
        row = rows[m["code"]]
        for side in ("a", "b"):
            team = m[f"team_{side}"]
            want = "" if team is None else str(team["number"])
            assert str(row[f"Team {side.upper()} #"]) == want, m["code"]
        assert row["Status"] == STATUS[m["status"]], m["code"]
        winner = next(
            (t for t in (m["team_a"], m["team_b"]) if t and t["id"] == m["winner_id"]), None
        )
        assert row["Winner"] == (f"#{winner['number']} {winner['name']}" if winner else "")
        assert row["Check"] == "", (m["code"], row["Check"])
    champion = client.get("/api/public/overview").json()["champion"]
    assert out["champion"] == (champion["number"] if champion else None)
    return out


def test_the_sheet_carries_on_where_the_app_stopped(
    client: TestClient, store: Store, admin: dict
) -> None:
    rng = random.Random(7)
    seeded(store, 32)
    teams = client.get("/api/public/teams").json()
    assert all(t["lunch_start"] for t in teams)  # the Teams tab shows each team's lunch
    group = [m for m in client.get("/api/public/schedule").json() if m["phase"] == "group"]
    for match in group[: len(group) // 2]:
        play(client, admin, match, rng)
    check_against_app(client)  # standings part way through, no knockout teams yet
    for match in group[len(group) // 2 :]:
        play(client, admin, match, rng)
    check_against_app(client)  # groups complete: the Round of 16 comes from the standings

    def bracket() -> dict[str, dict]:
        return {m["code"]: m for m in client.get("/api/public/bracket").json()["matches"]}

    for code in [f"R16-{i}" for i in range(1, 9)] + [f"QF-{i}" for i in range(1, 5)]:
        play(client, admin, bracket()[code], rng)
    play(client, admin, bracket()["SF-1"], rng)
    play(client, admin, bracket()["SF-2"], rng)
    check_against_app(client)  # every knockout round worked out, up to the Final's teams

    # The app goes down now: the organizers type the Final into the sheet, won 2-0.
    final = bracket()
    a = final["F-1"]["team_a"]["number"]
    typed = {
        code: {"Score A": "11", "Score B": "6", "How it ended": "reached 11", "Game time": "9:05"}
        for code in ("F-1", "F-2")
    }
    out = check_against_app(client, typed)
    rows = {r["Game"]: r for r in out["rows"]}
    assert rows["F-1"]["Status"] == rows["F-2"]["Status"] == "done"
    assert rows["F-3"]["Status"] == "not needed" and out["champion"] == a
    assert out["problems"] == 0
    # Game 3 typed by mistake after the 2-0: flagged, not counted, the champion unchanged.
    third = typed["F-1"] | {"Score A": "4", "Score B": "11"}
    out = check_against_app(client, typed | {"F-3": third})
    rows = {r["Game"]: r for r in out["rows"]}
    assert rows["F-3"]["Status"] == "not needed" and "does not count" in rows["F-3"]["Check"]
    assert out["champion"] == a and rows["F-3"]["Winner"] == ""
    # A mistyped result is flagged, not counted.
    typed["F-2"] = typed["F-2"] | {"Score A": "11", "Score B": "11"}
    out = check_against_app(client, typed)
    rows = {r["Game"]: r for r in out["rows"]}
    assert "winner" in rows["F-2"]["Check"] and rows["F-3"]["Status"] == "scheduled"
    assert out["champion"] is None

    # Back on the app: a split Final needs game 3, and the sheet agrees at every step.
    play(client, admin, final["F-1"], rng, winner="a")
    play(client, admin, bracket()["F-2"], rng, winner="b")
    out = check_against_app(client)
    assert {r["Game"]: r for r in out["rows"]}["F-3"]["Status"] == "scheduled"
    play(client, admin, bracket()["F-3"], rng, winner="a")
    assert check_against_app(client)["champion"] == a


def test_the_sheet_menus_work_end_to_end(client: TestClient, store: Store, admin: dict) -> None:
    """Setup, copying, the app going down, manual results, recompute and back, on a fake
    Google Sheet (fake_google_sheet.js) fed with the app's own pages."""
    rng = random.Random(3)
    seeded(store, 32)
    group = [m for m in client.get("/api/public/schedule").json() if m["phase"] == "group"]
    for match in group[:40]:
        play(client, admin, match, rng)
    pages = {
        page: client.get(f"/api/public/{page}").json()
        for page in ("overview", "teams", "schedule", "standings")
    }
    done = subprocess.run(  # noqa: S603 - our own script, run by node
        [NODE, str(FAKE_GOOGLE), str(CODE)],
        input=json.dumps({"pages": pages}),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)

    setup = report["setup"]
    assert setup["tabs"] == ["Info", "Courts", "Schedule", "Bracket", "Standings", "Teams"]
    assert setup["triggers"] == ["copyFromApp/1"] and setup["mode"] == "AUTO"
    assert setup["games"] == len(pages["schedule"]) and setup["teams"] == 32
    assert setup["check"].endswith(": OK") and setup["standings"][0] == "Group A"

    down = report["down"]  # the app stops answering: the copy stays
    assert down["games"] == len(pages["schedule"]) and "did not answer" in down["check"]

    manual = report["manual"]  # organizers type the rest of group play into the sheet
    assert manual["mode"] == "MANUAL" and manual["validation"] == "rule"
    assert manual["typed"] == manual["marked"] == len(group) - 40
    assert manual["done"] == manual["group_games"] == len(group)
    assert manual["standings"] == ["complete"] * 4 and manual["checks"] == []
    assert all(a and b for a, b in manual["r16"])  # the Round of 16 worked out by the sheet

    views = report["views"]  # Courts and Bracket follow the typed results
    assert [row[0] for row in views["courts"]] == ["Court"] + [f"Court {c}" for c in range(1, 10)]
    assert all(row[3].startswith("R16-") for row in views["courts"][1:9])  # each court's next game
    assert views["bracket"][:2] == ["Round of 16", "Game"]

    # the app is back: a wrong password is refused, then the app takes the changed rows
    assert "refused the login (401)" in report["wrong"]
    partly = report["partly"]
    assert partly["sent"] == len(group) - 40 and partly["auth"] == "Bearer tok"
    first = partly["first"]
    assert first["end_reason"] == "reached_11" and first["seconds"] == 510
    assert {first["score_a"], first["score_b"]} == {11, 7} and first["team_a"] and first["team_b"]
    assert partly["mode"] == "MANUAL" and partly["marked"] == [partly["refused"]]
    assert partly["check"].startswith("Not taken by the app: the sheet has other teams")
    assert "1 could not be taken" in partly["message"]
    back = report["back"]  # the last game taken: back to AUTO, copying the app again
    assert "took all 1 changed game(s)" in back["message"] and "Back to AUTO" in back["message"]
    assert back["mode"] == "AUTO" and back["validation"] is None and back["marked"] == 0
    assert back["done"] == 40 and back["check"].endswith(": OK")
    assert back["dialog"] == "Send the sheet to the app"
    assert (
        report["nothing"]["mode"] == "AUTO"
        and "Nothing was changed" in report["nothing"]["message"]
    )


def test_the_app_carries_on_from_what_the_sheet_recorded(
    client: TestClient, store: Store, admin: dict
) -> None:
    """The app goes down after 60 games; the organizers run the rest of the day in the sheet
    (manual mode, recompute after each round) and send it back: the app ends where the sheet
    did, with the same standings, bracket, game times and champion."""
    rng = random.Random(11)
    seeded(store, 32)
    group = [m for m in client.get("/api/public/schedule").json() if m["phase"] == "group"]
    for match in group[:60]:
        play(client, admin, match, rng)
    out = sheet(
        {
            "rest_of_the_day": True,
            "schedule": client.get("/api/public/schedule").json(),
            "teams": client.get("/api/public/teams").json(),
        }
    )
    rows = {r["Game"]: r for r in out["rows"]}
    assert all(r["Check"] == "" for r in rows.values())
    third = rows["F-3"]["Status"]  # game 3 only after a 1-1 split
    assert third in ("done", "not needed") and out["champion"] is not None
    assert len(out["payload"]) == 145 - 60 - (third == "not needed")
    assert all(":" in g["time"] and g["time"].endswith(("AM", "PM")) for g in out["payload"])
    titles = [r[0] for r in out["bracket"]]
    assert {"Round of 16", "Quarterfinals", "Semifinals", "Final (best of 3)"} <= set(titles)
    assert [r[1] for r in out["courts"][1:]] == ["done for the day"] * 9

    report = client.post(
        "/api/admin/sheet-import", headers=admin, json={"games": out["payload"]}
    ).json()
    assert report["skipped"] == [] and len(report["taken"]) == len(out["payload"])

    # the app now matches the sheet: standings, every knockout game, game times, champion
    for group_name, table in client.get("/api/public/standings").json()["groups"].items():
        assert table["complete"]
        assert blocks(table["rows"], "team_number") == blocks(
            out["standings"][group_name]["rows"], "team_number"
        )
    for m in client.get("/api/public/schedule").json():
        row = rows[m["code"]]
        assert STATUS[m["status"]] == row["Status"], m["code"]
        for side in ("a", "b"):
            team = m[f"team_{side}"]
            assert str(row[f"Team {side.upper()} #"]) == (
                "" if team is None else str(team["number"])
            )
        if m["code"] in report["taken"]:
            assert m["seconds"] == 510  # the 8:30 typed in the sheet, a tiebreak
    champion = client.get("/api/public/overview").json()["champion"]
    assert champion["number"] == out["champion"]
