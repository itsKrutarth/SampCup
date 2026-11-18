# SampCup Application Tracker

The working record of the build. Read this first; update it after every chunk.
Requirements live in `Tournament Resources/`; milestones below follow `04_BUILD_STAGES.md`.

## Current position (2026-11-17, end of session)
- **State:** the app is built, tested and was proven on real AWS with a full dummy-user
  tournament. **The AWS stack is torn down** (owner's request while offline). Only the
  Terraform state bucket `sampcup-tfstate-<account>` remains (a few KB, ~$0).
- **Branch:** `app/serverless` (pushed). `main` still has the older Postgres version; merge
  `app/serverless` once CI is green on it.
- **To bring everything back:** `infra/deploy.sh apply` (about 5 minutes), then the
  "After a fresh deploy" steps in `docs/DEPLOY.md` (create your admin, create the 9 judges).
- **Next:**
  1. Owner: say when to redeploy, and which email gets alarm emails.
  2. Redeploy, create the real admin and judges, set registration open.
  3. Connect sampcup.com (Namecheap records from `terraform output namecheap_records`).
  4. Upload the real registration export (Admin → Players), never into git.
  5. M10: tournament-day runbook and a paper fallback.
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
| 8 | Email address for alarm emails | Alerts on errors | Before the event | Waiting |
| 9 | Add DNS records at Namecheap (values from Terraform) | sampcup.com | Before registration opens | Waiting |
| 10 | Optional: Service Quotas case to raise Lambda concurrency above 10 | Headroom | Before the event | Optional |

## Live test on AWS (2026-11-17, `tools/dummy_run.py`, all dummy data, then wiped)
- 86 dummy players imported; 42 teams formed through the partner flow in parallel; the 43rd
  team went to the waitlist; wrong-center, declined, duplicate-name cases behaved.
- Check-in, draw (1..42), schedule (185 games, first at 10:00 AM Dec 6), lock, banner.
- 9 judges played all 184 games at once in 53 s while 20 spectators refreshed pages.
  All groups complete, every team 8+ group games, R16 seeded correctly, champion decided,
  Final ended at 2 wins (game 3 cancelled after 2-0), 364 audit entries.
- 1,418 requests: no server errors; p50 195 ms, p95 354 ms. 24 requests were throttled by the
  account's 10-concurrent-Lambda limit and retried successfully.
- First run found two real problems, both fixed: the judge queue dropped an action on a
  throttle (429) instead of retrying; standings were recomputed after every group game
  (now only once a group is complete). The throttle alarm fired as designed.

## Decisions (made while building)
- **Workspace:** clone at `~/dev/SampCup`; GitHub is the source of truth. OneDrive would sync
  tens of thousands of `node_modules` files to the shared library and can corrupt `.git`.
- **Public repo:** secrets and real player data never enter git. Spreadsheets are git-ignored
  (also in the OneDrive copy's `.git/info/exclude`); CI runs a secret scan. The AWS account id
  is passed at `terraform init`, not committed.
- **Serverless AWS (owner, 2026-11-17):** CloudFront → S3 (site) and → Lambda function URL
  (API, Python 3.12 arm64, Mangum). DynamoDB on-demand with point-in-time recovery. No API
  Gateway, VPC, NAT or server. Everything by Terraform (`infra/`); state in S3 with native
  locking. DNS stays at Namecheap (free) instead of Route 53.
- **Only CloudFront can call the API:** CloudFront adds a secret header; the app refuses
  requests without it. The function URL itself answers 403 to direct calls.
- **DynamoDB design:** one table, `pk` = record kind, `sk` = id. Each request reads whole kinds
  (a few hundred items) and filters in Python. Version-checked game updates; transactions with
  lock items keep players, team names and usernames from being claimed twice.
- **Live updates by polling** (every 4 s, paused when the tab is hidden). CloudFront caches
  public answers 3 s, so hundreds of phones barely reach Lambda. Scores show in ~5-7 s.
- **Rate limits in DynamoDB**, per IP and per account name, generous per IP so a shared venue
  Wi-Fi does not lock players out.
- **Logs and alarms:** one JSON line per request in CloudWatch Logs (30 days). Alarms: API 5xx,
  Lambda errors, Lambda throttles, CloudFront 5xx rate. One dashboard. `infra/ops.sh` for
  status, live logs, errors, cost.
- **Lambda concurrency limit 10 (new account):** AWS's API only accepts requests above the
  default 1,000, so no Terraform request; caching plus judge-queue retries make 10 enough.
- **Precomputed schedules:** `tools/export_schedules.py` runs OR-Tools once per team count
  (32-42), rule-checks each, writes JSON to `backend/app/schedule_data/`.
- **Team range 32-42 (2026-11-17):** 32 and 33 passed the rule checker and 200 simulated
  tournaments each. 43+ is impossible with 8 games each before Sabha.
- **Registration (owner):** admins upload the BAPS registration export (.xlsx/.csv, one row per
  player, matched by MISID). Players pick center, self, a same-center partner, team name and
  password; the partner accepts; then only admins can change it. No identity check (owner's
  call). Cap 42 active teams, then a waitlist. Public pages stay open; teams log in.
- **Announcements:** in-app banner only (the export has no email or phone).
- **Auth:** sessions stored in DynamoDB with TTL (random bearer token, SHA-256 stored), scrypt
  password hashes.
- **Results:** one match record per game (Final = F-1..F-3); every start, final, forfeit,
  correction and reset is written to the audit log. Standings are computed on request.
- **Bracket:** filled automatically from complete groups and earlier winners; a game that has
  started is never changed, only reported to the admin.
- **Judge offline queue:** actions wait in browser storage and resend in order; network loss,
  throttling and server errors are retried; only the latest live score per game is kept.
- **Times:** stored in UTC; displayed in America/New_York.
- **TypeScript 6, not 7:** `typescript-eslint` does not support 7 yet.
- **System fonts:** no external font, so pages load on poor venue Wi-Fi.
- **Actions pinned to commit hashes:** the repo is public; Dependabot proposes updates weekly.

## Milestones
- [x] **M0 Foundation** (Stage 0)
- [x] **M1 Data model + team import** (Stage 1)
- [x] **M2 Schedule engine** (Stage 2)
- [x] **M3 Auth + admin** (Stage 3)
- [x] **M4 Judge scoring** (Stage 4)
- [x] **M5 Standings + knockout** (Stage 5)
- [x] **M6 Live public views** (Stage 6), by polling
- [x] **M7 Announcements + delays** (Stage 7)
- [ ] **M8 Hardening** (Stage 8)
  - [x] Full simulated tournament through the API (backend test, moto)
  - [x] Full dummy-user tournament on real AWS with 9 judges and 20 spectators
  - [ ] Failure drill on AWS: judge phone offline mid-game, then back
  - [ ] QR code poster for the public site
- [x] **S Serverless move:** DynamoDB + Lambda + CloudFront + S3, Terraform, logs, alarms
- [ ] **M9 Deploy:** proven, then torn down on request; redeploy and connect sampcup.com
- [ ] **M10 Runbook** (Stage 10): tournament-day checklist, paper fallback, dry run

## Test status
- Backend: 96+ tests on moto (fake AWS), 98% coverage (gate 90%).
- Frontend: 64 tests; ~98.5% statements, ~92.6% branches (gate 90% on each).
- CI jobs: backend, frontend, tournament rules, infra (Terraform fmt/validate + Lambda package),
  local stack (DynamoDB Local), secret scan.

## Session log
- 2026-11-02: Tournament structure final. Application build started. Workspace moved out of OneDrive.
- 2026-11-02: M0 finished. Full stack verified in Docker, CI green.
- 2026-11-17: Registration export received (kept out of git). Range extended to 32-42. App
  built (M1-M7) on Postgres, merged to `main`.
- 2026-11-17: Owner chose serverless AWS with Terraform. Backend moved to DynamoDB + Lambda,
  frontend to polling, infrastructure written and deployed (28 resources), dummy tournament
  passed on AWS, two bugs fixed, then the stack was destroyed at the owner's request.
