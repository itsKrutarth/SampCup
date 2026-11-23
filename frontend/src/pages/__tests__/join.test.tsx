import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { PartnerRequest, PlayerLite } from '../../lib/types'
import { teamPage } from '../../test/data'
import { fail, mockApi, PLAYER, renderAt } from '../../test/utils'

const p = (id: number, first: string, state: PlayerLite['state'] = 'free'): PlayerLite => ({
  id, first_name: first, last_name: 'Tester', center: 'North', zone: 'Zone 1', state, team_name: null,
})
const me = p(1, 'Aarav')
const request = (id: number, from: PlayerLite, to: PlayerLite): PartnerRequest => ({
  id, team_name: 'Net Ninjas', status: 'pending', from, to, created_at: '',
})
const page = (overrides = {}) => ({ player: me, team: null, incoming: [], outgoing: null, ...overrides })

describe('creating your account', () => {
  it('matches the registration and logs the player in', async () => {
    const { sent } = mockApi({
      'GET /registration/status': { open: true, team_cap: 42, loaded: true },
      'POST /players/claim': { token: 'tok', kind: 'player', player: { id: 1, first_name: 'Aarav' } },
      'GET /player/me': page(),
      'GET /registration/players': [],
    })
    const user = userEvent.setup()
    renderAt('/join')
    await user.type(screen.getByLabelText('First name'), 'aarav')
    await user.type(screen.getByLabelText('Last name'), 'tester')
    await user.type(screen.getByLabelText('Registration email'), 'Aarav@Example.com')
    await user.type(screen.getByLabelText('Username'), 'aarav_t')
    await user.type(screen.getByLabelText('Password'), 'secret1')
    await user.type(screen.getByLabelText('Password again'), 'secret2')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(screen.getByRole('alert')).toHaveTextContent('do not match')
    await user.clear(screen.getByLabelText('Password again'))
    await user.type(screen.getByLabelText('Password again'), 'secret1')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText(/^Hi/)).toBeInTheDocument()
    expect(sent('POST', '/players/claim')[0].body).toEqual({
      first_name: 'aarav', last_name: 'tester', email: 'Aarav@Example.com', username: 'aarav_t', password: 'secret1',
    })
  })

  it('explains when the player is not found, registration is closed or nothing is loaded', async () => {
    mockApi({
      'GET /registration/status': { open: false, team_cap: 42, loaded: false },
      'POST /players/claim': fail(404, "We couldn't find you."),
    })
    const user = userEvent.setup()
    renderAt('/join')
    expect(await screen.findByText(/registration is closed/)).toBeInTheDocument()
    expect(await screen.findByText(/have not been loaded yet/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('First name'), 'x')
    await user.type(screen.getByLabelText('Last name'), 'y')
    await user.type(screen.getByLabelText('Registration email'), 'x@example.com')
    await user.type(screen.getByLabelText('Username'), 'xy_123')
    await user.type(screen.getByLabelText('Password'), 'secret1')
    await user.type(screen.getByLabelText('Password again'), 'secret1')
    await user.click(screen.getByRole('button', { name: 'Create account' }))
    expect(await screen.findByText(/couldn't find/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log in' })).toHaveAttribute('href', '/login')
  })

  it('sends logged-in players to their page', async () => {
    mockApi({ 'GET /player/me': page(), 'GET /registration/players': [] })
    renderAt('/join', PLAYER)
    expect(await screen.findByRole('heading', { name: 'Pick your partner' })).toBeInTheDocument()
  })
})

describe('the player page', () => {
  it('invites a partner from the same center', async () => {
    let invited = false
    const { sent } = mockApi({
      'GET /player/me': () => (invited ? page({ outgoing: request(5, me, p(2, 'Dev')) }) : page()),
      'GET /registration/players': [
        p(2, 'Dev', 'pending'),
        p(3, 'Jay', 'teamed'),
        { ...p(4, 'Kirtan'), hint: 'kir…@example.com' },
        { ...p(5, 'Kirtan'), hint: 'imk…@example.com' },
      ],
      'POST /registration/requests': () => {
        invited = true
        return request(5, me, p(2, 'Dev'))
      },
    })
    const user = userEvent.setup()
    renderAt('/my-team', PLAYER)
    const dev = await screen.findByRole('option', { name: /Dev Tester/ })
    expect(dev).toHaveTextContent('has a pending request')
    expect(dev).not.toHaveTextContent('Zone 1') // the export's zone is not a center: not shown
    // namesakes are told apart by a short email hint
    expect(screen.getByRole('option', { name: 'Kirtan Tester (kir…@example.com)' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Kirtan Tester (imk…@example.com)' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Jay/ })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Partner'), dev)
    await user.type(screen.getByLabelText('Team name'), 'Net Ninjas')
    await user.click(screen.getByRole('button', { name: 'Send invitation' }))
    expect(await screen.findByText(/Waiting for/)).toBeInTheDocument()
    expect(sent('POST', '/registration/requests')[0].body).toEqual({ to_player_id: 2, team_name: 'Net Ninjas' })
  })

  it('shows invitation errors, accepts one and then shows the team', async () => {
    let accepted = false
    mockApi({
      'GET /player/me': () =>
        accepted
          ? page({ team: teamPage({ players: [{ id: 1, name: 'Aarav Tester' }, { id: 2, name: 'Dev Tester' }] }) })
          : page({ incoming: [request(5, p(2, 'Dev'), me), request(6, p(3, 'Jay'), me)] }),
      'POST /registration/requests/6/decline': fail(409, 'This request was already cancelled'),
      'POST /registration/requests/5/accept': () => {
        accepted = true
        return {}
      },
      'POST /registration/requests': fail(409, 'That team name is taken'),
      'GET /registration/players': [p(2, 'Dev')],
    })
    const user = userEvent.setup()
    renderAt('/my-team', PLAYER)
    const declines = await screen.findAllByRole('button', { name: 'Decline' })
    expect(await screen.findByRole('heading', { name: 'Or invite someone else' })).toBeInTheDocument()
    await user.click(declines[1])
    expect(await screen.findByRole('alert')).toHaveTextContent('already cancelled')
    await user.click(screen.getAllByRole('button', { name: 'Accept' })[0])
    expect(await screen.findByRole('status')).toHaveTextContent("You're on Net Ninjas!")
    const mine = await screen.findByRole('region', { name: 'My team' })
    expect(within(mine).getByText('Aarav Tester & Dev Tester')).toBeInTheDocument()
    expect(screen.queryByLabelText('Partner')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument()
  })

  it("shows a teamed player's games from the public team page", async () => {
    const { calls } = mockApi({
      'GET /player/me': page({ team: teamPage({ players: [{ id: 1, name: 'Aarav Tester' }, { id: 2, name: 'Dev Tester' }] }) }),
      'GET /public/teams/1': teamPage({ players: [{ id: 1, name: 'Aarav Tester' }, { id: 2, name: 'Dev Renamed' }] }),
    })
    renderAt('/my-team', PLAYER)
    const mine = await screen.findByRole('region', { name: 'My team' })
    expect(await within(mine).findByText('Aarav Tester & Dev Renamed')).toBeInTheDocument()
    expect(calls.find((c) => c.path === '/public/teams/1')?.headers).not.toHaveProperty('Authorization')
  })

  it('shows refused invitations and lets the sender cancel', async () => {
    let cancelled = false
    mockApi({
      'GET /player/me': () => (cancelled ? page() : page({ outgoing: request(5, me, p(2, 'Dev')) })),
      'POST /registration/requests/5/cancel': () => {
        cancelled = true
        return {}
      },
      'GET /registration/players': [p(2, 'Dev')],
      'POST /registration/requests': fail(409, 'That team name is taken'),
    })
    const user = userEvent.setup()
    renderAt('/my-team', PLAYER)
    await user.click(await screen.findByRole('button', { name: 'Cancel invitation' }))
    await user.selectOptions(await screen.findByLabelText('Partner'), await screen.findByRole('option', { name: /Dev/ }))
    await user.type(screen.getByLabelText('Team name'), 'Taken')
    await user.click(screen.getByRole('button', { name: 'Send invitation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That team name is taken')
  })

  it('tells a player without a center that an admin pairs them', async () => {
    mockApi({ 'GET /player/me': page({ player: { ...me, center: '' } }) })
    renderAt('/my-team', PLAYER)
    expect(await screen.findByText(/no center yet/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Partner')).not.toBeInTheDocument()
  })

  it('needs a login, a password of their own, and handles an expired login', async () => {
    mockApi({ 'GET /player/me': fail(401, 'Your login has expired'), 'POST /auth/logout': null })
    renderAt('/my-team')
    expect(await screen.findByRole('heading', { name: 'Player login' })).toBeInTheDocument()
    renderAt('/my-team', { ...PLAYER, mustChange: true })
    expect((await screen.findAllByRole('heading', { name: 'Choose your own password' })).length).toBeGreaterThan(0)
  })

  it('offers a fresh login when the session is gone', async () => {
    mockApi({ 'GET /player/me': fail(401, 'Your login has expired'), 'POST /auth/logout': null })
    const user = userEvent.setup()
    renderAt('/my-team', PLAYER)
    await user.click(await screen.findByRole('button', { name: 'Log in again' }))
    await waitFor(() => expect(localStorage.getItem('sampcup-auth')).toBeNull())
  })
})
