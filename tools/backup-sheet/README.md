# Backup sheet: run the day without the app, then hand it back

A Google Sheet that keeps a full copy of the tournament, updated every minute. If the app
goes down, organizers run the day from the sheet. When the app comes back, one menu click
sends everything recorded in the sheet to the app, and the app carries on from there.

## How it works
- **Fills itself.** Set the sheet up once (below). From then on it copies the app every
  minute: before the draw it holds the teams; the moment the schedule comes out it holds
  every game, and all day it follows results, standings and the bracket.
- **Never loses the last copy.** It only replaces its copy with a good answer from the app,
  so if the app goes down the sheet keeps the last state.
- **Can run the day.** In manual mode organizers type results; the sheet ranks the groups by
  the app's exact rules, fills the knockout games and settles the best-of-3 Final.
- **Hands it back.** When the app is back, the sheet sends every changed row (results with
  their game times, new times, new courts). The app applies them in schedule order, so each
  round's winners fill the next round, and reports anything it could not take.
- **Safe and free.** The sheet reads the public pages and only writes to the app when an
  admin logs in from the sheet (the password is never stored). Nothing extra runs on AWS.
- **Tested against the app.** `backend/tests/test_backup_sheet.py` runs the sheet's own code
  against a whole simulated day: same rankings as the app (3,000 random groups), the rest of a
  day run in the sheet and sent back (the app ends with the same standings, bracket, game
  times and champion), and every menu on a stand-in for Google Sheets.

## The tabs
| Tab | What it shows | Who edits it |
|---|---|---|
| **Info** | Mode (AUTO or MANUAL), when it last copied the app, champion, what to do | Nobody (the menu changes it) |
| **Courts** | Each court: the game on it now (with the score) and its next game | Nobody (follows Schedule) |
| **Schedule** | Every game: time, court, teams, score, how it ended, game time, winner | Organizers, in MANUAL mode only |
| **Bracket** | Round of 16, quarterfinals, semifinals and the Final, with scores and winners | Nobody (follows Schedule) |
| **Standings** | Each group's table, with how ties were placed | Nobody (copied, or recomputed) |
| **Teams** | Every team by group: number, players, center, lunch time | Nobody |

## Set it up (once, about 5 minutes)
1. With the Google account that should own it, create a blank sheet (go to `sheets.new`) and
   name it "SampCup 2026 backup".
2. Choose **Extensions > Apps Script**. Delete the sample code, paste all of
   [`Code.gs`](Code.gs) (on GitHub: open the file, **Raw**, copy everything), then **Save**.
3. Pick `setup` in the function list at the top and click **Run**. Google asks for
   permission: **Review permissions**, choose the account, then on "Google hasn't verified
   this app" click **Advanced > Go to ... (unsafe)** and **Allow**. It is your own script: it
   edits this one sheet, reaches sampcup.com, runs every minute, and shows the login window.
4. Back in the sheet, reload the page: the tabs are there and a **SampCup** menu appears.
   Info > "Last check" should end in "OK".
5. Share the sheet (Editor) with the organizers who would run the day without the app. Keep
   it private: it lists players' names.
6. Copy the sheet's address from the browser and paste it in the app: **Admin > Overview >
   Settings > Backup sheet address**, then **Save settings**. Admins then open it from Admin >
   Overview > **Open the backup sheet**.

To update the script later (a new `Code.gs`): paste it over the old one and save. Missing
tabs are added at the next copy. Run `setup` again only to start the sheet afresh.

## On the day
- Glance at **Info > Last good copy**: it should be a minute or two old.
- After the draw, print the **Schedule** and **Teams** tabs (File > Print, fit to width): if
  the venue Wi-Fi fails, paper is the backup for the backup.
- In AUTO mode don't type in the sheet: the next copy replaces it.

## If the app goes down
1. **SampCup > The app is down: switch to manual.** Copying stops; the sheet is the record.
2. Run the courts from the **Courts** tab. When a game starts, set its **Status** to
   `playing` in the Schedule tab. When it ends, type **Score A**, **Score B**, **How it ended**
   (pick from the list) and, when it reached 11, **Game time** (m:ss from the first serve to
   the 11th point; it counts for tiebreaks). Type the final score, after any sudden-death
   point. Judges can keep score on paper and hand the results to whoever types.
3. **SampCup > Recompute standings and bracket** after each batch of results. Standings,
   knockout teams, the Final, Courts and Bracket update. Read the **Check** column: it flags a
   result that can't happen (like 11-11), a missing game time, or a Final game 3 typed after
   a 2-0 (not counted).
4. Running late? Change the **Time** (or **Court**) of games not yet played.

Every row you change is marked **yes** under "Changed in sheet": that is what goes back to
the app.

## When the app is back
1. **SampCup > The app is back: send the sheet's changes to the app.** A small window asks
   for an admin username and password (the app's own login; not stored).
2. The app takes every changed row, in schedule order: results with their game times, new
   times and courts. Knockout teams fill in as each round lands, exactly as on a normal day.
3. If everything was taken, the sheet goes back to **AUTO** and copies the app again. If a
   game could not be taken (for example its teams differ from the app's), it stays marked,
   the **Check** column says why, and the sheet stays in MANUAL: fix it (or fix the game in
   the app) and send again.
4. Games already finished in the app before the outage are left alone; a changed result for
   one is applied as a correction (it shows in Admin > Audit as "From the backup sheet").

Nothing changed in the sheet? **Switch to automatic without sending** goes straight back.

## Good to know
- The sheet ranks exactly like the app, with one exception: where the app draws lots (all
  four numbers and head-to-head tied), the sheet keeps team-number order and says "random
  draw". Draw lots by hand if that ever matters.
- Mock runs are copied too (Info says "mock run in progress"). After a mock is undone the app
  has no schedule, so the sheet keeps the mock copy and says so: use **SampCup > Clear and
  copy again**.
- At night (9 PM to 7 AM) it copies once an hour. A free Google account allows 90 minutes of
  script time a day; this uses less than half.
