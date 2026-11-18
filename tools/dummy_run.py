"""Play a whole tournament with dummy users against a deployed SampCup site.

Everything is made up (DUMMY MISIDs, "Dummy Team" names). Run it only on an empty
table, then wipe it with `python -m app.cli reset-data --yes`. Usage:

    DUMMY_ADMIN_PASSWORD=... python tools/dummy_run.py https://<cloudfront-domain> \
        --admin dummy-admin [--teams 42] [--spectators 20]
"""

import argparse
import io
import json
import os
import random
import secrets
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from openpyxl import Workbook

CENTERS = ["Dummy Center A", "Dummy Center B", "Dummy Center C", "Dummy Center D"]
stats_lock = threading.Lock()
timings: list[float] = []
codes: Counter = Counter()
stop = threading.Event()


class Api:
    def __init__(self, base: str, token: str | None = None) -> None:
        self.base, self.token = base.rstrip("/"), token

    def call(self, method: str, path: str, body: object = None, ok: tuple = (200, 201, 204),
             raw: bytes | None = None, content_type: str = "application/json") -> tuple[int, object]:
        headers = {"Content-Type": content_type}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = urllib.request.Request(f"{self.base}/api{path}", data=data, method=method,
                                         headers=headers)
        for attempt in range(8):
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                    status, text = response.status, response.read()
            except urllib.error.HTTPError as exc:
                status, text = exc.code, exc.read()
            with stats_lock:
                timings.append(time.perf_counter() - started)
                codes[status] += 1
            # Like the real app: a busy server (throttled) is retried, never fatal.
            if status not in (429, 502, 503, 504) or (status == 429 and b"Too many tries" in text):
                break
            time.sleep(0.5 * 2**attempt)
        payload = json.loads(text) if text else None
        if status not in ok:
            raise AssertionError(f"{method} {path} -> {status} {payload}")
        return status, payload


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"  ok  {message}")


def roster(n_players: int) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(["Region", "Event", "Center", "Zone", "FirstName", "LastName", "Gender", "MISID",
                  "What is your TShirt Size?"])
    for i in range(n_players):
        pair = i // 2
        sheet.append(["Northeast", "Dummy Cup", CENTERS[pair % 4], "Dummy Zone",
                      f"Dummy{i + 1:03d}", "Player", "Male", f"DUMMY{i + 1:04d}",
                      random.choice(["Small", "Medium", "Large", "X-Large"])])  # noqa: S311
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def multipart(filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n").encode() + content + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def claim(base: str, player: dict, index: int) -> Api:
    """Create the player's own account (name + center), like a real player would."""
    api = Api(base)
    _, made = api.call("POST", "/players/claim", {
        "first_name": player["first_name"], "last_name": "Player", "center": player["center"],
        "username": f"dummy{index:03d}", "password": "dummy-pass"})
    api.token = made["token"]
    return api


def form_team(base: str, index: int, me: dict, partner: dict) -> dict:
    mine = claim(base, me, 2 * index - 1)
    _, request = mine.call("POST", "/registration/requests", {
        "to_player_id": partner["id"], "team_name": f"Dummy Team {index:02d}"})
    theirs = claim(base, partner, 2 * index)
    _, team = theirs.call("POST", f"/registration/requests/{request['id']}/accept")
    return team


def judge_court(base: str, court: int, pin: str) -> int:
    rng = random.Random(court)  # noqa: S311
    api = Api(base)
    _, login = api.call("POST", "/auth/staff-login", {"username": f"dummy-judge-{court}",
                                                      "password": pin})
    api.token = login["token"]
    played, idle = 0, 0
    while not stop.is_set():
        _, board = api.call("GET", "/judge/matches")
        game = board["current"]
        if game is None or (game["prereqs"] and game["status"] == "scheduled" and not ready(board, game)):
            left = [m for m in board["matches"] if m["status"] in ("scheduled", "in_progress")]
            if not left:
                return played
            idle += 1
            time.sleep(1.5)
            continue
        url = f"/judge/matches/{game['id']}"
        roll = rng.random()
        if roll < 0.04:
            api.call("POST", f"{url}/forfeit", {"winner": rng.choice("ab")})
        else:
            api.call("POST", f"{url}/start")
            for points in range(1, rng.randint(2, 4)):
                time.sleep(0.2)  # judges tap, they do not machine-gun
                api.call("POST", f"{url}/score", {"score_a": points, "score_b": points - 1})
            winner = rng.choice("ab")
            if roll < 0.2:
                body = {"score_a": 7, "score_b": 7, "end_reason": "clock_lead", "sudden_death_winner": winner}
            elif roll < 0.35:
                body = {"score_a": 9, "score_b": 6, "end_reason": "clock_lead"} if winner == "a" else \
                       {"score_a": 6, "score_b": 9, "end_reason": "clock_lead"}
            else:
                loser = rng.randint(0, 10)
                body = {"score_a": 11, "score_b": loser, "end_reason": "reached_11"} if winner == "a" else \
                       {"score_a": loser, "score_b": 11, "end_reason": "reached_11"}
            api.call("POST", f"{url}/finish", body)
        played += 1
    return played


def ready(board: dict, game: dict) -> bool:
    done = {m["code"] for m in board["matches"] if m["status"] in ("completed", "cancelled")}
    return all(code in done for code in game["prereqs"] if any(m["code"] == code for m in board["matches"]))


def spectator(base: str, seed: int) -> None:
    rng = random.Random(seed)  # noqa: S311
    api = Api(base)
    pages = ["/public/overview", "/public/schedule", "/public/standings", "/public/bracket",
             "/public/schedule?group=A", f"/public/teams/{rng.randint(1, 32)}"]
    while not stop.is_set():
        api.call("GET", rng.choice(pages), ok=(200, 404))
        time.sleep(rng.uniform(2, 5))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("--admin", default="dummy-admin")
    parser.add_argument("--teams", type=int, default=42)
    parser.add_argument("--spectators", type=int, default=20)
    args = parser.parse_args()
    base, started = args.base, time.time()
    admin = Api(base)
    _, login = admin.call("POST", "/auth/staff-login", {"username": args.admin,
                                                        "password": os.environ["DUMMY_ADMIN_PASSWORD"]})
    admin.token = login["token"]

    print("1. Settings and roster")
    _, summary = admin.call("GET", "/admin/summary")
    check(summary["players"] == 0, "the table starts empty")
    admin.call("PATCH", "/admin/tournament", {"event_date": "2026-12-06", "registration_open": True,
                                              "team_cap": 42})
    n_pairs = args.teams + 1  # one extra pair must land on the waitlist
    body, content_type = multipart("dummy.xlsx", roster(n_pairs * 2))
    _, report = admin.call("POST", "/admin/players/import", raw=body, content_type=content_type)
    check(report["added"] == n_pairs * 2, f"imported {report['added']} dummy players")

    print("2. Players create accounts and form teams (in parallel)")
    public = Api(base)
    centers = public.call("GET", "/registration/centers")[1]
    check(len(centers) == 4, "4 dummy centers listed (names only)")
    _, players = admin.call("GET", "/admin/players")
    by_name = {p["first_name"]: p for p in players}
    pairs = [(by_name[f"Dummy{2 * i + 1:03d}"], by_name[f"Dummy{2 * i + 2:03d}"]) for i in range(n_pairs)]
    wrong = public.call("POST", "/players/claim", {"first_name": "Nobody", "last_name": "Player",
                        "center": centers[0], "username": "nobody", "password": "dummy-pass"}, ok=(404,))
    check(wrong[0] == 404, "an unregistered name cannot create an account")
    with ThreadPoolExecutor(8) as pool:
        teams = list(pool.map(lambda job: form_team(base, *job),
                              [(i + 1, me, partner) for i, (me, partner) in enumerate(pairs[:args.teams])]))
    check(all(t["status"] == "active" for t in teams), f"{len(teams)} teams formed, all active")
    me, partner = pairs[-1]
    late = form_team(base, args.teams + 1, me, partner)
    check(late["status"] == "waitlist", "the team past the cap is on the waitlist")
    again = public.call("POST", "/players/claim", {"first_name": me["first_name"], "last_name": "Player",
                        "center": me["center"], "username": "thief", "password": "dummy-pass"}, ok=(409,))
    check(again[0] == 409, "an account can only be claimed once")
    player = Api(base)
    _, login = player.call("POST", "/auth/player-login", {"username": "dummy013", "password": "dummy-pass"})
    player.token = login["token"]
    _, mine = player.call("GET", "/player/me")
    check(len(mine["team"]["players"]) == 2, "a player logs in and sees their team")

    print("3. Check-in, draw, schedule")
    _, all_teams = admin.call("GET", "/admin/teams")
    with ThreadPoolExecutor(6) as pool:
        list(pool.map(lambda t: admin.call("PATCH", f"/admin/teams/{t['id']}", {"checked_in": True}),
                      [t for t in all_teams if t["status"] == "active"]))
    _, drawn = admin.call("POST", "/admin/draw", {})
    check(sorted(t["number"] for t in drawn) == list(range(1, args.teams + 1)), "team numbers drawn 1..N")
    _, made = admin.call("POST", "/admin/schedule")
    _, matches = public.call("GET", "/public/schedule")
    check(made["matches"] == len(matches), f"schedule generated: {len(matches)} games")
    check(matches[0]["scheduled_at"].startswith("2026-12-06T15:00"), "first game 10:00 AM on Dec 6")
    admin.call("POST", "/admin/schedule/lock", {"locked": True})
    admin.call("POST", "/admin/announcements", {"title": "Dummy run in progress"})
    _, overview = public.call("GET", "/public/overview")
    check(overview["phase"] == "scheduled", "public overview shows the schedule is out")

    print("4. Nine judges play the whole day while spectators watch")
    pins = {}
    for court in range(1, 10):
        pins[court] = f"{secrets.randbelow(10_000):04d}"
        admin.call("POST", "/admin/staff", {"username": f"dummy-judge-{court}", "password": pins[court],
                                            "role": "judge", "court": court})
    watchers = ThreadPoolExecutor(args.spectators)
    for s in range(args.spectators):
        watchers.submit(spectator, base, s)
    play_started = time.time()
    with ThreadPoolExecutor(9) as pool:
        played = list(pool.map(lambda c: judge_court(base, c, pins[c]), range(1, 10)))
    stop.set()
    watchers.shutdown(wait=True)
    print(f"  games played per court: {played} (total {sum(played)}) in {time.time() - play_started:.0f}s")

    print("5. Results")
    time.sleep(4)  # let CloudFront's 3-second cache expire
    _, standings = public.call("GET", "/public/standings")
    groups = standings["groups"]
    check(all(g["complete"] for g in groups.values()), "every group complete")
    check(all(r["played"] >= 8 for g in groups.values() for r in g["rows"]), "every team played 8+ group games")
    _, bracket = public.call("GET", "/public/bracket")
    r16 = {m["code"]: m for m in bracket["matches"]}
    check(r16["R16-1"]["team_a"]["id"] == groups["A"]["rows"][0]["team_id"], "R16-1 holds the Group A winner")
    check(bracket["champion"] is not None, f"champion: {bracket['champion']['name']}")
    finals = [m for m in bracket["matches"] if m["code"].startswith("F-")]
    check(sum(m["status"] == "completed" for m in finals) in (2, 3), "best-of-3 Final ended at 2 wins")
    _, overview = public.call("GET", "/public/overview")
    check(overview["phase"] == "finished" and overview["announcements"], "overview: finished, banner shown")
    _, log = admin.call("GET", "/admin/audit?limit=1000")
    check(len(log) >= len(matches) - 1, f"audit log has {len(log)} entries")

    print("6. Traffic")
    ordered = sorted(timings)
    print(f"  requests: {len(ordered)}, by status: {dict(codes)}")
    print(f"  response time p50 {statistics.median(ordered) * 1000:.0f} ms, "
          f"p95 {ordered[int(len(ordered) * 0.95)] * 1000:.0f} ms, max {ordered[-1] * 1000:.0f} ms")
    print(f"  throttled then retried: {codes.get(429, 0) + codes.get(503, 0)}")
    unexpected = {c: n for c, n in codes.items() if c >= 500 and c != 503}
    check(not unexpected, "no server errors seen by any user")
    print(f"Done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        stop.set()
        print(f"FAILED: {exc}")
        sys.exit(1)
