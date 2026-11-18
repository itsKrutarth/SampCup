"""Run a mock tournament on a deployed SampCup with the real registrations.

Pairs the registered players within their own center (a dummy partner fills each odd
center), checks every team in, draws, schedules and plays every game on 9 courts at a
watchable pace, so the live site shows a real-looking day. Take a snapshot first
(tools/snapshot.py) and restore it afterwards.

    MOCK_ADMIN_PASSWORD=... python tools/mock_tournament.py https://sampcup.com \
        --admin mock-admin [--seconds-per-game 6]
"""

import argparse
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


def add_dummy_partners(table: str) -> int:
    """One made-up partner for each center with an odd number of unpaired players."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    os.environ.setdefault("TABLE_NAME", table)
    from app.models import Player
    from app.store import Store, get_table

    store = Store(get_table())
    players = [p for p in store.all(Player) if p.active and not p.team_id]
    per_center: dict[str, int] = defaultdict(int)
    for p in players:
        per_center[p.center] += 1
    odd = sorted(c for c, n in per_center.items() if n % 2)
    first = store.next_id(Player, len(odd)) if odd else 0
    for i, center in enumerate(odd):
        store.save(Player(id=first + i, mis_id=f"MOCK-{i + 1:02d}", first_name="Mock",
                          last_name=f"Partner {i + 1}", center=center, zone="Mock"))
    return len(odd)


def play_court(base: str, token: str, court: int, pace: float) -> int:
    rng = random.Random(court)  # noqa: S311
    api = Api(base, token)
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
        if rng.random() < 0.03:
            api.call("POST", f"{url}/forfeit", {"winner": rng.choice("ab")})
            played += 1
            continue
        api.call("POST", f"{url}/start")
        winner, loser_points = rng.choice("ab"), rng.randint(2, 10)
        a = b = 0
        for _ in range(4):  # a few live score updates, so the site shows rallies
            time.sleep(pace / 5)
            if winner == "a":
                a, b = min(10, a + rng.randint(2, 3)), min(loser_points, b + rng.randint(0, 2))
            else:
                a, b = min(loser_points, a + rng.randint(0, 2)), min(10, b + rng.randint(2, 3))
            api.call("POST", f"{url}/score", {"score_a": a, "score_b": b})
        time.sleep(pace / 5)
        roll = rng.random()
        if roll < 0.15:
            body = {"score_a": 8, "score_b": 8, "end_reason": "clock_lead", "sudden_death_winner": winner}
        else:
            body = ({"score_a": 11, "score_b": loser_points} if winner == "a"
                    else {"score_a": loser_points, "score_b": 11}) | {"end_reason": "reached_11"}
        api.call("POST", f"{url}/finish", body)
        played += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--admin", default="mock-admin")
    parser.add_argument("--table", default="sampcup-prod")
    parser.add_argument("--seconds-per-game", type=float, default=6)
    args = parser.parse_args()
    base = args.base
    admin = Api(base)
    _, login = admin.call("POST", "/auth/staff-login", {"username": args.admin,
                                                        "password": os.environ["MOCK_ADMIN_PASSWORD"]})
    admin.token = login["token"]

    print("1. Mock banner, registration closed, dummy partners")
    admin.call("POST", "/admin/announcements", {"title": BANNER, "body": "The real draw happens on December 6."})
    admin.call("PATCH", "/admin/tournament", {"registration_open": False})
    added = add_dummy_partners(args.table)
    print(f"  ok  added {added} dummy partners for centers with an odd number of players")

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
    check(len(teams) == number, f"{number} teams formed, every pair from one center")
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda t: admin.call("PATCH", f"/admin/teams/{t['id']}", {"checked_in": True}), teams))

    print("3. Draw and schedule")
    _, drawn = admin.call("POST", "/admin/draw", {})
    check(sorted(t["number"] for t in drawn) == list(range(1, len(drawn) + 1)), f"numbers 1..{len(drawn)} drawn")
    _, made = admin.call("POST", "/admin/schedule")
    admin.call("POST", "/admin/schedule/lock", {"locked": True})
    print(f"  ok  {made['matches']} games scheduled and locked")

    print(f"4. Playing on 9 courts (about {args.seconds_per_game:g}s per game) - watch {base}")
    started = time.time()
    with ThreadPoolExecutor(9) as pool:
        played = list(pool.map(lambda c: play_court(base, admin.token, c, args.seconds_per_game), range(1, 10)))
    print(f"  ok  {sum(played)} games in {time.time() - started:.0f}s")

    print("5. Result")
    time.sleep(4)
    _, bracket = Api(base).call("GET", "/public/bracket")
    check(bracket["champion"] is not None, f"champion: {bracket['champion']['name']}")
    _, standings = Api(base).call("GET", "/public/standings")
    check(all(g["complete"] for g in standings["groups"].values()), "every group complete")


if __name__ == "__main__":
    main()
