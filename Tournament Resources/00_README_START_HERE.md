# SAMP Cup Tournament App: Start Here

Project: web app to run SAMP Cup, a one-day pickleball tournament for the BAPS Shri Swaminarayan Mandir youth community in New England ("Samp" means unity in Gujarati). Owner: youth coordinator.

Format: 4 random groups with at least 8 group games per team, then the top 4 of each group play a Round of 16, quarterfinals, semifinals and a best-of-3 Final, around the leads' day plan (Sabha 3:30-4:30 PM; Final over by 6:37 PM). No team plays more than 2 games in a row or waits longer than lunch. Works for 34-42 teams on 9 courts. Details in `02_TOURNAMENT_RULES.md`.

## How to use this kit (for you or any AI assistant)
1. Read files in order: 01 -> 05. They are the single source of truth. Chat history is NOT needed.
2. Work one stage at a time from `04_BUILD_STAGES.md`. Do not start a stage until the previous stage's acceptance checks pass.
3. If a decision is missing, check `05_DECISIONS_AND_OPEN_ITEMS.md`. If still unclear, ask the owner; then record the answer there.
4. Never change tournament rules in code without updating `02_TOURNAMENT_RULES.md` first.
5. The scheduler, checker, simulator and ranking code here are validated. Reuse them; do not rewrite from scratch. The scheduler gives the same schedule every time for the same team count (about 1-3 minutes to generate).

## Files
| File | Purpose |
|---|---|
| 01_PROJECT_SPEC.md | Goals, users, scope, tech stack, non-goals |
| 02_TOURNAMENT_RULES.md | Day plan, groups, game rules, standings, knockout, team-count table (locked) |
| 03_ARCHITECTURE_DATA_MODEL.md | Components, DB tables, APIs, live updates |
| 04_BUILD_STAGES.md | Stage-by-stage plan with acceptance checks |
| 05_DECISIONS_AND_OPEN_ITEMS.md | Decision log, validated results, risks, open questions |
| sampcup_scheduler.py | Schedule generator: random groups, group play, 16-team knockout (needs `pip install ortools`) |
| check_schedule.py | Rule checker: verifies every scheduling rule for a range of team counts |
| simulate_tournament.py | Full test: runs the rule checker, then plays 200 complete random tournaments per team count (scores, ties, standings, bracket, best-of-3 Final) |
| ranking.py | Group standings with every tiebreak step and `decided_by`; self-tests (`python ranking.py`) |
| sampcup_40team_groups.csv | 40-team groups: which team is in which group, games per team |
| sampcup_40team_pool_schedule.csv | 40-team group play: group, time, court, teams |
| sampcup_40team_knockout_schedule.csv | 40-team Round of 16 to the best-of-3 Final: match codes, group places, where the winner goes |
| sampcup_40team_per_team.csv | 40-team per-team summary: group, first/last game, lunch block, full lunch break length, longest gap between games, back-to-back games |
| sampcup_40team_court_plan.csv | 40-team court release plan: games per court and when each court's last game ends |
| sampcup_40team_team_slips.txt | Printable slip for each team: group, 8 games, lunch, knockout times |
| flowchart_pool_play.png | Flow chart: check-in, groups, group games, group standings |
| flowchart_knockout.png | Flow chart: Round of 16 to Final on the timeline, with courts in use |
| flowchart_*.dot | Graphviz sources for the charts (`dot -Tpng -Gdpi=150 flowchart_knockout.dot -o flowchart_knockout.png`) |

## Commands
```
pip install ortools
python sampcup_scheduler.py --teams 40        # writes the sampcup_40team_* files
python check_schedule.py --teams 34-42        # verifies every scheduling rule; exit code 1 on failure
python simulate_tournament.py --teams 34-42   # rule checks + 200 simulated tournaments per team count
python ranking.py                             # ranking self-tests
```
