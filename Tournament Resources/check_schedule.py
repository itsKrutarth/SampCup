"""
Independent checks for sampcup_scheduler.py.

For each team count, builds the day and plays the knockout through many random results,
tracking every team's real games. Fails (exit code 1) if any rule in
02_TOURNAMENT_RULES.md is broken.

Run: python check_schedule.py --teams 32-42 [--trials 300]
"""

import argparse
import random
import sys
from collections import defaultdict

import sampcup_scheduler as s


def check_day(day, trials, seed=1):
    p = day.plan
    problems = []
    # pool: games per team, repeats, courts, double booking
    opponents = defaultdict(list)
    used = set()
    for r in day.pool:
        if (r["slot"], r["court"]) in used or r["court"] > p.courts:
            problems.append(f"pool court clash at slot {r['slot']} court {r['court']}")
        used.add((r["slot"], r["court"]))
        opponents[r["team_a"]].append(r["team_b"])
        opponents[r["team_b"]].append(r["team_a"])
    for t in range(1, day.n_teams + 1):
        games = opponents[t]
        if len(set(games)) != len(games):
            problems.append(f"team {t} meets an opponent twice in pool play")
        need = s.POOL_GAMES if day.n_teams % 2 == 0 else s.POOL_GAMES - 1
        if len(games) < need:
            problems.append(f"team {t} has only {len(games)} pool games")
    # lunch: one gap of LUNCH_MIN or more inside the window, before the knockout starts
    lo = p.lunch_start - s.EDGE_TOLERANCE
    hi = min(p.lunch_end + s.EDGE_TOLERANCE, day.knockout_start)
    for t in range(1, day.n_teams + 1):
        busy = sorted(day.pool_time(r) for r in s.team_games(day, t))
        free = [p.first_game] + [x for g in busy for x in (g, g + p.slot)] + [day.knockout_start]
        best = max((min(b, hi) - max(a, lo)).total_seconds() / 60
                   for a, b in zip(free[::2], free[1::2]))
        if best < s.LUNCH_MIN:
            problems.append(f"team {t} has no {s.LUNCH_MIN}-min lunch between 12 and 2")
    # knockout: courts, Sabha placement, finish time
    ko_used = set()
    for m in day.matches:
        key = (m.slot, m.court)
        if key in ko_used or m.court > p.courts:
            problems.append(f"knockout court clash at {s.fmt(day.match_time(m))}")
        ko_used.add(key)
        t = day.match_time(m)
        if p.sabha_start < t + p.slot and t < p.sabha_end:
            problems.append(f"{m.mid} overlaps Sabha")
        if m.label in ("Gold Play-in", "Gold Round of 32") and t >= p.sabha_end:
            problems.append(f"{m.mid} is after Sabha (Round of 32 must finish before 3:30)")
        if m.after_sabha and t < p.sabha_end:
            problems.append(f"{m.mid} is before Sabha")
    if day.last_game_end > p.last_game_end:
        problems.append(f"last game ends {s.fmt(day.last_game_end)}, after {s.fmt(p.last_game_end)}")
    # simulated results: rest rule, double booking, second chance, minimum games
    pool_times = {t: [day.pool_time(r) for r in s.team_games(day, t)]
                  for t in range(1, day.n_teams + 1)}
    rng = random.Random(seed)
    stats = dict(min_games=99, max_games=0, max_in_a_row=0)
    for _ in range(trials):
        result, ko_times, in_silver, out_of_gold_early = {}, defaultdict(list), set(), set()

        def team(ref):
            if ref.startswith("Seed "):
                return int(ref[5:])
            return result[ref[2:]][0 if ref[0] == "W" else 1]

        for m in sorted(day.matches, key=lambda m: m.slot):
            a, b = team(m.team_a), team(m.team_b)
            win, lose = (a, b) if rng.random() < 0.5 else (b, a)
            result[m.mid] = (win, lose)
            ko_times[a].append(day.match_time(m))
            ko_times[b].append(day.match_time(m))
            if m.bracket == "Silver":
                in_silver |= {a, b}
            if m.bracket == "Gold" and m.label not in (
                    "Gold Quarterfinal", "Gold Semifinal", "Gold Final"):
                out_of_gold_early.add(lose)
        for t in out_of_gold_early - in_silver:
            problems.append(f"team {t} lost early in Gold but played no Silver game")
        for t in range(1, day.n_teams + 1):
            times = sorted(pool_times[t] + ko_times[t])
            stats["min_games"] = min(stats["min_games"], len(times))
            stats["max_games"] = max(stats["max_games"], len(times))
            run = 1
            for x, y in zip(times, times[1:]):
                if y < x + p.slot:
                    problems.append(f"team {t} double-booked at {s.fmt(y)}")
                run = run + 1 if y == x + p.slot else 1
                stats["max_in_a_row"] = max(stats["max_in_a_row"], run)
    if stats["max_in_a_row"] > s.MAX_IN_A_ROW:
        problems.append(f"a team plays {stats['max_in_a_row']} games in a row")
    if day.n_teams % 2 == 0 and stats["min_games"] < 8:
        problems.append(f"a team plays only {stats['min_games']} games")
    return sorted(set(problems)), stats


def parse_range(text):
    if "-" in text:
        lo, hi = text.split("-")
        return range(int(lo), int(hi) + 1)
    return [int(x) for x in text.split(",")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default="32-42", help='e.g. "40", "32-42" or "36,40,42"')
    parser.add_argument("--trials", type=int, default=300)
    args = parser.parse_args()
    failed = False
    for n in parse_range(args.teams):
        day = s.build_day(n)
        problems, st = check_day(day, args.trials)
        status = "OK  " if not problems else "FAIL"
        print(f"{status} {n} teams: pool {s.fmt(day.plan.first_game)}-{s.fmt(day.pool_end)}, "
              f"knockout {s.fmt(day.knockout_start)}, last game ends {s.fmt(day.last_game_end)}, "
              f"games per team {st['min_games']}-{st['max_games']}, "
              f"max in a row {st['max_in_a_row']}", flush=True)
        for msg in problems[:5]:
            print(f"     - {msg}")
        failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
