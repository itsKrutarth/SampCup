# 02 Tournament Rules (LOCKED; change only with owner approval)

Format: **pool play + Gold/Silver brackets**, adopted 2026-10-26. It replaces the earlier pool + single-elimination plan; nothing from that plan applies any more.

## Day plan (set by the leads)
| Time | What |
|---|---|
| 9:00 - 9:45 AM | Breakfast, warm-up, check-in, team-number draw |
| 9:45 - 10:00 AM | Aarti and Deep pragatya |
| 10:00 AM | First pool game |
| 12:00 - 2:00 PM | Rolling lunch (each team at its own time, no single break) |
| about 2:00 PM | Pool play ends; 17-minute seeding break; brackets posted |
| by 3:30 PM | Gold play-in and Gold Round of 32 complete |
| 3:30 - 4:30 PM | Sabha, group photo, awards/gifts (no games) |
| 4:30 - 6:30 PM | Gold Round of 16, quarterfinals, semifinals, final; Silver bracket to its final |
| 6:30 - 7:00 PM | Wrap-up, final awards, thank-yous |

The building must be vacated by 7:00 PM.

## Constants
- 9 courts.
- Slot: 17 minutes = 12-minute game + 5 minutes to change courts, enter the score and drink water.
- Team count: 32 to 42, kept even (see Team count policy).

## Game rules
- Doubles teams. First team to 11 points wins. No win-by-2.
- 12-minute game clock.
- Clock ends with a lead: the team ahead wins and the score stands.
- Clock ends tied: sudden death. The next rally winner gets 1 point, added to their score (8-8 becomes 9-8 or 8-9).
- Forfeit / no-show: 11-0 for the other team, recorded game time 12:00.
- The same rules apply to every game, pool and knockout.

## Rest and lunch
- No team plays more than 3 games in a row (3 consecutive slots). After 3 in a row, a team sits out at least one slot.
- Every team gets a lunch break of at least 45 minutes between 12:00 and 2:00. With 17-minute slots that means 3 empty slots in a row (51 minutes); 2 empty slots (34 minutes) is not enough.
- Each team's lunch time is fixed by the schedule and printed on its team slip.
- Within those rules the scheduler gives teams as few back-to-back games as possible.

## Phase 1: Pool play (seeding games)
- Every team plays 6 games against 6 different opponents (circle-method pairings by team number).
- Team numbers are assigned by random draw at check-in so friends and family do not cluster.
- 40 teams: 120 games, 10:00 AM to 1:58 PM.

## Ranking after pool play (strict order)
1. Most wins (win = 1 point, loss = 0).
2. Highest cumulative score (sum of points scored in all pool games).
3. Lowest average game time. Games that reach 11 use the real time from first serve to the 11th point. Games ended by the clock (lead or sudden death) count as 12:00 (720 s). Forfeits count as 12:00.
4. Fewer points allowed.
5. Head-to-head, only when exactly two teams are tied and they played each other.
6. Random draw by admin (logged).

The UI must show which step broke each tie. Rank 1..N becomes Seed 1..N.

## Seeding break
One empty slot (17 minutes) after the last pool game. All pool scores must be entered; the admin clicks "Generate brackets"; seeds and the first knockout matches are posted.

## Phase 2: Gold bracket (every team)
- Single elimination by seed in standard bracket order (Seed 1 v 32, 16 v 17, 8 v 25 ...).
- More than 32 teams: the lowest seeds play **Gold play-in** games for the last Round of 32 places. With N teams, seeds (65 - N) to N play in and seeds 1 to (64 - N) go straight to the Round of 32. For 40 teams: seeds 25-40 play in (25 v 40 ... 32 v 33); seeds 1-24 wait for the Round of 32.
- Gold play-in and Round of 32 are played before Sabha. Round of 16 and later are played after Sabha.
- Gold quarterfinal losers play **5th-8th place games**. These decide a placement band, not a unique place.
- Gold semifinal losers play the **Gold 3rd place game**.
- The **Gold Final** is the last game of the day, played next to the Silver Final.

## Phase 2: Silver bracket (losers bracket)
- Every team that loses in the Gold play-in, Gold Round of 32 or Gold Round of 16 drops into Silver. No team is out after its first knockout loss.
- Silver is single elimination: a loss in Silver ends the team's day.
- The Silver champion is a separate title and does not play the Gold champion.
- Silver rounds alternate. In a drop-in round, newly arriving Gold losers meet Silver survivors. In the next round, the survivors play each other. Pairings are reversed/half-swapped to avoid quick rematches. For 40 teams:
  - Silver Round 1: 8 play-in losers v 8 Round of 32 losers; the other 8 Round of 32 losers go straight to Round 2.
  - Silver Round 2: 16 teams to 8.
  - Silver Round 3: those 8 v the 8 Gold Round of 16 losers.
  - Silver Round 4: 8 to 4. Then the Silver Semifinal (4 to 2) and the Silver Final.
- Why Gold quarterfinal losers play for 5th-8th instead of dropping into Silver: one more Silver round would not fit between 4:30 and 6:30 with the 3-in-a-row rule.

## Guarantees (checked by `check_schedule.py`)
- Every team plays at least 8 games (6 pool + at least 2 knockout) when the team count is even. The busiest teams play 13-14.
- No team plays more than 3 games in a row, and no team is ever booked in two games at once.
- Every team gets its 45+ minute lunch between 12:00 and 2:00.
- Every team that loses early in Gold gets at least one Silver game.
- The last game ends by 6:30 PM for every team count from 32 to 42.

## 40-team reference day
| Time | Games |
|---|---|
| 10:00 AM - 1:58 PM | Pool play: 120 games on 9 courts; lunch blocks start between 11:59 AM and 1:07 PM |
| 1:58 - 2:15 PM | Seeding break |
| 2:15 - 3:23 PM | Gold play-in (8), Gold Round of 32 (16), Silver Rounds 1-2 begin |
| 3:30 - 4:30 PM | Sabha |
| 4:30 - 6:29 PM | Gold Round of 16 (8), quarterfinals (4), semifinals (2), 5th-8th (2), 3rd place (1); Silver Rounds 2-4, Silver Semifinal (2); Gold Final and Silver Final at 6:12 PM |

The exact times and courts are in `sampcup_40team_knockout_schedule.csv` and `sampcup_40team_pool_schedule.csv`.

## Team count policy
- Supported: 32 to 42 teams. Keep the count even: with an odd count some teams get only 5 pool games (7 total) and rank unfairly low, so add a house or volunteer team.
- **Cap registration at 42 teams.** 43 teams still finish by 6:29, but 43 is odd (some teams get only 7 games) and adding a house team makes 44, which does not fit: at 44 the last game ends 7:03 PM and part of the Gold Round of 32 slips past Sabha.
- If the count changes, regenerate with `sampcup_scheduler.py --teams N` and rerun `check_schedule.py`.

## Time risks (operational)
- **The schedule has almost no slack.** At 40 teams the last game before Sabha ends at 3:23 (7 minutes spare), and the last game of the day ends at 6:29 (1 minute before wrap-up; 31 minutes before 7:00).
- Slot length is the biggest risk. Every extra minute per slot pushes the evening about 7 minutes later and the pre-Sabha games about 19 minutes later.
- The seeding break only works if the last pool scores are entered immediately; judges must enter scores before leaving the court.
- Admin "Running behind" tool shifts all remaining start times and notifies affected teams. The owner decides on the day how to recover (for example a shorter change-over, or eating into wrap-up time).
