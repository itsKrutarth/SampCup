# 02 Tournament Rules (LOCKED; change only with owner approval)

## Constants (40-team plan)
- Courts: 9. Slot length: 17 minutes (12 min play + 5 min switch/score/water). Check-in 9:30 AM. First game 10:00 AM.
- Hard stop: building vacated by 7:00 PM. Planned finish: about 5:59 PM (about 61 minutes spare).

## Game rules
- Doubles teams. First team to 11 points wins. No win-by-2 (first to 11 wins).
- 12-minute game clock.
- Clock ends with a lead: team ahead wins, score stands.
- Clock ends tied: sudden death. The next rally winner gets 1 point, and that point is ADDED to the winner's score (8-8 becomes 9-8 or 8-9).
- Forfeit / no-show: 11-0 for the other team, recorded game time 12:00.

## Phase 1: Pool play (ranking games)
- Every team plays exactly 6 games against 6 different opponents (circle-method pairings by team number).
- 120 matches for 40 teams, 10:00 AM to about 2:49 PM.
- No team plays in consecutive slots. Each team gets one lunch gap of at least 3 empty slots (51 min) after its game 2, 3 or 4 (rotated by team number); lunch is rolling, not one big break.
- Team numbers are assigned by random draw at check-in so friends/family do not cluster.

## Ranking (after all pool games; strict order)
1. Most wins (win = 1 point, loss = 0).
2. Highest cumulative score (sum of points scored in all pool games).
3. Lowest average game time. Games that reach 11 use the real time from first serve to the 11th point. Games ended by the clock (lead or sudden death) count as 12:00 (720 s). Forfeits count as 12:00.
4. Fewer points allowed.
5. Head-to-head, only when exactly two teams are tied and they played each other.
6. Random draw by admin (logged).
The UI must show which step broke each tie.

## Seeding break
20 minutes after the last pool game (about 2:49 to 3:09 PM). Admin clicks "Generate playoffs". Ranks map to Seed 1..N.

## Phase 2: Playoffs (every team plays at least 2 playoff games, so at least 8 total)
- Main bracket: seeds 1-32. Round of 32 (Seed 1 v 32, 2 v 31 ... standard bracket order) = Game 7; Round of 16 = Game 8; then Quarterfinals, Semifinals, Final, 3rd place game.
- Losers of Round of 32 play each other (places 17-32). Losers of Round of 16 play each other (places 9-16). Losers of quarterfinals play each other (places 5-8). Semifinal losers play the 3rd place game.
- Lower bracket: seeds 33-40 in two groups of 4 (semifinals, then final + 3rd place); 8 games each total.
- Every playoff match may start only after at least one empty slot (17 min) following the matches that feed it, so no team plays back-to-back.
- Expected playoff window: 3:09 PM to 5:59 PM (final and 3rd place game at 5:42 PM).
- Early-loser placement games determine a placement band, not a full unique ranking within that band.

## Team count policy
- Plan is 40 teams. Keep team count EVEN. Tested 8-64; all even counts 8-56 give 6 pool games and at least 8 total games and finish before 7 PM; 58+ do not fit. Recommended cap: 48 teams.
- Odd counts give some teams a bye (5 pool games, 7 total) and bias their ranking; avoid by adding a house/volunteer team (see open items).
- If the count changes, regenerate schedules with the scheduler and re-run the checks in `reference/`.

## Time-risk rules (operational)
- Slot length is the biggest risk: each extra minute per slot pushes the finish about 27 minutes later (19-minute slots finish 6:53 PM; 20 minutes misses the deadline).
- 8 courts give the same finish as 9 (one spare court). 7 courts finish 6:50 PM; 6 courts miss 7 PM.
- Starting 60 minutes late leaves about 1 minute spare.
- Admin "Running behind" tool shifts all remaining start times and notifies affected teams. Suggested trigger: if pool play will end after 3:00 PM, consider shortening playoff games (owner decision on the day).
