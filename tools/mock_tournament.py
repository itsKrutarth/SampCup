"""Run a mock tournament on a deployed SampCup with the real registrations.

Pairs the registered players who have no team yet within their own center (a dummy partner
fills each odd center, and dummy pairs top the field up to the draw's minimum), checks the
mock teams in, draws, schedules and plays the day on 9 courts, so the live site shows a
real-looking day. Teams the players formed themselves stay out: never checked in, drawn or
played. Games follow the schedule on a fast clock (--speed 20: a game in 24-36 seconds, the
day in about half an hour; --speed 30: about 20 seconds a game): each game starts at its own
time, never just because its court is free, and waits while one of its teams is still
playing elsewhere. Take a snapshot first (tools/snapshot.py save) and restore it afterwards
with tools/mock_restore.py, which keeps what real people did meanwhile (account claims,
judge PIN changes, logins).

    MOCK_ADMIN_PASSWORD=... python tools/mock_tournament.py https://sampcup.com \
        --admin mock-admin [--speed 20]
"""

import argparse
import datetime as dt
import os
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dummy_run import Api, check, ready  # noqa: E402

BANNER = "Mock tournament: test data only"


def add_dummy_players(table: str) -> int:
    """Made-up players: a partner for each center with an odd number of unpaired players,
    then pairs at a "Mock" center until the mock teams reach the draw's minimum."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    os.environ.setdefault("TABLE_NAME", table)
    from app.models import Player
    from app.store import Store, get_table
    from app.tournament.templates import MIN_TEAMS

    store = Store(get_table())
    players = [p for p in store.all(Player) if p.active and not p.team_id]
    per_center: dict[str, int] = defaultdict(int)
    for p in players:
        per_center[p.center] += 1
    centers = sorted(c for c, n in per_center.items() if n % 2)
    short = MIN_TEAMS - (len(players) + len(centers)) // 2
    centers += ["Mock"] * (2 * max(0, short))
    first = store.next_id(Player, len(centers)) if centers else 0
    for i, center in enumerate(centers):
        store.save(Player(id=first + i, mis_id=f"MOCK-{i + 1:02d}", first_name="Mock",
                          last_name=f"Partner {i + 1}", center=center, zone="Mock"))
    return len(centers)


def play_court(base: str, token: str, court: int, speed: float, day_start: dt.datetime,
               wall_start: float) -> int:
    rng = random.Random(court)  # noqa: S311
    api = Api(base)
    api.token = token
    played = 0
    while True:
        _, board = api.call("GET", f"/judge/matches?court={court}")
        game = board["current"]
        if game is None or (game["prereqs"] and game["status"] == "scheduled" and not ready(board, game)):
            if not [m for m in board["matches"] if m["status"] in ("scheduled", "in_progress")]:
                return played
            time.sleep(2)
            continue
        url = f"/judge/matches/{game['id']}"
        if game["status"] == "scheduled":
            # the game's time on the fast clock; the real day is weeks away, so the admin
            # starts it "early", exactly when the fast clock reaches it
            due = wall_start + (dt.datetime.fromisoformat(game["scheduled_at"]) - day_start).total_seconds() / speed
            if time.time() < due or board["waiting"]:
                time.sleep(min(2.0, max(0.2, due - time.time())))
                continue
            if rng.random() < 0.03:
                status, _ = api.call("POST", f"{url}/forfeit", {"winner": rng.choice("ab")}, ok=(200, 409))
                played += status == 200
                continue
            status, _ = api.call("POST", f"{url}/start", {"early": True}, ok=(200, 409))
            if status == 409:  # a team got busy meanwhile
                continue
        pace = rng.uniform(8, 12) * 60 / speed  # an 8-12 minute game on the fast clock
        winner, loser_points = rng.choice("ab"), rng.randint(2, 10)
        a = b = 0
        # Someone on the court's real judge screen may score or finish the game too: the app
        # then refuses our update (409), so read the board again instead of giving up.
        taken = False
        for _ in range(4):  # a few live score updates, so the site shows rallies
            time.sleep(pace / 5)
            if winner == "a":
                a, b = min(10, a + rng.randint(2, 3)), min(loser_points, b + rng.randint(0, 2))
            else:
                a, b = min(loser_points, a + rng.randint(0, 2)), min(10, b + rng.randint(2, 3))
            status, _ = api.call("POST", f"{url}/score", {"score_a": a, "score_b": b}, ok=(200, 409))
            if status == 409:
                taken = True
                break
        if taken:
            continue
        time.sleep(pace / 5)
        if rng.random() < 0.15:
            body = {"score_a": 8, "score_b": 8, "end_reason": "clock_lead", "sudden_death_winner": winner}
        else:
            body = ({"score_a": 11, "score_b": loser_points} if winner == "a"
                    else {"score_a": loser_points, "score_b": 11}) | {"end_reason": "reached_11"}
        status, _ = api.call("POST", f"{url}/finish", body, ok=(200, 409))
        played += status == 200


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--admin", default="mock-admin")
    parser.add_argument("--table", default="sampcup-prod")
    parser.add_argument("--speed", type=float, default=20, help="how much faster than real time")
    args = parser.parse_args()
    base = args.base
    admin = Api(base)
    _, login = admin.call("POST", "/auth/staff-login", {"username": args.admin,
                                                        "password": os.environ["MOCK_ADMIN_PASSWORD"]})
    admin.token = login["token"]

    print("1. Mock banner, registration closed, dummy partners")
    admin.call("POST", "/admin/announcements", {"title": BANNER, "body": "The real draw happens on December 6."})
    admin.call("PATCH", "/admin/tournament", {"registration_open": False})
    added = add_dummy_players(args.table)
    print(f"  ok  added {added} dummy players (odd centers, and enough teams for a draw)")

    print("2. Teams by center")
    _, players = admin.call("GET", "/admin/players")
    by_center: dict[str, list[dict]] = defaultdict(list)
    for p in players:
        if p["active"] and not p["team"]:
            by_center[p["center"]].append(p)
    number = 0
    for center in sorted(by_center):
        group = sorted(by_center[center], key=lambda p: (p["last_name"], p["first_name"]))
        for i in range(0, len(group) - 1, 2):
            number += 1
            admin.call("POST", "/admin/teams", {"name": f"Mock Team {number:02d}",
                                                "player_ids": [group[i]["id"], group[i + 1]["id"]]})
    _, teams = admin.call("GET", "/admin/teams")
    real = [t for t in teams if not t["name"].startswith("Mock Team ")]
    teams = [t for t in teams if t["name"].startswith("Mock Team ")]
    check(len(teams) == number, f"{number} mock teams formed, every pair from one center")
    check(not any(t["checked_in"] for t in real), f"{len(real)} real teams left out of the mock")
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda t: admin.call("PATCH", f"/admin/teams/{t['id']}", {"checked_in": True}), teams))

    print("3. Draw and schedule")
    _, drawn = admin.call("POST", "/admin/draw", {})
    check(sorted(t["number"] for t in drawn) == list(range(1, len(drawn) + 1)), f"numbers 1..{len(drawn)} drawn")
    _, made = admin.call("POST", "/admin/schedule")
    admin.call("POST", "/admin/schedule/lock", {"locked": True})
    print(f"  ok  {made['matches']} games scheduled and locked")

    _, games = Api(base).call("GET", "/public/schedule")
    day_start = min(dt.datetime.fromisoformat(m["scheduled_at"]) for m in games)
    print(f"4. Playing the schedule on 9 courts at {args.speed:g}x speed - watch {base}")
    started = time.time()
    with ThreadPoolExecutor(9) as pool:
        played = list(pool.map(lambda c: play_court(base, admin.token, c, args.speed, day_start, started),
                               range(1, 10)))
    print(f"  ok  {sum(played)} games in {time.time() - started:.0f}s")

    print("5. Result")
    time.sleep(4)
    _, bracket = Api(base).call("GET", "/public/bracket")
    check(bracket["champion"] is not None, f"champion: {bracket['champion']['name']}")
    _, standings = Api(base).call("GET", "/public/standings")
    check(all(g["complete"] for g in standings["groups"].values()), "every group complete")


if __name__ == "__main__":
    main()
