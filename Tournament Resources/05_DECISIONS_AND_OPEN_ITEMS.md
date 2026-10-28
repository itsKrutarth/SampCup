# 05 Decisions and Open Items

## Decisions made (with reason)
- **Format: pool play + Gold/Silver brackets (2026-10-26).** The leads asked for a loser's bracket for every team inside their day plan (games 10:00-3:30, Sabha 3:30-4:30, Round of 16 to finals 4:30-6:30). True double elimination was measured and does not fit: at 40 teams the grand final would end about 8:11 PM (8:45 PM with a rematch final). Gold/Silver gives every early loser a second chance, and the whole day fits by 6:29 PM.
- **Gold quarterfinal losers play for 5th-8th instead of dropping into Silver.** One more Silver round needs an eighth evening slot; there are seven between 4:30 and 6:30.
- **6 pool games per team.** Pool play seeds both brackets and, with at least 2 knockout games, guarantees every team at least 8 games (owner requirement).
- **17-minute slots (12 min play + 5 min change-over).** Set by the leads.
- **At most 3 games in a row** for any team. Set by the leads ("1, 2 or 3 back to back is fine, not more").
- **Rolling lunch 12:00-2:00:** each team gets 3 empty slots (51 min) inside the window, which meets the 45-minute minimum. 2 slots (34 min) would not.
- **9 courts; supported team counts 32-42; cap registration at 42.** Measured with the final scheduler: 43 teams fit (6:29) but are odd, and a house team would make 44; 44 teams finish 7:03 PM with part of the Gold Round of 32 after Sabha.
- **Exact pool solver (Google OR-Tools CP-SAT).** A simple greedy scheduler needs one extra pool slot at 40-42 teams, which pushes the finish to about 6:46 PM. The exact solver finds the 14-slot pool. It runs single-threaded on a fixed work limit, so results are reproducible.
- **Seeding break of one slot (17 min)** between pool play and the knockout. Starting the knockout in the next slot was tested and can create 4 games in a row.
- **Ranking order and clock/sudden-death rules:** owner-approved (see 02). Clock-ended games count as 12:00 in the time tiebreak.
- **SSE instead of WebSockets:** one-way updates are enough.

## Validated results (`check_schedule.py --teams 32-42`, 300 simulated result sets per team count)
- Every team count from 32 to 42 finishes by 6:29 PM, with Gold play-in and Round of 32 before Sabha and Gold Round of 16 onward after it.
- No team plays more than 3 in a row; no team is double-booked; every team gets its lunch; every early Gold loser plays in Silver.
- Even team counts: every team plays at least 8 games (most 13-14). Odd counts: teams with a pool bye get 7.
- 40 teams: 120 pool matches (10:00 AM-1:58 PM) + 73 knockout matches (2:15-6:29 PM).

## Known risks
- **Almost no slack.** At 40 teams: 7 minutes spare before Sabha, 1 minute before 6:30 (31 before 7:00). Slot-length overrun is the main risk.
- Odd team counts: bye teams play 5 pool games and rank unfairly low.
- Pool opponents are fixed by team number, not skill; strength of schedule varies.
- The speed tiebreak depends on the opponent; accepted by owner.
- Judge timing accuracy matters for ranking step 3; the app must record timestamps automatically.
- The seeding break needs every last-slot pool score entered within minutes.
- Some teams play up to 13-14 games in the day.

## Known issues to fix in code
- `ranking.py` (Stage 5):
  - A tied final score is silently counted as a win for team B; it should be rejected.
  - Ranking guesses whether a game reached 11 from the score. It should use `end_reason`: a 10-10 sudden-death game becomes 11-10 and must count as 12:00.
  - It does not record which tiebreak step separated each team (the UI must show it).
- Repo setup (Stage 0): missing `.gitignore`, `.env.example` and CI workflow, which the README promises; no Alembic setup yet; frontend uses Node 20 (end of life). `ortools` must be added to the backend requirements when the scheduler moves into the backend.

## Open questions for the owner (answer before the stage that needs them)
1. Google Sheet columns and sample rows (team name, player names, contacts, division?). Needed in Stage 1.
2. Odd team count on the day: add a house/volunteer team (recommended)? Needed in Stage 5.
3. SMS: needs sender registration for US traffic (verify current AWS SNS/Twilio requirements and lead time). Default plan is email + in-app banner + optional web push. Needed in Stage 7.
4. How many judges/volunteers and devices (phones/tablets)? Judge PIN login per court? Stage 3-4.
5. Do the Silver champion and the 5th-8th place games get awards? Affects the 6:30 ceremony. Stage 10.
6. Any age/skill divisions or families-only rules affecting pairings? Assumed none. Stage 2.
7. Hosting budget and preferred AWS approach (ECS/RDS vs single instance). Stage 9.
8. Who decides on the day if the schedule runs late, and what is the first recovery step (shorter change-over, use wrap-up time)? Stage 10.
9. Event date and domain/URL preference.
