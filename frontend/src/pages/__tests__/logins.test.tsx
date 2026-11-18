import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { fail, mockApi, renderAt } from '../../test/utils'

const me = { player: { id: 1, first_name: 'Aarav', last_name: 'Tester', center: 'North', zone: 'Z' }, team: null, incoming: [], outgoing: null }

describe('player login', () => {
  it('logs in, shows the player page, then logs out', async () => {
    const { sent } = mockApi({
      'POST /auth/player-login': { token: 't-player', kind: 'player', player: { first_name: 'Aarav', must_change_password: false } },
      'GET /player/me': me,
      'GET /registration/players': [],
      'POST /auth/logout': null,
    })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(screen.getByLabelText('Username'), 'aarav_t')
    await user.type(screen.getByLabelText('Password'), 'secret1')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Pick your partner' })).toBeInTheDocument()
    expect(sent('GET', '/player/me')[0].headers).toEqual({ Authorization: 'Bearer t-player' })
    await user.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Player login' })).toBeInTheDocument()
    expect(localStorage.getItem('sampcup-auth')).toBeNull()
  })

  it('sends a player with a temporary password to choose their own', async () => {
    const { sent } = mockApi({
      'POST /auth/player-login': { token: 't-player', kind: 'player', player: { first_name: 'Aarav', must_change_password: true } },
      'POST /auth/change-password': { player: { first_name: 'Aarav', must_change_password: false } },
      'GET /player/me': me,
      'GET /registration/players': [],
    })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(screen.getByLabelText('Username'), 'aarav_t')
    await user.type(screen.getByLabelText('Password'), 'temp123')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('At least 6 characters.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Password or PIN you were given'), 'temp123')
    await user.type(screen.getByLabelText('New password or PIN'), 'mine123')
    await user.type(screen.getByLabelText('New password again'), 'mine123')
    await user.click(screen.getByRole('button', { name: 'Save and continue' }))
    expect(await screen.findByRole('heading', { name: 'Pick your partner' })).toBeInTheDocument()
    expect(sent('POST', '/auth/change-password')).toHaveLength(1)
    await waitFor(() => expect(JSON.parse(localStorage.getItem('sampcup-auth')!).mustChange).toBe(false))
  })

  it('shows a wrong password', async () => {
    mockApi({ 'POST /auth/player-login': fail(401, 'Username or password is wrong') })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(screen.getByLabelText('Username'), 'x')
    await user.type(screen.getByLabelText('Password'), 'y')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('wrong')
  })
})

describe('staff login', () => {
  it.each([
    ['admin', { username: 'admin', display_name: 'Admin', role: 'admin', court: null, must_change_password: false }, /Admin/],
    ['judge1', { username: 'judge1', display_name: 'Judge One', role: 'judge', court: 2, must_change_password: false }, /Court 2/],
  ])('sends %s to the right screen', async (username, user, heading) => {
    mockApi({
      'POST /auth/staff-login': { token: 'tok', kind: 'staff', user },
      'GET /admin/summary': fail(500, 'later'),
      'GET /judge/matches?court=2': { court: 2, current: null, matches: [] },
    })
    const u = userEvent.setup()
    renderAt('/staff')
    await u.type(screen.getByLabelText('Username'), username)
    await u.type(screen.getByLabelText('Password or PIN'), 'secret')
    await u.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
  })

  it('shows a failed staff login', async () => {
    mockApi({ 'POST /auth/staff-login': fail(401, 'Username or password is wrong') })
    const u = userEvent.setup()
    renderAt('/staff')
    await u.type(screen.getByLabelText('Username'), 'x')
    await u.type(screen.getByLabelText('Password or PIN'), 'y')
    await u.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('wrong')
  })
})
