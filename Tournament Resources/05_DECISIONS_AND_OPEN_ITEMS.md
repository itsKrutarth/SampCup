# 05 Decisions and Open Items

## Decisions made (with reason)
- 40 teams, 9 courts, 6 pool games + at least 2 playoff games: owner requirement (min 8 games per team).
- 17-minute slots (12 min play + 5): realistic turnover; 15-min slots were too tight.
- Ranking order and clock/sudden-death rules: see 02 (owner-approved; steps 3 and 4 of the original proposal were merged by counting clock-ended games as 12:00).
- SSE instead of WebSockets: one-way updates are enough.
- Lunch is rolling per team (3 empty slots) because 40 teams cannot all stop at once.
- Playoff rest rule (1 empty slot): original scheduler had 7 zero-rest matches (one quarterfinal, both semifinals, both 5-8 placement games, final, 3rd place); fixed in scheduler v2.
- Cost: pool ends 2:49 PM (was 2:32) and playoffs end 5:59 PM (was 5:08); still about 61 minutes before 7 PM.

## Changes made to the original scheduler (v2)
1. LUNCH_REST_SLOTS 2 -> 3 (lunch gap 34 -> 51 min).
2. New ELIM_REST_SLOTS = 1; a playoff match's earliest start = latest prerequisite end + one slot.
3. Printed tiebreaker text replaced with the final ranking order and game rules.
4. Old warning replaced with a playoff rest rule note.
Original attached files remain unchanged as a fallback.

## Validated results (40 teams)
- Pool: 120 matches, 6 games each, no repeat opponents, no double booking, no back-to-back.
- Playoffs: 54 matches, zero back-to-back, no court double-booking, min 8 games per team in simulated brackets.
- Ranking: in 300 simulated tournaments, a random draw was needed in 1, never at the rank 32/33 cut.

## Known risks
- Odd team counts: bye teams play 5 pool games and rank unfairly low (average relative rank 0.646 vs fair 0.5 in simulation).
- Fields above about 56 teams do not fit before 7 PM at this slot length. Counts 36 and 37 finish late (6:16 and 6:33 PM).
- Slot-length overrun is the main schedule risk (see 02).
- Pool opponents are fixed by team number and not skill-based; strength of schedule varies.
- Speed tiebreaker depends on opponent; accepted by owner.
- Judge timing accuracy matters for step 3 of ranking; app must record timestamps automatically.

## Open questions for the owner (answer before the stage that needs them)
1. Google Sheet columns and sample rows (team name, player names, contacts, division?). Needed in Stage 1.
2. Odd team counts: add a house team, or normalize ranking per game for bye teams? Needed in Stage 5.
3. SMS: needs sender registration for US traffic (verify current AWS SNS/Twilio requirements and lead time). Default plan is email + in-app banner + optional web push. Needed in Stage 7.
4. How many judges/volunteers and devices (phones/tablets)? Judge PIN login per court? Stage 3-4.
5. Are playoff games first to 11 with the same 12-minute clock and sudden death? Assumed yes. Stage 5.
6. Any age/skill divisions or families-only rules affecting pairings? Assumed none. Stage 2.
7. Hosting budget and preferred AWS approach (ECS/RDS vs single instance). Stage 9.
8. Who handles photos/awards timing and what is the cutoff for a "running behind" decision? Stage 10.
9. Event date and domain/URL preference.
