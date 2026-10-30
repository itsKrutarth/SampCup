# 03 Architecture and Data Model

## Components
- API service (FastAPI): auth, import, scheduling, scoring, ranking, bracket, announcements, SSE stream.
- Scheduler library: wraps `Tournament Resources/sampcup_scheduler.py` (groups, group play via OR-Tools CP-SAT, knockout bracket and times; no I/O) behind a service function. `check_schedule.py` (rule checker) and `simulate_tournament.py` (full simulated tournaments) become the test suite.
- Ranking library: `Tournament Resources/ranking.py` behind a service function; called once per group; returns rank, stats and `decided_by` per team.
- DB: PostgreSQL.
- Web UI: Public, Judge, Admin areas.
- Worker/async tasks: Sheets sync, email sending.

## Tables (minimum)
- tournaments(id, name, date, courts, slot_minutes, start_time, game_minutes, lunch_start, lunch_end, sabha_start, sabha_end, last_game_end, group_games (8), max_in_a_row (2), max_gap_minutes (51), final_best_of (3), random_draw_seed, status)
- teams(id, tournament_id, sheet_row_id UNIQUE, name, players, contact_email, contact_phone, team_number NULL until draw, group NULL until draw, checked_in, lunch_start NULL until schedule, notes)
- courts(id, number, active, judge_user_id NULL)
- users(id, name, role[admin|judge], pin_hash/password_hash)
- matches(id, tournament_id, phase[group|knockout], group NULL, match_code (e.g. R16-3, QF-2, SF-1, F-1, F-2, F-3), round_label, source_a, source_b, team_a_id NULL, team_b_id NULL, court_id, scheduled_time, status[scheduled|in_progress|completed|forfeit|cancelled], prereq_match_ids[], winner_goes_to_match_id NULL, admin_override_court). Single elimination: a knockout loser goes nowhere.
- game_results(id, match_id, started_at, ended_at, score_a, score_b, end_reason[reached_11|clock_lead|sudden_death|forfeit], seconds_for_ranking, entered_by, version)
- score_audit(id, match_id, old_values, new_values, changed_by, changed_at, reason)
- standings_cache(team_id, group, wins, points_for, points_against, avg_seconds, rank, decided_by[""|wins|points scored|average game time|points allowed|head-to-head|random draw])
- announcements(id, title, body, audience[all|team|court|match], channel[banner|email|sms], target_ids, sent_at, created_by)
- delays(id, minutes, applied_from_time, created_by, created_at)

## Key behaviors
- Import is idempotent via sheet_row_id. Never delete teams on re-sync; mark missing rows as inactive and warn admin.
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

## APIs (sketch)
- POST /admin/sync-teams; GET /admin/teams; POST /admin/draw-numbers
- POST /admin/schedule/generate; POST /admin/schedule/lock; PATCH /admin/matches/{id}/court
- POST /admin/brackets/generate (after group play; fills the Round of 16 from the top 4 of each group)
- POST /judge/matches/{id}/start | /score | /final | /forfeit
- POST /admin/matches/{id}/correct
- POST /admin/delay {minutes, from_time}
- POST /admin/announcements; GET /public/announcements
- GET /public/schedule, /public/standings (per group), /public/bracket, /public/team/{number}
- GET /public/stream (SSE events: score_update, match_status, standings, bracket, announcement, delay)

## Non-functional
- SSE with 15s heartbeat; clients auto-reconnect and refetch full state.
- Judge client queues unsent actions locally and retries.
- Rate limit public endpoints; admin/judge endpoints require auth.
- Secrets (Google key, DB, SES) in AWS Secrets Manager or env vars; never commit.
- Data: one tournament; keep backups; export final results CSV.
