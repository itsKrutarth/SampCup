# 03 Architecture and Data Model

## Components
- API service (FastAPI): auth, import, scheduling, scoring, ranking, bracket, announcements, SSE stream.
- Scheduler library: wraps `reference/pickleball_tournament_scheduler_v2.py` logic (pure Python, no I/O) behind a service function.
- Ranking library: `reference/ranking.py` logic behind a service function.
- DB: PostgreSQL.
- Web UI: Public, Judge, Admin areas.
- Worker/async tasks: Sheets sync, email sending.

## Tables (minimum)
- tournaments(id, name, date, courts, slot_minutes, start_time, game_minutes, status)
- teams(id, tournament_id, sheet_row_id UNIQUE, name, players, contact_email, contact_phone, team_number NULL until draw, checked_in, notes)
- courts(id, number, active, judge_user_id NULL)
- users(id, name, role[admin|judge], pin_hash/password_hash)
- matches(id, tournament_id, phase[pool|playoff|lower], round_label, source_a, source_b, team_a_id NULL, team_b_id NULL, court_id, scheduled_time, status[scheduled|in_progress|completed|forfeit|cancelled], prereq_match_ids[], loser_goes_to_match_id NULL, winner_goes_to_match_id NULL, admin_override_court)
- game_results(id, match_id, started_at, ended_at, score_a, score_b, end_reason[reached_11|clock_lead|sudden_death|forfeit], seconds_for_ranking, entered_by, version)
- score_audit(id, match_id, old_values, new_values, changed_by, changed_at, reason)
- standings_cache(team_id, wins, points_for, points_against, avg_seconds, rank, tiebreak_note)
- announcements(id, title, body, audience[all|team|court|match], channel[banner|email|sms], target_ids, sent_at, created_by)
- delays(id, minutes, applied_from_time, created_by, created_at)

## Key behaviors
- Import is idempotent via sheet_row_id. Never delete teams on re-sync; mark missing rows as inactive and warn admin.
- Team number draw: random permutation, stored, re-drawable only before schedule is locked.
- Schedule lock: after generation, matches have fixed pairings; admin may override court per match (`admin_override_court`) but not pairings after play starts.
- Playoff labels like "Seed 1" and "Winner of R32-M1" in the scheduler output become source_a/source_b; the app resolves them to real teams when ranks/results exist. Match ids and prereqs come from the scheduler (`mid`, `prereqs`).
- Score entry: judge taps Start (stores started_at), enters points, presses Final (stores ended_at). Buttons: Clock Ended (if tied, forces sudden-death prompt), Sudden-Death winner, Forfeit. Validate: someone has 11, OR clock-ended flag set.
- seconds_for_ranking = real elapsed seconds only when end_reason = reached_11, else 720.
- Any correction by admin writes score_audit and triggers recompute of standings and downstream matches (with warning if downstream matches already started).
- Standings recompute is deterministic from game_results (see `reference/ranking.py`); random draw results are stored once and reused.

## APIs (sketch)
- POST /admin/sync-teams; GET /admin/teams; POST /admin/draw-numbers
- POST /admin/schedule/generate; POST /admin/schedule/lock; PATCH /admin/matches/{id}/court
- POST /admin/playoffs/generate (after pool complete)
- POST /judge/matches/{id}/start | /score | /final | /forfeit
- POST /admin/matches/{id}/correct
- POST /admin/delay {minutes, from_time}
- POST /admin/announcements; GET /public/announcements
- GET /public/schedule, /public/standings, /public/bracket, /public/team/{number}
- GET /public/stream (SSE events: score_update, match_status, standings, bracket, announcement, delay)

## Non-functional
- SSE with 15s heartbeat; clients auto-reconnect and refetch full state.
- Judge client queues unsent actions locally and retries.
- Rate limit public endpoints; admin/judge endpoints require auth.
- Secrets (Google key, DB, SES) in AWS Secrets Manager or env vars; never commit.
- Data: one tournament; keep backups; export final results CSV.
