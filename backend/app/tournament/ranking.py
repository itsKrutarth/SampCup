"""Group standings for SAMP Cup (rank each group separately).

Order: 1) most wins  2) most points scored  3) lowest average game time
       4) fewest points allowed  5) head-to-head (exactly two teams still tied:
       more wins in the games between them)  6) random draw (seeded, so the same results
       always give the same order; the admin logs the seed)
Game time for ranking: the real seconds from first serve to the 11th point when the game
reached 11; 720 s (12:00) when the clock ended it (lead or sudden death) or for a forfeit.
A game tied when the clock ends is settled by one sudden-death point added to the winner.
"""
import random

CLOCK_CAP = 12 * 60
END_REASONS = ("reached_11", "clock_lead", "sudden_death", "forfeit")
STEPS = ("wins", "points scored", "average game time", "points allowed", "head-to-head",
         "random draw")


def resolve_clock_end(score_a, score_b, sudden_death_winner=None):
    """Final score when the clock ends: the leader wins, or one sudden-death point decides."""
    if score_a == score_b:
        if sudden_death_winner not in ("a", "b"):
            raise ValueError("Tied at clock end: sudden-death winner required")
        return (score_a + 1, score_b) if sudden_death_winner == "a" else (score_a, score_b + 1)
    return score_a, score_b


def ranking_seconds(end_reason, seconds):
    """Seconds that count for the time tiebreak."""
    return min(seconds, CLOCK_CAP) if end_reason == "reached_11" else CLOCK_CAP


def check_game(game):
    """Reject results that cannot happen under the game rules."""
    a, b, reason = game["score_a"], game["score_b"], game["end_reason"]
    if reason not in END_REASONS:
        raise ValueError(f"unknown end_reason {reason!r}")
    if a == b:
        raise ValueError(f"tied final score {a}-{b}: a game always has a winner")
    if reason == "reached_11" and max(a, b) != 11:
        raise ValueError(f"reached_11 needs a score of 11, got {a}-{b}")
    if reason in ("clock_lead", "sudden_death") and max(a, b) > 11:
        raise ValueError(f"clock-ended game cannot pass 11, got {a}-{b}")
    if reason == "sudden_death" and abs(a - b) != 1:
        raise ValueError(f"sudden death ends one point apart, got {a}-{b}")
    if reason == "forfeit" and sorted((a, b)) != [0, 11]:
        raise ValueError(f"forfeit is recorded 11-0, got {a}-{b}")


def rank_teams(teams, games, seed=0):
    """Rank one group.

    teams: team ids in the group (every team is ranked, even with no games yet).
    games: dicts with team_a, team_b, score_a, score_b, end_reason, seconds.
    Returns one dict per team in rank order: rank, team, wins, points_for, avg_seconds,
    points_against, decided_by (the step that put the team below the one above it;
    "" for rank 1).
    """
    s = {t: {"w": 0, "pf": 0, "pa": 0, "t": 0, "g": 0} for t in teams}
    h2h = {}
    for g in games:
        check_game(g)
        a, b = g["team_a"], g["team_b"]
        sa, sb = g["score_a"], g["score_b"]
        sec = ranking_seconds(g["end_reason"], g["seconds"])
        for x, f, o in ((a, sa, sb), (b, sb, sa)):
            s[x]["pf"] += f
            s[x]["pa"] += o
            s[x]["t"] += sec
            s[x]["g"] += 1
        win = a if sa > sb else b
        s[win]["w"] += 1
        h2h[(a, b)] = h2h.get((a, b), 0) + (win == a)
        h2h[(b, a)] = h2h.get((b, a), 0) + (win == b)

    def avg(t):
        return round(s[t]["t"] / s[t]["g"], 1) if s[t]["g"] else float(CLOCK_CAP)

    keys = (lambda t: -s[t]["w"], lambda t: -s[t]["pf"], avg, lambda t: s[t]["pa"])
    rng = random.Random(seed)
    order, reason = [], {}

    def place(group, step):
        if len(group) == 1:
            order.append(group[0])
            return
        if step < len(keys):
            group = sorted(group, key=keys[step])
            i = 0
            while i < len(group):
                j = i
                while j < len(group) and keys[step](group[j]) == keys[step](group[i]):
                    j += 1
                start = len(order)
                place(group[i:j], step + 1)
                if i:  # this step separated the sub-group's top team from the team above
                    reason[order[start]] = STEPS[step]
                i = j
            return
        a, b = (group + [None])[:2]
        if len(group) == 2 and (a, b) in h2h and h2h[(a, b)] != h2h[(b, a)]:
            group = [a, b] if h2h[(a, b)] > h2h[(b, a)] else [b, a]
            reason[group[1]] = STEPS[4]
        else:
            group = sorted(group)
            rng.shuffle(group)
            for t in group[1:]:
                reason[t] = STEPS[5]
        order.extend(group)

    place(sorted(teams), 0)
    return [{"rank": r, "team": t, "wins": s[t]["w"], "points_for": s[t]["pf"],
             "avg_seconds": avg(t), "points_against": s[t]["pa"],
             "decided_by": reason.get(t, "") if r > 1 else ""}
            for r, t in enumerate(order, start=1)]


def _game(a, b, sa, sb, reason="reached_11", sec=400):
    return {"team_a": a, "team_b": b, "score_a": sa, "score_b": sb, "end_reason": reason,
            "seconds": sec}


if __name__ == "__main__":
    assert resolve_clock_end(8, 8, "a") == (9, 8)
    assert resolve_clock_end(8, 8, "b") == (8, 9)
    assert resolve_clock_end(9, 7) == (9, 7)
    # same wins and points: the faster team ranks higher
    g = [_game("X", "P", 11, 5, sec=400), _game("X", "Q", 11, 6, sec=420), _game("X", "R", 11, 4, sec=380),
         _game("Y", "P", 11, 9, sec=300), _game("Y", "Q", 11, 10, sec=310), _game("Y", "R", 11, 4, sec=290)]
    r = rank_teams(["X", "Y", "P", "Q", "R"], g)
    assert [x["team"] for x in r][:2] == ["Y", "X"], r
    assert r[1]["decided_by"] == "average game time", r
    # a clock-ended or sudden-death game counts as 12:00 even if it was quick
    g2 = g[:5] + [_game("Y", "R", 10, 9, "sudden_death", sec=200)]
    r2 = rank_teams(["X", "Y", "P", "Q", "R"], g2)
    assert r2[0]["team"] == "X", r2  # X has more points; Y's last game counts 720 s
    # exactly two teams tied on everything: head-to-head decides
    g3 = [_game("A", "B", 11, 9), _game("B", "C", 11, 9), _game("C", "A", 11, 9),
          _game("A", "D", 11, 9), _game("B", "D", 11, 9), _game("C", "D", 9, 11)]
    r3 = rank_teams(["A", "B", "C", "D"], g3)
    assert {x["team"] for x in r3[:2]} == {"A", "B"} and r3[0]["team"] == "A", r3
    assert r3[1]["decided_by"] == "head-to-head", r3
    # three-way tie on everything: random draw, the same every time for the same seed
    g4 = [_game("A", "B", 11, 9), _game("B", "C", 11, 9), _game("C", "A", 11, 9)]
    r4 = rank_teams(["A", "B", "C"], g4, seed=7)
    assert r4 == rank_teams(["A", "B", "C"], g4, seed=7)
    assert [x["decided_by"] for x in r4] == ["", "random draw", "random draw"], r4
    # two tied teams that split two games (a rematch): head-to-head cannot decide
    g5 = [_game("A", "B", 11, 9), _game("B", "A", 11, 9)]
    r5 = rank_teams(["A", "B"], g5, seed=1)
    assert r5[1]["decided_by"] == "random draw", r5
    # ranks are a permutation; a team with no games yet still appears
    r6 = rank_teams(["A", "B", "C", "Z"], g4)
    assert sorted(x["rank"] for x in r6) == [1, 2, 3, 4] and r6[-1]["team"] == "Z"
    # a later step reorders a tied block: each team keeps the step that separated it
    g7 = [_game("A", "B", 11, 0), _game("A", "C", 11, 0), _game("A", "D", 11, 0),
          _game("B", "C", 11, 9), _game("C", "D", 11, 10), _game("D", "B", 11, 1)]
    r7 = rank_teams(["A", "B", "C", "D"], g7)
    assert [(x["team"], x["decided_by"]) for x in r7] == [
        ("A", ""), ("D", "wins"), ("C", "points scored"), ("B", "points scored")], r7
    # impossible results are rejected
    for bad in (_game("A", "B", 9, 9), _game("A", "B", 11, 9, "forfeit"),
                _game("A", "B", 10, 8, "reached_11"), _game("A", "B", 9, 7, "sudden_death"),
                _game("A", "B", 11, 9, "timeout")):
        try:
            rank_teams(["A", "B"], [bad])
        except ValueError:
            continue
        raise AssertionError(f"accepted an impossible result: {bad}")
    print("ranking tests passed")
