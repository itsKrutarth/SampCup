import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { groups, match, overview, team, teamPage } from '../../test/data'
import { ADMIN, fail, JUDGE, mockApi, PLAYER, renderAt } from '../../test/utils'

const tempJudge = { username: 'court-3', display_name: 'Court 3 judge', role: 'judge', court: 3, must_change_password: true }

describe('choosing your own password', () => {
  it('sends a judge with a temporary PIN to choose their own, then to their court', async () => {
    const { sent } = mockApi({
      'POST /auth/staff-login': { token: 'tok', kind: 'staff', user: tempJudge },
      'POST /auth/change-password': () => ({ user: { ...tempJudge, must_change_password: false } }),
      'GET /judge/matches?court=3': { court: 3, current: null, matches: [] },
    })
    const user = userEvent.setup()
    renderAt('/staff')
    await user.type(screen.getByLabelText('Username'), 'court-3')
    await user.type(screen.getByLabelText('Password or PIN'), '1111')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Choose your own password' })).toBeInTheDocument()
    expect(screen.getByText('At least 4 characters.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Password or PIN you were given'), '1111')
    await user.type(screen.getByLabelText('New password or PIN'), '2468')
    await user.type(screen.getByLabelText('New password again'), '2469')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('do not match')
    await user.clear(screen.getByLabelText('New password again'))
    await user.type(screen.getByLabelText('New password again'), '2468')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('heading', { name: 'Court 3' })).toBeInTheDocument()
    expect(sent('POST', '/auth/change-password')[0].body).toEqual({ current_password: '1111', new_password: '2468' })
  })

  it('shows a wrong current password and sends admins to the admin console', async () => {
    let attempts = 0
    mockApi({
      'POST /auth/change-password': () =>
        ++attempts === 1
          ? fail(400, 'Your current password or PIN is wrong')
          : { user: { username: 'boss', display_name: 'boss', role: 'admin', court: null, must_change_password: false } },
      'GET /admin/summary': fail(500, 'later'),
    })
    const user = userEvent.setup()
    renderAt('/staff/password', { ...ADMIN, mustChange: true })
    expect(screen.getByText('At least 8 characters.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Password or PIN you were given'), 'wrong-one')
    await user.type(screen.getByLabelText('New password or PIN'), 'brand-new-pass')
    await user.type(screen.getByLabelText('New password again'), 'brand-new-pass')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('current password or PIN is wrong')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('heading', { name: /Admin/ })).toBeInTheDocument()
  })

  it('keeps staff with a temporary password out of the judge and admin screens', async () => {
    mockApi({})
    renderAt('/judge', { ...JUDGE, mustChange: true })
    expect(await screen.findByRole('heading', { name: 'Choose your own password' })).toBeInTheDocument()
    renderAt('/admin', { ...ADMIN, mustChange: true })
    expect((await screen.findAllByRole('heading', { name: 'Choose your own password' })).length).toBeGreaterThan(0)
  })

  it('needs a login first', async () => {
    mockApi({})
    renderAt('/staff/password')
    expect(await screen.findByRole('heading', { name: 'Player login' })).toBeInTheDocument()
  })
})

describe('home page states', () => {
  it('is about play once games start: short hero, courts first, the venue further down', async () => {
    mockApi({
      'GET /public/overview': overview({
        phase: 'group_play',
        tournament: { ...overview().tournament, event_date: '2020-01-01', name: 'SAMP Cup' },
        live: [match({ status: 'in_progress', team_b: { id: 9, name: 'New Pair', number: null, group: null } })],
        courts: [{ court: 1, match: match({ status: 'in_progress', team_b: { id: 9, name: 'New Pair', number: null, group: null } }) }],
      }),
    })
    renderAt('/')
    const courts = await screen.findByRole('region', { name: 'Courts' })
    expect(screen.getByRole('heading', { name: 'SAMP Cup' })).toBeInTheDocument()
    expect(screen.getByText('Unity in every rally')).toBeInTheDocument()
    // the hero stops at the tagline: no date, countdown or buttons (the tab bar has them)
    expect(screen.queryByText('January 1')).not.toBeInTheDocument()
    expect(screen.queryByRole('timer')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Full schedule' })).not.toBeInTheDocument()
    const venue = screen.getByRole('region', { name: 'Venue' })
    expect(courts.compareDocumentPosition(venue) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Directions' })).toBeInTheDocument()
    expect(screen.getByText('NP')).toBeInTheDocument() // initials before the draw
  })

  it("shows a logged-in player their own next game, then the one they're playing", async () => {
    const mine = team(1, 'Net Ninjas')
    let playing = false
    mockApi({
      'GET /public/overview': overview({ phase: 'scheduled' }),
      'GET /player/me': { player: {}, team: teamPage(), incoming: [], outgoing: null },
      'GET /public/schedule?team=1': () => [
        match({ id: 1, status: 'completed', score_a: 11, score_b: 3, winner_id: 1 }),
        match({ id: 2, code: 'G009', court: 4, status: playing ? 'in_progress' : 'scheduled', team_a: mine }),
        match({ id: 3, code: 'G020', team_b: mine }),
      ],
    })
    const page = renderAt('/', PLAYER)
    const game = await screen.findByRole('region', { name: 'Your game' })
    expect(within(game).getByRole('heading', { name: 'Your next game' })).toBeInTheDocument()
    expect(within(game).getByRole('article', { name: /G009/ })).toBeInTheDocument()
    expect(within(game).getByRole('link', { name: 'Your whole day' })).toHaveAttribute('href', '/schedule')
    expect(screen.getByText('December 12')).toBeInTheDocument() // before play: the full hero stays
    page.unmount()
    playing = true
    renderAt('/', PLAYER)
    expect(await screen.findByRole('heading', { name: 'Your game now' })).toBeInTheDocument()
  })

  it('reads the schedule from now during play: live games, then coming up, then results', async () => {
    const at = (h: number, m: number) => `2026-12-12T${String(h + 5).padStart(2, '0')}:${String(m).padStart(2, '0')}:00+00:00`
    mockApi({
      'GET /public/schedule': [
        match({ id: 1, code: 'G001', scheduled_at: at(10, 0), status: 'completed', score_a: 11, score_b: 4, winner_id: 1 }),
        match({ id: 2, code: 'G010', scheduled_at: at(10, 17), status: 'completed', score_a: 6, score_b: 11, winner_id: 2 }),
        match({ id: 3, code: 'G020', scheduled_at: at(10, 34), status: 'in_progress', score_a: 5, score_b: 3 }),
        match({ id: 4, code: 'G030', scheduled_at: at(10, 51) }),
        match({ id: 5, code: 'G040', scheduled_at: at(11, 8) }),
      ],
    })
    renderAt('/schedule')
    const live = await screen.findByRole('region', { name: 'Playing now' })
    const coming = screen.getByRole('region', { name: 'Coming up' })
    const done = screen.getByRole('region', { name: 'Completed' })
    expect(within(live).getByRole('article', { name: /G020/ })).toBeInTheDocument()
    expect(within(coming).getAllByRole('article').map((a) => a.getAttribute('aria-label'))).toEqual([
      expect.stringMatching(/^G030/),
      expect.stringMatching(/^G040/),
    ])
    // results last, the most recent first
    expect(within(done).getAllByRole('article').map((a) => a.getAttribute('aria-label'))).toEqual([
      expect.stringMatching(/^G010/),
      expect.stringMatching(/^G001/),
    ])
    const order = [live, coming, done].map((s) => s.compareDocumentPosition(done))
    expect(order[0] & Node.DOCUMENT_POSITION_FOLLOWING && order[1] & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(live.compareDocumentPosition(coming) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('opens a logged-in player on their own schedule, and lets them see everyone', async () => {
    const mine = team(1, 'Net Ninjas')
    const { calls } = mockApi({
      'GET /player/me': { player: {}, team: teamPage(), incoming: [], outgoing: null },
      'GET /public/teams': [mine, team(2, 'Dink Squad')],
      'GET /public/schedule?team=1': [match({ id: 2, code: 'G009', team_a: mine }), match({ id: 3, code: 'G020', team_b: mine })],
      'GET /public/schedule': [match(), match({ id: 7, code: 'G007', team_a: team(2, 'Dink Squad'), team_b: team(3, 'Lob Stars') })],
    })
    const user = userEvent.setup()
    renderAt('/schedule', PLAYER)
    expect(await screen.findByRole('heading', { name: 'Your schedule' })).toBeInTheDocument()
    const game = await screen.findByRole('region', { name: 'Your game' })
    expect(within(game).getByRole('article', { name: /G009/ })).toBeInTheDocument()
    // the rest of their day below it, without repeating the game on top
    const next = screen.getByRole('region', { name: 'Your next games' })
    expect(within(next).getByRole('article', { name: /G020/ })).toBeInTheDocument()
    expect(within(next).queryByRole('article', { name: /G009/ })).not.toBeInTheDocument()
    expect(calls.some((c) => c.path === '/public/schedule?')).toBe(false) // never everyone's games first
    const teamPick = await screen.findByRole('combobox', { name: 'Team' })
    expect(teamPick).toHaveValue('1')
    expect(within(teamPick).getByRole('option', { name: '#1 Net Ninjas (your team)' })).toBeInTheDocument()
    await user.selectOptions(teamPick, 'All teams')
    expect(await screen.findByRole('heading', { name: 'Schedule' })).toBeInTheDocument()
    expect(await screen.findByText('Lob Stars')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Your game' })).not.toBeInTheDocument()
  })

  it('works before the date is set and when registration is closed', async () => {
    mockApi({
      'GET /public/overview': overview({
        tournament: { ...overview().tournament, event_date: null, registration_open: false, venue_name: '', age_group: '' },
      }),
    })
    renderAt('/')
    expect(await screen.findByText('Date to be announced')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Directions' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Create your account' })).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Log in' }).length).toBeGreaterThan(0)
  })

  it('shows unknown knockout opponents and empty standings', async () => {
    mockApi({
      'GET /public/schedule': [match({ phase: 'knockout', group: null, code: 'QF-1', round: 'Quarterfinal', team_a: null, source_a: null })],
      'GET /public/standings': { groups: {} },
    })
    renderAt('/schedule')
    expect(await screen.findByText('To be decided')).toBeInTheDocument()
    expect(screen.getByText('Quarterfinal')).toBeInTheDocument()
    renderAt('/standings')
    expect(await screen.findByText('Standings appear once the draw is done.')).toBeInTheDocument()
    expect(groups.A.rows).toHaveLength(2)
  })
})

describe('home page buttons depend on who is looking', () => {
  it('offers My team to a player with a team, and no sign-up', async () => {
    mockApi({ 'GET /public/overview': overview(), 'GET /player/me': { team: { id: 1 } } })
    renderAt('/', PLAYER)
    await waitFor(() => expect(screen.getAllByRole('link', { name: 'My team' })).toHaveLength(2)) // header and hero
    expect(screen.queryByRole('link', { name: 'Create your account' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Registered on the MySatsang app/)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'My account' })).toHaveAttribute('href', '/my-team')
  })

  it('offers Pick your partner to a player without a team', async () => {
    mockApi({ 'GET /public/overview': overview(), 'GET /player/me': { team: null } })
    renderAt('/', PLAYER)
    expect(await screen.findByRole('link', { name: 'Pick your partner' })).toHaveAttribute('href', '/my-team')
  })

  it('shows staff no join or login buttons', async () => {
    mockApi({ 'GET /public/overview': overview() })
    renderAt('/', ADMIN)
    expect(await screen.findByText('Registration is open')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Create your account' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument()
  })
})
