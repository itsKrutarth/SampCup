import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { groups, match, overview } from '../../test/data'
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
  it('hides the countdown once play has started and offers the schedule', async () => {
    mockApi({
      'GET /public/overview': overview({
        phase: 'group_play',
        tournament: { ...overview().tournament, event_date: '2020-01-01', name: 'SAMP Cup' },
        live: [match({ status: 'in_progress', team_b: { id: 9, name: 'New Pair', number: null, group: null } })],
      }),
    })
    renderAt('/')
    expect(await screen.findByText('Group play under way')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'SAMP Cup' })).toBeInTheDocument()
    expect(screen.queryByRole('timer')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Full schedule' })).toHaveAttribute('href', '/schedule')
    expect(screen.getByText('NP')).toBeInTheDocument() // initials before the draw
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
