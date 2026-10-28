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
Tasks: move `Tournament Resources/sampcup_scheduler.py` into a backend library returning structured data (match codes, prereqs, winner/loser destinations, lunch blocks); store pool, Gold, Silver and placement matches; court override; schedule lock; CSV export and printable team slips.
Accept: for N=40 reproduce the reference outputs exactly (`sampcup_40team_*` files: 120 pool matches 10:00 AM-1:58 PM, 73 knockout matches 2:15-6:29 PM). `check_schedule.py --teams 32-42` passes as a pytest test.

## Stage 3: Admin dashboard (core)
Tasks: login; sync button; team list with check-in and number draw; schedule view by time/court/team; court override; judge accounts and court assignment; tournament status.
Accept: admin can complete pre-tournament setup without touching the DB.

## Stage 4: Judge scoring
Tasks: mobile UI per assigned court; shows current/next match; Start timer; point buttons; Final; Clock Ended; sudden-death winner; Forfeit; offline queue and retry; confirm dialog before final.
Accept: all end_reasons produce correct stored scores/seconds (tests for: reach 11, clock lead, clock tie then sudden death 8-8 becomes 9-8, forfeit 11-0 at 720 s).

## Stage 5: Ranking, seeding, Gold/Silver brackets
Tasks: integrate `Tournament Resources/ranking.py` (strict order in rules doc; fix the known issues listed in 05); show tiebreak step per team; "Generate brackets" maps ranks to seeds; auto-advance Gold winners, drop early Gold losers into Silver, fill placement games; corrections recompute downstream.
Accept: simulation of 300 random tournaments never errors; ranks are a permutation; every team plays at least 2 knockout games; every early Gold loser plays in Silver; corrections update standings and both brackets; random-draw ties are logged once and reused.

## Stage 6: Live public views
Tasks: SSE stream; public schedule, my-team page (by team number, with lunch time and next match), standings, Gold and Silver brackets; projector mode (auto-rotate); QR code page.
Accept: score entered by judge appears on public page within 2 seconds; reconnect after network drop restores state.

## Stage 7: Announcements and delays
Tasks: composer with audience (all, team, court, match players) and channels (banner, email; SMS if approved); "Running behind" tool that shifts remaining start times and notifies affected teams; automatic "your match is next" alerts (optional, owner choice).
Accept: delay of 10 minutes shifts all unstarted matches and is reflected live; emails go only to chosen audience.

## Stage 8: Dry run and hardening
Tasks: full-day simulator (fake judges entering scores at speed); load test with ~300 concurrent public viewers; failure drills (kill API mid-game, offline judge); backups; export results CSV; security review.
Accept: simulated day completes with correct final ranking and both brackets, finishing by 6:30 PM; no lost scores in failure drills.

## Stage 9: Deploy
Tasks: Terraform (VPC, RDS or small DB, ECS/Fargate or single instance, ALB/HTTPS, SES), secrets, GitHub Actions deploy, domain/QR.
Accept: staging deploy from main; production deployed at least one week before the event; teardown plan after event.

## Stage 10: Tournament-day runbook
Tasks: written checklist: setup before 9:00, 9:00 breakfast/check-in/number draw, 9:45 Aarti and Deep pragatya, 10:00 first pool game, rolling lunch 12-2, 1:58 seeding break, 2:15 knockout starts, 3:30 Sabha/photo/awards, 4:30 Gold Round of 16, 6:12 Gold and Silver finals, 6:30 wrap-up and final awards; fallback plan (paper score sheets and printed schedule from CSV); contact list; who edits scores; what to do if behind.
Accept: owner and two volunteers have run the dry run end to end.
