# 02 Tournament Rules (LOCKED; change only with owner approval)

Format: **group play, then a 16-team knockout with a best-of-3 Final.** Teams are split into 4 random groups and every team plays at least 8 games inside its group. The top 4 of every group go to a Round of 16, quarterfinals, semifinals and a best-of-3 Final. Adopted 2026-10-29; it replaces every earlier format.

## Day plan (40 teams)
| Time | What |
|---|---|
| 9:00 - 9:45 AM | Breakfast, warm-up, check-in, team-number draw (sets the groups) |
| 9:45 - 10:00 AM | Aarti and Deep pragatya |
| 10:00 AM - 3:23 PM | Group play: 160 games on 9 courts |
| 12:00 - 2:00 PM | Rolling lunch (each team at its own time, no single break) |
| 3:30 - 4:30 PM | Sabha, group photo, awards/gifts (no games); group standings and the bracket are posted |
| 4:30 PM | Round of 16 (8 games) |
| 4:47 PM | Quarterfinals (4 games) |
| 5:04 PM | rest (no team plays more than 2 games in a row) |
| 5:21 PM | Semifinals (2 games) |
| 5:38 PM | rest |
| 5:55 PM | **Final, best of 3** (court 1): game 1 5:55, game 2 6:10, game 3 (if needed) 6:25 |
| 6:22 or 6:37 PM | Final over (2-0 or 2-1); final awards, thank-yous, wrap-up until 7:00 |

The building must be vacated by 7:00 PM.

## Constants
- 9 courts.
- Slot: 17 minutes = 12-minute game + 5 minutes to change courts, enter the score and drink water.
- Team count: any number from 34 to 42 (see Team count policy).

## Game rules
- Doubles teams. First team to 11 points wins. No win-by-2.
- 12-minute game clock.
- Clock ends with a lead: the team ahead wins and the score stands.
- Clock ends tied: sudden death. The next rally winner gets 1 point, added to their score (8-8 becomes 9-8 or 8-9).
- Forfeit / no-show: 11-0 for the other team, recorded game time 12:00.
- The same rules apply to every game, including each game of the Final.

## Rest and lunch (every team, all day)
- **At most 2 games in a row** (2 consecutive slots). After 2 in a row, a team sits out at least one slot. This holds in group play and the knockout; the best-of-3 Final is one match (its games are played back to back, 3 minutes apart).
- **No break longer than lunch.** In group play a team never waits more than 3 empty slots (51 minutes) between its games, and its first game is no later than 10:51 AM.
- **Lunch:** every team gets one break of 3 empty slots (51 minutes) between 12:00 and 2:00 PM.
- Each team's game times, courts and lunch are fixed by the schedule and printed on its team slip.
- Within those rules the scheduler gives teams as few back-to-back games as possible.

## Phase 1: Group play
- Team numbers are drawn at random at check-in. Groups are consecutive team numbers (40 teams: Group A = Teams 1-10, B = 11-20, C = 21-30, D = 31-40), so the groups are random. Groups are as even as possible (largest first).
- **Every team plays 8 group games.** In a group of 9 that is everyone once; in a group of 10 or 11 each team misses 1 or 2 group-mates. A group of 8 has only 7 opponents, so everyone also plays one group-mate a second time (the team opposite it in the group: 1st v 5th, 2nd v 6th, 3rd v 7th, 4th v 8th of the group list).
- Odd team counts need nothing special: every group size gives every team exactly 8 games.

| Teams | Group sizes (A / B / C / D) | Group games | Group play ends |
|---|---|---|---|
| 34 | 9 / 9 / 8 / 8 | 136 | 2:49 PM |
| 35 | 9 / 9 / 9 / 8 | 140 | 2:49 PM |
| 36 | 9 / 9 / 9 / 9 | 144 | 2:49 PM |
| 37 | 10 / 9 / 9 / 9 | 148 | 3:06 PM |
| 38 | 10 / 10 / 9 / 9 | 152 | 3:06 PM |
| 39 | 10 / 10 / 10 / 9 | 156 | 3:06 PM |
| 40 | 10 / 10 / 10 / 10 | 160 | 3:23 PM |
| 41 | 11 / 10 / 10 / 10 | 164 | 3:23 PM |
| 42 | 11 / 11 / 10 / 10 | 168 | 3:23 PM |

Group games must finish by 3:30 PM: there is room for 19 slots x 9 courts = 171 games.

## Group standings (strict order, inside each group)
1. Most wins (win = 1 point, loss = 0).
2. Highest cumulative score (sum of points scored in all group games).
3. Lowest average game time. Games that reach 11 use the real time from first serve to the 11th point. Games ended by the clock (lead or sudden death) count as 12:00 (720 s). Forfeits count as 12:00.
4. Fewer points allowed.
5. Head-to-head, only when exactly two teams are still tied: the team with more wins in the games between them (in an 8-team group they may have played twice; 1-1 does not decide).
6. Random draw (seeded and logged by the admin, so recomputing gives the same order).

The UI must show which step placed each team below the team above it (`decided_by` in `ranking.py`). Standings are final when the last group game ends; they and the bracket are posted during Sabha.

## Phase 2: Knockout (top 4 of each group, 16 teams)
Single elimination; a loss ends the team's day. Teams from the same group cannot meet before the semifinals.

| Round of 16 (4:30 PM, courts 1-8) | goes to |
|---|---|
| R16-1: A 1st v B 4th | QF-1 |
| R16-2: C 2nd v D 3rd | QF-1 |
| R16-3: D 1st v C 4th | QF-2 |
| R16-4: B 2nd v A 3rd | QF-2 |
| R16-5: C 1st v D 4th | QF-3 |
| R16-6: A 2nd v B 3rd | QF-3 |
| R16-7: B 1st v A 4th | QF-4 |
| R16-8: D 2nd v C 3rd | QF-4 |

- Quarterfinals 4:47 PM (courts 1-4): QF-1 and QF-2 feed SF-1; QF-3 and QF-4 feed SF-2.
- Semifinals 5:21 PM (courts 1-2), after a rest slot: Round of 16 and quarterfinal are already 2 in a row.
- **Final: best of 3** on court 1, after a rest slot. Game 1 at 5:55 PM, game 2 at 6:10 PM, game 3 at 6:25 PM only if the games are 1-1. The first team to win 2 games is the SAMP Cup champion. Every game uses the normal game rules.
- No 3rd-place game.

## Guarantees (checked by `check_schedule.py` and `simulate_tournament.py` for every team count 34-42)
- Every team plays at least 8 group games, against group-mates only (one rematch each in a group of 8, none otherwise). Over the day teams play 8 to 14 games.
- All group games end before Sabha; no games during Sabha.
- No team plays more than 2 games in a row, waits more than 51 minutes between group games, or starts later than 10:51 AM; no team is ever booked in two games at once.
- Every team gets its 51-minute lunch between 12:00 and 2:00.
- Group standings are a full ranking of each group, every tie is resolved by the steps above, and recomputing gives the same result.
- The Round of 16 holds exactly the top 4 of every group; same-group teams cannot meet before the semifinals.
- The Final is won by the first team to 2 game wins; it ends by 6:37 PM (6:22 PM if 2-0).

## Court release (40 teams, `sampcup_40team_court_plan.csv`)
| Courts | Free after |
|---|---|
| 9 | 3:23 PM (end of group play) |
| 5, 6, 7, 8 | 4:47 PM (after the Round of 16) |
| 3, 4 | 5:04 PM (after the quarterfinals) |
| 2 | 5:38 PM (after the semifinals) |
| 1 | 6:22 PM (Final 2-0) or 6:37 PM (2-1) |

All 9 courts are needed during group play; after Sabha the most needed at once is 8.

## Team count policy
- Supported and checked: any count from 34 to 42; odd counts are fine.
- 43 or more teams cannot each get 8 group games before Sabha (43 x 8 / 2 = 172 games; the courts hold 171). Cap registration at 42.
- If the count changes, regenerate with `sampcup_scheduler.py --teams N` and rerun `simulate_tournament.py --teams N`.

## Time risks (operational)
- Group play is tight: from 40 teams on it ends at 3:23 PM, 7 minutes before Sabha (at 42 teams it uses 168 of the 171 court slots). Every extra minute per slot pushes the end of group play about 19 minutes later.
- The knockout ends 6:22-6:37 PM, leaving 23-38 minutes for awards before 7:00.
- Teams outside the top 4 of their group are done after group play.
- Admin "Running behind" tool shifts remaining start times and notifies affected teams. If group play runs late, the owner decides on the day (for example a shorter change-over).
