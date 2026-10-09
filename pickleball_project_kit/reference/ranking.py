"""Ranking for pickleball tournament pool play.
Order: 1) wins  2) total points scored  3) lower average time to finish games
       4) fewer points allowed  5) head-to-head (2-team ties only)  6) random draw
Time to finish = seconds from first serve to the final point. A game decided by the
12-minute clock or sudden death counts as CLOCK_CAP seconds.
A game tied at clock end is settled by one sudden-death point added to the winner.
"""
import random
from collections import defaultdict

CLOCK_CAP = 12 * 60


def resolve_clock_end(score_a, score_b, sudden_death_winner=None):
    if score_a == score_b:
        if sudden_death_winner not in ("a", "b"):
            raise ValueError("Tied at clock end: sudden-death winner required")
        return (score_a + 1, score_b) if sudden_death_winner == "a" else (score_a, score_b + 1)
    return score_a, score_b


def rank_teams(games, seed=None):
    """games: list of (team_a, team_b, score_a, score_b, seconds_to_finish)."""
    rng = random.Random(seed)
    s = defaultdict(lambda: {"w": 0, "pf": 0, "pa": 0, "t": 0, "g": 0})
    h2h = {}
    for a, b, sa, sb, sec in games:
        sec = min(sec, CLOCK_CAP) if max(sa, sb) >= 11 else CLOCK_CAP
        for x, f, o in ((a, sa, sb), (b, sb, sa)):
            s[x]["pf"] += f; s[x]["pa"] += o; s[x]["t"] += sec; s[x]["g"] += 1
        win = a if sa > sb else b
        s[win]["w"] += 1
        h2h[(a, b)] = h2h[(b, a)] = win
    avg = lambda t: round(s[t]["t"] / s[t]["g"], 1)
    key = lambda t: (-s[t]["w"], -s[t]["pf"], avg(t), s[t]["pa"])
    teams = sorted(s, key=key)
    out, i = [], 0
    while i < len(teams):
        j = i
        while j < len(teams) and key(teams[j]) == key(teams[i]):
            j += 1
        grp = teams[i:j]
        if len(grp) == 2 and (grp[0], grp[1]) in h2h:
            if h2h[(grp[0], grp[1])] == grp[1]:
                grp.reverse()
        elif len(grp) > 1:
            rng.shuffle(grp)
        out += grp
        i = j
    return [(r + 1, t, s[t]["w"], s[t]["pf"], avg(t), s[t]["pa"]) for r, t in enumerate(out)]


if __name__ == "__main__":
    assert resolve_clock_end(8, 8, "a") == (9, 8)
    assert resolve_clock_end(8, 8, "b") == (8, 9)
    assert resolve_clock_end(9, 7) == (9, 7)
    g = [("X", "P", 11, 5, 400), ("X", "Q", 11, 6, 420), ("X", "R", 11, 4, 380),
         ("Y", "P", 11, 9, 300), ("Y", "Q", 11, 10, 310), ("Y", "R", 11, 4, 290)]
    r = rank_teams(g, seed=1)
    assert [x[1] for x in r][:2] == ["Y", "X"], r  # same wins/points, Y faster
    g2 = g[:5] + [("Y", "R", 11, 4, 700)]
    r2 = rank_teams(g2, seed=1)
    assert [x[1] for x in r2][:2] == ["X", "Y"], r2  # Y avg time now slower
    g3 = [("A", "B", 11, 5, 720), ("C", "D", 11, 5, 720)]
    assert rank_teams(g3, seed=1) == rank_teams(g3, seed=1)  # deterministic
    g4 = [("A", "B", 11, 10, 300), ("A", "C", 10, 11, 300), ("B", "C", 11, 10, 300),
          ("B", "D", 10, 11, 300), ("A", "D", 11, 10, 300), ("C", "D", 10, 11, 300)]
    assert sorted(x[0] for x in rank_teams(g4, seed=1)) == [1, 2, 3, 4]
    g5 = [("A", "B", 6, 7, 300), ("C", "A", 9, 11, 420)]  # clock-ended game counts 720s
    assert rank_teams(g5, seed=1)[0][1] == "A"
    print("ranking tests passed")
