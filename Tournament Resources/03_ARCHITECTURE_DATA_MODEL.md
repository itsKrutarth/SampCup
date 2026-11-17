# 03 Architecture and Data Model

## Components
- One FastAPI process serves the API, the live-update stream (SSE) and the built React frontend (same origin).
- Schedules: precomputed by `tools/export_schedules.py` from `sampcup_scheduler.py` (OR-Tools) for every team count 32-42, rule-checked, and stored in `backend/app/schedule_data/`. No solver runs in production.
- Ranking: `backend/app/tournament/ranking.py`, a byte-identical copy of `Tournament Resources/ranking.py` (a test enforces it).
- DB: PostgreSQL (SQLite in local tests).

## Tables (as built; see `backend/app/models.py`)
- tournament(name, event_date, timezone, registration_open, team_cap, draw_seed, schedule_locked)
- players(mis_id UNIQUE, first_name, last_name, center, zone, region, gender, tshirt_size, active, team_id)
- teams(name, name_key UNIQUE, password_hash, center, status[active|waitlist|withdrawn], checked_in, team_number UNIQUE, group, lunch_start)
- partner_requests(from_player_id, to_player_id, team_name, password_hash, status[pending|accepted|declined|cancelled])
- staff_users(username UNIQUE, display_name, role[admin|judge], password_hash, court, active)
- auth_sessions(token_hash UNIQUE, staff_id | team_id, expires_at)
- matches(code UNIQUE e.g. G001, R16-3, QF-2, SF-1, F-1..F-3; phase, group, round_label, slot, court, scheduled_at, source_a/b, team_a/b, prereqs, winner_goes_to, status[scheduled|in_progress|completed|cancelled], score_a/b, end_reason, seconds, winner_id, started_at, ended_at, version). One row per game; a forfeit is a completed game with end_reason forfeit.
- score_audit(match_id, action[start|final|forfeit|correct|reset], old_values, new_values, changed_by, reason, changed_at)
- announcements(title, body, active, created_by)
- delays(minutes, applied_from, matches_moved, created_by)
- Standings are computed from completed games on every request (no cache table).

## Key behaviors
- Import is idempotent via MISID. Never delete players on re-upload; mark missing players inactive and list affected teams.
- Team number draw: random permutation, stored, re-drawable only before schedule is locked.
- Schedule lock: after generation, matches have fixed pairings; admin may override court per match (`admin_override_court`) but not pairings after play starts.
- Knockout labels like "Group A 1st" and "Winner of R16-1" in the scheduler output become source_a/source_b; the app resolves them to real teams when group standings/results exist. Match codes, prereqs and winner destinations come from the scheduler (`match_id`, `prereqs`, `winner_goes_to`).
- Each team's lunch block comes from the scheduler and is shown on the my-team page and team slip.
- No game is ever scheduled during Sabha (3:30-4:30 PM). All group games end before it; the knockout is after it and the Final ends by 6:37 PM. The "Running behind" tool must keep these rules (a game pushed past 3:30 moves to after Sabha), must not create more than 2 games in a row for any team, and must not leave a team waiting more than 51 minutes between group games.
- Score entry: judge taps Start (stores started_at), enters points, presses Final (stores ended_at). Buttons: Clock Ended (if tied, forces sudden-death prompt), Sudden-Death winner, Forfeit. Validate exactly as `ranking.check_game`: no tied final score; reached_11 needs an 11; clock-ended games cannot pass 11; sudden death ends one point apart; forfeit is 11-0.
- seconds_for_ranking = real elapsed seconds only when end_reason = reached_11, else 720.
- Any correction by admin writes score_audit and triggers recompute of standings and downstream matches (with warning if downstream matches already started).
- Standings recompute is deterministic from game_results (see `Tournament Resources/ranking.py`): the random-draw seed is stored once per tournament and reused.
- The Final is best of 3: three match rows (F-1, F-2, F-3) on court 1; F-3 is cancelled when one team wins F-1 and F-2. The champion is the first team to 2 game wins.
- In a group of 8 each team plays one group-mate twice; both games count in the standings.

## APIs (as built; full list at /api/docs in development)
- Public: GET /api/public/overview, /schedule (?group, ?court, ?team), /standings, /bracket, /teams, /teams/{number}, /stream (SSE)
- Registration: GET /api/registration/status, /centers, /players?center=, /players/{id}; POST /requests, /requests/{id}/accept | decline | cancel
- Auth: POST /api/auth/team-login, /staff-login, /logout; GET /api/auth/me, /api/team/me
- Judge: GET /api/judge/matches; POST /api/judge/matches/{id}/start | score | finish | forfeit
- Admin: /api/admin/summary, /tournament, /players(/import), /teams, /requests, /draw, /schedule(/lock), /matches/{id} (court), /matches/{id}/correct | reset, /delays, /announcements, /staff, /audit, /export/results.csv

## Non-functional
- SSE with 15s heartbeat; clients auto-reconnect and refetch full state.
- Judge client queues unsent actions locally and retries.
- Rate limit public endpoints; admin/judge endpoints require auth.
- Secrets (DB password) only in `deploy/.env` on the server; never commit.
- Data: one tournament; keep backups; export final results CSV.
