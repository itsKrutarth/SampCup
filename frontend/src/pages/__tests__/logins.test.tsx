import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { teamPage } from '../../test/data'
import { fail, mockApi, renderAt, TEAM } from '../../test/utils'

describe('team login', () => {
  it('logs in and shows the team page, then logs out', async () => {
    const { sent } = mockApi({
      'POST /auth/team-login': { token: 't-team', kind: 'team', team: { name: 'Net Ninjas' } },
      'GET /team/me': teamPage({ players: [{ id: 1, name: 'Aarav Tester' }, { id: 2, name: 'Dev Tester' }] }),
      'POST /auth/logout': null,
    })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(screen.getByLabelText('Team name'), 'Net Ninjas')
    await user.type(screen.getByLabelText('Password'), 'pass1')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Aarav Tester & Dev Tester')).toBeInTheDocument()
    expect(sent('GET', '/team/me')[0].headers).toEqual({ Authorization: 'Bearer t-team' })
    await user.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Team login' })).toBeInTheDocument()
    expect(sent('POST', '/auth/logout')).toHaveLength(1)
    expect(localStorage.getItem('sampcup-auth')).toBeNull()
  })

  it('shows a wrong password', async () => {
    mockApi({ 'POST /auth/team-login': fail(401, 'Team name or password is wrong') })
    const user = userEvent.setup()
    renderAt('/login')
    await user.type(screen.getByLabelText('Team name'), 'x')
    await user.type(screen.getByLabelText('Password'), 'y')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Judges and admins log in on the staff page')
    await user.click(screen.getByRole('link', { name: 'Staff login' }))
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Team login' }))
    expect(await screen.findByRole('heading', { name: 'Team login' })).toBeInTheDocument()
  })

  it('sends logged-out visitors to the login and handles expired logins', async () => {
    mockApi({ 'GET /team/me': fail(401, 'Your login has expired'), 'POST /auth/logout': null })
    renderAt('/my-team')
    expect(await screen.findByRole('heading', { name: 'Team login' })).toBeInTheDocument()
    const user = userEvent.setup()
    renderAt('/my-team', TEAM)
    await user.click(await screen.findByRole('button', { name: 'Log in again' }))
    await waitFor(() => expect(localStorage.getItem('sampcup-auth')).toBeNull())
  })
})

describe('staff login', () => {
  it.each([
    ['admin', { display_name: 'Admin', role: 'admin', court: null }, 'Admin'],
    ['judge1', { display_name: 'Judge One', role: 'judge', court: 2 }, 'Court 2'],
  ])('sends %s to the right screen', async (username, user, heading) => {
    mockApi({
      'POST /auth/staff-login': { token: 'tok', kind: 'staff', user },
      'GET /admin/summary': fail(500, 'later'),
      'GET /judge/matches': { court: 2, current: null, matches: [] },
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
