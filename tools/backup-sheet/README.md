# Backup sheet: run the day without the app

A Google Sheet that copies the tournament from https://sampcup.com every minute. If the app
goes down, the sheet already holds every team, game, score and standing, and it can carry
on by itself: organizers type results in, and it ranks the groups by the app's rules, fills
in the knockout games and settles the best-of-3 Final.

- **Pull, not push:** the sheet's own script reads the app's public pages (the same ones the
  website shows), so AWS holds no Google password and nothing extra runs on AWS. Free.
- **Keeps the last good copy:** a failed or empty answer from the app never replaces it.
- **Tested against the app:** `backend/tests/test_backup_sheet.py` checks the sheet's ranking
  against `ranking.py` on 3,000 groups, its manual mode against a whole simulated day, and
  its menus on a stand-in for Google Sheets.

## Set it up (once, about 5 minutes)
1. Create a blank Google Sheet with the Google account that should own it (go to
   `sheets.new`) and name it "SampCup 2026 backup".
2. In the sheet, choose **Extensions > Apps Script**. Delete the sample code in `Code.gs`,
   paste all of [`Code.gs`](Code.gs) (on GitHub, use the **Raw** button and copy everything),
   then click **Save**.
3. Choose `setup` in the function list at the top and click **Run**. Google asks for
   permission: **Review permissions**, pick the account, then on "Google hasn't verified this
   app" click **Advanced > Go to ... (unsafe)** and **Allow**. It is your own script; it asks
   to edit this one spreadsheet, to reach sampcup.com, and to run every minute.
4. Back in the sheet there are four tabs: **Info, Schedule, Standings, Teams**. Reload the
   page to see the **SampCup** menu. On the Info tab, "Last check" should end in "OK".
5. Share the sheet (as Editor) with the organizers who would run the day without the app.
   Keep it private: it lists players' names.

## On the day
- Glance at **Info > Last good copy**: it should be a minute or two old.
- After the draw, print the **Schedule** and **Teams** tabs (File > Print, fit to width). If
  the venue Wi-Fi fails, paper is the backup for the backup.
- Don't type in the Schedule, Standings or Teams tabs while the sheet is in AUTO mode: the
  next copy replaces them.

## If the app goes down
1. **SampCup > The app is down: switch to manual.** Copying stops; the sheet is the record.
2. Judges keep score on paper. For each finished game, type into the Schedule tab:
   **Score A, Score B, How it ended** (pick from the list) and, when it reached 11, **Game
   time** (m:ss from the first serve to the 11th point; it counts for tiebreaks). Type the
   final score, after any sudden-death point.
3. **SampCup > Recompute standings and bracket** after each batch of results. The Standings
   tab updates, knockout games get their teams once a group is complete or a game is won,
   and Final game 3 shows "not needed" after a 2-0. Read the **Check** column: it flags a
   result that can't happen (like 11-11) or a missing game time.
4. Running late? Edit the **Time** column, and call courts and teams from the Schedule tab.

## When the app is back
1. Rows changed in the sheet say **yes** under "Changed in sheet". Enter those results into
   the app, in time order: an admin opens the judge screen, picks the court and scores the
   game, then sets its real game time in **Admin > Results > Correct** (otherwise the app
   records the few seconds it took to type it, and game time is a tiebreak).
2. **SampCup > The app is back: switch to automatic.** It lists any changed games first, then
   copies the app again every minute.

## Good to know
- The sheet ranks exactly like the app, with one exception: where the app draws lots (all
  four numbers and head-to-head tied), the sheet keeps team-number order and says "random
  draw". Draw lots by hand if that ever matters.
- Mock runs are copied too (Info says "mock run in progress"). After the mock is undone, the
  app has no schedule, so the sheet keeps the mock copy and says so: use **SampCup > Clear and
  copy again**.
- At night (9 PM to 7 AM) it copies once an hour. A free Google account allows 90 minutes of
  script time a day; this uses about half of that at most.
- To change the script later: paste the new `Code.gs` over the old one and save. Run `setup`
  again only to reset the sheet (it starts a fresh copy in AUTO mode).
