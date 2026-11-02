# SampCup Application Tracker

The working record of the build. Read this first; update it after every chunk.
Requirements live in `Tournament Resources/`; milestones below follow `04_BUILD_STAGES.md`.

## Current position
- **Milestone:** M1 Data model + team import
- **Branch:** `app/stage-1-data-model` (create from `main`)
- **Doing now:** Not started; waiting on owner item 4 for the importer. The tables can start without it.
- **Next:** 1.1 All tables and the first Alembic migration

## Needs from the owner
| # | What | Why | Needed by | Status |
|---|---|---|---|---|
| 1 | Confirm hosting: AWS (recommended, see Decisions) | Deploy target | M9 | Waiting |
| 2 | Create an AWS account, with MFA on the root user | Hosting and email | M9 | Waiting |
| 3 | Event date | Correct dates on the schedule, deploy deadline | M2 | Waiting |
| 4 | Google Sheet columns and 2-3 made-up sample rows | Team import | M1 | Waiting |
| 5 | Number of judges and devices; PIN per court? | Judge login design | M3 | Waiting |
| 6 | Open `~/dev/SampCup` in VS Code from now on | Code stays out of OneDrive | Now | Waiting |

## Decisions (made while building)
- **Workspace:** clone at `~/dev/SampCup`; GitHub is the source of truth. OneDrive would sync
  tens of thousands of `node_modules` files to the shared library and can corrupt `.git`.
- **Public repo:** secrets and real player data never enter git. `.gitignore`, secret scan in CI.
- **Precomputed schedules:** the OR-Tools solver takes 1-3 minutes per team count and is heavy.
  Generate the 9 schedules (34-42 teams) once, commit them as data, and load them instantly in
  the app. No solver in production, so nothing can stall on tournament morning.
- **Same-origin app:** the browser talks to one host; `/api/*` goes to FastAPI, everything else
  to the built frontend. No CORS, and SSE just works.
- **Sync SQLAlchemy + psycopg 3:** simplest to test; FastAPI runs routes in a thread pool.
- **Times:** stored in UTC; displayed in America/New_York.
- **TypeScript 6, not 7:** `typescript-eslint` does not support 7 yet. Move up when it does.
- **System fonts:** no external font, so pages load on poor venue Wi-Fi.
- **Actions pinned to commit hashes:** the repo is public; Dependabot proposes updates weekly.
- **Hosting: AWS, not Vercel (pending owner confirmation).** One Lightsail instance (2 GB, 4 GB for
  event week) running Docker Compose with Caddy for HTTPS, FastAPI and Postgres, plus nightly
  `pg_dump` to S3 and SES for email. Vercel suits neither long-lived SSE connections nor this
  Python backend, and would need a separate database vendor. DNS stays at Namecheap with A records
  for `@` and `www` pointing to the static IP; the current URL redirect gets removed.

## Milestones
- [x] **M0 Foundation** (Stage 0)
  - [x] 0.1 Tracker, CLAUDE.md, `.gitignore`, `.env.example`, remove `.DS_Store`
  - [x] 0.2 Backend: config, DB session, health/ready, Alembic, ruff, pytest 90% gate
  - [x] 0.3 Frontend: React shell, ESLint, Vitest 90% gate, lockfile
  - [x] 0.4 Docker: non-root images, `.dockerignore`, Compose with hot reload
  - [x] 0.5 CI: GitHub Actions (backend, frontend, ranking tests, secret scan)
  - [x] 0.6 Push, CI green, merge to `main`
- [ ] **M1 Data model + team import** (Stage 1): all tables, Sheets sync, number draw, groups
- [ ] **M2 Schedule engine** (Stage 2): precomputed schedules, load into DB, lock, court override, CSV and slips
- [ ] **M3 Auth + admin** (Stage 3): login, judge accounts, check-in, schedule views
- [ ] **M4 Judge scoring** (Stage 4): mobile scoring, timer, sudden death, forfeit, offline queue, best-of-3
- [ ] **M5 Standings + knockout** (Stage 5): per-group ranking, bracket, corrections
- [ ] **M6 Live public views** (Stage 6): SSE, schedule, my team, standings, bracket, projector, QR
- [ ] **M7 Announcements + delays** (Stage 7): banner, email, running-behind tool
- [ ] **M8 Hardening** (Stage 8): full-day simulator, load test, failure drills, security review
- [ ] **M9 Deploy** (Stage 9): Terraform, HTTPS, sampcup.com DNS, backups, CD
- [ ] **M10 Runbook** (Stage 10): tournament-day checklist, paper fallback, dry run

## Session log
- 2026-11-02: Tournament structure final. Application build started. Workspace moved out of OneDrive.
- 2026-11-02: M0 finished. Backend and frontend at 100% coverage, full stack verified in Docker, all five CI jobs green.
