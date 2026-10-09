"""
Pickleball Tournament Scheduler
==============================
Generates a full one-day tournament schedule:
  Phase 1 - Pool Play (Round Robin): 6 rounds, used to rank teams 1..N.
  Phase 2 - Championship bracket plus lower seeded flights.

Reconstructed from supplied screenshots. Whitespace and long comments have
been normalized. The original header described four-team flights for all
teams, but the photographed implementation uses a power-of-two championship
bracket and flights for remaining teams. This file follows the implementation.

Produces:
  pool_play_schedule.csv
  elimination_schedule.csv
  per_team_schedule.csv (pool-play summary only)
  team_slips.txt

Run: python pickleball_tournament_scheduler.py --teams 40
"""

import csv
import argparse
import datetime

ELIM_REST_SLOTS = 1
SLOT_MIN = 17
GAME_PLAY_MIN = 12
NUM_COURTS = 9
CHECK_IN_START = datetime.datetime(2026, 1, 1, 9, 30)
START_TIME = datetime.datetime(2026, 1, 1, 10, 0)
POOL_ROUNDS = 6
LUNCH_REST_SLOTS = 3  # 51 min minimum lunch gap (3 x 17 min)
LUNCH_CANDIDATE_GAMES = [2, 3, 4]


def circle_method_rounds(n_teams, n_rounds):
    """Circle-method pairings; odd team counts receive a rotating bye."""
    teams = list(range(1, n_teams + 1))
    bye = n_teams % 2 == 1
    if bye:
        teams.append(None)
    n = len(teams)
    half = n // 2
    arr = teams[:]
    rounds = []
    for _ in range(n_rounds):
        pairs = []
        for i in range(half):
            a, b = arr[i], arr[n - 1 - i]
            if a is not None and b is not None:
                pairs.append((a, b))
        rounds.append(pairs)
        arr = [arr[0], arr[-1]] + arr[1:-1]
    return rounds


def build_pool_schedule(n_teams, start_time=None, num_courts=NUM_COURTS,
                        slot_min=SLOT_MIN):
    """Schedule fixed pairings with one empty rest slot between games.

    After a team's designated second, third, or fourth game, require two
    empty slots instead. These are minimum gaps, not maximum gaps.
    """
    if start_time is None:
        start_time = START_TIME
    rounds = circle_method_rounds(n_teams, POOL_ROUNDS)
    remaining = []
    for r_idx, pairs in enumerate(rounds, start=1):
        for a, b in pairs:
            remaining.append({"round": r_idx, "team_a": a, "team_b": b})
    lunch_after_game = {
        team: LUNCH_CANDIDATE_GAMES[(team - 1) % len(LUNCH_CANDIDATE_GAMES)]
        for team in range(1, n_teams + 1)
    }
    team_last_end = {}
    games_played = {}
    court_free_at = [start_time] * num_courts
    rows = []
    back_to_back_count = 0
    t = start_time
    slots_done = 0
    slot_cap = 600

    def required_rest_minutes(team):
        gp = games_played.get(team, 0)
        if gp == lunch_after_game[team]:
            return slot_min * LUNCH_REST_SLOTS
        return slot_min

    def is_rested(team, at_time):
        last = team_last_end.get(team)
        return (last is None or last + datetime.timedelta(
            minutes=required_rest_minutes(team)) <= at_time)

    while remaining and slots_done < slot_cap:
        free_courts = [c for c in range(num_courts) if court_free_at[c] <= t]
        for c in free_courts:
            if not remaining:
                break
            chosen = None
            for i, m in enumerate(remaining):
                if is_rested(m["team_a"], t) and is_rested(m["team_b"], t):
                    chosen = i
                    break
            if chosen is None:
                continue
            m = remaining.pop(chosen)
            a, b = m["team_a"], m["team_b"]
            end_t = t + datetime.timedelta(minutes=slot_min)
            rows.append({
                "phase": "Pool Play", "round": m["round"],
                "time": t.strftime("%I:%M %p"), "court": c + 1,
                "team_a": a, "team_b": b, "admin_override_court": "",
            })
            team_last_end[a] = end_t
            team_last_end[b] = end_t
            games_played[a] = games_played.get(a, 0) + 1
            games_played[b] = games_played.get(b, 0) + 1
            court_free_at[c] = end_t
        t += datetime.timedelta(minutes=slot_min)
        slots_done += 1
    if remaining:
        raise RuntimeError(
            f"Could not schedule {len(remaining)} pool matches within the safety cap.")
    rows.sort(key=lambda r: (datetime.datetime.strptime(r["time"], "%I:%M %p"),
                             r["court"]))
    after_pool_time = max(court_free_at)
    return rows, after_pool_time, back_to_back_count


def standard_bracket_order(n):
    """Classic single-elimination seeding order; n must be a power of two."""
    if n == 1:
        return [1]
    prev = standard_bracket_order(n // 2)
    order = []
    for s in prev:
        order.append(s)
        order.append(n + 1 - s)
    return order


def largest_power_of_two_leq(n):
    p = 1
    while p * 2 <= n:
        p *= 2
    return p


ROUND_NAMES = {
    64: "Round of 64",
    32: "Playoff Round 1 (Round of 32)",
    16: "Playoff Round 2 (Round of 16)",
    8: "Quarterfinals",
    4: "Semifinals",
    2: "Final",
}


class Match:
    __slots__ = ("mid", "phase", "label_a", "label_b", "prereqs", "is_placement")

    def __init__(self, mid, phase, label_a, label_b, prereqs, is_placement=False):
        self.mid = mid
        self.phase = phase
        self.label_a = label_a
        self.label_b = label_b
        self.prereqs = prereqs
        self.is_placement = is_placement


def build_championship_bracket(seed_start, bracket_size):
    """Build the championship, third-place, and early-loser placement matches.

    Every entrant gets at least two games for bracket sizes of four or more.
    Early-loser placement matches identify a placement band, not a complete
    unique ranking within that band.
    """
    matches = []
    seed_order = [seed_start + s - 1
                  for s in standard_bracket_order(bracket_size)]
    round_ids_by_size = {}
    round_name = ROUND_NAMES.get(bracket_size, f"Round of {bracket_size}")
    cur_ids = []
    first_round_pairs = [(seed_order[i], seed_order[i + 1])
                         for i in range(0, bracket_size, 2)]
    for i, (a, b) in enumerate(first_round_pairs, start=1):
        mid = f"R{bracket_size}-M{i}"
        matches.append(Match(mid, round_name, f"Seed {a}", f"Seed {b}", []))
        cur_ids.append(mid)
    round_ids_by_size[bracket_size] = cur_ids
    cur_size = bracket_size // 2
    prev_ids = cur_ids
    while len(prev_ids) > 1:
        round_name = ROUND_NAMES.get(cur_size, f"Round of {cur_size}")
        new_ids = []
        for i in range(0, len(prev_ids), 2):
            m1, m2 = prev_ids[i], prev_ids[i + 1]
            mid = f"R{cur_size}-M{i // 2 + 1}"
            matches.append(Match(mid, round_name, f"Winner of {m1}",
                                 f"Winner of {m2}", [m1, m2]))
            new_ids.append(mid)
        round_ids_by_size[cur_size] = new_ids
        prev_ids = new_ids
        cur_size //= 2
    final_match_id = prev_ids[0]
    final_match = next(m for m in matches if m.mid == final_match_id)
    sf1, sf2 = final_match.prereqs
    matches.append(Match(f"{final_match_id}-3rdPlace", "3rd Place Game",
                         f"Loser of {sf1}", f"Loser of {sf2}", [sf1, sf2]))
    size = bracket_size
    while size >= 8:
        ids = round_ids_by_size[size]
        lo, hi = placement_range(size)
        for i in range(0, len(ids), 2):
            m1, m2 = ids[i], ids[i + 1]
            pid = f"Placement-{size}-M{i // 2 + 1}"
            matches.append(Match(pid, f"Placement Game (Places {lo}-{hi})",
                                 f"Loser of {m1}", f"Loser of {m2}", [m1, m2],
                                 is_placement=True))
        size //= 2
    return matches


def placement_range(round_size):
    hi = round_size
    lo = round_size // 2 + 1
    return lo, hi


def chunk_remainder(n_remaining):
    """Split into groups of four; merge a trailing singleton into its predecessor."""
    if n_remaining <= 0:
        return []
    if n_remaining <= 4:
        return [n_remaining]
    sizes = []
    rem = n_remaining
    while rem > 4:
        sizes.append(4)
        rem -= 4
    sizes.append(rem)
    if sizes[-1] == 1:
        sizes[-2] += 1
        sizes.pop()
    return sizes


def build_lower_bracket_flights(seed_start, n_remaining):
    """Four-team brackets, three-team round robins, or two-team rematches.

    Merged groups of five or more use a full round robin.
    """
    matches = []
    seed = seed_start
    fid = 1
    for size in chunk_remainder(n_remaining):
        group = list(range(seed, seed + size))
        if size == 4:
            m1, m2 = f"L{fid}-SF1", f"L{fid}-SF2"
            matches.append(Match(m1, "Lower Bracket Semifinal",
                                 f"Seed {group[0]}", f"Seed {group[3]}", []))
            matches.append(Match(m2, "Lower Bracket Semifinal",
                                 f"Seed {group[1]}", f"Seed {group[2]}", []))
            matches.append(Match(f"L{fid}-Final", "Lower Bracket Final",
                                 f"Winner of {m1}", f"Winner of {m2}", [m1, m2]))
            matches.append(Match(f"L{fid}-3rd", "Lower Bracket 3rd Place",
                                 f"Loser of {m1}", f"Loser of {m2}", [m1, m2]))
        elif size == 3:
            a, b, c = group
            matches.append(Match(f"L{fid}-G1", "Lower Bracket Mini Round Robin (3 teams)",
                                 f"Seed {a}", f"Seed {b}", []))
            matches.append(Match(f"L{fid}-G2", "Lower Bracket Mini Round Robin (3 teams)",
                                 f"Seed {b}", f"Seed {c}", []))
            matches.append(Match(f"L{fid}-G3", "Lower Bracket Mini Round Robin (3 teams)",
                                 f"Seed {a}", f"Seed {c}", []))
        elif size == 2:
            a, b = group
            matches.append(Match(f"L{fid}-G1", "Lower Bracket Rematch (Game 1)",
                                 f"Seed {a}", f"Seed {b}", []))
            matches.append(Match(f"L{fid}-G2", "Lower Bracket Rematch (Game 2)",
                                 f"Seed {a}", f"Seed {b}", []))
        else:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    matches.append(Match(f"L{fid}-G{i}_{j}",
                                         f"Lower Bracket Round Robin ({size} teams)",
                                         f"Seed {group[i]}", f"Seed {group[j]}", []))
        seed += size
        fid += 1
    return matches


def greedy_schedule(matches, start_time, num_courts=NUM_COURTS, slot_min=SLOT_MIN):
    """Dependency-aware court scheduler with team rest.

    A match may start only ELIM_REST_SLOTS empty slots after its prerequisite
    matches end, so no team plays in consecutive slots.
    """
    by_id = {m.mid: m for m in matches}
    completed_end = {}
    courts_free_at = [start_time] * num_courts
    remaining = list(matches)
    rows = []

    def earliest_start(m):
        if not m.prereqs:
            return start_time
        return max(completed_end[p] for p in m.prereqs) + datetime.timedelta(minutes=slot_min * ELIM_REST_SLOTS)

    while remaining:
        ready = [m for m in remaining if all(p in completed_end for p in m.prereqs)]
        if not ready:
            raise RuntimeError("Dependency cycle or missing prereq in bracket generation")
        ready.sort(key=earliest_start)
        for m in ready:
            est = earliest_start(m)
            court_idx = min(range(num_courts), key=lambda c: courts_free_at[c])
            start = max(courts_free_at[court_idx], est)
            end = start + datetime.timedelta(minutes=slot_min)
            rows.append({
                "phase": m.phase, "round": "", "time": start.strftime("%I:%M %p"),
                "court": court_idx + 1, "team_a": m.label_a, "team_b": m.label_b,
                "admin_override_court": "",
            })
            courts_free_at[court_idx] = end
            completed_end[m.mid] = end
            remaining.remove(m)
    rows.sort(key=lambda r: (datetime.datetime.strptime(r["time"], "%I:%M %p"),
                             r["court"]))
    end_time = max(courts_free_at)
    return rows, end_time


def build_elimination_schedule(n_teams, start_time):
    bracket_size = largest_power_of_two_leq(n_teams)
    remainder = n_teams - bracket_size
    while remainder == 1 and bracket_size > 2:
        bracket_size //= 2
        remainder = n_teams - bracket_size
    matches = build_championship_bracket(1, bracket_size)
    lower_info = "none (bracket_size == n_teams)"
    if remainder > 0:
        matches += build_lower_bracket_flights(bracket_size + 1, remainder)
        group_sizes = chunk_remainder(remainder)
        lower_info = (f"seeds {bracket_size + 1}-{n_teams} "
                      f"({remainder} teams, groups of {group_sizes})")
    rows, end_time = greedy_schedule(matches, start_time)
    return rows, end_time, bracket_size, remainder, lower_info


def build_per_team_view(pool_rows, n_teams):
    per_team = {i: [] for i in range(1, n_teams + 1)}
    for row in pool_rows:
        per_team[row["team_a"]].append(row)
        per_team[row["team_b"]].append(row)
    out = []
    for team in range(1, n_teams + 1):
        games = sorted(per_team[team], key=lambda r: datetime.datetime.strptime(
            r["time"], "%I:%M %p"))
        times = [datetime.datetime.strptime(g["time"], "%I:%M %p") for g in games]
        gaps = []
        for i in range(1, len(times)):
            gap_min = int((times[i] - times[i - 1]).total_seconds() / 60) - SLOT_MIN
            gaps.append(gap_min)
        longest_gap = max(gaps) if gaps else 0
        longest_gap_idx = gaps.index(longest_gap) if gaps else -1
        lunch_after_game = longest_gap_idx + 1 if longest_gap_idx >= 0 else "-"
        out.append({
            "team": f"Team {team}", "games_scheduled": len(games),
            "first_game": games[0]["time"] if games else "-",
            "last_game": games[-1]["time"] if games else "-",
            "longest_rest_gap_min": longest_gap,
            "suggested_lunch_after_game_num": lunch_after_game,
        })
    return out


def opponent_label(row, team_str):
    if row["team_a"] == team_str:
        return row["team_b"]
    return row["team_a"]


def build_team_slips(pool_rows, n_teams):
    """Printable pool-play cards, with a note about elimination matchups."""
    lines = []
    for team in range(1, n_teams + 1):
        team_label = team
        games = [r for r in pool_rows
                 if r["team_a"] == team_label or r["team_b"] == team_label]
        games.sort(key=lambda r: datetime.datetime.strptime(r["time"], "%I:%M %p"))
        lines.append("=" * 44)
        lines.append(f"  TEAM {team} - POOL PLAY SCHEDULE")
        lines.append("=" * 44)
        lines.append(f"  Check-in: {CHECK_IN_START.strftime('%I:%M %p')}")
        lines.append("-" * 44)
        lines.append(f"{'Game#':<6}{'Time':<10}{'Court':<7}{'Opponent'}")
        for i, g in enumerate(games, start=1):
            opp = g["team_b"] if g["team_a"] == team_label else g["team_a"]
            lines.append(f"{i:<6}{g['time']:<10}{g['court']:<7}Team {opp}")
        lines.append("-" * 44)
        lines.append("  Games 7-8 (Elimination Round):")
        lines.append("  Seeding posted ~20 min after pool play ends.")
        lines.append("  Check the posted bracket for your matchup, time & court.")
        lines.append("  (Courts may be reassigned by tournament admin on the day.)")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", type=int, default=40)
    args = parser.parse_args()
    n_teams = args.teams
    # The photographed championship builder requires at least four teams.
    if n_teams < 4:
        parser.error("--teams must be at least 4 for this bracket implementation")
    pool_rows, after_pool_time, back_to_back_count = build_pool_schedule(n_teams)
    elim_start = after_pool_time + datetime.timedelta(minutes=20)
    elim_rows, end_time, bracket_size, remainder, lower_info = build_elimination_schedule(
        n_teams, elim_start)
    per_team = build_per_team_view(pool_rows, n_teams)
    slips_text = build_team_slips(pool_rows, n_teams)
    fieldnames = ["phase", "round", "time", "court", "team_a", "team_b",
                  "admin_override_court"]
    with open("pool_play_schedule.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(pool_rows)
    with open("elimination_schedule.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(elim_rows)
    with open("per_team_schedule.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["team", "games_scheduled", "first_game",
                                         "last_game", "longest_rest_gap_min",
                                         "suggested_lunch_after_game_num"])
        w.writeheader()
        w.writerows(per_team)
    with open("team_slips.txt", "w") as f:
        f.write(slips_text)
    print(f"Teams: {n_teams}")
    print(f"Check-in: {CHECK_IN_START.strftime('%I:%M %p')} - "
          f"{START_TIME.strftime('%I:%M %p')} (optional buffer, doesn't shift game times)")
    print(f"Pool play: {len(pool_rows)} matches, {START_TIME.strftime('%I:%M %p')} - "
          f"{after_pool_time.strftime('%I:%M %p')}")
    print(f"Game length: {GAME_PLAY_MIN} min play + {SLOT_MIN - GAME_PLAY_MIN} "
          f"min relocate/score/water break ({SLOT_MIN} min slots)")
    print(f"Back-to-back games (0 rest between a team's consecutive games): "
          f"{back_to_back_count}, out of {n_teams} teams x 6 rounds")
    print(f"Lunch: designated transition requires at least "
          f"{SLOT_MIN * LUNCH_REST_SLOTS} min of empty slots after game "
          f"{LUNCH_CANDIDATE_GAMES[0]}, {LUNCH_CANDIDATE_GAMES[1]}, or "
          f"{LUNCH_CANDIDATE_GAMES[2]}; actual gaps may be longer.")
    print("Pool ranking (in order): 1) most wins 2) highest cumulative score "
          "3) lowest average game time (clock-ended games count as 12:00) "
          "4) fewer points allowed 5) head-to-head (two-team ties only) "
          "6) random draw")
    print("Game rules: first to 11, 12-minute clock; ahead at clock end wins; "
          "tied at clock end = sudden death (next rally = 1 point, added to winner's score)")
    print(f"Seeding break: {after_pool_time.strftime('%I:%M %p')} - "
          f"{elim_start.strftime('%I:%M %p')}")
    print(f"Elimination: {len(elim_rows)} matches, {elim_start.strftime('%I:%M %p')} - "
          f"{end_time.strftime('%I:%M %p')}")
    print(f"Championship bracket: top {bracket_size} seeds "
          "(Playoff Rd1 -> Playoff Rd2 -> QF -> SF -> Final/3rd)")
    print(f"Lower bracket: {lower_info}")
    print(f"Estimated finish time (before awards/buffer): {end_time.strftime('%I:%M %p')}")
    print("\nWrote: pool_play_schedule.csv, elimination_schedule.csv, "
          "per_team_schedule.csv, team_slips.txt")
    print(f"Playoff rest rule: every team gets at least {ELIM_REST_SLOTS} empty slot "
          "between playoff games.")


if __name__ == "__main__":
    main()
