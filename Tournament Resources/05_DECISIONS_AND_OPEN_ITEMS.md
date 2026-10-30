# 05 Decisions and Open Items

## Decisions made (with reason)
- **Format: group play + 16-team knockout (2026-10-29).** The leads' plan: random groups, the top 4 of each group into a Round of 16, then quarterfinals, semifinals and Final. Simple to run and to explain.
- **Best-of-3 Final (2026-10-29).** Owner request: the finalists play up to 3 games; the first to win 2 is champion. Games 3 minutes apart on court 1; game 3 only at 1-1.
- **At least 8 group games for every team (2026-10-29).** Owner request ("more is fine, never less"). Every group size gives exactly 8; a group of 8 (only 7 opponents) adds one rematch per team.
- **4 groups for every team count, as even as possible.** Top 4 x 4 groups = 16 teams, exactly a Round of 16.
- **Team count 34-42.** 8 games each must fit before Sabha: 19 slots x 9 courts = 171 games; 43 teams would need 172.
- **At most 2 games in a row, all day (2026-10-29).** Owner request ("they need rest"). In the knockout this puts rest slots before the semifinals (5:21) and before the Final (5:55). The best-of-3 Final counts as one match.
- **No break longer than lunch (2026-10-29).** Owner request ("they will get bored"): in group play no team waits more than 3 empty slots (51 min) between games, and every team's first game is by 10:51 AM.
- **The day now ends 6:22-6:37 PM, not 5:50.** A consequence of the best-of-3 Final plus the 2-in-a-row rule: the Final cannot start before 5:55. Still before the 7:00 PM deadline.
- **Groups by team-number draw:** team numbers are drawn at random at check-in and groups are consecutive numbers, so groups are random. Inside a group of 10-11 each team plays the group-mates nearest it in a circle (circulant pairing), so every team plays exactly 8 different opponents.
- **Same-group teams cannot meet before the semifinals:** the Round of 16 pairs 1st v 4th and 2nd v 3rd of neighbouring groups, spread over all four quarters of the bracket.
- **Standings and bracket posted during Sabha:** no separate seeding break, which gives group play the whole time up to 3:30.
- **No 3rd-place game, no placement games.**
- **Exact group-play solver (Google OR-Tools CP-SAT), one small solve per group.** Groups only share courts, so each group gets a fixed share per slot (2 of the 9 courts, the 9th rotating to the groups that need it) and is scheduled on its own. A whole-field solve (42 teams: 168 games in 171 court slots) could not be found reliably; per-group solves take about 1-3 minutes per team count, run single-threaded on a fixed work limit, and give the same schedule every time.
- **Ranking per group (`ranking.py`, rewritten 2026-10-29):** ranks one group; rejects impossible results (tied scores, wrong end reasons); uses `end_reason` for the time tiebreak; head-to-head counts wins between the two tied teams (works with rematches); random draw seeded; returns `decided_by` for every team.
- **17-minute slots (12 min play + 5 min change-over), rolling lunch 12:00-2:00 with 3 empty slots (51 min):** leads' rules.
- **Ranking order and clock/sudden-death rules:** owner-approved (see 02), applied inside each group.
- **SSE instead of WebSockets:** one-way updates are enough.

## Formats tried and rejected (do not re-propose without a change in the rules)
- Pool play + Gold/Silver brackets with placement games, separate Gold and Silver champions.
- Gold/Silver with one SAMP Cup Final (Gold winner v Silver winner), in several versions of who gets a second chance.
- Double elimination for every team.
- Group play with 7 games for 43+ teams (replaced by "at least 8 for everyone", range 34-42).

## Validated results (`simulate_tournament.py --teams 34-42`: every rule check plus 200 full simulated tournaments per team count)
- Every team count from 34 to 42 passes every check (1,800 simulated tournaments in total).
- Group play ends 2:49 PM (34-36 teams), 3:06 PM (37-39) or 3:23 PM (40-42). The Final ends 6:22 PM (2-0) or 6:37 PM (2-1); it went to game 3 in about half the simulations.
- Every team plays 8 group games; over the day 8 to 14 games. No team ever plays more than 2 in a row, waits more than 51 minutes between group games, or starts after 10:51 AM; every team gets its 51-minute lunch; no team is double-booked; courts never clash.
- At 40 teams: at most 2 back-to-back pairs for any team in group play.
- Standings: every group is fully ranked, every tie gets a reason, and recomputing gives the same order. With realistic random scores, the 4th/5th cut (who goes through) was decided by points scored about 55% of the time, wins about 38% and average game time about 4%; random draw did not decide it. In the forced-tie tournaments (every game 11-9) head-to-head and random draw were exercised and behaved as specified.
- The Round of 16 always holds the 16 group qualifiers; the best-of-3 Final always ends with a team on 2 wins, with game 3 played only at 1-1.
- `ranking.py` self-tests cover sudden death, clock-ended times, head-to-head, split rematches, three-way draws, reordered tie blocks and rejected impossible results.

## Known risks
- **Group play is tight.** From 40 teams on it ends 3:23 PM, 7 minutes before Sabha (42 teams use 168 of 171 court slots); slot-length overrun is the main risk.
- Teams outside the top 4 of their group are done after group play (about 3:00-3:20 PM); 24 of 40 teams do not play after Sabha.
- In groups of 10-11 not every pair plays, and in groups of 8 each team plays one group-mate twice, so strength of schedule varies a little inside a group.
- The speed tiebreak depends on the opponent; accepted by owner.
- Judge timing accuracy matters for ranking step 3; the app must record timestamps automatically.
- All group scores must be entered before Sabha so the bracket can be posted.

## Known issues to fix in code
- Repo setup (Stage 0): missing `.gitignore`, `.env.example` and CI workflow, which the README promises; no Alembic setup yet; frontend uses Node 20 (end of life). `ortools` must be added to the backend requirements when the scheduler moves into the backend.

## Open questions for the owner (answer before the stage that needs them)
1. Google Sheet columns and sample rows (team name, player names, contacts, division?). Needed in Stage 1.
2. SMS: needs sender registration for US traffic (verify current AWS SNS/Twilio requirements and lead time). Default plan is email + in-app banner + optional web push. Needed in Stage 7.
3. How many judges/volunteers and devices (phones/tablets)? Judge PIN login per court? Stage 3-4.
4. Awards: champion and runner-up only, or also group winners? Affects the 6:22-7:00 wrap-up. Stage 10.
5. Teams outside the top 16 finish around 3:00 PM: anything for them after Sabha (friendly games on the free courts)? Optional.
6. Any age/skill divisions or families-only rules affecting groups? Assumed none (random groups). Stage 2.
7. Hosting budget and preferred AWS approach (ECS/RDS vs single instance). Stage 9.
8. Who decides on the day if the schedule runs late, and what is the first recovery step (shorter change-over)? Stage 10.
9. Event date and domain/URL preference.
10. Hand back courts as they free up (court plan)? Depends on how the venue bills. Before booking the venue.
