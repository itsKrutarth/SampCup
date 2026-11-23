# SampCup Application Tracker

The working record of the build. Read this first; update it after every chunk.
Requirements live in `Tournament Resources/`; milestones below follow `04_BUILD_STAGES.md`.

## Current position (2026-11-22)
- **State:** live at **https://sampcup.com** again since 2026-11-22 (owner redeployed; offline
  2026-11-21 night). Restored `~/dev/sampcup-snapshot-2026-11-21-before-teardown.json`:
  110 items, 59 real players (6 with logins), 1 real team, 8 partner requests, admin,
  9 judges, settings (registration open, event 2026-12-06). The alarm email subscription
  awaits confirmation. Both snapshots (11-18, 11-21) stay on the owner's Mac (owner's choice).
- **Teardown/bring-back recipe:** `tools/snapshot.py save`, `infra/destroy.sh` (keeps the
  foundation and state bucket); later `infra/deploy.sh apply`, then `tools/snapshot.py
  restore` (returns admin and judges too; skip create-admin/create-judges). Only one deploy
  at a time: a second `deploy.sh` rebuilds `api.zip` under a running apply and fails it.
  After a deploy, check the table: a fresh one holds only the default settings until restored.
- **Deployed 2026-11-22 (owner):** mock clock, Final as one series, clearer judge message
  (commit ce776b4, branch `fix/final-series-and-judge-message`).
- **Logs kept through teardowns (owner: "keep logs"), done 2026-11-22:** the API log group
  lives in `infra/foundation` (applied by the owner; plan now "No changes"); the app stack
  only reads it (data source). The one-time `import` and `removed` blocks are deleted.
- **Deployed 2026-11-22 (owner), all on `main`:** logos, backup-sheet support, home page
  during play and player defaults (`home/live-layout`).
- **Backup sheet (owner: "a backup plan if the app goes down"), branch
  `backup/google-sheet`:** a Google Sheet whose own Apps Script (`tools/backup-sheet/Code.gs`)
  copies the public pages every minute (teams, players, lunch, every game, standings) and
  keeps the last good copy. Manual mode: organizers type results; "Recompute" ranks groups
  exactly like `ranking.py` (except lots: number order), fills knockout teams and settles
  the Final. Tested in `backend/tests/test_backup_sheet.py` (3,000 groups vs `ranking.py`, a
  whole simulated day, and the menus on a fake Google Sheet). Also: `/public/teams` now
  includes `lunch_start`, and Admin > Results > Correct takes a game time (for results
  entered after an outage). Owner sets the sheet up once (README there, ~5 minutes).
- **Official logo (owner, 2026-11-22), branch `home/logo-in-hero`:** the owner's logo
  (`frontend/public/brand/samp-cup-logo.webp`) replaces the drawn crest above the hero
  wordmark and in the header (same 38 px height); nothing else changes. The earlier version
  is tag `home-before-logo`. Branch `home/real-logo` (logo replacing the whole title block)
  was a misread; kept, unused. The drawn crest is still on Join, Logins and the projector.
- **Second mock (2026-11-21, `--speed 30`, ~20 s a game, 32 teams, 145 games):** the app held
  up; the mock tool did not:
  - Real players have started forming teams, so the mock now leaves real teams out (never
    checked in or drawn) and tops the field up to the draw's 32 with dummy pairs.
  - The owner scored court 1 from the real judge screen during the mock; the app correctly
    refused the mock's stale update (409) but the mock's court worker gave up, freezing
    court 1 and the knockouts behind it. Now the mock re-reads the board on a 409.
  - A short network drop on the Mac killed the other court workers (SSL handshake timeout),
    leaving the last 6 games unplayed for two hours with registration closed. The API
    client now retries network errors like a throttled server.
  - Owner's two 15-minute delays moved exactly the Final games (5:55/6:10/6:25 to
    6:25/6:40/6:55). The bracket spread the three Final cards down the whole column, so game 3
    was below the screen and game 1 sat at game 3's old time: it looked like a game had gone.
    Now the Final's games sit together at the top of the column with the series score
    ("X leads 1-0"). A judge phone that sends a score for a game already finished elsewhere
    now reads "already final" instead of "Start the game first".
  - All of it came from the mock tool, not from the owner's actions: scoring on the judge
    screen and adding delays during play is exactly what staff will do on the day.
  - The header clock showed the real time during the mock, so nobody could tell where the
    mock's day was. Now a mock clock (tournament settings `mock_started_at`, `mock_day_start`,
    `mock_speed`, set by `tools/mock_tournament.py` when play begins) drives the header clock
    (marked "Mock"), the home countdown, the judge screens' countdown and timer, and the
    server's game-start rule and game times. It switches itself off after 6 hours, and the
    snapshot restore removes it, so the real day always runs on real time.
  - Yesterday's API logs were lost with the teardown (the log group was in the app stack);
    see `infra/keep-api-logs`.
  - `tools/mock_restore.py` restores the snapshot and keeps real changes made during the
    mock (3 accounts were set or claimed that day). Run it with `--dry-run` first.
- **Mock tournament findings (2026-11-18, `tools/mock_tournament.py` on prod, then restored):**
  - Games started as soon as a court was free, so 24 times a team was in two games at once.
    Now a game starts only at its scheduled time (1 minute grace for phone clocks) and only
    when neither team is still playing elsewhere. Admins can start a game early. The judge
    screen shows the time, a countdown and why it is waiting; Start stays locked until then.
  - The home page court board showed "Free" for courts whose next game was not among the next
    9 games overall. The overview now sends each court's own game (`courts`).
  - A small venue-time clock sits in the header on every page.
  - Schedule filter: a team dropdown sorted by name ("#3 Net Ninjas") replaces the "Team #"
    number box, since people won't know their drawn number. Links with `?team=N` still work.
  - Load test (100 logged-in players, 60 spectators, 9 judges, 3 minutes): the account's
    limit of 10 Lambda runs at once was reached and ~5% of requests got 429. Requests are
    CPU-bound (parsing DynamoDB replies, ~160 ms at 512 MB). Fixes: Lambda memory 1769 MB
    (one vCPU, same GB-seconds bill), players' pages poll less (account every 30s, team page
    every 10s from the cached public page; home page account check every 60s), CloudFront may
    serve a stale public page while refreshing (`stale-while-revalidate`, `stale-if-error`).
    Re-run the load test after deploying.
  - The 9 judges predated temporary PINs; now flagged to choose their own PIN at first login
    (done in the data after the restore).
  - Restore: prod is back to the real registrations. One real player claimed their account
    during the mock (claims stay open while registration is closed); that login was kept.
- **This chunk (owner requests, 2026-11-18):**
  - Staff usernames are the display name, unique, renamable by admins, and the login.
  - A password or PIN set by an admin is temporary: the user must choose their own at the
    next login (`must_change_password`; judge/admin APIs refuse until changed).
  - Full visual redesign in the style of the official flyer (owner shared it 2026-11-18):
    navy theme, ribbon red, cream, gold; Anton wordmark, Bebas Neue headings, Outfit body
    (all bundled, no outside requests); crest with crossed paddles, gold ball, navy shield
    and red ribbon (the real logo file will replace it when the owner sends it). Hero shows
    "SAMP CUP 2026 / YUVAK MANDAL / PICKLEBALL TOURNAMENT", date, age 22-35, Rt. 12 Pickle
    with address and directions, countdown, MySatsang note, contacts. Phone tab bar,
    scoreboard judge screen with ring timer, standings with medals, projector screen,
    installable on phones (manifest).
  - Home page (owner request): Bhagwan Swaminarayan murti image as the header, BAPS footer
    artwork on every page (owner-supplied images, WebP in `frontend/public/brand/`), live
    score ticker, court-by-court board, at-a-glance strip, group leaderboard. Team counts
    removed from public pages (admins still see them).
  - Venue, address, age group, ribbon text and contacts are settings in Admin -> Overview,
    stored in DynamoDB (contacts with phone numbers stay out of the public repo).
- **Player accounts (owner, 2026-11-18, replaces team logins):** a registered player creates
  their account once with first name + last name (any case) + center, then a username and
  password. Logged-in players invite a partner from their center; the partner sees the
  invitation when they log in and accepts or declines. Everyone logs in at `/login` with their
  own account; team passwords are gone. Player names are visible only to logged-in players of
  the same center until teams form; formed teams and members are public. Admins set or reset a
  player's login (temporary password, must change) and can release a wrongly claimed account.
  Same-name players at one center need the admin to set their logins.
- **Judges:** court-1..court-9; PINs in `~/dev/sampcup-judge-pins.txt` (owner's Mac only).
- **Waiting on the owner:** approve the production deploy (a permission check stopped me
  deploying without an explicit go-ahead), and the logo file (transparent PNG or SVG).
- **Next:** M10 runbook and paper fallback; failure drill on AWS; QR poster.
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
| 8 | Email address for alarm emails | Alerts on errors | Before the event | Done (confirm the AWS email) |
| 9 | Namecheap nameservers -> Route 53 | sampcup.com | Before registration opens | Done 2026-11-18 |
| 11 | Create the admin account | Admin login | Now | Done: `imgp004` |
| 12 | Email on @sampcup.com? | Route 53 records | - | None, closed |
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
- **Route 53 for DNS (owner, 2026-11-18):** zone and certificate in `infra/foundation`
  (long-lived, $0.50/month); the app stack adds the alias records. Registration stays at
  Namecheap.
- **Serverless AWS (owner, 2026-11-17):** CloudFront → S3 (site) and → Lambda function URL
  (API, Python 3.12 arm64, Mangum). DynamoDB on-demand with point-in-time recovery. No API
  Gateway, VPC, NAT or server. Everything by Terraform (`infra/`); state in S3 with native
  locking.
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
  player, matched by MISID). Players claim their account (name + center, once), then invite a
  same-center partner who accepts; then only admins can change the team. MISID is not used
  for sign-up (players never see it). Cap 42 active teams, then a waitlist.
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
- 2026-11-22 (late night): Fourth mock (`--speed 30`) to see the play-time home page and the
  player views (all 59 real players paired by center, so the owner's logins aalay and
  keertanp7 were in mock teams). Owner stopped it at 119/145 games; restored with
  `mock_restore.py`. The login jay123 (player 20) was the owner's test again: released.
  Logins in use now: aalay, hpatel, keertanp7, kpatel.
- 2026-11-22 (late): Owner's feedback after the mock, branch `home/live-layout`: once play
  starts (group play, knockout, finished) the home hero stops at "Unity in every rally";
  then the logged-in player's own game, Courts, Up next, Leaderboard, the venue card
  (address, Directions), then the rest. A logged-in player sees their next game on the home
  page as soon as the schedule is out, and the Schedule page opens on their own team ("Your
  game now/next", then "Your whole day"; "All teams" shows everyone). Owner confirmed the
  layout choices (asked first). Also removed the owner's test data: logins jay123 and parth1
  released, team "admins" deleted (snapshot before: `~/dev/sampcup-snapshot-2026-11-22-before-test-cleanup.json`).
- 2026-11-22 (night): Owner deployed the logos and backup-sheet changes (`foundation.sh apply`
  did not take: foundation state still from 11-18; rerun it). Third mock, `--speed 30`: 145
  games in ~18 min, champion Mock Team 13, Final 2-0; mock clock drove the header and the
  court-1 judge screen (G037 scored there, game time 6:19 mock); 0 server errors, 0
  throttles, no alarms. Owner added five 15-minute delays on purpose (testing), which moved
  the Final to 7:10-7:40 PM. Restored with `mock_restore.py`, keeping the owner's test
  logins jay123 (player 20) and parth1 (player 42) and 2 released logins (players 11, 37);
  asked the owner whether to release the test logins and remove team "admins".
- 2026-11-22: Owner redeployed; restored the 2026-11-21 snapshot (110 items). Branch
  `fix/final-series-and-judge-message`: Final kept together with series score, clearer judge
  message for a game finished on another phone, and the mock clock (owner: the header showed
  the real time during the mock).
- 2026-11-21 (night): Owner asked to take the app offline again. Saved a full snapshot
  (110 items), then ran `infra/destroy.sh`; foundation and state bucket kept.
- 2026-11-21: Owner asked to start the app. Two deploys overlapped (mine and the owner's);
  mine stopped on a rebuilt `api.zip`, the owner's finished all 42 resources. Restored the
  snapshot; site, API and www redirect verified.
- 2026-11-21 (evening): Second mock at ~20 s a game, finished after fixing the mock tool's
  court workers; restored keeping 3 real accounts made meanwhile; registration open again.
- 2026-11-18 (night): Owner asked to take the app offline for now. Saved a full snapshot,
  then ran `infra/destroy.sh`; foundation (zone + certificate) and state bucket kept.
- 2026-11-18 (evening): Mock tournament run twice on prod with the real registrations (teams
  by center, dummy partners for odd centers), then restored from a snapshot. Fixed the start
  rules, the court board and the server load found by it (see Current position).
- 2026-11-02: Tournament structure final. Application build started. Workspace moved out of OneDrive.
- 2026-11-02: M0 finished. Full stack verified in Docker, CI green.
- 2026-11-17: Registration export received (kept out of git). Range extended to 32-42. App
  built (M1-M7) on Postgres, merged to `main`.
- 2026-11-18: Owner created admin `imgp004`, imported the real export, gave the alert email.
  Built staff renames, temporary passwords and the full brand redesign (checked with
  screenshots at phone and desktop sizes on a local stack with demo data).
- 2026-11-18: Owner back; chose Route 53. Added `infra/foundation` (zone + certificate),
  redeployed the app, set the event date, created the 9 judge accounts. Owner switched the
  nameservers; certificate issued; sampcup.com live. An apply cut off mid-run left a stale
  state lock (released after checking no Terraform process held it) and was re-applied.
- 2026-11-17: Owner chose serverless AWS with Terraform. Backend moved to DynamoDB + Lambda,
  frontend to polling, infrastructure written and deployed (28 resources), dummy tournament
  passed on AWS, two bugs fixed, then the stack was destroyed at the owner's request.
