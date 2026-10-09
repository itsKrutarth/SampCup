# Pickleball Tournament App: Start Here

Project: web app to run a one-day pickleball tournament for the BAPS Shri Swaminarayan Mandir (Westborough, MA) youth community. Owner: youth coordinator.

## How to use this kit (for you or any AI assistant)
1. Read files in order: 01 -> 05. They are the single source of truth. Chat history is NOT needed.
2. Work one stage at a time from `04_BUILD_STAGES.md`. Do not start a stage until the previous stage's acceptance checks pass.
3. If a decision is missing, check `05_DECISIONS_AND_OPEN_ITEMS.md`. If still unclear, ask the owner; then record the answer there.
4. Never change tournament rules in code without updating `02_TOURNAMENT_RULES.md` first.
5. `reference/` holds the validated scheduler, ranking code and test results. Reuse them; do not rewrite from scratch.

## Files
| File | Purpose |
|---|---|
| 01_PROJECT_SPEC.md | Goals, users, scope, tech stack, non-goals |
| 02_TOURNAMENT_RULES.md | Exact format, timing, rules, ranking (locked) |
| 03_ARCHITECTURE_DATA_MODEL.md | Components, DB tables, APIs, live updates |
| 04_BUILD_STAGES.md | Stage-by-stage plan with acceptance checks |
| 05_DECISIONS_AND_OPEN_ITEMS.md | Decision log, known risks, open questions |
| reference/pickleball_tournament_scheduler_v2.py | Validated schedule generator (rest-aware) |
| reference/ranking.py | Validated ranking function with real tests |
| reference/team_count_sweep.csv | Results for 8-64 teams |
| reference/time_scenarios.csv | Delay/court-loss scenarios for 40 teams |
