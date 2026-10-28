# SAMP Cup Tournament App: Start Here

Project: web app to run SAMP Cup, a one-day pickleball tournament for the BAPS Shri Swaminarayan Mandir youth community in New England ("Samp" means unity in Gujarati). Owner: youth coordinator.

Format: pool play for seeding, then a Gold bracket for every team and a Silver (losers) bracket, around the leads' day plan (Sabha 3:30-4:30 PM, finals by 6:30 PM). Details in `02_TOURNAMENT_RULES.md`.

## How to use this kit (for you or any AI assistant)
1. Read files in order: 01 -> 05. They are the single source of truth. Chat history is NOT needed.
2. Work one stage at a time from `04_BUILD_STAGES.md`. Do not start a stage until the previous stage's acceptance checks pass.
3. If a decision is missing, check `05_DECISIONS_AND_OPEN_ITEMS.md`. If still unclear, ask the owner; then record the answer there.
4. Never change tournament rules in code without updating `02_TOURNAMENT_RULES.md` first.
5. The scheduler, checker and ranking code here are validated. Reuse them; do not rewrite from scratch.

## Files
| File | Purpose |
|---|---|
| 01_PROJECT_SPEC.md | Goals, users, scope, tech stack, non-goals |
| 02_TOURNAMENT_RULES.md | Day plan, format, game rules, ranking, team-count policy (locked) |
| 03_ARCHITECTURE_DATA_MODEL.md | Components, DB tables, APIs, live updates |
| 04_BUILD_STAGES.md | Stage-by-stage plan with acceptance checks |
| 05_DECISIONS_AND_OPEN_ITEMS.md | Decision log, validated results, risks, open questions |
| sampcup_scheduler.py | Schedule generator: pool play + Gold/Silver brackets (needs `pip install ortools`) |
| check_schedule.py | Rule checker: simulates results and verifies every rule for a range of team counts |
| ranking.py | Pool ranking function with self-tests (known issues listed in 05) |
| sampcup_40team_pool_schedule.csv | 40-team pool play: time, court, teams |
| sampcup_40team_knockout_schedule.csv | 40-team Gold/Silver/placement matches with match codes, sources, destinations |
| sampcup_40team_per_team.csv | 40-team per-team summary: first/last pool game, lunch block, full lunch break length (`lunch_break_min`, counts free time up to the knockout when lunch comes after a team's last pool game), longest gap between pool games, back-to-back games |
| sampcup_40team_team_slips.txt | Printable pool-play slip for each team |
| flowchart_pool_play.png | Flow chart: check-in to seeding (game outcomes, ranking) |
| flowchart_knockout.png | Flow chart: Gold, Silver and placement games on the 40-team timeline |
| flowchart_*.dot | Graphviz sources for the charts (`dot -Tpng -Gdpi=150 flowchart_knockout.dot -o flowchart_knockout.png`) |

## Commands
```
pip install ortools
python sampcup_scheduler.py --teams 40        # writes the sampcup_40team_* files
python check_schedule.py --teams 32-42        # verifies every rule; exit code 1 on failure
python ranking.py                             # ranking self-tests
```
