import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { match } from '../../test/data'
import { ADMIN, fail, JUDGE, mockApi, renderAt } from '../../test/utils'

const summary = (t = {}) => ({
  tournament: { name: 'SAMP Cup 2026', subtitle: 'Yuvak Mandal Pickleball Tournament', venue_name: 'Rt. 12 Pickle', venue_address: '184 W. Boylston St', age_group: '22-35', contacts: '', event_date: '2026-12-12', registration_open: true, team_cap: 42, draw_seed: null, schedule_locked: false, schedule_exists: false, ...t },
  players: 80, players_on_teams: 70, teams: { active: 35, waitlist: 1, withdrawn: 0 }, checked_in: 30, pending_requests: 2,
  tshirts: { Large: 40, Medium: 40 },
})
const player = (id: number, first: string, team: { id: number; name: string } | null = null, active = true, username: string | null = null) => ({
  id, mis_id: String(1000 + id), first_name: first, last_name: 'Tester', center: 'North', zone: 'Z', tshirt_size: 'L', active, team,
  username, must_change_password: false,
})
const teamRow = { id: 7, name: 'Net Ninjas', number: null, group: null, center: 'North', status: 'active', lunch_start: null, checked_in: false, players: [{ id: 1, name: 'Aarav Tester' }] }

describe('admin access', () => {
  it('sends visitors to staff login and judges to their court', async () => {
    mockApi({ 'GET /judge/matches?court=1': { court: 1, current: null, matches: [] } })
    renderAt('/admin')
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
    renderAt('/admin', JUDGE)
    expect(await screen.findByRole('heading', { name: 'Court 1' })).toBeInTheDocument()
  })
})

describe('overview tab', () => {
  it('shows counts, saves settings and downloads results', async () => {
    const { sent } = mockApi({
      'GET /admin/summary': summary({ draw_seed: 77, schedule_exists: true, schedule_locked: true }),
      'PATCH /admin/tournament': summary(),
      'GET /admin/export/results.csv': fail(500, 'export failed'),
    })
    const user = userEvent.setup()
    renderAt('/admin', ADMIN)
    expect(await screen.findByText(/active teams, 1 waitlist/)).toBeInTheDocument()
    expect(screen.getByText(/Schedule: locked · Draw seed: 77/)).toBeInTheDocument()
    expect(screen.getByText('Large: 40 · Medium: 40')).toBeInTheDocument()
    await user.clear(screen.getByLabelText('Event date'))
    await user.type(screen.getByLabelText('Event date'), '2026-12-13')
    await user.type(screen.getByLabelText('Contacts on the home page'), 'Organizer (555) 010-0100')
    await user.click(screen.getByLabelText('Players can form teams'))
    expect(within(screen.getByRole('region', { name: 'Backup sheet' })).getByText(/Not linked yet/)).toBeInTheDocument()
    const sheet = 'https://docs.google.com/spreadsheets/d/abc/edit'
    await user.type(screen.getByLabelText('Backup sheet address (Google Sheets)'), sheet)
    await user.click(screen.getByRole('button', { name: 'Save settings' }))
    expect(await screen.findByText('Settings saved')).toBeInTheDocument()
    expect(sent('PATCH', '/admin/tournament')[0].body).toEqual({
      name: 'SAMP Cup 2026',
      subtitle: 'Yuvak Mandal Pickleball Tournament',
      venue_name: 'Rt. 12 Pickle',
      venue_address: '184 W. Boylston St',
      age_group: '22-35',
      contacts: 'Organizer (555) 010-0100',
      registration_open: false,
      team_cap: 42,
      backup_sheet_url: sheet,
      event_date: '2026-12-13',
    })
    await user.click(screen.getByRole('button', { name: 'Download results (CSV)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('export failed')
  })

  it('shows a schedule that is not generated or not locked', async () => {
    mockApi({ 'GET /admin/summary': summary({ schedule_exists: true }) })
    renderAt('/admin', ADMIN)
    expect(await screen.findByText(/Schedule: generated, not locked/)).toBeInTheDocument()
  })

  it('links the backup sheet once its address is saved', async () => {
    const sheet = 'https://docs.google.com/spreadsheets/d/abc/edit'
    mockApi({ 'GET /admin/summary': summary({ backup_sheet_url: sheet }) })
    renderAt('/admin', ADMIN)
    const link = await screen.findByRole('link', { name: 'Open the backup sheet' })
    expect(link).toHaveAttribute('href', sheet)
    expect(link).toHaveAttribute('target', '_blank')
  })
})

describe('players tab', () => {
  it('checks the export first, then imports what the check showed, and searches players', async () => {
    const report = {
      added: 3, updated: 1, unchanged: 0, deactivated: 1,
      added_names: ['Om Tester (North)', 'Kush Patel (No center provided)', 'Ved Shah (Hartford)'], updated_names: ['Aarav Tester'],
      center_changes: ['Aarav Tester: South -> North'], deactivated_names: ['Dev Tester (North)'], no_center: ['Kush Patel'],
      possible_duplicates: ['Aarav Tester (North)'], skipped: [{ row: 4, reason: 'same person as row 2' }], teams_with_removed_players: ['Net Ninjas'],
    }
    const { sent } = mockApi({
      'GET /admin/players': [player(1, 'Aarav', { id: 7, name: 'Net Ninjas' }), player(2, 'Dev', null, false)],
      'POST /admin/players/import?preview=true': { ...report, preview: true },
      'POST /admin/players/import': { ...report, preview: false },
    })
    const user = userEvent.setup()
    renderAt('/admin/players', ADMIN)
    expect(await screen.findByText('Dev Tester (removed)')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Search players'), 'aarav')
    expect(screen.queryByText('Dev Tester (removed)')).not.toBeInTheDocument()
    await user.upload(screen.getByLabelText('Registration file'), new File(['x'], 'export.xlsx'))
    await user.click(screen.getByRole('button', { name: 'Check file' }))
    // the check changes nothing and shows what would change
    const check = await screen.findByRole('status', { name: 'Import preview' })
    expect(within(check).getByText(/This file would add 3, update 1, leave 0 unchanged and switch off 1/)).toBeInTheDocument()
    expect(within(check).getByText('Center changes (1)')).toBeInTheDocument()
    expect(within(check).getByText('Would be switched off (not in the file) (1)')).toBeInTheDocument()
    expect(within(check).getByText(/No center provided: Kush Patel/)).toBeInTheDocument()
    expect(within(check).getByText('Skipped rows: 4 (same person as row 2)')).toBeInTheDocument()
    expect(within(check).getByText(/Same name at one center/)).toBeInTheDocument()
    expect(within(check).getByText('Teams with removed players: Net Ninjas')).toBeInTheDocument()
    expect(sent('POST', '/admin/players/import')).toHaveLength(0)
    await user.click(within(check).getByRole('button', { name: 'Import these changes' }))
    const done = await screen.findByRole('status', { name: 'Import result' })
    expect(within(done).getByText(/Added 3, updated 1, leave 0 unchanged and switched off 1/)).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: 'Import preview' })).not.toBeInTheDocument()
    expect(sent('POST', '/admin/players/import')[0].body).toBeInstanceOf(FormData)
  })

  it('cancels a checked file and sets a center by hand', async () => {
    const kush = { ...player(3, 'Kush'), center: 'No center provided' }
    const { sent } = mockApi({
      'GET /admin/players': [kush],
      'POST /admin/players/import?preview=true': { added: 1, updated: 0, unchanged: 0, deactivated: 0, possible_duplicates: [], skipped: [], teams_with_removed_players: [], preview: true },
      'PATCH /admin/players/3': { ...kush, center: 'Boston' },
    })
    const user = userEvent.setup()
    renderAt('/admin/players', ADMIN)
    expect(await screen.findByText('No center provided')).toBeInTheDocument()
    await user.upload(screen.getByLabelText('Registration file'), new File(['x'], 'export.xlsx'))
    await user.click(screen.getByRole('button', { name: 'Check file' }))
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('status', { name: 'Import preview' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Edit center for Kush Tester' }))
    await user.click(within(screen.getByRole('form', { name: 'Center for Kush Tester' })).getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getByRole('button', { name: 'Edit center for Kush Tester' }))
    const form = screen.getByRole('form', { name: 'Center for Kush Tester' })
    await user.type(within(form).getByLabelText('Center'), 'Boston')
    await user.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Center saved')).toBeInTheDocument()
    expect(sent('PATCH', '/admin/players/3')[0].body).toEqual({ center: 'Boston' })
  })

  it('sets, resets and releases player logins', async () => {
    const { sent } = mockApi({
      'GET /admin/players': [player(1, 'Aarav', null, true, 'aarav_t'), player(2, 'Twin')],
      'PUT /admin/players/2/login': { ...player(2, 'Twin'), username: 'twin1', must_change_password: true },
      'PUT /admin/players/1/login': fail(409, 'That username is taken'),
      'DELETE /admin/players/1/login': player(1, 'Aarav'),
    })
    const user = userEvent.setup()
    renderAt('/admin/players', ADMIN)
    expect(await screen.findByText('aarav_t')).toBeInTheDocument()
    expect(screen.getByText('No account')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Set login' })[1])
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getAllByRole('button', { name: 'Set login' })[1])
    const form = screen.getByRole('form', { name: 'Login for Twin Tester' })
    await user.type(within(form).getByLabelText('Username'), 'twin1')
    await user.type(within(form).getByLabelText('Temporary password'), 'temp123')
    await user.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Login saved. The password is temporary.')).toBeInTheDocument()
    expect(sent('PUT', '/admin/players/2/login')[0].body).toEqual({ username: 'twin1', password: 'temp123' })
    await user.click(screen.getAllByRole('button', { name: 'Set login' })[0])
    await user.click(within(screen.getByRole('form', { name: 'Login for Aarav Tester' })).getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('taken')
    expect(sent('PUT', '/admin/players/1/login')[0].body).toEqual({ username: 'aarav_t', password: null })
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    await user.click(screen.getByRole('button', { name: 'Release' }))
    await user.click(screen.getByRole('button', { name: 'Release' }))
    expect(await screen.findByText('Account released')).toBeInTheDocument()
  })

  it('shows a refused file', async () => {
    mockApi({ 'GET /admin/players': [], 'POST /admin/players/import?preview=true': fail(400, 'Missing columns: first_name') })
    const user = userEvent.setup()
    renderAt('/admin/players', ADMIN)
    await user.click(await screen.findByRole('button', { name: 'Check file' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Choose the registration export first')
    await user.upload(await screen.findByLabelText('Registration file'), new File(['x'], 'bad.csv'))
    await user.click(screen.getByRole('button', { name: 'Check file' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Missing columns')
    expect(screen.queryByRole('button', { name: 'Import these changes' })).not.toBeInTheDocument()
  })
})

describe('teams tab', () => {
  it('checks in, changes status, deletes and creates teams', async () => {
    const { sent } = mockApi({
      'GET /admin/teams': [teamRow],
      'GET /admin/players': [player(3, 'Jay'), player(4, 'Om'), player(1, 'Aarav', { id: 7, name: 'Net Ninjas' })],
      'GET /admin/requests': [{ id: 5, team_name: 'Pending Pair', status: 'pending', from: player(3, 'Jay'), to: player(4, 'Om'), created_at: '' }],
      'PATCH /admin/teams/7': teamRow,
      'DELETE /admin/teams/7': null,
      'POST /admin/teams': teamRow,
      'POST /admin/requests/5/cancel': {},
    })
    const user = userEvent.setup()
    renderAt('/admin/teams', ADMIN)
    await user.click(await screen.findByLabelText('Net Ninjas checked in'))
    expect(await screen.findByText('Net Ninjas checked in')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Status of Net Ninjas'), 'withdrawn')
    expect(await screen.findByText('Net Ninjas is now withdrawn')).toBeInTheDocument()
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('Net Ninjas deleted')).toBeInTheDocument()
    expect(sent('PATCH', '/admin/teams/7').map((c) => c.body)).toEqual([{ checked_in: true }, { status: 'withdrawn' }])
    expect(screen.queryByRole('option', { name: /Aarav/ })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('Team name'), 'New Pair')
    await user.selectOptions(screen.getByLabelText('Player 1'), '3')
    await user.selectOptions(screen.getByLabelText('Player 2'), '4')
    await user.click(screen.getByRole('button', { name: 'Create team' }))
    expect(await screen.findByText('Team New Pair created')).toBeInTheDocument()
    expect(sent('POST', '/admin/teams')[0].body).toEqual({ name: 'New Pair', player_ids: [3, 4] })
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(await screen.findByText('Request cancelled')).toBeInTheDocument()
  })

  it('shows refused team changes', async () => {
    mockApi({ 'GET /admin/teams': [teamRow], 'GET /admin/players': [], 'GET /admin/requests': [], 'PATCH /admin/teams/7': fail(409, 'The tournament is full') })
    const user = userEvent.setup()
    renderAt('/admin/teams', ADMIN)
    await user.selectOptions(await screen.findByLabelText('Status of Net Ninjas'), 'waitlist')
    expect(await screen.findByRole('alert')).toHaveTextContent('full')
    expect(screen.getByText('None.')).toBeInTheDocument()
  })
})

describe('schedule tab', () => {
  it('draws, generates, locks, clears, shifts and moves courts', async () => {
    let state = summary()
    const { sent } = mockApi({
      'GET /admin/summary': () => state,
      'GET /public/schedule': [match(), match({ id: 2, code: 'G002', status: 'completed' })],
      'POST /admin/draw': () => [{}, {}],
      'POST /admin/schedule': () => {
        state = summary({ schedule_exists: true })
        return { matches: 177 }
      },
      'POST /admin/schedule/lock': () => {
        state = summary({ schedule_exists: true, schedule_locked: !state.tournament.schedule_locked })
        return { locked: true }
      },
      'DELETE /admin/schedule': () => {
        state = summary()
        return null
      },
      'POST /admin/delays': { moved: 12, warnings: ['G150 now overlaps Sabha'] },
      'PATCH /admin/matches/1': match({ court: 5 }),
    })
    const user = userEvent.setup()
    renderAt('/admin/schedule', ADMIN)
    await user.click(await screen.findByRole('button', { name: 'Draw team numbers' }))
    expect(await screen.findByText('Drew numbers for 2 teams')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Generate schedule' }))
    expect(await screen.findByText('Schedule ready: 177 games')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Lock schedule' }))
    expect(await screen.findByText('Schedule locked')).toBeInTheDocument()
    await user.click(await screen.findByRole('button', { name: 'Unlock schedule' }))
    expect(await screen.findByText('Schedule unlocked')).toBeInTheDocument()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await user.click(await screen.findByRole('button', { name: 'Clear schedule' }))
    expect(await screen.findByText('Schedule cleared')).toBeInTheDocument()
    state = summary({ schedule_exists: true })
    await user.click(screen.getByRole('button', { name: 'Draw team numbers' }))
    await screen.findByRole('button', { name: 'Shift games' })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Shift games' })).toBeEnabled())
    await user.type(screen.getByLabelText('From (venue time)'), '14:00')
    await user.type(screen.getByLabelText('Minutes (negative to pull earlier)'), '15')
    await user.click(screen.getByRole('button', { name: 'Shift games' }))
    expect(await screen.findByText('Moved 12 games. Check: G150 now overlaps Sabha')).toBeInTheDocument()
    expect(sent('POST', '/admin/delays')[0].body).toEqual({ minutes: 15, from_time: '2026-12-12T19:00:00.000Z' })
    expect(screen.getByLabelText('Court for G002')).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Court for G001'), '5')
    expect(await screen.findByText('G001 moved to court 5')).toBeInTheDocument()
  })

  it('shows a refused draw', async () => {
    mockApi({ 'GET /admin/summary': summary(), 'GET /public/schedule': [], 'POST /admin/draw': fail(400, '20 active teams are checked in') })
    const user = userEvent.setup()
    renderAt('/admin/schedule', ADMIN)
    await user.click(await screen.findByRole('button', { name: 'Draw team numbers' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('20 active teams')
  })
})

describe('results tab', () => {
  it('corrects and resets results', async () => {
    const done = match({ status: 'completed', score_a: 11, score_b: 4, end_reason: 'reached_11', winner_id: 1 })
    const { sent } = mockApi({
      'GET /public/schedule': [done, match({ id: 2, code: 'G002', status: 'in_progress', score_a: 3, score_b: 2 }), match({ id: 3 })],
      'POST /admin/matches/1/correct': { ...done, warnings: ['R16-1 is completed with other teams; check it'] },
      'POST /admin/matches/2/reset': match({ id: 2 }),
    })
    const user = userEvent.setup()
    renderAt('/admin/results', ADMIN)
    expect(await screen.findByText('live')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Correct' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getByRole('button', { name: 'Correct' }))
    const form = screen.getByRole('form', { name: 'Correct G001' })
    await user.clear(within(form).getByLabelText('#1 Net Ninjas score'))
    await user.type(within(form).getByLabelText('#1 Net Ninjas score'), '4')
    await user.clear(within(form).getByLabelText('#2 Dink Squad score'))
    await user.type(within(form).getByLabelText('#2 Dink Squad score'), '11')
    await user.type(within(form).getByLabelText('Reason'), 'teams swapped')
    await user.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/G001 corrected. Check: R16-1/)).toBeInTheDocument()
    expect(sent('POST', '/admin/matches/1/correct')[0].body).toEqual({ score_a: 4, score_b: 11, end_reason: 'reached_11', reason: 'teams swapped' })
    // a result entered after the app was down gets its real game time (a tiebreak)
    await user.click(screen.getByRole('button', { name: 'Correct' }))
    const again = screen.getByRole('form', { name: 'Correct G001' })
    await user.type(within(again).getByLabelText('Game time'), '8:30')
    await user.type(within(again).getByLabelText('Reason'), 'entered after the outage')
    await user.click(within(again).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(sent('POST', '/admin/matches/1/correct')).toHaveLength(2))
    expect(sent('POST', '/admin/matches/1/correct')[1].body).toMatchObject({ seconds: 510 })
    vi.spyOn(window, 'prompt').mockReturnValueOnce('').mockReturnValueOnce('wrong game')
    const resets = screen.getAllByRole('button', { name: 'Reset' })
    await user.click(resets[1])
    await user.click(resets[1])
    expect(await screen.findByText('G002 reset')).toBeInTheDocument()
  })

  it('says when nothing has been played', async () => {
    mockApi({ 'GET /public/schedule': [match()] })
    renderAt('/admin/results', ADMIN)
    expect(await screen.findByText('No games played yet.')).toBeInTheDocument()
  })
})

describe('announcements, staff and audit tabs', () => {
  it('posts, hides and deletes announcements', async () => {
    const { sent } = mockApi({
      'GET /admin/announcements': [{ id: 1, title: 'Lunch', body: 'in hall', active: true, created_at: '' }, { id: 2, title: 'Old', body: '', active: false, created_at: '' }],
      'POST /admin/announcements': {},
      'PATCH /admin/announcements/1': {},
      'PATCH /admin/announcements/2': {},
      'DELETE /admin/announcements/1': null,
    })
    const user = userEvent.setup()
    renderAt('/admin/announcements', ADMIN)
    await user.type(await screen.findByLabelText('Title'), 'Courts 8-9 closed')
    await user.type(screen.getByLabelText('Details'), 'Use court 7')
    await user.click(screen.getByRole('button', { name: 'Post' }))
    expect(await screen.findByText('Announcement posted')).toBeInTheDocument()
    expect(sent('POST', '/admin/announcements')[0].body).toEqual({ title: 'Courts 8-9 closed', body: 'Use court 7' })
    await user.click(screen.getByRole('button', { name: 'Hide' }))
    expect(await screen.findByText('Hidden')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show' }))
    expect(await screen.findByText('Shown again')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Delete' })[0])
    expect(await screen.findByText('Deleted')).toBeInTheDocument()
  })

  it('adds judges, renames them and sets temporary passwords', async () => {
    const judge = { id: 3, username: 'court-1', display_name: 'Court 1 judge', role: 'judge', court: 1, active: true, must_change_password: false }
    const boss = { id: 1, username: 'imgp004', display_name: 'imgp004', role: 'admin', court: null, active: true, must_change_password: false }
    const { sent } = mockApi({
      'GET /admin/staff': [boss, judge, { ...judge, id: 4, username: 'floater', court: null, must_change_password: true }],
      'POST /admin/staff': judge,
      'PATCH /admin/staff/3': judge,
      'PATCH /admin/staff/4': judge,
    })
    const user = userEvent.setup()
    renderAt('/admin/staff', ADMIN)
    expect(await screen.findByText('court-1')).toBeInTheDocument()
    expect(screen.getByText('Court 1')).toBeInTheDocument()
    expect(within(screen.getByRole('table')).getByText('Admin')).toBeInTheDocument()
    expect(screen.getByText('Any court · temporary password')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Court for court-1'), '6')
    expect(await screen.findByText('court-1: court 6')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Court for floater'), '')
    expect(await screen.findByText('floater: any court')).toBeInTheDocument()
    await user.click(screen.getByLabelText('court-1 active'))
    expect(await screen.findByText('court-1 disabled')).toBeInTheDocument()
    const renames = screen.getAllByRole('button', { name: 'Rename' })
    await user.click(renames[1])
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getAllByRole('button', { name: 'Rename' })[1])
    const renameForm = screen.getByRole('form', { name: 'Rename court-1' })
    await user.clear(within(renameForm).getByLabelText('New username'))
    await user.type(within(renameForm).getByLabelText('New username'), 'Ravi_Patel')
    await user.click(within(renameForm).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Renamed to ravi_patel')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Set password' })[2])
    const pinForm = screen.getByRole('form', { name: 'New password for floater' })
    await user.type(within(pinForm).getByLabelText('Temporary password or PIN'), '4321')
    await user.click(within(pinForm).getByRole('button', { name: 'Set' }))
    expect(await screen.findByText(/New password set for floater/)).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'Set password' })[1])
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.type(screen.getByLabelText('Username'), 'court-2')
    await user.type(screen.getByLabelText('Temporary password or PIN'), '2222')
    await user.selectOptions(screen.getAllByLabelText('Court')[0], '2')
    await user.click(screen.getByRole('button', { name: 'Add' }))
    expect(await screen.findByText('Added court-2')).toBeInTheDocument()
    expect(sent('POST', '/admin/staff')[0].body).toEqual({ username: 'court-2', password: '2222', role: 'judge', court: 2 })
    expect(sent('PATCH', '/admin/staff/3').map((c) => c.body)).toEqual([{ court: 6 }, { active: false }, { username: 'Ravi_Patel' }])
    expect(sent('PATCH', '/admin/staff/4').map((c) => c.body)).toEqual([{ clear_court: true }, { password: '4321' }])
    await user.type(screen.getByLabelText('Username'), 'boss')
    await user.type(screen.getByLabelText('Temporary password or PIN'), 'long-password')
    await user.selectOptions(screen.getByLabelText('Role'), 'admin')
    await user.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(sent('POST', '/admin/staff')[1]?.body).toMatchObject({ role: 'admin', court: null }))
  })

  it('lists the audit log', async () => {
    mockApi({
      'GET /admin/audit': [
        { id: 2, match: 'G001', action: 'correct', old: { score_a: 11, score_b: 4 }, new: { score_a: 4, score_b: 11 }, by: 'admin', reason: 'swapped', at: '2026-12-12T16:00:00Z' },
        { id: 1, match: 'G001', action: 'start', old: { score_a: null }, new: { score_a: 0, score_b: 0 }, by: 'judge1', reason: '', at: '2026-12-12T15:00:00Z' },
      ],
    })
    renderAt('/admin/audit', ADMIN)
    expect(await screen.findByText('correct: 11-4 → 4-11')).toBeInTheDocument()
    expect(screen.getByText('start: - → 0-0')).toBeInTheDocument()
  })

  it('logs out from the admin header', async () => {
    mockApi({ 'GET /admin/summary': summary(), 'POST /auth/logout': null })
    const user = userEvent.setup()
    renderAt('/admin', ADMIN)
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
  })
})
