from collections import Counter
from typing import Any

from app.models import Match, Team
from app.services.tournament import get_tournament
from app.store import Store
from app.tournament.ranking import rank_teams


def group_standings(
    store: Store, teams: list[Team] | None = None, matches: list[Match] | None = None
) -> dict[str, dict[str, Any]]:
    """Each group ranked by the rules (ranking.py), keyed by team number."""
    seed = get_tournament(store).draw_seed or 0
    teams = [t for t in (store.all(Team) if teams is None else teams) if t.group]
    matches = [m for m in (store.all(Match) if matches is None else matches) if m.phase == "group"]
    out: dict[str, dict[str, Any]] = {}
    for group in sorted({t.group for t in teams if t.group}):
        members = {t.team_number: t for t in teams if t.group == group}
        number_of = {t.id: n for n, t in members.items()}
        games = [m for m in matches if m.group == group]
        done = [m for m in games if m.status == "completed"]
        results = [
            {
                "team_a": number_of[m.team_a_id],
                "team_b": number_of[m.team_b_id],
                "score_a": m.score_a,
                "score_b": m.score_b,
                "end_reason": m.end_reason,
                "seconds": m.seconds,
            }
            for m in done
            if m.team_a_id in number_of and m.team_b_id in number_of
        ]
        played = Counter(n for r in results for n in (r["team_a"], r["team_b"]))
        rows = []
        for row in rank_teams(sorted(members), results, seed=seed):
            team = members[row["team"]]
            rows.append(
                {
                    **row,
                    "team": None,
                    "team_id": team.id,
                    "team_number": team.team_number,
                    "team_name": team.name,
                    "played": played[row["team"]],
                    "losses": played[row["team"]] - row["wins"],
                }
            )
        out[group] = {
            "complete": bool(games) and len(done) == len(games),
            "played": len(done),
            "total": len(games),
            "rows": rows,
        }
    return out
