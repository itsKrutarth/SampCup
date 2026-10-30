# 04 Build Stages
Each stage ends with acceptance checks. Do not skip. Keep the repo runnable with docker compose at every stage.

## Stage 0: Repo and environment
Tasks: monorepo (backend/, frontend/, infra/, docs/, Tournament Resources/), docker compose (api, db), linting, pytest, GitHub Actions (test on push).
Accept: `docker compose up` runs API health check; CI green.

## Stage 1: Data model + Sheets import
Tasks: Alembic migrations for tables in 03; gspread import with service account; idempotent sync; admin endpoint and test with a sample sheet; team number random draw.
Accept: re-sync twice gives no duplicates; removed sheet row is flagged not deleted; team numbers are a unique permutation 1..N.
Needs from owner: Sheet columns/format (see open items).

## Stage 2: Schedule engine
Tasks: move `Tournament Resources/sampcup_scheduler.py` into a backend library returning structured data (groups, match codes, prereqs, winner destinations, lunch blocks, court plan); store groups, group games and knockout matches; court override; schedule lock; CSV export and printable team slips.
Accept: for N=40 reproduce the reference outputs exactly (`sampcup_40team_*` files: 4 groups of 10, 160 group games 10:00 AM-3:23 PM, Round of 16 4:30 PM to best-of-3 Final 5:55-6:37 PM, court plan). `simulate_tournament.py --teams 34-42` passes as a pytest test.

## Stage 3: Admin dashboard (core)
Tasks: login; sync button; team list with check-in and number draw; schedule view by time/court/team; court override; judge accounts and court assignment; tournament status.
Accept: admin can complete pre-tournament setup without touching the DB.

## Stage 4: Judge scoring
Tasks: mobile UI per assigned court; shows current/next match; Start timer; point buttons; Final; Clock Ended; sudden-death winner; Forfeit; offline queue and retry; confirm dialog before final. The best-of-3 Final is scored game by game on court 1 (F-1, F-2, then F-3 only at 1-1); the screen shows the game score in the series.
Accept: all end_reasons produce correct stored scores/seconds (tests for: reach 11, clock lead, clock tie then sudden death 8-8 becomes 9-8, forfeit 11-0 at 720 s); impossible results are refused (same rules as `ranking.check_game`); the Final ends at 2 game wins and F-3 is cancelled at 2-0.

## Stage 5: Group standings and knockout
Tasks: integrate `Tournament Resources/ranking.py` (strict order in rules doc; already rejects impossible results and returns `decided_by`); show the tiebreak step per team; rank each group separately; "Generate bracket" fills the Round of 16 from the top 4 of each group; auto-advance winners to the best-of-3 Final; cancel Final game 3 at 2-0; corrections recompute downstream.
Accept: `simulate_tournament.py` passes (200 random tournaments per team count) and the app's own full-day simulation never errors; ranks inside each group are a permutation; the Round of 16 holds the top 4 of every group; corrections update standings and the bracket; random-draw ties are logged once and reused.

## Stage 6: Live public views
Tasks: SSE stream; public schedule, my-team page (by team number, with lunch time and next match), group standings, knockout bracket; projector mode (auto-rotate); QR code page.
Accept: score entered by judge appears on public page within 2 seconds; reconnect after network drop restores state.

## Stage 7: Announcements and delays
Tasks: composer with audience (all, team, court, match players) and channels (banner, email; SMS if approved); "Running behind" tool that shifts remaining start times and notifies affected teams; automatic "your match is next" alerts (optional, owner choice).
Accept: delay of 10 minutes shifts all unstarted matches and is reflected live; emails go only to chosen audience.

## Stage 8: Dry run and hardening
Tasks: full-day simulator (fake judges entering scores at speed); load test with ~300 concurrent public viewers; failure drills (kill API mid-game, offline judge); backups; export results CSV; security review.
Accept: simulated day completes with correct group standings and bracket, finishing by 6:37 PM; no lost scores in failure drills.

## Stage 9: Deploy
Tasks: Terraform (VPC, RDS or small DB, ECS/Fargate or single instance, ALB/HTTPS, SES), secrets, GitHub Actions deploy, domain/QR.
Accept: staging deploy from main; production deployed at least one week before the event; teardown plan after event.

## Stage 10: Tournament-day runbook
Tasks: written checklist: setup before 9:00, 9:00 breakfast/check-in/number draw, 9:45 Aarti and Deep pragatya, 10:00 first group game, rolling lunch 12-2, group play ends by 3:23, 3:30 Sabha/photo/awards and standings posted, 4:30 Round of 16, 4:47 quarterfinals, 5:21 semifinals, 5:55 best-of-3 Final (6:10, 6:25 if needed), awards and wrap-up until 7:00; hand back courts as they free up (court plan); fallback plan (paper score sheets and printed schedule from CSV); contact list; who edits scores; what to do if behind.
Accept: owner and two volunteers have run the dry run end to end.
