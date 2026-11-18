# SampCup Application Tracker

The working record of the build. Read this first; update it after every chunk.
Requirements live in `Tournament Resources/`; milestones below follow `04_BUILD_STAGES.md`.

## Current position
- **Milestone:** S Serverless move (owner, 2026-11-17: AWS, Terraform only, serverless, as cheap as possible, logs and alarms)
- **Branch:** `app/serverless`
- **Plan:** S1 DynamoDB data layer + Lambda adapter -> S2 frontend polling -> S3 Terraform
  (state bucket, DynamoDB, Lambda + function URL, S3 site, CloudFront, logs, alarms, dashboard)
  -> S4 deploy -> S5 full dummy-user tournament on the live site, then wipe -> S6 docs
- **Doing now:** S1
- **Event date:** Sunday, December 6, 2026. 9 judges (one per court); the owner is the admin.

## Needs from the owner
| # | What | Why | Needed by | Status |
|---|---|---|---|---|
| 1 | Hosting: AWS serverless | Deploy target | M9 | Done 2026-11-17 |
| 2 | AWS account and CLI access (user `mac`) | Hosting | M9 | Done 2026-11-17 |
| 3 | Event date | Schedule times | Before the draw | Done: 2026-12-06 |
| 4 | Registration export format | Player import | M1 | Done 2026-11-17 |
| 5 | Judges | Judge accounts | Event week | Done: 9 judges, one per court |
| 6 | Open `~/dev/SampCup` in VS Code from now on | Code stays out of OneDrive | Now | Waiting |
| 7 | Awards | Not part of the app (owner's lead decides) | - | Closed |

## Decisions (made while building)
- **Workspace:** clone at `~/dev/SampCup`; GitHub is the source of truth. OneDrive would sync
  tens of thousands of `node_modules` files to the shared library and can corrupt `.git`.
- **Public repo:** secrets and real player data never enter git. Spreadsheets are git-ignored
  (also in the OneDrive copy's `.git/info/exclude`); CI runs a secret scan.
- **Precomputed schedules:** `tools/export_schedules.py` runs the OR-Tools solver once per team
  count (32-42), rule-checks each schedule and writes JSON to `backend/app/schedule_data/`.
  No solver in production, so nothing can stall on tournament morning.
- **Team range 32-42 (2026-11-17):** owner expects 32-42 teams. 32 and 33 passed the rule
  checker and 200 simulated tournaments each. 43+ is impossible with 8 games each before Sabha.
- **Registration (2026-11-17, owner):** admins upload the BAPS registration export (.xlsx/.csv,
  one row per player, matched by MISID). Players form teams in the app: pick center, self,
  a partner from the same center, team name and password; the partner must accept; then only
  admins can change it. No identity check (owner's call; admins fix mistakes). Cap 42 active
  teams, then a waitlist. Public pages stay open; teams log in for their own page.
- **Announcements:** in-app banner only (the export has no email or phone).
- **Same-origin app:** one FastAPI process serves `/api/*`, the SSE stream and the built
  frontend. No CORS. One worker on purpose: live updates fan out in memory.
- **Auth:** server-side sessions (random bearer token, SHA-256 stored), scrypt password
  hashes, login rate limit 10 per 5 minutes per IP, registration requests 30 per 10 minutes.
- **Results:** one match row per game (the best-of-3 Final is F-1..F-3); every start, final,
  forfeit, correction and reset is written to `score_audit`. Standings are computed on request.
- **Bracket:** filled automatically from complete groups and earlier winners; a game that has
  already started is never changed, only reported to the admin.
- **Judge offline queue:** actions wait in browser storage and resend in order; only the latest
  live score per game is kept.
- **Times:** stored in UTC; displayed in America/New_York.
- **TypeScript 6, not 7:** `typescript-eslint` does not support 7 yet.
- **System fonts:** no external font, so pages load on poor venue Wi-Fi.
- **Actions pinned to commit hashes:** the repo is public; Dependabot proposes updates weekly.
- **Hosting: AWS Lightsail, not Vercel (pending owner confirmation).** One instance running
  `deploy/docker-compose.yml`: Caddy (automatic HTTPS), the app, Postgres, and a pg_dump every
  6 hours. Vercel suits neither long-lived SSE connections nor this Python backend and would
  need a separate database vendor. Steps in `docs/DEPLOY.md`.

## Milestones
- [x] **M0 Foundation** (Stage 0)
- [x] **M1 Data model + team import** (Stage 1): 10 tables, export upload, partner flow, waitlist, draw
- [x] **M2 Schedule engine** (Stage 2): 11 precomputed schedules, load into DB, lock, court override, CSV export
- [x] **M3 Auth + admin** (Stage 3): staff and team logins, judge accounts with courts, check-in, admin console
- [x] **M4 Judge scoring** (Stage 4): timer, points, clock end, sudden death, forfeit, offline queue, best-of-3
- [x] **M5 Standings + knockout** (Stage 5): per-group ranking, automatic bracket, corrections with audit
- [x] **M6 Live public views** (Stage 6): SSE, schedule, team pages, standings, bracket, projector
- [x] **M7 Announcements + delays** (Stage 7): banners, running-behind tool with Sabha warnings
- [ ] **M8 Hardening** (Stage 8)
  - [x] Full simulated tournament day through the API (backend test)
  - [x] Production image boots against Postgres in CI
  - [ ] Load test with ~300 viewers on the real server
  - [ ] Failure drills on the real server (restart mid-game, judge offline)
  - [ ] QR code poster for the public site
- [ ] **M9 Deploy** (Stage 9): files ready in `deploy/`; needs the AWS account
- [ ] **M10 Runbook** (Stage 10): tournament-day checklist, paper fallback, dry run

## Test status
- Backend: 94 tests, 99% coverage (gate 90%); SQLite locally, Postgres in CI.
- Frontend: 63 tests; 98.6% statements, 92.7% branches (gate 90% on each).

## Session log
- 2026-11-02: Tournament structure final. Application build started. Workspace moved out of OneDrive.
- 2026-11-02: M0 finished. Backend and frontend at 100% coverage, full stack verified in Docker, all five CI jobs green.
- 2026-11-17: Owner shared the registration export (59 players, one row each, no contacts; kept out of git). Range extended to 32-42. Backend and frontend built (M1-M7), production packaging written, real app exercised end to end on this Mac.
