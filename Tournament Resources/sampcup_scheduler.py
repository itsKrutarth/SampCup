"""
SampCup 2026 Tournament Scheduler
=================================
One-day pickleball tournament: group play, then a 16-team knockout.

  Groups     teams are split into 4 random groups (by the team-number draw at check-in);
             every team plays at least 8 games inside its group (a group of 8 adds one
             rematch, because it has only 7 opponents)
  Knockout   the top 4 of every group (16 teams): Round of 16 4:30 PM, quarterfinals
             4:47 PM, semifinals 5:21 PM, best-of-3 Final from 5:55 PM (done by 6:37 PM)

Day plan: first game 10:00 AM, rolling lunch 12:00-2:00 PM, group play ends before Sabha
3:30-4:30 PM (group standings and the bracket are posted during Sabha).
Rules: 17-minute slots (12 min play + 5 min change-over); at most 2 games in a row per team;
no wait between a team's games, or before its first game, longer than lunch (3 empty slots,
51 min); every team gets a lunch break of 51 min between 12:00 and 2:00.

Produces:
  sampcup_<N>team_groups.csv
  sampcup_<N>team_pool_schedule.csv
  sampcup_<N>team_knockout_schedule.csv
  sampcup_<N>team_per_team.csv
  sampcup_<N>team_court_plan.csv   (when each court can be handed back)
  sampcup_<N>team_team_slips.txt

Requires: ortools  (pip install ortools)
Run: python sampcup_scheduler.py --teams 40
Check: python check_schedule.py --teams 34-42
Simulate: python simulate_tournament.py --teams 34-42
"""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

SLOT_MIN = 17            # 12 min play + 5 min change-over
GAME_PLAY_MIN = 12
NUM_COURTS = 9
MAX_IN_A_ROW = 2
LUNCH_MIN = 45
EDGE_TOLERANCE = dt.timedelta(minutes=5)  # a slot starting at 11:59 counts as noon
DAY = dt.date(2026, 1, 1)

GROUPS = "ABCD"
GROUP_GAMES = 8              # games per team inside its group (at least)
MIN_TEAMS, MAX_TEAMS = 34, 42  # 8 games each fit before Sabha up to 42 teams


def at(hour, minute):
    return dt.datetime.combine(DAY, dt.time(hour, minute))


# Knockout: top 4 of each group. Teams from the same group cannot meet before the semifinals.
ROUND_OF_16 = [("A1", "B4"), ("C2", "D3"), ("D1", "C4"), ("B2", "A3"),
               ("C1", "D4"), ("A2", "B3"), ("B1", "A4"), ("D2", "C3")]
# At most 2 games in a row: the semifinal and the Final each come after a rest slot.
KNOCKOUT_ROUNDS = [("R16", "Round of 16", at(16, 30)),
                   ("QF", "Quarterfinal", at(16, 47)),
                   ("SF", "Semifinal", at(17, 21))]
FINAL_START = at(17, 55)
FINAL_GAMES = 3              # best of 3: first to win 2 games
FINAL_BREAK_MIN = 3          # between Final games (same court, same teams)
SOLVER_ATTEMPTS = 4          # court-share patterns tried per slot count


@dataclass
class DayPlan:
    breakfast: dt.datetime = at(9, 0)
    aarti: dt.datetime = at(9, 45)
    first_game: dt.datetime = at(10, 0)
    lunch_start: dt.datetime = at(12, 0)
    lunch_end: dt.datetime = at(14, 0)
    sabha_start: dt.datetime = at(15, 30)
    sabha_end: dt.datetime = at(16, 30)
    last_game_end: dt.datetime = at(18, 40)
    wrap_up_end: dt.datetime = at(19, 0)
    courts: int = NUM_COURTS
    slot_min: int = SLOT_MIN

    @property
    def slot(self):
        return dt.timedelta(minutes=self.slot_min)

    @property
    def lunch_slots(self):
        return -(-LUNCH_MIN // self.slot_min)

    @property
    def max_gap_slots(self):
        """Longest wait between a team's games (and before its first): no longer than lunch."""
        return self.lunch_slots

    @property
    def group_slots(self):
        """Slots between the first game and Sabha."""
        return int((self.sabha_start - self.first_game) / self.slot)


def fmt(t):
    return t.strftime("%I:%M %p")


# ---------------------------------------------------------------------- groups

def group_games(size):
    """Games per team in a group: always GROUP_GAMES (8). Every team plays the same number,
    and 8 x size is always even, so the pairings always work out."""
    return GROUP_GAMES


def group_sizes(n_teams, plan):
    """Most even split into 4 groups (largest first); the games must fit before Sabha."""
    sizes = [n_teams // len(GROUPS) + (1 if i < n_teams % len(GROUPS) else 0)
             for i in range(len(GROUPS))]
    games = sum(g * group_games(g) // 2 for g in sizes)
    if games > plan.group_slots * plan.courts:
        raise ValueError(f"{n_teams} teams x {GROUP_GAMES} games ({games}) do not fit "
                         f"before Sabha ({plan.group_slots * plan.courts} court slots)")
    return sizes


def build_groups(n_teams, plan):
    """Group letter -> team numbers. Team numbers come from the random draw at check-in."""
    groups, t = {}, 1
    for letter, size in zip(GROUPS, group_sizes(n_teams, plan)):
        groups[letter] = list(range(t, t + size))
        t += size
    return groups


def group_pairings(members, games):
    """Pairings so that every team plays exactly `games` games inside its group.

    Group of games+1 or more: circulant pairing, each team plays the group-mates 1..games/2
    places either side of it around the group (plus the one opposite when games is odd),
    all different. Smaller group: everyone plays everyone, plus rematches to make up the
    count (group of 8: one rematch each, with the team opposite in the group).
    """
    size = len(members)
    if size - 1 >= games:
        offsets = list(range(1, games // 2 + 1)) + ([size // 2] if games % 2 else [])
        pairs = {frozenset((members[i], members[(i + o) % size]))
                 for i in range(size) for o in offsets}
        return sorted(tuple(sorted(p)) for p in pairs)
    if size % 2 or games - (size - 1) != 1:
        raise ValueError(f"a group of {size} cannot give everyone {games} games")
    pairs = [(a, b) for i, a in enumerate(members) for b in members[i + 1:]]
    pairs += [(members[i], members[i + size // 2]) for i in range(size // 2)]  # rematches
    return sorted(pairs)


# ------------------------------------------------------------------ group play

def lunch_window_slots(plan):
    """Slot indexes that lie fully inside the lunch window."""
    out, k = [], 0
    while True:
        start = plan.first_game + k * plan.slot
        if start > plan.lunch_end:
            return out
        if (start >= plan.lunch_start - EDGE_TOLERANCE
                and start + plan.slot <= plan.lunch_end + EDGE_TOLERANCE):
            out.append(k)
        k += 1


def court_shares(sizes, n_slots, courts, rotation=0):
    """Courts each group may use in each slot, or None if the games cannot fit.

    Every group gets courts // groups courts in every slot (2 of 9); the spare courts go to
    the groups that need more, spread evenly over the day (`rotation` shifts the pattern).
    """
    n = len(sizes)
    base, spare = courts // n, courts - courts // n * n
    need = [max(0, size * GROUP_GAMES // 2 - base * n_slots) for size in sizes]
    if sum(need) > spare * n_slots:
        return None
    # unneeded spare courts are shared out too: they give every group room to breathe
    extra = spare * n_slots - sum(need)
    target = [need[g] + extra * (g + 1) // n - extra * g // n for g in range(n)]
    caps = [[base] * n_slots for _ in range(n)]
    given = [0] * n
    for i in range(n_slots):
        k = (i + rotation) % n_slots
        for _ in range(spare):
            open_groups = [g for g in range(n) if given[g] < target[g]]
            if not open_groups:
                break
            g = min(open_groups, key=lambda g: (given[g] / target[g], g))
            caps[g][k] += 1
            given[g] += 1
    return caps


def build_pool(matches, teams, plan, n_slots, caps, optimize=True, work_limit=10.0):
    """Exact schedule (CP-SAT) for one group's games inside n_slots slots, or None.

    matches: (group, team_a, team_b); caps: courts the group may use in each slot.
    Constraints: one game per team per slot, at most MAX_IN_A_ROW games in a row, one lunch
    gap of `lunch_slots` empty slots inside the lunch window, and no wait longer than
    `max_gap_slots` empty slots between a team's games or before its first game. With
    optimize, also aims for the fewest back-to-back games. The solver runs single-threaded on
    a deterministic work limit, so the same inputs always give the same schedule.
    Returns (rows without courts, lunch, slot per match) or None.
    """
    slots = range(n_slots)
    window = [k for k in lunch_window_slots(plan) if k < n_slots]
    blocks = [b for b in window if all(b + j in window for j in range(plan.lunch_slots))]
    if not blocks:
        return None
    model = cp_model.CpModel()
    x = {(i, k): model.NewBoolVar(f"x{i}_{k}") for i in range(len(matches)) for k in slots}
    for i in range(len(matches)):
        model.AddExactlyOne(x[i, k] for k in slots)
    for k in slots:
        model.Add(sum(x[i, k] for i in range(len(matches))) <= caps[k])
    plays = {}
    for t in teams:
        mine = [i for i, (_, a, b) in enumerate(matches) if t in (a, b)]
        for k in slots:
            plays[t, k] = model.NewBoolVar(f"p{t}_{k}")
            model.Add(plays[t, k] == sum(x[i, k] for i in mine))
        for k in range(n_slots - MAX_IN_A_ROW):
            model.Add(sum(plays[t, k + j] for j in range(MAX_IN_A_ROW + 1)) <= MAX_IN_A_ROW)
        gap = plan.max_gap_slots
        model.Add(sum(plays[t, k] for k in range(gap + 1)) >= 1)  # first game soon after 10:00
        # played[k]: a game before slot k; more[k]: a game after slot k
        played = [model.NewConstant(0)] + [model.NewBoolVar(f"s{t}_{k}") for k in slots][1:]
        more = [model.NewBoolVar(f"m{t}_{k}") for k in slots][:-1] + [model.NewConstant(0)]
        for k in range(1, n_slots):
            model.AddMaxEquality(played[k], [played[k - 1], plays[t, k - 1]])
        for k in range(n_slots - 2, -1, -1):
            model.AddMaxEquality(more[k], [more[k + 1], plays[t, k + 1]])
        for k in range(n_slots - gap):  # gap+1 empty slots between two games is too long
            model.AddBoolOr([plays[t, k + j] for j in range(gap + 1)]
                            + [played[k].Not(), more[k + gap].Not()])
        lunch_choice = [model.NewBoolVar(f"l{t}_{b}") for b in blocks]
        model.AddBoolOr(lunch_choice)
        for chosen, b in zip(lunch_choice, blocks):
            for j in range(plan.lunch_slots):
                model.AddImplication(chosen, plays[t, b + j].Not())
    if optimize:
        back_to_back = []
        for t in teams:
            for k in range(n_slots - 1):
                z = model.NewBoolVar(f"b{t}_{k}")
                model.AddBoolOr([plays[t, k].Not(), plays[t, k + 1].Not(), z])
                back_to_back.append(z)
        model.Minimize(sum(back_to_back))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_deterministic_time = work_limit
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    assign = [next(k for k in slots if solver.Value(x[i, k])) for i in range(len(matches))]
    rows = [{"slot": assign[i], "group": g, "team_a": a, "team_b": b}
            for i, (g, a, b) in enumerate(matches)]
    lunch = {}
    for t in teams:
        busy = {k for k in slots if solver.Value(plays[t, k])}
        lunch[t] = next(b for b in blocks
                        if not any(b + j in busy for j in range(plan.lunch_slots)))
    return rows, lunch, assign


# -------------------------------------------------------------------- knockout

@dataclass
class Match:
    mid: str
    label: str
    team_a: str               # "A1" (group A, 1st place) or "W:<mid>" (winner of)
    team_b: str
    start: dt.datetime
    court: int
    deps: list = field(default_factory=list)
    minutes: int = SLOT_MIN   # court time: play + change-over (Final games: play only)

    @property
    def end(self):
        return self.start + dt.timedelta(minutes=self.minutes)


def build_knockout():
    """Round of 16, quarterfinals, semifinals with fixed times and courts, then the
    best-of-3 Final on court 1: games 1 and 2, and game 3 only if they split the first two."""
    matches = []
    cur = []
    for i, (a, b) in enumerate(ROUND_OF_16, start=1):
        code, label, start = KNOCKOUT_ROUNDS[0]
        matches.append(Match(f"{code}-{i}", label, a, b, start, i))
        cur.append(f"W:{code}-{i}")
    for code, label, start in KNOCKOUT_ROUNDS[1:]:
        nxt = []
        for i in range(0, len(cur), 2):
            mid = code if len(cur) == 2 else f"{code}-{i // 2 + 1}"
            a, b = cur[i], cur[i + 1]
            matches.append(Match(mid, label, a, b, start, i // 2 + 1, [a[2:], b[2:]]))
            nxt.append(f"W:{mid}")
        cur = nxt
    a, b = cur
    gap = dt.timedelta(minutes=GAME_PLAY_MIN + FINAL_BREAK_MIN)
    for g in range(1, FINAL_GAMES + 1):
        label = f"Final game {g}" + (" (if needed)" if g == FINAL_GAMES else "")
        deps = [a[2:], b[2:]] if g == 1 else [f"F-{g - 1}"]
        matches.append(Match(f"F-{g}", label, a, b, FINAL_START + (g - 1) * gap, 1, deps,
                             GAME_PLAY_MIN))
    return matches


# ----------------------------------------------------------------- whole day

@dataclass
class Day:
    n_teams: int
    plan: DayPlan
    groups: dict
    pool: list
    lunch: dict
    pool_end: dt.datetime
    matches: list

    def pool_time(self, row):
        return self.plan.first_game + row["slot"] * self.plan.slot

    def lunch_time(self, team):
        start = self.plan.first_game + self.lunch[team] * self.plan.slot
        return start, start + self.plan.lunch_slots * self.plan.slot

    def group_of(self, team):
        return next(g for g, members in self.groups.items() if team in members)

    @property
    def last_game_end(self):
        """End of play in the last possible game (Final game 3)."""
        return max(m.start for m in self.matches) + dt.timedelta(minutes=GAME_PLAY_MIN)


def build_day(n_teams, plan=None):
    plan = plan or DayPlan()
    groups = build_groups(n_teams, plan)
    matches = [(g, a, b) for g, members in groups.items()
               for a, b in group_pairings(members, group_games(len(members)))]
    lower = -(-len(matches) // plan.courts)
    # Groups only share courts, so each group is solved on its own with a fixed share of
    # the courts per slot; the fewest slots that work wins. Small, single-threaded solves
    # are fast and reproducible.
    result = None
    for n_slots in range(lower, plan.group_slots + 1):
        for rotation in range(SOLVER_ATTEMPTS):
            caps = court_shares([len(m) for m in groups.values()], n_slots, plan.courts,
                                rotation * n_slots // SOLVER_ATTEMPTS)
            if caps is None:
                break
            parts = []
            for (g, members), cap in zip(groups.items(), caps):
                part = build_pool([m for m in matches if m[0] == g], members, plan, n_slots, cap)
                if part is None:
                    break
                parts.append(part)
            else:
                result = parts
                break
        if result:
            break
    else:
        raise RuntimeError("group play does not fit before Sabha")
    rows, lunch = [], {}
    for part_rows, part_lunch, _ in result:
        rows += part_rows
        lunch.update(part_lunch)
    rows.sort(key=lambda r: (r["slot"], r["group"], r["team_a"]))
    court = {}
    for r in rows:  # courts 1, 2, ... in each slot, so the highest courts free up first
        court[r["slot"]] = court.get(r["slot"], 0) + 1
        r["court"] = court[r["slot"]]
    pool_end = plan.first_game + n_slots * plan.slot
    return Day(n_teams, plan, groups, rows, lunch, pool_end, build_knockout())


# ------------------------------------------------------------------- outputs

def describe(ref):
    if ref.startswith("W:"):
        return f"Winner of {ref[2:]}"
    places = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}
    return f"Group {ref[0]} {places[ref[1]]}"


def group_rows(day):
    return [{"group": g, "team": f"Team {t}", "group_size": len(members),
             "games_per_team": group_games(len(members))}
            for g, members in day.groups.items() for t in members]


def pool_rows(day):
    return [{"phase": "Group play", "group": r["group"], "time": fmt(day.pool_time(r)),
             "court": r["court"], "team_a": r["team_a"], "team_b": r["team_b"],
             "admin_override_court": ""} for r in day.pool]


def knockout_rows(day):
    nxt = {}
    for m in day.matches:
        for dep in m.deps:
            if not (m.mid.startswith("F-") and dep.startswith("F-")):  # games of one Final
                nxt[dep] = m.mid
    return [{"match_id": m.mid, "round": m.label, "time": fmt(m.start), "court": m.court,
             "team_a": describe(m.team_a), "team_b": describe(m.team_b),
             "winner_goes_to": nxt.get(m.mid, ""), "prereqs": " ".join(m.deps),
             "admin_override_court": ""}
            for m in sorted(day.matches, key=lambda m: (m.start, m.court))]


def team_games(day, team):
    return sorted((r for r in day.pool if team in (r["team_a"], r["team_b"])),
                  key=lambda r: r["slot"])


def per_team_rows(day):
    out = []
    for t in range(1, day.n_teams + 1):
        games = team_games(day, t)
        ks = [g["slot"] for g in games]
        rests = [(b - a - 1) * day.plan.slot_min for a, b in zip(ks, ks[1:])]
        ls, le = day.lunch_time(t)
        # the whole free stretch around the lunch block; after a team's last group game
        # it runs until the end of group play
        free_from = max((day.pool_time(g) + day.plan.slot for g in games
                         if day.pool_time(g) < ls), default=day.plan.first_game)
        free_to = min((day.pool_time(g) for g in games if day.pool_time(g) >= le),
                      default=day.pool_end)
        out.append({"team": f"Team {t}", "group": day.group_of(t), "games": len(games),
                    "first_game": fmt(day.pool_time(games[0])),
                    "last_game": fmt(day.pool_time(games[-1])),
                    "lunch": f"{fmt(ls)} - {fmt(le)}",
                    "lunch_break_min": int((free_to - free_from).total_seconds() // 60),
                    "longest_gap_between_games_min": max(rests) if rests else 0,
                    "back_to_back_games": sum(1 for r in rests if r == 0)})
    return out


def court_plan_rows(day):
    """Per court: games played and when its last game ends (the court is free after that).

    Each slot fills courts from 1 upward, so the highest-numbered courts free up first.
    """
    out = []
    for c in range(1, day.plan.courts + 1):
        pool = [day.pool_time(r) + day.plan.slot for r in day.pool if r["court"] == c]
        ko = [m.end for m in day.matches if m.court == c]
        ends = pool + ko
        out.append({"court": c, "group_games": len(pool), "knockout_games": len(ko),
                    "last_game_ends": fmt(max(ends)) if ends else "-"})
    return out


def team_slips(day):
    p = day.plan
    ko = {label: start for _, label, start in KNOCKOUT_ROUNDS}
    final = [m for m in day.matches if m.mid.startswith("F-")]
    lines = []
    for t in range(1, day.n_teams + 1):
        g = day.group_of(t)
        ls, le = day.lunch_time(t)
        lines += ["=" * 48, f"  TEAM {t} - SAMP CUP GROUP {g}", "=" * 48,
                  f"  Check-in / breakfast: {fmt(p.breakfast)}   Aarti: {fmt(p.aarti)}",
                  "-" * 48, f"{'Game':<6}{'Time':<10}{'Court':<7}Opponent"]
        for i, r in enumerate(team_games(day, t), start=1):
            opp = r["team_b"] if r["team_a"] == t else r["team_a"]
            lines.append(f"{i:<6}{fmt(day.pool_time(r)):<10}{r['court']:<7}Team {opp}")
        lines += ["-" * 48,
                  f"  Your lunch: {fmt(ls)} - {fmt(le)} (no games for you)",
                  f"  Top 4 of Group {g} go to the Round of 16 ({fmt(ko['Round of 16'])}).",
                  f"  Quarterfinals {fmt(ko['Quarterfinal'])}, semifinals {fmt(ko['Semifinal'])}.",
                  f"  Final: best of 3 games from {fmt(final[0].start)}, first to win 2.",
                  "  Standings and bracket posted during Sabha.",
                  f"  Sabha, group photo, awards: {fmt(p.sabha_start)} - {fmt(p.sabha_end)}",
                  ""]
    return "\n".join(lines)


def write_outputs(day, prefix):
    tables = (
        ("groups.csv", ["group", "team", "group_size", "games_per_team"], group_rows(day)),
        ("pool_schedule.csv", ["phase", "group", "time", "court", "team_a", "team_b",
                               "admin_override_court"], pool_rows(day)),
        ("knockout_schedule.csv", ["match_id", "round", "time", "court", "team_a", "team_b",
                                   "winner_goes_to", "prereqs", "admin_override_court"],
         knockout_rows(day)),
        ("per_team.csv", ["team", "group", "games", "first_game", "last_game", "lunch",
                          "lunch_break_min", "longest_gap_between_games_min",
                          "back_to_back_games"], per_team_rows(day)),
        ("court_plan.csv", ["court", "group_games", "knockout_games", "last_game_ends"],
         court_plan_rows(day)),
    )
    files = []
    for name, fields, rows in tables:
        path = f"{prefix}{name}"
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        files.append(path)
    path = f"{prefix}team_slips.txt"
    with open(path, "w") as f:
        f.write(team_slips(day))
    files.append(path)
    return files


def print_summary(day):
    p = day.plan
    print(f"Teams: {day.n_teams}   Courts: {p.courts}   Slot: {GAME_PLAY_MIN} min play + "
          f"{p.slot_min - GAME_PLAY_MIN} min change-over ({p.slot_min} min)")
    print(f"Breakfast & warm-up {fmt(p.breakfast)}, Aarti & Deep pragatya {fmt(p.aarti)}")
    for g, members in day.groups.items():
        print(f"  Group {g}: {len(members)} teams (Teams {members[0]}-{members[-1]}), "
              f"{group_games(len(members))} games each")
    print(f"Group play: {len(day.pool)} games, {fmt(p.first_game)} - {fmt(day.pool_end)} "
          f"(rolling lunch {fmt(p.lunch_start)} - {fmt(p.lunch_end)}, "
          f"{p.lunch_slots * p.slot_min} min per team)")
    print(f"Sabha {fmt(p.sabha_start)} - {fmt(p.sabha_end)} (standings and bracket posted)")
    for code, label, start in KNOCKOUT_ROUNDS:
        n = sum(1 for m in day.matches if m.label == label)
        print(f"  {label}: {n} game{'s' if n > 1 else ''} at {fmt(start)}")
    final = [m for m in day.matches if m.mid.startswith("F-")]
    print("  Final (best of 3, court 1): " + ", ".join(
        f"game {i} {fmt(m.start)}" for i, m in enumerate(final, start=1))
        + f"; ends {fmt(final[1].start + dt.timedelta(minutes=GAME_PLAY_MIN))} if 2-0")
    end = day.last_game_end
    print(f"Last possible game ends: {fmt(end)} ({'OK' if end <= p.last_game_end else 'LATE'}; "
          f"must end by {fmt(p.last_game_end)})")
    print("Courts free after: " + ", ".join(
        f"court {r['court']} {r['last_game_ends']}" for r in court_plan_rows(day)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", type=int, default=40)
    parser.add_argument("--prefix", default=None,
                        help="output file prefix (default sampcup_<N>team_)")
    args = parser.parse_args()
    if not MIN_TEAMS <= args.teams <= MAX_TEAMS:
        parser.error(f"--teams must be between {MIN_TEAMS} and {MAX_TEAMS}")
    day = build_day(args.teams)
    print_summary(day)
    files = write_outputs(day, args.prefix or f"sampcup_{args.teams}team_")
    print("\nWrote: " + ", ".join(files))


if __name__ == "__main__":
    main()
