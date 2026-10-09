# 04 Build Stages
Each stage ends with acceptance checks. Do not skip. Keep the repo runnable with docker compose at every stage.

## Stage 0: Repo and environment
Tasks: monorepo (backend/, frontend/, infra/, docs/, reference/), docker compose (api, db), linting, pytest, GitHub Actions (test on push).
Accept: `docker compose up` runs API health check; CI green.

## Stage 1: Data model + Sheets import
Tasks: Alembic migrations for tables in 03; gspread import with service account; idempotent sync; admin endpoint and test with a sample sheet; team number random draw.
Accept: re-sync twice gives no duplicates; removed sheet row is flagged not deleted; team numbers are a unique permutation 1..N.
Needs from owner: Sheet columns/format (see open items).

## Stage 2: Schedule engine
Tasks: port `reference/pickleball_tournament_scheduler_v2.py` into a library returning structured data (with match ids and prereqs, not only CSV); store pool and playoff matches; court override; schedule lock; CSV export and printable team slips.
Accept: for N=40 reproduce reference results exactly (120 pool matches, 54 playoff matches, pool ends 2:49 PM, playoffs end 5:59 PM, every team 6 pool games, no repeats, min lunch gap 51, zero playoff back-to-backs, min 8 games). Also run for 36, 38, 44 and compare with `team_count_sweep.csv`.

## Stage 3: Admin dashboard (core)
Tasks: login; sync button; team list with check-in and number draw; schedule view by time/court/team; court override; judge accounts and court assignment; tournament status.
Accept: admin can complete pre-tournament setup without touching the DB.

## Stage 4: Judge scoring
Tasks: mobile UI per assigned court; shows current/next match; Start timer; point buttons; Final; Clock Ended; sudden-death winner; Forfeit; offline queue and retry; confirm dialog before final.
Accept: all end_reasons produce correct stored scores/seconds (tests for: reach 11, clock lead, clock tie then sudden death 8-8 becomes 9-8, forfeit 11-0 at 720 s).

## Stage 5: Ranking, seeding, playoffs
Tasks: integrate `reference/ranking.py` (strict order in rules doc); show tiebreak step per team; "Generate playoffs" maps ranks to seeds; auto-advance winners/losers; corrections recompute downstream.
Accept: simulation of 300 random tournaments never errors; ranks are a permutation; playoff games per team at least 2; corrections update standings and bracket; random-draw ties are logged once and reused.

## Stage 6: Live public views
Tasks: SSE stream; public schedule, my-team page (by team number), standings, bracket; projector mode (auto-rotate); QR code page.
Accept: score entered by judge appears on public page within 2 seconds; reconnect after network drop restores state.

## Stage 7: Announcements and delays
Tasks: composer with audience (all, team, court, match players) and channels (banner, email; SMS if approved); "Running behind" tool that shifts remaining start times and notifies affected teams; automatic "your match is next" alerts (optional, owner choice).
Accept: delay of 10 minutes shifts all unstarted matches and is reflected live; emails go only to chosen audience.

## Stage 8: Dry run and hardening
Tasks: full-day simulator (fake judges entering scores at speed); load test with ~300 concurrent public viewers; failure drills (kill API mid-game, offline judge); backups; export results CSV; security review.
Accept: simulated day completes with correct final ranking and bracket; no lost scores in failure drills.

## Stage 9: Deploy
Tasks: Terraform (VPC, RDS or small DB, ECS/Fargate or single instance, ALB/HTTPS, SES), secrets, GitHub Actions deploy, domain/QR.
Accept: staging deploy from main; production deployed at least one week before the event; teardown plan after event.

## Stage 10: Tournament-day runbook
Tasks: written checklist: 9:00 setup, 9:30 check-in, 10:00 start, rolling lunch, 2:49 seeding, 3:09 playoffs, 5:42 finals, awards; fallback plan (paper score sheets and printed schedule from CSV); contact list; who edits scores; what to do if behind.
Accept: owner and two volunteers have run the dry run end to end.
