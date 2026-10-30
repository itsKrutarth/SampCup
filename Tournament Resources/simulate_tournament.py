"""
Full simulated SAMP Cup tournaments.

For each team count: builds the day (sampcup_scheduler), runs every rule check
(check_schedule.check_day), then plays many complete tournaments with random results:
realistic scores and end reasons for every group game, group standings from
ranking.rank_teams, the top 4 of each group into the Round of 16, winners through to the
best-of-3 Final. Every fourth tournament gives every game the same score, so teams tie on
everything and the head-to-head and random-draw steps are exercised. Fails (exit code 1)
if anything is wrong.

Run: python simulate_tournament.py --teams 34-42 [--tournaments 200]
"""

import argparse
import random
import sys
from collections import Counter, defaultdict

import check_schedule
import ranking
import sampcup_scheduler as s


def random_result(rng, a, b, same_scores):
    """One group game result that the ranking rules accept."""
    if same_scores:
        sa, sb, reason, sec = 11, 9, "reached_11", 600
    else:
        r = rng.random()
        if r < 0.75:
            sa, sb, reason, sec = 11, rng.randint(0, 10), "reached_11", rng.randint(300, 720)
        elif r < 0.90:
            sa = rng.randint(6, 10)
            sa, sb, reason, sec = sa, rng.randint(max(0, sa - 5), sa - 1), "clock_lead", 720
        elif r < 0.97:
            v = rng.randint(5, 10)
            sa, sb, reason, sec = v + 1, v, "sudden_death", 720
        else:
            sa, sb, reason, sec = 11, 0, "forfeit", 720
    if rng.random() < 0.5:
        sa, sb = sb, sa
    return {"team_a": a, "team_b": b, "score_a": sa, "score_b": sb, "end_reason": reason,
            "seconds": sec}


def ranking_key(row):
    return (-row["wins"], -row["points_for"], row["avg_seconds"], row["points_against"])


def play(day, rng, trial, same_scores):
    """One whole tournament. Returns (problems, facts)."""
    p = day.plan
    problems = []
    games = defaultdict(list)
    played = Counter()
    for r in day.pool:
        games[r["group"]].append(random_result(rng, r["team_a"], r["team_b"], same_scores))
        played[r["team_a"]] += 1
        played[r["team_b"]] += 1
    # group standings
    place, cut = {}, []
    for g, members in day.groups.items():
        table = ranking.rank_teams(members, games[g], seed=trial)
        if sorted(x["rank"] for x in table) != list(range(1, len(members) + 1)):
            problems.append(f"Group {g} ranks are not 1..{len(members)}")
        if sorted(x["team"] for x in table) != sorted(members):
            problems.append(f"Group {g} standings do not list every team once")
        for upper, lower in zip(table, table[1:]):
            if ranking_key(upper) > ranking_key(lower):
                problems.append(f"Group {g}: Team {upper['team']} ranked above a better team")
            same = ranking_key(upper) == ranking_key(lower)
            if same != (lower["decided_by"] in ("head-to-head", "random draw")):
                problems.append(f"Group {g}: wrong tiebreak shown for Team {lower['team']}")
        if table[0]["decided_by"] != "" or any(x["decided_by"] not in ranking.STEPS
                                                for x in table[1:]):
            problems.append(f"Group {g}: tiebreak labels missing or unknown")
        if table != ranking.rank_teams(members, games[g], seed=trial):
            problems.append(f"Group {g}: standings change when recomputed")
        cut.append(table[4]["decided_by"])  # what separated 4th (through) from 5th (out)
        for x in table[:4]:
            place[f"{g}{x['rank']}"] = x["team"]
    # knockout
    winner, ko_played = {}, Counter()

    def team(ref):
        return winner[ref[2:]] if ref.startswith("W:") else place[ref]

    final_wins, final_games, final_end = Counter(), 0, None
    for m in sorted(day.matches, key=lambda m: (m.start, m.court)):
        a, b = team(m.team_a), team(m.team_b)
        if a == b:
            problems.append(f"{m.mid}: a team plays itself")
        if m.mid.startswith("F-"):
            if max(final_wins.values(), default=0) == 2:
                continue  # best of 3 already decided
            final_games += 1
            w = a if rng.random() < 0.5 else b
            final_wins[w] += 1
            final_end = m.start + s.dt.timedelta(minutes=s.GAME_PLAY_MIN)
        else:
            winner[m.mid] = a if rng.random() < 0.5 else b
        ko_played[a] += 1
        ko_played[b] += 1
    r16 = {team(x) for m in day.matches if m.label == "Round of 16" for x in (m.team_a, m.team_b)}
    if len(r16) != 16 or r16 != set(place.values()):
        problems.append("Round of 16 is not the 16 group qualifiers")
    champion, top = final_wins.most_common(1)[0]
    if top != 2 or final_games not in (2, 3) or (final_games == 3) != (sorted(final_wins.values()) == [1, 2]):
        problems.append(f"best-of-3 Final wrong: {final_games} games, wins {dict(final_wins)}")
    if final_end > p.last_game_end:
        problems.append(f"Final ends {s.fmt(final_end)}, after {s.fmt(p.last_game_end)}")
    totals = [played[t] + ko_played[t] for t in range(1, day.n_teams + 1)]
    if min(played[t] for t in range(1, day.n_teams + 1)) < s.GROUP_GAMES:
        problems.append("a team played fewer than 8 group games")
    return problems, {"cut": cut, "final_games": final_games, "final_end": final_end,
                      "min_games": min(totals), "max_games": max(totals)}


def simulate(day, tournaments, seed=2026):
    rng = random.Random(seed)
    problems, cut, tie_cut, finals3, ends = [], Counter(), Counter(), 0, set()
    lo, hi = 99, 0
    for trial in range(tournaments):
        same_scores = trial % 4 == 3
        prob, facts = play(day, rng, trial, same_scores)
        problems += prob
        (tie_cut if same_scores else cut).update(facts["cut"])
        finals3 += facts["final_games"] == 3
        ends.add(facts["final_end"])
        lo, hi = min(lo, facts["min_games"]), max(hi, facts["max_games"])
    return sorted(set(problems)), {"cut": cut, "tie_cut": tie_cut, "finals3": finals3,
                                   "ends": sorted(ends),
                                   "min_games": lo, "max_games": hi}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default="34-42", help='e.g. "40", "34-42" or "34,38,42"')
    parser.add_argument("--tournaments", type=int, default=200)
    args = parser.parse_args()
    failed = False
    for n in check_schedule.parse_range(args.teams):
        day = s.build_day(n)
        problems, st = check_schedule.check_day(day, 300)
        sim_problems, sim = simulate(day, args.tournaments)
        problems += sim_problems
        sizes = "/".join(str(len(m)) for m in day.groups.values())
        def shares(c):
            return ", ".join(f"{k} {100 * v // sum(c.values())}%" for k, v in c.most_common())
        print(f"{'OK  ' if not problems else 'FAIL'} {n} teams: groups {sizes}, group play ends "
              f"{s.fmt(day.pool_end)}, Final ends {' / '.join(s.fmt(e) for e in sim['ends'])}, "
              f"games per team {sim['min_games']}-{sim['max_games']}, max in a row "
              f"{st['max_in_a_row']}, Final went to game 3 in {sim['finals3']}/{args.tournaments}",
              flush=True)
        print(f"     4th/5th place decided by: {shares(sim['cut'])} "
              f"(forced-tie tournaments: {shares(sim['tie_cut'])})", flush=True)
        for msg in problems[:8]:
            print(f"     - {msg}")
        failed |= bool(problems)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
