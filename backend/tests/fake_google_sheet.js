// A small stand-in for the Google services tools/backup-sheet/Code.gs uses, enough to run
// its menus end to end in node (test_backup_sheet.py). Usage:
//   node fake_google_sheet.js Code.gs < {"pages": {overview, teams, schedule, standings}}
// Prints a JSON report of what each step left in the sheet.
const crypto = require('crypto')
const fs = require('fs')
const vm = require('vm')

const input = JSON.parse(fs.readFileSync(0, 'utf8'))
const state = { down: false, alerts: [], triggers: [], props: {} }

class Range {
  constructor(sheet, row, col, rows, cols) {
    if (row < 1 || col < 1 || row + rows - 1 > sheet.maxRows || col + cols - 1 > sheet.maxCols) {
      throw new Error('The coordinates of the range are outside the dimensions of the sheet.')
    }
    Object.assign(this, { sheet, row, col, rows, cols })
  }
  each(fn) {
    for (let r = 0; r < this.rows; r++) for (let c = 0; c < this.cols; c++) fn(this.row + r, this.col + c, r, c)
  }
  setValues(values) {
    if (values.length !== this.rows || values.some((v) => v.length !== this.cols)) throw new Error('size mismatch')
    this.each((r, c, i, j) => this.sheet.put(r, c, values[i][j]))
    return this
  }
  setValue(value) {
    this.each((r, c) => this.sheet.put(r, c, value))
    return this
  }
  getDisplayValue() { return this.sheet.get(this.row, this.col) }
  getDisplayValues() {
    return Array.from({ length: this.rows }, (_, i) =>
      Array.from({ length: this.cols }, (_, j) => this.sheet.get(this.row + i, this.col + j)))
  }
  getSheet() { return this.sheet }
  getRow() { return this.row }
  getLastRow() { return this.row + this.rows - 1 }
  setNumberFormat() { return this }
  setFontWeight() { return this }
  setFontSize() { return this }
  setDataValidation(rule) { this.sheet.validation = rule; return this }
  clearDataValidations() { this.sheet.validation = null; return this }
}

class Sheet {
  constructor(book, name) {
    Object.assign(this, { book, name, cells: {}, maxRows: 1000, maxCols: 26, validation: null })
  }
  put(r, c, v) { this.cells[r + ',' + c] = v === null || v === undefined ? '' : String(v) }
  get(r, c) { return this.cells[r + ',' + c] || '' }
  filled() { return Object.keys(this.cells).filter((k) => this.cells[k] !== '').map((k) => k.split(',').map(Number)) }
  getName() { return this.name }
  setName(name) { this.name = name }
  getParent() { return this.book }
  getRange(a, b, c, d) {
    if (typeof a === 'string') {
      const [from, to] = a.split(':').map((ref) => [Number(ref.slice(1)), ref.charCodeAt(0) - 64])
      const end = to || from
      return new Range(this, from[0], from[1], end[0] - from[0] + 1, end[1] - from[1] + 1)
    }
    return new Range(this, a, b, c || 1, d || 1)
  }
  clear() { this.cells = {} }
  clearContents() { this.cells = {} }
  getMaxRows() { return this.maxRows }
  getMaxColumns() { return this.maxCols }
  insertRowsAfter(_, n) { this.maxRows += n }
  insertColumnsAfter(_, n) { this.maxCols += n }
  getLastRow() { return Math.max(0, ...this.filled().map((p) => p[0])) }
  getLastColumn() { return Math.max(0, ...this.filled().map((p) => p[1])) }
  getDataRange() { return new Range(this, 1, 1, Math.max(1, this.getLastRow()), Math.max(1, this.getLastColumn())) }
  setFrozenRows() {}
  setColumnWidth() {}
}

const book = {
  sheets: [],
  getSheets() { return this.sheets },
  getSheetByName(name) { return this.sheets.find((s) => s.name === name) || null },
  insertSheet(name) { const s = new Sheet(this, name); this.sheets.push(s); return s },
  toast() {},
}
book.insertSheet('Sheet1')

const ui = {
  Button: { YES: 'YES', NO: 'NO' },
  ButtonSet: { YES_NO: 'YES_NO' },
  alert(...args) { state.alerts.push(args.filter((a) => typeof a === 'string').join(' | ')); return 'YES' },
  createMenu() { const menu = { addItem: () => menu, addSeparator: () => menu, addToUi: () => {} }; return menu },
}
const rule = { requireValueInList: () => rule, setAllowInvalid: () => rule, build: () => 'rule' }

const google = {
  SpreadsheetApp: { getActive: () => book, getUi: () => ui, newDataValidation: () => rule },
  Utilities: {
    DigestAlgorithm: { MD5: 'md5' },
    formatDate: (date, tz, format) => (format === 'H' ? '12' : date.toISOString()), // midday: no night pause
    computeDigest: (alg, text) => Array.from(crypto.createHash(alg).update(text).digest()),
    base64Encode: (bytes) => Buffer.from(bytes).toString('base64'),
  },
  PropertiesService: {
    getDocumentProperties: () => ({
      getProperty: (k) => (k in state.props ? state.props[k] : null),
      setProperty: (k, v) => { state.props[k] = String(v) },
      deleteProperty: (k) => { delete state.props[k] },
      deleteAllProperties: () => { state.props = {} },
    }),
  },
  LockService: { getDocumentLock: () => ({ tryLock: () => true, waitLock: () => {}, releaseLock: () => {} }) },
  ScriptApp: {
    getProjectTriggers: () => state.triggers.slice(),
    deleteTrigger: (t) => { state.triggers = state.triggers.filter((x) => x !== t) },
    newTrigger: (fn) => ({ timeBased: () => ({ everyMinutes: (n) => ({ create: () => state.triggers.push(fn + '/' + n) }) }) }),
  },
  UrlFetchApp: {
    fetchAll: (requests) => {
      if (state.down) throw new Error('Address unavailable: https://sampcup.com')
      return requests.map((r) => {
        const page = r.url.split('/').pop()
        return { getResponseCode: () => 200, getContentText: () => JSON.stringify(input.pages[page]) }
      })
    },
    // "send to the app": the login, then the import; state.reply decides the app's answers
    fetch: (url, options) => {
      if (state.down) throw new Error('Address unavailable: https://sampcup.com')
      const body = JSON.parse(options.payload)
      state.posts.push({ path: url.replace(/^.*\/api/, ''), body, auth: (options.headers || {}).Authorization })
      const [code, answer] = state.reply(url.replace(/^.*\/api/, ''), body)
      return { getResponseCode: () => code, getContentText: () => JSON.stringify(answer) }
    },
  },
  HtmlService: {
    createHtmlOutput: (html) => { state.dialog = html; const out = { setWidth: () => out, setHeight: () => out }; return out },
  },
}
state.posts = []
ui.showModalDialog = (html, title) => { state.dialogTitle = title }
const ctx = vm.createContext(google)
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx)
const run = (code) => vm.runInContext(code, ctx)
const tab = (name) => book.getSheetByName(name)
const table = (name) => run('readTable')(tab(name))
const info = (cell) => tab('Info').getRange(cell).getDisplayValue()
const report = {}

run('setup()')
run('onOpen()')
report.setup = {
  tabs: book.sheets.map((s) => s.name), triggers: state.triggers.slice(), mode: info('B2'),
  games: table('Schedule').length, teams: table('Teams').length, check: info('B4'),
  standings: tab('Standings').getDataRange().getDisplayValues().map((r) => r[0]),
}

state.down = true
run('copyFromApp()')
report.down = { games: table('Schedule').length, check: info('B4') }

run('switchToManual()')
const sheet = tab('Schedule')
const head = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getDisplayValues()[0]
const col = (h) => head.indexOf(h) + 1
const typed = []
table('Schedule').forEach((row, i) => {
  if (row.Group && row.Status !== 'done') { // the rest of group play, typed by the organizers
    const range = sheet.getRange(i + 2, col('Score A'), 1, 2).setValues([['11', '7']])
    run('onEdit')({ range })
    sheet.getRange(i + 2, col('How it ended')).setValue('reached 11')
    sheet.getRange(i + 2, col('Game time')).setValue('8:30')
    typed.push(row.Game)
  }
})
run('recompute()')
const after = table('Schedule')
report.manual = {
  mode: info('B2'), validation: sheet.validation, typed: typed.length,
  marked: after.filter((r) => r['Changed in sheet'] === 'yes').length,
  done: after.filter((r) => r.Group && r.Status === 'done').length,
  group_games: after.filter((r) => r.Group).length,
  r16: after.filter((r) => /^R16-/.test(r.Game)).map((r) => [r['Team A #'], r['Team B #']]),
  checks: after.filter((r) => r.Check).map((r) => r.Game + ': ' + r.Check),
  standings: tab('Standings').getDataRange().getDisplayValues().filter((r) => /^Group /.test(r[0])).map((r) => r[1]),
  check: info('B4'),
}

report.views = {
  courts: tab('Courts').getDataRange().getDisplayValues(),
  bracket: tab('Bracket').getDataRange().getDisplayValues().map((r) => r[0]),
}

// The app is back: send the sheet. A wrong password first, then the app takes all but one
// game, then (once that game is "fixed") the rest.
state.down = false
run('openSendDialog()')
const marked = () => table('Schedule').filter((r) => r['Changed in sheet'] === 'yes').map((r) => r.Game)
const login = (path, body) => (body.password === 'right'
  ? [200, { token: 'tok', user: { role: 'admin', must_change_password: false } }]
  : [401, { detail: 'Wrong username or password' }])
let refuse = null
state.reply = (path, body) => {
  if (path === '/auth/staff-login') return login(path, body)
  const codes = body.games.map((g) => g.code)
  const skipped = codes.filter((c) => c === refuse).map((c) => ({ code: c, applied: [], skipped: 'the sheet has other teams for this game than the app' }))
  return [200, { games: [], taken: codes.filter((c) => c !== refuse), skipped }]
}
report.wrong = run('sendToApp')('admin', 'wrong')
refuse = marked()[0]
report.partly = { message: run('sendToApp')('admin', 'right'), mode: info('B2'), marked: marked(), refused: refuse,
  check: table('Schedule').find((r) => r.Game === refuse).Check, sent: state.posts.at(-1).body.games.length,
  auth: state.posts.at(-1).auth, first: state.posts.at(-1).body.games[0] }
refuse = null
const message = run('sendToApp')('admin', 'right')
report.back = {
  message, mode: info('B2'), validation: sheet.validation, dialog: state.dialogTitle,
  done: table('Schedule').filter((r) => r.Status === 'done').length,
  marked: marked().length, check: info('B4'),
}
// nothing left to send: straight back to AUTO
run('switchToManual()')
report.nothing = { message: run('sendToApp')('admin', 'right'), mode: info('B2') }
process.stdout.write(JSON.stringify(report))
