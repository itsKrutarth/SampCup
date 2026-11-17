"""Export the precomputed schedules (one JSON file per team count) for the backend.

Dev-only: needs OR-Tools. Run from the repo root:
    python tools/export_schedules.py            # every supported count
    python tools/export_schedules.py --teams 40
Each schedule is rule-checked before it is written.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Tournament Resources"))

import check_schedule  # noqa: E402
import sampcup_scheduler as s  # noqa: E402

OUT = ROOT / "backend" / "app" / "schedule_data"


def hhmm(t):
    return t.strftime("%H:%M")


def export(n_teams):
    day = s.build_day(n_teams)
    problems, _ = check_schedule.check_day(day, 50)
    if problems:
        raise SystemExit(f"{n_teams} teams failed the rule check: {problems[:3]}")
    plan = day.plan
    next_match = {}
    for m in day.matches:
        for dep in m.deps:
            if not (m.mid.startswith("F-") and dep.startswith("F-")):
                next_match[dep] = m.mid
    data = {
        "teams": n_teams,
        "slot_minutes": plan.slot_min,
        "game_minutes": s.GAME_PLAY_MIN,
        "courts": plan.courts,
        "first_game": hhmm(plan.first_game),
        "group_play_ends": hhmm(day.pool_end),
        "lunch_minutes": plan.lunch_slots * plan.slot_min,
        "sabha": [hhmm(plan.sabha_start), hhmm(plan.sabha_end)],
        "groups": day.groups,
        "lunch": {str(t): hhmm(day.lunch_time(t)[0]) for t in range(1, n_teams + 1)},
        "pool": [{"slot": r["slot"], "time": hhmm(day.pool_time(r)), "court": r["court"],
                  "group": r["group"], "team_a": r["team_a"], "team_b": r["team_b"]}
                 for r in day.pool],
        "knockout": [{"code": m.mid, "round": m.label, "time": hhmm(m.start),
                      "court": m.court, "source_a": m.team_a, "source_b": m.team_b,
                      "prereqs": list(m.deps), "winner_goes_to": next_match.get(m.mid)}
                     for m in sorted(day.matches, key=lambda m: (m.start, m.court))],
    }
    path = OUT / f"teams_{n_teams}.json"
    path.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {path.relative_to(ROOT)}: {len(data['pool'])} group games, "
          f"group play ends {data['group_play_ends']}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teams", default=f"{s.MIN_TEAMS}-{s.MAX_TEAMS}")
    for n in check_schedule.parse_range(parser.parse_args().teams):
        export(n)


if __name__ == "__main__":
    main()
