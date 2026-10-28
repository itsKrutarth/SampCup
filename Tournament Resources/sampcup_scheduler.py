"""
SampCup 2026 Tournament Scheduler
=================================
One-day pickleball tournament: pool play for seeding, then Gold and Silver brackets.

  Pool play       every team plays 6 games (circle-method pairings by team number)
  Gold bracket    every team, single elimination by seed (play-in games when > 32 teams)
  Silver bracket  losers of the Gold play-in, Round of 32 and Round of 16 drop in here
                  (second chance, own champion)
  Placement       Gold quarterfinal losers play for 5th-8th, semifinal losers for 3rd

Day plan: first game 10:00 AM, rolling lunch 12:00-2:00 PM, Sabha 3:30-4:30 PM (no games),
Gold Round of 16 onward after Sabha, last game ends by 6:30 PM.
Rules: 17-minute slots (12 min play + 5 min change-over), at most 3 games in a row per team,
every team gets a lunch break of at least 45 min between 12:00 and 2:00.

Produces:
  sampcup_<N>team_pool_schedule.csv
  sampcup_<N>team_knockout_schedule.csv
  sampcup_<N>team_per_team.csv
  sampcup_<N>team_team_slips.txt

Requires: ortools  (pip install ortools)
Run: python sampcup_scheduler.py --teams 40
Check: python check_schedule.py --teams 32-42
"""

import argparse
import csv
import datetime as dt
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

SLOT_MIN = 17            # 12 min play + 5 min change-over
GAME_PLAY_MIN = 12
NUM_COURTS = 9
POOL_GAMES = 6
MAX_IN_A_ROW = 3
LUNCH_MIN = 45
SEEDING_BREAK_SLOTS = 1  # empty slot between pool play and the first knockout game
EDGE_TOLERANCE = dt.timedelta(minutes=5)  # a slot starting at 11:59 counts as noon
DAY = dt.date(2026, 1, 1)


def at(hour, minute):
    return dt.datetime.combine(DAY, dt.time(hour, minute))


@dataclass
class DayPlan:
    breakfast: dt.datetime = at(9, 0)
    aarti: dt.datetime = at(9, 45)
    first_game: dt.datetime = at(10, 0)
    lunch_start: dt.datetime = at(12, 0)
    lunch_end: dt.datetime = at(14, 0)
    sabha_start: dt.datetime = at(15, 30)
    sabha_end: dt.datetime = at(16, 30)
    last_game_end: dt.datetime = at(18, 30)
    wrap_up_end: dt.datetime = at(19, 0)
    courts: int = NUM_COURTS
    slot_min: int = SLOT_MIN

    @property
    def slot(self):
        return dt.timedelta(minutes=self.slot_min)

    @property
    def lunch_slots(self):
        return -(-LUNCH_MIN // self.slot_min)


def fmt(t):
    return t.strftime("%I:%M %p")


# ------------------------------------------------------------------ pool play

def circle_method_rounds(n_teams, n_rounds):
    """Circle-method pairings; odd team counts receive a rotating bye."""
    teams = list(range(1, n_teams + 1))
    if n_teams % 2 == 1:
        teams.append(None)
    n = len(teams)
    arr, rounds = teams[:], []
    for _ in range(n_rounds):
        rounds.append([(arr[i], arr[n - 1 - i]) for i in range(n // 2)
                       if arr[i] is not None and arr[n - 1 - i] is not None])
        arr = [arr[0], arr[-1]] + arr[1:-1]
    return rounds


def lunch_window_slots(plan):
    """Pool slot indexes that lie fully inside the lunch window."""
    out, k = [], 0
    while True:
        start = plan.first_game + k * plan.slot
        if start > plan.lunch_end:
            return out
        if (start >= plan.lunch_start - EDGE_TOLERANCE
                and start + plan.slot <= plan.lunch_end + EDGE_TOLERANCE):
            out.append(k)
        k += 1


def build_pool(n_teams, plan, n_slots, optimize=True, work_limit=20.0):
    """Exact pool schedule (CP-SAT) inside n_slots slots, or None if none was found.

    Constraints: fixed pairings, at most `courts` games per slot, one game per team per
    slot, at most MAX_IN_A_ROW games in a row, and one lunch gap of `lunch_slots` empty
    slots inside the lunch window. With optimize, also aims for the fewest back-to-back
    games.
    The solver runs single-threaded on a deterministic work limit, so the same inputs
    always give the same schedule.
    """
    rounds = circle_method_rounds(n_teams, POOL_GAMES)
    matches = [(r, a, b) for r, pairs in enumerate(rounds, start=1) for a, b in pairs]
    slots = range(n_slots)
    teams = range(1, n_teams + 1)
    window = [k for k in lunch_window_slots(plan) if k < n_slots]
    blocks = [b for b in window if all(b + j in window for j in range(plan.lunch_slots))]
    if not blocks:
        return None
    model = cp_model.CpModel()
    x = {(i, k): model.NewBoolVar(f"x{i}_{k}") for i in range(len(matches)) for k in slots}
    for i in range(len(matches)):
        model.AddExactlyOne(x[i, k] for k in slots)
    for k in slots:
        model.Add(sum(x[i, k] for i in range(len(matches))) <= plan.courts)
    plays = {}
    for t in teams:
        mine = [i for i, (_, a, b) in enumerate(matches) if t in (a, b)]
        for k in slots:
            plays[t, k] = model.NewBoolVar(f"p{t}_{k}")
            model.Add(plays[t, k] == sum(x[i, k] for i in mine))
        for k in range(n_slots - MAX_IN_A_ROW):
            model.Add(sum(plays[t, k + j] for j in range(MAX_IN_A_ROW + 1)) <= MAX_IN_A_ROW)
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
    rows = []
    for k in slots:
        here = sorted(matches[i] for i in range(len(matches)) if solver.Value(x[i, k]))
        for court, (r, a, b) in enumerate(here, start=1):
            rows.append({"slot": k, "court": court, "round": r, "team_a": a, "team_b": b})
    lunch = {}
    for t in teams:
        busy = {k for k in slots if solver.Value(plays[t, k])}
        lunch[t] = next(b for b in blocks
                        if not any(b + j in busy for j in range(plan.lunch_slots)))
    return rows, lunch


# ------------------------------------------------------- Gold / Silver brackets

@dataclass
class Match:
    mid: str
    bracket: str              # Gold, Silver or Placement
    label: str
    team_a: str               # "Seed 5", "W:<mid>" (winner of), "L:<mid>" (loser of)
    team_b: str
    after_sabha: bool = False
    deps: list = field(default_factory=list)
    slot: int = None
    court: int = None


def standard_bracket_order(n):
    """Classic single-elimination seeding order; n must be a power of two."""
    if n == 1:
        return [1]
    prev = standard_bracket_order(n // 2)
    return [x for s in prev for x in (s, n + 1 - s)]


def build_brackets(n_teams):
    """Gold bracket, Silver bracket and placement games, with BYE matches removed.

    Gold round r of R has bracket size 2**(R - r + 1). Silver takes losers of Gold rounds
    up to the Round of 16: its first round pairs first-round Gold losers, then each later
    Gold round's losers drop in against the Silver survivors (reversed / half-swapped to
    avoid quick rematches), with a halving round in between. Silver then halves to a final.
    """
    R = max(4, (n_teams - 1).bit_length())
    size = 2 ** R
    order = standard_bracket_order(size)
    raw, gold = [], {}
    for r in range(1, R + 1):
        gold[r] = []
        for i in range(size >> r):
            mid = f"g{r}-{i}"
            if r == 1:
                sa, sb = order[2 * i], order[2 * i + 1]
                a = f"Seed {sa}" if sa <= n_teams else "BYE"
                b = f"Seed {sb}" if sb <= n_teams else "BYE"
            else:
                a, b = f"W:{gold[r - 1][2 * i]}", f"W:{gold[r - 1][2 * i + 1]}"
            raw.append(("Gold", r, mid, a, b))
            gold[r].append(mid)
    last_drop = R - 3  # Gold Round of 16
    sr, cur = 1, []
    for i in range(size >> 2):
        mid = f"s{sr}-{i}"
        raw.append(("Silver", sr, mid, f"L:{gold[1][2 * i]}", f"L:{gold[1][2 * i + 1]}"))
        cur.append(mid)
    for k in range(1, last_drop):
        drops = gold[k + 1][:]
        if k % 2 == 1:
            drops.reverse()
        elif len(drops) > 1:
            drops = drops[len(drops) // 2:] + drops[:len(drops) // 2]
        sr += 1
        nxt = []
        for i, d in enumerate(drops):
            mid = f"s{sr}-{i}"
            raw.append(("Silver", sr, mid, f"W:{cur[i]}", f"L:{d}"))
            nxt.append(mid)
        cur = nxt
        if k < last_drop - 1:
            sr += 1
            nxt = []
            for i in range(len(cur) // 2):
                mid = f"s{sr}-{i}"
                raw.append(("Silver", sr, mid, f"W:{cur[2 * i]}", f"W:{cur[2 * i + 1]}"))
                nxt.append(mid)
            cur = nxt
    while len(cur) > 1:
        sr += 1
        nxt = []
        for i in range(len(cur) // 2):
            mid = f"s{sr}-{i}"
            raw.append(("Silver", sr, mid, f"W:{cur[2 * i]}", f"W:{cur[2 * i + 1]}"))
            nxt.append(mid)
        cur = nxt
    qf, sf = gold[R - 2], gold[R - 1]
    for i in range(0, len(qf), 2):
        raw.append(("Placement", 5, f"p5-{i // 2}", f"L:{qf[i]}", f"L:{qf[i + 1]}"))
    raw.append(("Placement", 3, "p3-0", f"L:{sf[0]}", f"L:{sf[1]}"))
    return _name_matches(_remove_byes(raw), R)


def _remove_byes(raw):
    """Drop matches with a BYE side and point their references at the real team."""
    bye_result = {}  # mid -> (winner ref, loser ref)
    out = []

    def resolve(ref):
        if ref[:2] in ("W:", "L:") and ref[2:] in bye_result:
            return bye_result[ref[2:]][0 if ref[0] == "W" else 1]
        return ref

    for bracket, rnd, mid, a, b in raw:
        a, b = resolve(a), resolve(b)
        if "BYE" in (a, b):
            bye_result[mid] = (b if a == "BYE" else a, "BYE")
            continue
        out.append((bracket, rnd, mid, a, b))
    return out


def _name_matches(raw, R):
    silver_rounds = sorted({rnd for br, rnd, *_ in raw if br == "Silver"})
    silver_no = {r: i + 1 for i, r in enumerate(silver_rounds)}
    s_last = len(silver_rounds)
    s_count = {}
    for br, rnd, *_ in raw:
        if br == "Silver":
            s_count[silver_no[rnd]] = s_count.get(silver_no[rnd], 0) + 1
    rename, seen, named = {}, {}, []
    for br, rnd, mid, a, b in raw:
        after = False
        if br == "Gold":
            bsize = 2 ** (R - rnd + 1)
            code, label = {2: ("F", "Gold Final"), 4: ("SF", "Gold Semifinal"),
                           8: ("QF", "Gold Quarterfinal")}.get(
                bsize, (f"R{bsize}", f"Gold Round of {bsize}"))
            if bsize > 32:
                code, label = "PI", "Gold Play-in"
            after = bsize <= 16
            prefix = f"G-{code}"
        elif br == "Silver":
            n = silver_no[rnd]
            if n == s_last:
                prefix, label = "S-F", "Silver Final"
            elif n == s_last - 1 and s_count[n] == 2:
                prefix, label = "S-SF", "Silver Semifinal"
            else:
                prefix, label = f"S-R{n}", f"Silver Round {n}"
        else:
            prefix, label = ("G-3RD", "Gold 3rd Place") if rnd == 3 else ("G-5TH", "Gold 5th-8th Place")
            after = True
        seen[prefix] = seen.get(prefix, 0) + 1
        rename[mid] = prefix
        named.append([br, label, after, prefix, seen[prefix], mid, a, b])
    final_ids = {}
    for row in named:
        prefix, idx, mid = row[3], row[4], row[5]
        final_ids[mid] = prefix if seen[prefix] == 1 else f"{prefix}-{idx}"

    def ref(r):
        return r if r.startswith("Seed ") else f"{r[:2]}{final_ids[r[2:]]}"

    out = []
    for br, label, after, _, _, mid, a, b in named:
        a, b = ref(a), ref(b)
        deps = [r[2:] for r in (a, b) if r[:2] in ("W:", "L:")]
        out.append(Match(final_ids[mid], br, label, a, b, after, deps))
    return out


# ---------------------------------------------------------- knockout schedule

def knockout_slots(plan, first_start):
    """(start time, after_sabha) for every usable knockout slot, plus overflow room."""
    out, t = [], first_start
    while t + plan.slot <= plan.sabha_start:
        out.append((t, False))
        t += plan.slot
    t = max(plan.sabha_end, first_start)
    limit = plan.last_game_end + dt.timedelta(hours=3)  # room to report an overrun
    while t + plan.slot <= limit:
        out.append((t, True))
        t += plan.slot
    return out


def schedule_knockout(matches, slots, courts):
    """Dependency-aware list scheduling with team rest.

    A match waits until its feeder matches are done. A team never plays more than
    MAX_IN_A_ROW slots in a row: each match carries the longest run of back-to-back
    games any of its teams can arrive with, whatever the earlier results were.
    Sabha resets every run. Longest remaining chain goes first.
    """
    by_id = {m.mid: m for m in matches}
    children = {m.mid: [] for m in matches}
    for m in matches:
        for d in m.deps:
            children[d].append(m.mid)
    depth = {}

    def chain(mid):
        if mid not in depth:
            depth[mid] = 1 + max((chain(c) for c in children[mid]), default=0)
        return depth[mid]

    run = {}
    left = list(matches)
    si = 0
    while left:
        if si == len(slots):
            raise RuntimeError("knockout does not fit in the available slots")
        after = slots[si][1]
        ready = []
        for m in left:
            if m.after_sabha and not after:
                continue
            if not all(by_id[d].slot is not None and by_id[d].slot < si for d in m.deps):
                continue
            arriving = max((run[d] for d in m.deps
                            if by_id[d].slot == si - 1 and slots[si - 1][1] == after), default=0)
            if arriving < MAX_IN_A_ROW:
                ready.append((m, arriving + 1))
        ready.sort(key=lambda x: (-chain(x[0].mid), x[1], x[0].mid))
        for m, r in ready[:courts]:
            m.slot = si
            run[m.mid] = r
            left.remove(m)
        si += 1
    # The Gold Final closes the day next to the Silver Final. Moving a last game later
    # only lengthens its teams' rest.
    final = by_id["G-F"]
    last = max(m.slot for m in matches)
    if final.slot < last and sum(1 for m in matches if m.slot == last) < courts:
        final.slot = last
    order = {"G-F": 0, "S-F": 1}
    for s in sorted({m.slot for m in matches}):
        here = sorted((m for m in matches if m.slot == s),
                      key=lambda m: (order.get(m.mid, 2), m.bracket != "Gold", m.mid))
        for court, m in enumerate(here, start=1):
            m.court = court


# ----------------------------------------------------------------- whole day

@dataclass
class Day:
    n_teams: int
    plan: DayPlan
    pool: list
    lunch: dict
    pool_end: dt.datetime
    knockout_start: dt.datetime
    matches: list
    slots: list

    def pool_time(self, row):
        return self.plan.first_game + row["slot"] * self.plan.slot

    def match_time(self, m):
        return self.slots[m.slot][0]

    def lunch_time(self, team):
        start = self.plan.first_game + self.lunch[team] * self.plan.slot
        return start, start + self.plan.lunch_slots * self.plan.slot

    @property
    def last_game_end(self):
        return max(self.match_time(m) for m in self.matches) + self.plan.slot


def build_day(n_teams, plan=None):
    plan = plan or DayPlan()
    n_pool = len([p for r in circle_method_rounds(n_teams, POOL_GAMES) for p in r])
    lower = -(-n_pool // plan.courts)
    # quick feasibility pass for the fewest slots, then optimise rest at that size
    for n_slots in range(lower, lower + 12):
        if build_pool(n_teams, plan, n_slots, optimize=False, work_limit=10.0):
            break
    else:
        raise RuntimeError("could not build a pool schedule")
    rows, lunch = build_pool(n_teams, plan, n_slots)
    used = max(r["slot"] for r in rows) + 1
    pool_end = plan.first_game + used * plan.slot
    knockout_start = pool_end + SEEDING_BREAK_SLOTS * plan.slot
    matches = build_brackets(n_teams)
    slots = knockout_slots(plan, knockout_start)
    schedule_knockout(matches, slots, plan.courts)
    return Day(n_teams, plan, rows, lunch, pool_end, knockout_start, matches, slots)


# ------------------------------------------------------------------- outputs

def describe(ref):
    if ref.startswith("Seed "):
        return ref
    return f"{'Winner' if ref[0] == 'W' else 'Loser'} of {ref[2:]}"


def pool_rows(day):
    return [{"phase": "Pool Play", "round": r["round"], "time": fmt(day.pool_time(r)),
             "court": r["court"], "team_a": r["team_a"], "team_b": r["team_b"],
             "admin_override_court": ""} for r in day.pool]


def knockout_rows(day):
    nxt = {}
    for m in day.matches:
        for ref in (m.team_a, m.team_b):
            if ref[:2] in ("W:", "L:"):
                nxt[(ref[2:], ref[0])] = m.mid
    out = []
    for m in sorted(day.matches, key=lambda m: (m.slot, m.court)):
        out.append({"match_id": m.mid, "bracket": m.bracket, "round": m.label,
                    "time": fmt(day.match_time(m)), "court": m.court,
                    "team_a": describe(m.team_a), "team_b": describe(m.team_b),
                    "winner_goes_to": nxt.get((m.mid, "W"), ""),
                    "loser_goes_to": nxt.get((m.mid, "L"), ""),
                    "prereqs": " ".join(m.deps), "admin_override_court": ""})
    return out


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
        # the whole free stretch around the lunch block; after a team's last pool game
        # it runs until the knockout starts
        free_from = max((day.pool_time(g) + day.plan.slot for g in games
                         if day.pool_time(g) < ls), default=day.plan.first_game)
        free_to = min((day.pool_time(g) for g in games if day.pool_time(g) >= le),
                      default=day.knockout_start)
        out.append({"team": f"Team {t}", "pool_games": len(games),
                    "first_game": fmt(day.pool_time(games[0])),
                    "last_pool_game": fmt(day.pool_time(games[-1])),
                    "lunch": f"{fmt(ls)} - {fmt(le)}",
                    "lunch_break_min": int((free_to - free_from).total_seconds() // 60),
                    "longest_gap_between_pool_games_min": max(rests) if rests else 0,
                    "back_to_back_games": sum(1 for r in rests if r == 0)})
    return out


def team_slips(day):
    p = day.plan
    lines = []
    for t in range(1, day.n_teams + 1):
        ls, le = day.lunch_time(t)
        lines += ["=" * 48, f"  TEAM {t} - SAMP CUP POOL PLAY", "=" * 48,
                  f"  Check-in / breakfast: {fmt(p.breakfast)}   Aarti: {fmt(p.aarti)}",
                  "-" * 48, f"{'Game':<6}{'Time':<10}{'Court':<7}Opponent"]
        for i, g in enumerate(team_games(day, t), start=1):
            opp = g["team_b"] if g["team_a"] == t else g["team_a"]
            lines.append(f"{i:<6}{fmt(day.pool_time(g)):<10}{g['court']:<7}Team {opp}")
        lines += ["-" * 48,
                  f"  Your lunch: {fmt(ls)} - {fmt(le)} (no games for you)",
                  f"  Seeding posted {fmt(day.pool_end)}; knockout starts {fmt(day.knockout_start)}.",
                  "  Every team plays in the Gold bracket. Lose once before the",
                  "  Gold quarterfinals and you move to the Silver bracket.",
                  f"  Sabha, group photo, awards: {fmt(p.sabha_start)} - {fmt(p.sabha_end)}",
                  "  Check the live bracket for your next match, time & court.",
                  ""]
    return "\n".join(lines)


def write_outputs(day, prefix):
    pool_fields = ["phase", "round", "time", "court", "team_a", "team_b", "admin_override_court"]
    ko_fields = ["match_id", "bracket", "round", "time", "court", "team_a", "team_b",
                 "winner_goes_to", "loser_goes_to", "prereqs", "admin_override_court"]
    team_fields = ["team", "pool_games", "first_game", "last_pool_game", "lunch",
                   "lunch_break_min", "longest_gap_between_pool_games_min",
                   "back_to_back_games"]
    files = []
    for name, fields, rows in (("pool_schedule.csv", pool_fields, pool_rows(day)),
                               ("knockout_schedule.csv", ko_fields, knockout_rows(day)),
                               ("per_team.csv", team_fields, per_team_rows(day))):
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
    counts = {}
    for m in day.matches:
        counts[m.label] = counts.get(m.label, 0) + 1
    print(f"Teams: {day.n_teams}   Courts: {p.courts}   Slot: {GAME_PLAY_MIN} min play + "
          f"{p.slot_min - GAME_PLAY_MIN} min change-over ({p.slot_min} min)")
    print(f"Breakfast & warm-up {fmt(p.breakfast)}, Aarti & Deep pragatya {fmt(p.aarti)}")
    print(f"Pool play: {len(day.pool)} matches, {fmt(p.first_game)} - {fmt(day.pool_end)} "
          f"(rolling lunch {fmt(p.lunch_start)} - {fmt(p.lunch_end)}, "
          f"{p.lunch_slots * p.slot_min} min per team)")
    print(f"Seeding break: {fmt(day.pool_end)} - {fmt(day.knockout_start)}")
    print(f"Knockout: {len(day.matches)} matches from {fmt(day.knockout_start)}; "
          f"Sabha {fmt(p.sabha_start)} - {fmt(p.sabha_end)}")
    for label, n in counts.items():
        print(f"  {label}: {n}")
    end = day.last_game_end
    print(f"Last game ends: {fmt(end)} "
          f"({'OK' if end <= p.last_game_end else 'LATE'}; wrap-up until {fmt(p.wrap_up_end)})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", type=int, default=40)
    parser.add_argument("--prefix", default=None,
                        help="output file prefix (default sampcup_<N>team_)")
    args = parser.parse_args()
    if not 16 <= args.teams <= 64:
        parser.error("--teams must be between 16 and 64 (planned range 32-42)")
    day = build_day(args.teams)
    print_summary(day)
    files = write_outputs(day, args.prefix or f"sampcup_{args.teams}team_")
    print("\nWrote: " + ", ".join(files))


if __name__ == "__main__":
    main()
