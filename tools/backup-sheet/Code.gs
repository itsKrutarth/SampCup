/**
 * @OnlyCurrentDoc
 *
 * SampCup backup sheet (Google Apps Script, bound to one Google Sheet).
 *
 * While the app is up, the sheet copies the tournament from the app's public pages every
 * minute: teams with players and lunch, every game (time, court, teams, score, how it
 * ended, game time) and the group standings. A copy is only replaced by a good answer from
 * the app, so if the app goes down the sheet keeps the last state.
 *
 * If the app goes down: SampCup menu -> "The app is down: switch to manual". Organizers type
 * results into the Schedule tab, and "Recompute standings and bracket" ranks each group by
 * the app's rules (Tournament Resources/ranking.py) and fills in the knockout games.
 *
 * Setup and the procedure: tools/backup-sheet/README.md. The functions under "Pure logic"
 * are checked against the app itself in backend/tests/test_backup_sheet.py.
 */

const SITE = 'https://sampcup.com'
const TZ = 'America/New_York'
const TAB = { info: 'Info', schedule: 'Schedule', standings: 'Standings', teams: 'Teams' }
const SCHEDULE_HEAD = [
  'Time', 'Court', 'Game', 'Round', 'Team A', 'Score A', 'Score B', 'Team B', 'Status',
  'How it ended', 'Game time', 'Winner', 'Check', 'Team A #', 'Team B #', 'From A', 'From B',
  'Group', 'Changed in sheet',
]
// what "Recompute" writes back; everything else in the Schedule tab is the organizers' to type
const COMPUTED = ['Team A', 'Team B', 'Status', 'Winner', 'Check', 'Team A #', 'Team B #']
const TEAMS_HEAD = ['#', 'Team', 'Group', 'Center', 'Players', 'Lunch']
const STANDINGS_HEAD = [
  'Rank', '#', 'Team', 'Played', 'Won', 'Lost', 'Points for', 'Points against',
  'Avg game time', 'Placed by',
]
const STATUS = { scheduled: 'scheduled', in_progress: 'playing', completed: 'done', cancelled: 'not needed' }
const ENDINGS = {
  reached_11: 'reached 11', clock_lead: 'clock, leader won', sudden_death: 'sudden death',
  forfeit: 'forfeit',
}
const CLOCK_CAP = 12 * 60
const STEPS = ['wins', 'points scored', 'average game time', 'points allowed', 'head-to-head', 'random draw']
const INFO_ROWS = [
  ['SampCup 2026 backup', ''],
  ['Mode', 'AUTO'],
  ['Last good copy', ''],
  ['Last check', ''],
  ['Champion', ''],
  ['Tournament', ''],
  ['Contacts', ''],
  ['Site', SITE],
  ['', ''],
  ['AUTO: the sheet copies the app every minute. Don\'t edit the other tabs: the next copy replaces them.', ''],
  ['If the app goes down:', ''],
  ['1. SampCup menu > "The app is down: switch to manual". Copying stops; this sheet is now the record.', ''],
  ['2. For each finished game, type in the Schedule tab: Score A, Score B, How it ended, and Game time (m:ss from the first serve to the 11th point) when it reached 11. Type the final score, after any sudden-death point.', ''],
  ['3. SampCup menu > "Recompute standings and bracket" after each batch of results. Standings, knockout teams and the Final update. Read the Check column.', ''],
  ['4. Running late? Change the Time column. Tell courts and teams from the Schedule tab (print it if the Wi-Fi is poor).', ''],
  ['5. When the app is back: enter the games marked "yes" under "Changed in sheet" into the app in time order (judge screen as admin, then Admin > Results > Correct to set the game time), then SampCup menu > "The app is back: switch to automatic".', ''],
  ['', ''],
  ['Group ranking: 1) wins 2) points scored 3) lowest average game time (a game ended by the clock, or a forfeit, counts 12:00) 4) fewest points allowed 5) head-to-head, when exactly two teams are still tied 6) draw lots.', ''],
  ['Knockout: the top 4 of each group go to the Round of 16 (see From A and From B). The Final is best of 3; game 3 only if it is 1-1.', ''],
]

// ------------------------------------------------------------------ menu and setup

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('SampCup')
    .addItem('Copy from the app now', 'copyNow')
    .addSeparator()
    .addItem('The app is down: switch to manual', 'switchToManual')
    .addItem('Recompute standings and bracket', 'recompute')
    .addItem('The app is back: switch to automatic', 'switchToAutomatic')
    .addSeparator()
    .addItem('Clear and copy again', 'clearAndCopy')
    .addToUi()
}

/** Run once from the script editor: makes the tabs, copies the app now and every minute. */
function setup() {
  const book = SpreadsheetApp.getActive()
  const first = book.getSheets()[0]
  if (!book.getSheetByName(TAB.info)) first.setName(TAB.info)
  ;[TAB.schedule, TAB.standings, TAB.teams].forEach(function (name) {
    if (!book.getSheetByName(name)) book.insertSheet(name)
  })
  const info = book.getSheetByName(TAB.info)
  info.clear()
  info.getRange(1, 1, INFO_ROWS.length, 2).setNumberFormat('@').setValues(INFO_ROWS)
  info.getRange('A1').setFontWeight('bold').setFontSize(14)
  info.getRange('A2:A8').setFontWeight('bold')
  info.setColumnWidth(1, 190)
  info.setColumnWidth(2, 520)
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t) })
  ScriptApp.newTrigger('copyFromApp').timeBased().everyMinutes(1).create()
  PropertiesService.getDocumentProperties().deleteAllProperties()
  copyFromApp()
}

// ------------------------------------------------------------------ copying the app

/** Every minute (trigger): replace the copy with the app's data when the app answers. */
function copyFromApp() {
  const lock = LockService.getDocumentLock()
  if (!lock.tryLock(10000)) return
  try {
    const book = SpreadsheetApp.getActive()
    const info = book.getSheetByName(TAB.info)
    if (mode(book) !== 'AUTO') return
    const props = PropertiesService.getDocumentProperties()
    const hour = Number(Utilities.formatDate(new Date(), TZ, 'H'))
    const last = Number(props.getProperty('checked') || 0)
    if ((hour < 7 || hour >= 21) && Date.now() - last < 55 * 60 * 1000) return // nights: hourly
    props.setProperty('checked', String(Date.now()))
    let data
    try {
      data = fetchApp()
    } catch (e) {
      info.getRange('B4').setValue(stamp() + ': the app did not answer (' + e.message + '). The sheet keeps the last copy.')
      return
    }
    const games = book.getSheetByName(TAB.schedule).getLastRow() - 1
    if (data.schedule.length === 0 && games > 0) {
      info.getRange('B4').setValue(stamp() + ': the app has no schedule, so the copy was kept. If that is expected (after a mock run), use "Clear and copy again".')
      return
    }
    const digest = Utilities.base64Encode(
      Utilities.computeDigest(Utilities.DigestAlgorithm.MD5, JSON.stringify(data)))
    if (props.getProperty('digest') !== digest) {
      writeCopy(book, data)
      props.setProperty('digest', digest)
    }
    const mock = data.overview.tournament.mock_clock ? ' (mock run in progress)' : ''
    info.getRange('B3').setValue(stamp() + mock)
    info.getRange('B4').setValue(stamp() + ': OK')
  } finally {
    lock.releaseLock()
  }
}

function fetchApp() {
  const pages = ['overview', 'teams', 'schedule', 'standings']
  const answers = UrlFetchApp.fetchAll(pages.map(function (page) {
    return { url: SITE + '/api/public/' + page, muteHttpExceptions: true }
  }))
  const data = {}
  answers.forEach(function (answer, i) {
    if (answer.getResponseCode() !== 200) throw new Error(pages[i] + ' answered ' + answer.getResponseCode())
    data[pages[i]] = JSON.parse(answer.getContentText())
  })
  return data
}

function writeCopy(book, data) {
  const t = data.overview.tournament
  writeTable(book.getSheetByName(TAB.teams), [TEAMS_HEAD].concat(teamRows(data.teams, venueTime)), [1])
  const rows = scheduleRows(data.schedule, venueTime)
  writeTable(book.getSheetByName(TAB.schedule), [SCHEDULE_HEAD].concat(rows.map(function (r) {
    return SCHEDULE_HEAD.map(function (h) { return text(r[h]) })
  })), [1])
  writeStandings(book, standingsFromApp(data.standings))
  const info = book.getSheetByName(TAB.info)
  info.getRange('B5').setValue(data.overview.champion ? data.overview.champion.name : '')
  info.getRange('B6').setValue([t.name, t.event_date, t.venue_name, t.venue_address].filter(String).join(' · '))
  info.getRange('B7').setValue(t.contacts || '')
}

function copyNow() {
  if (mode(SpreadsheetApp.getActive()) !== 'AUTO') {
    SpreadsheetApp.getUi().alert('The sheet is in MANUAL mode. Switch back to automatic first.')
    return
  }
  PropertiesService.getDocumentProperties().deleteProperty('checked')
  copyFromApp()
  SpreadsheetApp.getActive().toast('Copied from the app (see Info for the result).')
}

function clearAndCopy() {
  const ui = SpreadsheetApp.getUi()
  if (ui.alert('Clear the copy and copy the app again?', ui.ButtonSet.YES_NO) !== ui.Button.YES) return
  const book = SpreadsheetApp.getActive()
  ;[TAB.schedule, TAB.standings, TAB.teams].forEach(function (n) { book.getSheetByName(n).clearContents() })
  PropertiesService.getDocumentProperties().deleteAllProperties()
  copyFromApp()
}

// ------------------------------------------------------------------ manual mode

function switchToManual() {
  const ui = SpreadsheetApp.getUi()
  const answer = ui.alert('Switch to manual?',
    'Copying from the app stops and this sheet becomes the record. Type results in the Schedule tab, then use "Recompute standings and bracket".',
    ui.ButtonSet.YES_NO)
  if (answer !== ui.Button.YES) return
  const book = SpreadsheetApp.getActive()
  setMode(book, 'MANUAL')
  const sheet = book.getSheetByName(TAB.schedule)
  const col = SCHEDULE_HEAD.indexOf('How it ended') + 1
  const rows = Math.max(1, sheet.getLastRow() - 1)
  sheet.getRange(2, col, rows, 1).setDataValidation(SpreadsheetApp.newDataValidation()
    .requireValueInList(Object.keys(ENDINGS).map(function (k) { return ENDINGS[k] }), true)
    .setAllowInvalid(false).build())
  book.getSheetByName(TAB.info).getRange('B4').setValue(stamp() + ': MANUAL. The sheet is the record.')
}

/** Simple trigger: in manual mode, mark each Schedule row someone changes. */
function onEdit(e) {
  const sheet = e.range.getSheet()
  if (sheet.getName() !== TAB.schedule || mode(sheet.getParent()) !== 'MANUAL') return
  const first = Math.max(2, e.range.getRow())
  const last = e.range.getLastRow()
  if (last < first) return
  const col = SCHEDULE_HEAD.indexOf('Changed in sheet') + 1
  sheet.getRange(first, col, last - first + 1, 1).setValue('yes')
}

function recompute() {
  const lock = LockService.getDocumentLock()
  lock.waitLock(20000)
  try {
    const book = SpreadsheetApp.getActive()
    const teams = readTable(book.getSheetByName(TAB.teams)).map(function (r) {
      return { number: num(r['#']), name: r['Team'], group: r['Group'] }
    }).filter(function (t) { return t.number !== null && t.group })
    const sheet = book.getSheetByName(TAB.schedule)
    const result = recomputeAll(teams, readTable(sheet))
    if (result.rows.length) {
      COMPUTED.forEach(function (h) {
        const col = SCHEDULE_HEAD.indexOf(h) + 1
        sheet.getRange(2, col, result.rows.length, 1).setNumberFormat('@')
          .setValues(result.rows.map(function (r) { return [text(r[h])] }))
      })
    }
    writeStandings(book, result.standings)
    const info = book.getSheetByName(TAB.info)
    info.getRange('B5').setValue(result.champion ? label(result.champion, teamName(teams, result.champion)) : '')
    info.getRange('B4').setValue(stamp() + ': MANUAL. Recomputed; ' + result.problems + ' game(s) to check (Check column).')
  } finally {
    lock.releaseLock()
  }
}

function switchToAutomatic() {
  const ui = SpreadsheetApp.getUi()
  const book = SpreadsheetApp.getActive()
  const changed = readTable(book.getSheetByName(TAB.schedule))
    .filter(function (r) { return r['Changed in sheet'] === 'yes' })
    .map(function (r) { return r['Game'] })
  const note = changed.length
    ? 'These games were changed in the sheet: ' + changed.join(', ') + '. Enter them into the app first, or the next copy replaces them.\n\n'
    : ''
  if (ui.alert('Switch back to automatic?', note + 'The sheet will copy the app again every minute.', ui.ButtonSet.YES_NO) !== ui.Button.YES) return
  const sheet = book.getSheetByName(TAB.schedule)
  sheet.getRange(2, 1, Math.max(1, sheet.getMaxRows() - 1), SCHEDULE_HEAD.length).clearDataValidations()
  setMode(book, 'AUTO')
  PropertiesService.getDocumentProperties().deleteAllProperties()
  copyFromApp()
}

// ------------------------------------------------------------------ sheet helpers

function mode(book) {
  return String(book.getSheetByName(TAB.info).getRange('B2').getDisplayValue()).trim().toUpperCase()
}

function setMode(book, value) {
  book.getSheetByName(TAB.info).getRange('B2').setValue(value)
}

function stamp() {
  return Utilities.formatDate(new Date(), TZ, 'MMM d, h:mm:ss a')
}

function venueTime(iso) {
  return Utilities.formatDate(new Date(iso), TZ, 'h:mm a')
}

/** Write rows (plain text, so "8:30" stays a game time), bolding the given row numbers. */
function writeTable(sheet, rows, bold) {
  sheet.clearContents()
  sheet.getRange(1, 1, sheet.getMaxRows(), sheet.getMaxColumns()).setFontWeight('normal')
  if (!rows.length) return
  const width = Math.max.apply(null, rows.map(function (r) { return r.length }))
  const grid = rows.map(function (r) {
    return r.map(text).concat(new Array(width - r.length).fill(''))
  })
  if (sheet.getMaxRows() < grid.length) sheet.insertRowsAfter(sheet.getMaxRows(), grid.length - sheet.getMaxRows())
  if (sheet.getMaxColumns() < width) sheet.insertColumnsAfter(sheet.getMaxColumns(), width - sheet.getMaxColumns())
  sheet.getRange(1, 1, grid.length, width).setNumberFormat('@').setValues(grid)
  ;(bold || []).forEach(function (row) { sheet.getRange(row, 1, 1, width).setFontWeight('bold') })
  sheet.setFrozenRows(1)
}

function writeStandings(book, standings) {
  const grid = standingsGrid(standings)
  const bold = []
  grid.forEach(function (r, i) { if (r[0] === 'Rank' || /^Group /.test(r[0])) bold.push(i + 1) })
  writeTable(book.getSheetByName(TAB.standings), grid, bold)
  book.getSheetByName(TAB.standings).setFrozenRows(0)
}

/**
 * The table under the header row, as objects keyed by header, every value as shown.
 * Blank rows stay in, so row i is always sheet row i + 2 (recompute writes back by position).
 */
function readTable(sheet) {
  const values = sheet.getDataRange().getDisplayValues()
  const head = values[0] || []
  return values.slice(1).map(function (r) {
    const row = {}
    head.forEach(function (h, i) { row[h] = r[i] })
    return row
  })
}

// ------------------------------------------------------------------ pure logic
// No Google services below this line: backend/tests/test_backup_sheet.py runs it in node.

function text(value) {
  return value === null || value === undefined ? '' : String(value)
}

function num(value) {
  const s = text(value).trim()
  return s === '' ? null : Number(s)
}

function label(number, name) {
  return '#' + number + ' ' + name
}

function teamName(teams, number) {
  const team = teams.filter(function (t) { return t.number === number })[0]
  return team ? team.name : ''
}

function clock(seconds) {
  const whole = Math.round(seconds)
  return Math.floor(whole / 60) + ':' + String(whole % 60).padStart(2, '0')
}

/** An average game time with its tenth of a second, which can decide a tie: "6:45.3". */
function clockTenths(seconds) {
  const rest = (seconds % 60).toFixed(1)
  return Math.floor(seconds / 60) + ':' + (Number(rest) < 10 ? '0' : '') + rest
}

/** "8:30" -> 510; "" -> null; anything else -> NaN. */
function parseClock(value) {
  const s = text(value).trim()
  if (s === '') return null
  const m = /^(\d{1,2}):([0-5]\d)$/.exec(s)
  return m ? Number(m[1]) * 60 + Number(m[2]) : NaN
}

/** Python's round(x, 1) (ranking.py): like toFixed(1), except an exact .x5 rounds to even. */
function pyRound1(x) {
  if (Number.isInteger(x * 4) && !Number.isInteger(x * 2)) { // exactly m.25 or m.75
    const whole = Math.floor(x)
    return Number((whole + (x - whole === 0.25 ? 0.2 : 0.8)).toFixed(1))
  }
  return Number(x.toFixed(1))
}

function rankingSeconds(endReason, seconds) {
  return endReason === 'reached_11' ? Math.min(seconds, CLOCK_CAP) : CLOCK_CAP
}

/** The game rules (ranking.py check_game): '' when the result can happen, else why not. */
function checkGame(a, b, reason) {
  if (a === b) return 'a game always has a winner (' + a + '-' + b + ')'
  if (reason === 'reached_11' && Math.max(a, b) !== 11) return '"reached 11" needs a score of 11'
  if ((reason === 'clock_lead' || reason === 'sudden_death') && Math.max(a, b) > 11) return 'a game ended by the clock cannot pass 11'
  if (reason === 'sudden_death' && Math.abs(a - b) !== 1) return 'sudden death ends one point apart'
  if (reason === 'forfeit' && !((a === 11 && b === 0) || (a === 0 && b === 11))) return 'a forfeit is recorded 11-0'
  if (Math.min(a, b) < 0) return 'scores cannot be negative'
  return ''
}

/**
 * Rank one group exactly as ranking.py rank_teams does. The one difference: where the app
 * draws lots (step 6) the sheet keeps team-number order and says "random draw".
 */
function rankGroup(teams, games) {
  const s = {}
  teams.forEach(function (t) { s[t] = { w: 0, pf: 0, pa: 0, t: 0, g: 0 } })
  const h2h = {}
  const pair = function (a, b) { return a + ':' + b }
  games.forEach(function (g) {
    const sec = rankingSeconds(g.end_reason, g.seconds)
    ;[[g.team_a, g.score_a, g.score_b], [g.team_b, g.score_b, g.score_a]].forEach(function (x) {
      s[x[0]].pf += x[1]
      s[x[0]].pa += x[2]
      s[x[0]].t += sec
      s[x[0]].g += 1
    })
    const win = g.score_a > g.score_b ? g.team_a : g.team_b
    s[win].w += 1
    h2h[pair(g.team_a, g.team_b)] = (h2h[pair(g.team_a, g.team_b)] || 0) + (win === g.team_a ? 1 : 0)
    h2h[pair(g.team_b, g.team_a)] = (h2h[pair(g.team_b, g.team_a)] || 0) + (win === g.team_b ? 1 : 0)
  })
  const avg = function (t) { return s[t].g ? pyRound1(s[t].t / s[t].g) : CLOCK_CAP }
  const keys = [
    function (t) { return -s[t].w },
    function (t) { return -s[t].pf },
    avg,
    function (t) { return s[t].pa },
  ]
  const order = []
  const reason = {}
  const byNumber = function (x, y) { return x - y }
  function place(group, step) {
    if (group.length === 1) {
      order.push(group[0])
      return
    }
    if (step < keys.length) {
      const sorted = group.slice().sort(function (x, y) { return keys[step](x) - keys[step](y) })
      let i = 0
      while (i < sorted.length) {
        let j = i
        while (j < sorted.length && keys[step](sorted[j]) === keys[step](sorted[i])) j++
        const start = order.length
        place(sorted.slice(i, j), step + 1)
        if (i) reason[order[start]] = STEPS[step]
        i = j
      }
      return
    }
    const a = group[0]
    const b = group[1]
    if (group.length === 2 && pair(a, b) in h2h && h2h[pair(a, b)] !== h2h[pair(b, a)]) {
      const won = h2h[pair(a, b)] > h2h[pair(b, a)] ? [a, b] : [b, a]
      reason[won[1]] = STEPS[4]
      order.push(won[0], won[1])
    } else {
      const lots = group.slice().sort(byNumber)
      lots.slice(1).forEach(function (t) { reason[t] = STEPS[5] })
      order.push.apply(order, lots)
    }
  }
  place(teams.slice().sort(byNumber), 0)
  return order.map(function (t, i) {
    return {
      rank: i + 1, team: t, wins: s[t].w, points_for: s[t].pf, avg_seconds: avg(t),
      points_against: s[t].pa, decided_by: i ? (reason[t] || '') : '',
    }
  })
}

/** Schedule rows from the app's /public/schedule, keyed by SCHEDULE_HEAD. */
function scheduleRows(games, formatTime) {
  const named = function (team, source) { return team ? label(team.number, team.name) : (source || '') }
  return games.map(function (g) {
    const winner = [g.team_a, g.team_b].filter(function (t) { return t && t.id === g.winner_id })[0]
    return {
      'Time': formatTime(g.scheduled_at),
      'Court': g.court,
      'Game': g.code,
      'Round': g.round,
      'Team A': named(g.team_a, g.source_a),
      'Score A': g.score_a,
      'Score B': g.score_b,
      'Team B': named(g.team_b, g.source_b),
      'Status': STATUS[g.status] || g.status,
      'How it ended': g.end_reason ? ENDINGS[g.end_reason] : '',
      'Game time': g.status === 'completed' && g.seconds !== null ? clock(g.seconds) : '',
      'Winner': winner ? named(winner) : '',
      'Check': '',
      'Team A #': g.team_a ? g.team_a.number : '',
      'Team B #': g.team_b ? g.team_b.number : '',
      'From A': g.source_a || '',
      'From B': g.source_b || '',
      'Group': g.group || '',
      'Changed in sheet': '',
    }
  })
}

/** Teams tab rows from the app's /public/teams. */
function teamRows(teams, formatTime) {
  return teams.map(function (t) {
    return [
      t.number === null ? '' : t.number, t.name, t.group || '', t.center || '',
      (t.players || []).map(function (p) { return p.name }).join(', '),
      t.lunch_start ? formatTime(t.lunch_start) : '',
    ]
  })
}

/** The app's /public/standings in the shape recomputeAll returns. */
function standingsFromApp(answer) {
  const out = {}
  Object.keys(answer.groups || {}).forEach(function (g) {
    const table = answer.groups[g]
    out[g] = {
      complete: table.complete, played: table.played, total: table.total,
      rows: table.rows.map(function (r) {
        return {
          rank: r.rank, team_number: r.team_number, team_name: r.team_name, played: r.played,
          wins: r.wins, losses: r.losses, points_for: r.points_for,
          points_against: r.points_against, avg_seconds: r.avg_seconds, decided_by: r.decided_by,
        }
      }),
    }
  })
  return out
}

function standingsGrid(standings) {
  const grid = []
  Object.keys(standings).sort().forEach(function (g) {
    const table = standings[g]
    grid.push(['Group ' + g, table.complete ? 'complete' : table.played + ' of ' + table.total + ' games played'])
    grid.push(STANDINGS_HEAD)
    table.rows.forEach(function (r) {
      grid.push([r.rank, r.team_number, r.team_name, r.played, r.wins, r.losses, r.points_for,
        r.points_against, clockTenths(r.avg_seconds), r.decided_by])
    })
    grid.push([''])
  })
  return grid
}

/** A typed result, checked by the game rules: { result } or { problem } (or neither). */
function readResult(row) {
  const a = num(row['Score A'])
  const b = num(row['Score B'])
  const how = text(row['How it ended']).trim().toLowerCase()
  if (a === null || b === null || how === '') return {}
  const reason = Object.keys(ENDINGS).filter(function (k) { return k === how || ENDINGS[k] === how })[0]
  if (!reason) return { problem: 'How it ended: use one of ' + Object.keys(ENDINGS).map(function (k) { return ENDINGS[k] }).join(', ') }
  if (!Number.isInteger(a) || !Number.isInteger(b)) return { problem: 'scores are whole numbers' }
  const rule = checkGame(a, b, reason)
  if (rule) return { problem: rule }
  let seconds = CLOCK_CAP
  let note = ''
  if (reason === 'reached_11') {
    const t = parseClock(row['Game time'])
    if (t !== null && isNaN(t)) return { problem: 'Game time looks like 8:30' }
    if (t === null) note = 'no game time: counted as 12:00'
    else seconds = t
  }
  return { result: { score_a: a, score_b: b, end_reason: reason, seconds: seconds }, problem: note }
}

/**
 * Manual mode: from the Teams tab and the Schedule rows (as typed), work out each game's
 * status and winner, the group standings, the knockout teams, Final game 3 and the
 * champion, like the app does. Rows come back with the COMPUTED columns filled in.
 */
function recomputeAll(teams, rows) {
  const names = {}
  const members = {}
  teams.forEach(function (t) {
    names[t.number] = t.name
    ;(members[t.group] = members[t.group] || []).push(t.number)
  })
  const out = rows.map(function (r) { return Object.assign({}, r, { 'Check': '' }) })
  const byCode = {}
  out.forEach(function (r) { byCode[r['Game']] = r })
  const read = out.map(readResult)
  const knockout = function (r) { return r['From A'] !== '' || r['From B'] !== '' }

  // group games first: their results make the standings the knockout games come from
  const standings = {}
  Object.keys(members).sort().forEach(function (g) {
    const games = out.filter(function (r) { return r['Group'] === g && !knockout(r) })
    const results = []
    const played = {}
    games.forEach(function (r) {
      const i = out.indexOf(r)
      const a = num(r['Team A #'])
      const b = num(r['Team B #'])
      if (!read[i].result) return
      if (members[g].indexOf(a) < 0 || members[g].indexOf(b) < 0) {
        read[i] = { problem: 'Team A # and Team B # must be teams of group ' + g }
        return
      }
      results.push(Object.assign({ team_a: a, team_b: b }, read[i].result))
      played[a] = (played[a] || 0) + 1
      played[b] = (played[b] || 0) + 1
    })
    standings[g] = {
      complete: games.length > 0 && results.length === games.length,
      played: results.length,
      total: games.length,
      rows: rankGroup(members[g], results).map(function (r) {
        return {
          rank: r.rank, team_number: r.team, team_name: names[r.team], played: played[r.team] || 0,
          wins: r.wins, losses: (played[r.team] || 0) - r.wins, points_for: r.points_for,
          points_against: r.points_against, avg_seconds: r.avg_seconds, decided_by: r.decided_by,
        }
      }),
    }
  })

  const winnerOf = function (r) {
    const i = out.indexOf(r)
    const a = num(r['Team A #'])
    const b = num(r['Team B #'])
    if (!read[i].result || a === null || b === null) return null
    return read[i].result.score_a > read[i].result.score_b ? a : b
  }
  const resolve = function (source) {
    let m = /^Group ([A-Z]) (\d)(?:st|nd|rd|th)$/.exec(source)
    if (m) {
      const table = standings[m[1]]
      const row = table && table.complete ? table.rows[Number(m[2]) - 1] : null
      return row ? row.team_number : null
    }
    m = /^Winner of (.+)$/.exec(source)
    const before = m ? byCode[m[1]] : null
    return before ? winnerOf(before) : null
  }
  // knockout teams, repeated so a winner found in one pass fills the next round
  for (let pass = 0; pass < 6; pass++) {
    out.filter(knockout).forEach(function (r) {
      const i = out.indexOf(r)
      const locked = Boolean(read[i].result) || r['Status'] === 'playing'
      ;[['Team A', 'From A'], ['Team B', 'From B']].forEach(function (side) {
        const want = resolve(r[side[1]])
        const have = num(r[side[0] + ' #'])
        if (locked && have !== null) {
          if (want !== null && want !== have) read[i].problem = side[1] + ' now gives #' + want + ': check this game'
          return
        }
        r[side[0] + ' #'] = want === null ? '' : want
        r[side[0]] = want === null ? r[side[1]] : label(want, names[want])
      })
    })
  }

  out.forEach(function (r, i) {
    const won = winnerOf(r)
    if (read[i].result && won === null) read[i].problem = 'Team A # and Team B # are needed for a result'
    r['Winner'] = won === null ? '' : label(won, names[won])
    if (read[i].result && won !== null) r['Status'] = 'done'
    else if (r['Status'] === 'done') r['Status'] = 'scheduled' // its result was cleared
    r['Check'] = read[i].problem || ''
  })

  // best of 3: game 3 only when the first two are split
  const f1 = byCode['F-1']
  const f2 = byCode['F-2']
  const f3 = byCode['F-3']
  let champion = null
  if (f1 && f2 && f3) {
    const w1 = winnerOf(f1)
    const decided = w1 !== null && w1 === winnerOf(f2)
    if (decided && !read[out.indexOf(f3)].result) f3['Status'] = 'not needed'
    else if (!decided && f3['Status'] === 'not needed') f3['Status'] = 'scheduled'
    const wins = {}
    ;[f1, f2, f3].forEach(function (r) {
      const w = winnerOf(r)
      if (w !== null) wins[w] = (wins[w] || 0) + 1
    })
    Object.keys(wins).forEach(function (t) { if (wins[t] >= 2) champion = Number(t) })
  }
  const problems = out.filter(function (r) { return r['Check'] !== '' }).length
  return { rows: out, standings: standings, champion: champion, problems: problems }
}
