"""
Independent checks for sampcup_scheduler.py.

For each team count, builds the day, checks group play directly and plays the knockout
through many random results, tracking every team's real games. Fails (exit code 1) if any
rule in 02_TOURNAMENT_RULES.md is broken.

Run: python check_schedule.py --teams 34-42 [--trials 300]
(simulate_tournament.py runs these checks too, plus full simulated tournaments.)
"""

import argparse
import random
import sys
from collections import defaultdict

import sampcup_scheduler as s


def check_day(day, trials, seed=1):
    p = day.plan
    problems = []
    # groups: 4 groups, every team in exactly one, equal games inside each group
    teams = [t for members in day.groups.values() for t in members]
    if len(day.groups) != len(s.GROUPS) or sorted(teams) != list(range(1, day.n_teams + 1)):
        problems.append("teams are not split into 4 groups exactly once")
    group_of = {t: g for g, members in day.groups.items() for t in members}
    opponents = defaultdict(list)
    used = set()
    for r in day.pool:
        a, b = r["team_a"], r["team_b"]
        if (r["slot"], r["court"]) in used or r["court"] > p.courts:
            problems.append(f"court clash at slot {r['slot']} court {r['court']}")
        used.add((r["slot"], r["court"]))
        if group_of[a] != group_of[b] or group_of[a] != r["group"]:
            problems.append(f"Team {a} v Team {b} is not a game inside one group")
        opponents[a].append(b)
        opponents[b].append(a)
        if day.pool_time(r) + p.slot > p.sabha_start:
            problems.append(f"group game at {s.fmt(day.pool_time(r))} runs into Sabha")
    for g, members in day.groups.items():
        want = s.group_games(len(members))
        rematches = max(0, want - (len(members) - 1))  # a group of 8 has one rematch each
        for t in members:
            if len(opponents[t]) != want or want < s.GROUP_GAMES:
                problems.append(f"Team {t} plays {len(opponents[t])} group games, needs {want}")
            if len(opponents[t]) - len(set(opponents[t])) != rematches:
                problems.append(f"Team {t} has the wrong number of rematches")
    # rest: no wait longer than lunch between group games, or before the first game
    gap = p.max_gap_slots
    for t in teams:
        ks = [r["slot"] for r in s.team_games(day, t)]
        if ks and ks[0] > gap:
            problems.append(f"Team {t} waits until {s.fmt(day.pool_time(s.team_games(day, t)[0]))} for its first game")
        if any(b - a - 1 > gap for a, b in zip(ks, ks[1:])):
            problems.append(f"Team {t} has a break longer than lunch between group games")
    # lunch: one gap of LUNCH_MIN or more inside the window, during group play
    lo = p.lunch_start - s.EDGE_TOLERANCE
    hi = min(p.lunch_end + s.EDGE_TOLERANCE, day.pool_end)
    for t in teams:
        busy = sorted(day.pool_time(r) for r in s.team_games(day, t))
        free = [p.first_game] + [x for g in busy for x in (g, g + p.slot)] + [day.pool_end]
        best = max((min(b, hi) - max(a, lo)).total_seconds() / 60
                   for a, b in zip(free[::2], free[1::2]))
        if best < s.LUNCH_MIN:
            problems.append(f"Team {t} has no {s.LUNCH_MIN}-min lunch between 12 and 2")
    # knockout: top 4 of every group, same-group teams apart until the semifinals, timing
    r16 = [m for m in day.matches if m.label == "Round of 16"]
    seeds = sorted(x for m in r16 for x in (m.team_a, m.team_b))
    if seeds != sorted(f"{g}{i}" for g in s.GROUPS for i in range(1, 5)):
        problems.append("Round of 16 does not hold exactly the top 4 of every group")
    quarter = {}
    for i, m in enumerate(r16):
        for x in (m.team_a, m.team_b):
            quarter[x] = i // 2
    for g in s.GROUPS:
        if len({quarter[f"{g}{i}"] for i in range(1, 5)}) < 4:
            problems.append(f"two Group {g} teams can meet before the semifinals")
    ko_used = set()
    for m in day.matches:
        if (m.start, m.court) in ko_used or m.court > p.courts:
            problems.append(f"knockout court clash at {s.fmt(m.start)}")
        ko_used.add((m.start, m.court))
        if m.start < p.sabha_end:
            problems.append(f"{m.mid} is before the end of Sabha")
    if day.last_game_end > p.last_game_end:
        problems.append(f"Final ends {s.fmt(day.last_game_end)}, after {s.fmt(p.last_game_end)}")
    final = [m for m in day.matches if m.mid.startswith("F-")]
    if len(final) != s.FINAL_GAMES or any(m.court != 1 for m in final):
        problems.append("the Final is not a best-of-3 on court 1")
    # simulated results: rest rule and double booking across the whole day
    pool_times = {t: [day.pool_time(r) for r in s.team_games(day, t)] for t in teams}
    rng = random.Random(seed)
    stats = dict(min_games=99, max_games=0, max_in_a_row=0)
    for _ in range(trials):
        ranking = {g: rng.sample(members, 4) for g, members in day.groups.items()}
        result, ko_times = {}, defaultdict(list)

        def team(ref):
            if ref.startswith("W:"):
                return result[ref[2:]]
            return ranking[ref[0]][int(ref[1]) - 1]

        final_games, wins = 0, defaultdict(int)
        for m in sorted(day.matches, key=lambda m: m.start):
            a, b = team(m.team_a), team(m.team_b)
            if m.mid.startswith("F-"):
                if max(wins.values(), default=0) == 2:  # best of 3 already decided
                    continue
                final_games += 1
                win = a if rng.random() < 0.5 else b
                wins[win] += 1
                if m.mid == "F-1":  # the Final is one match for the rest rule
                    ko_times[a].append(m.start)
                    ko_times[b].append(m.start)
                continue
            result[m.mid] = a if rng.random() < 0.5 else b
            ko_times[a].append(m.start)
            ko_times[b].append(m.start)
        if final_games not in (2, 3) or sorted(wins.values())[-1] != 2:
            problems.append("best-of-3 Final did not end with a team winning 2 games")
        finalists = {team(final[0].team_a), team(final[0].team_b)}
        for t in teams:
            times = sorted(pool_times[t] + ko_times[t])
            # the Final counts once for the rest rule but 2 or 3 games for games played
            played = len(times) + (final_games - 1 if t in finalists else 0)
            stats["min_games"] = min(stats["min_games"], played)
            stats["max_games"] = max(stats["max_games"], played)
            run = 1
            for x, y in zip(times, times[1:]):
                if y < x + p.slot:
                    problems.append(f"Team {t} double-booked at {s.fmt(y)}")
                run = run + 1 if y == x + p.slot else 1
                stats["max_in_a_row"] = max(stats["max_in_a_row"], run)
    if stats["max_in_a_row"] > s.MAX_IN_A_ROW:
        problems.append(f"a team plays {stats['max_in_a_row']} games in a row")
    return sorted(set(problems)), stats


def parse_range(text):
    if "-" in text:
        lo, hi = text.split("-")
        return range(int(lo), int(hi) + 1)
    return [int(x) for x in text.split(",")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default="34-42", help='e.g. "40", "34-42" or "34,38,42"')
    parser.add_argument("--trials", type=int, default=300)
    args = parser.parse_args()
    failed = False
    for n in parse_range(args.teams):
        day = s.build_day(n)
        problems, st = check_day(day, args.trials)
        status = "OK  " if not problems else "FAIL"
        sizes = "/".join(str(len(m)) for m in day.groups.values())
        print(f"{status} {n} teams: groups {sizes}, group play {s.fmt(day.plan.first_game)}-"
              f"{s.fmt(day.pool_end)}, last possible game ends {s.fmt(day.last_game_end)}, "
              f"games per team {st['min_games']}-{st['max_games']}, "
              f"max in a row {st['max_in_a_row']}", flush=True)
        for msg in problems[:5]:
            print(f"     - {msg}")
        failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
