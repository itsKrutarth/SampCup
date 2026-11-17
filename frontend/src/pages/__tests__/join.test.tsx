import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { PartnerRequest, PlayerLite } from '../../lib/types'
import { fail, mockApi, renderAt } from '../../test/utils'

const p = (id: number, first: string, state: PlayerLite['state'] = 'free', team_name: string | null = null): PlayerLite => ({
  id, first_name: first, last_name: 'Tester', center: 'North', zone: 'Zone 1', state, team_name,
})
const players = [p(1, 'Aarav'), p(2, 'Dev', 'pending'), p(3, 'Jay', 'teamed', 'Smashers')]
const request = (id: number, from: PlayerLite, to: PlayerLite): PartnerRequest => ({
  id, team_name: 'Net Ninjas', status: 'pending', from, to, created_at: '',
})
const status = (overrides = {}) => ({ player: players[0], team: null, incoming: [], outgoing: null, ...overrides })

const common = {
  'GET /registration/status': { open: true, team_cap: 42, teams: 1 },
  'GET /registration/centers': [{ center: 'North', players: 3, on_teams: 2 }],
  'GET /registration/players': players,
}

describe('joining with a partner', () => {
  it('walks a player from center to sending a request', async () => {
    let sentRequest = false
    const { sent } = mockApi({
      ...common,
      'GET /registration/players/1': () => (sentRequest ? status({ outgoing: request(5, players[0], players[1]) }) : status()),
      'POST /registration/requests': () => {
        sentRequest = true
        return request(5, players[0], players[1])
      },
    })
    const user = userEvent.setup()
    renderAt('/join')
    await user.click(await screen.findByRole('button', { name: 'North' }))
    expect(await screen.findByText(/Smashers/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Aarav Tester/ }))
    expect(await screen.findByText(/^Hi/)).toBeInTheDocument()
    const partner = await screen.findByRole('option', { name: /Dev Tester/ })
    expect(partner).toHaveTextContent('has a pending request')
    expect(screen.queryByRole('option', { name: /Jay/ })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Partner'), partner)
    await user.type(screen.getByLabelText('Team name'), 'Net Ninjas')
    await user.type(screen.getByLabelText('Team password'), 'pass1')
    await user.type(screen.getByLabelText('Password again'), 'pass2')
    await user.click(screen.getByRole('button', { name: 'Send request' }))
    expect(screen.getByRole('alert')).toHaveTextContent('do not match')
    await user.clear(screen.getByLabelText('Password again'))
    await user.type(screen.getByLabelText('Password again'), 'pass1')
    await user.click(screen.getByRole('button', { name: 'Send request' }))
    expect(await screen.findByText(/Waiting for/)).toBeInTheDocument()
    expect(sent('POST', '/registration/requests')[0].body).toEqual({
      from_player_id: 1, to_player_id: 2, team_name: 'Net Ninjas', password: 'pass1',
    })
    await user.click(screen.getByRole('button', { name: '← Back' }))
    expect(await screen.findByText('2. Who are you?')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '← Back' }))
    expect(await screen.findByText('1. Your center')).toBeInTheDocument()
  })

  it('shows request errors from the server', async () => {
    mockApi({ ...common, 'GET /registration/players/1': status(), 'POST /registration/requests': fail(409, 'That team name is taken') })
    const user = userEvent.setup()
    renderAt('/join?center=North&me=1')
    await user.selectOptions(await screen.findByLabelText('Partner'), await screen.findByRole('option', { name: /Dev/ }))
    await user.type(screen.getByLabelText('Team name'), 'Taken')
    await user.type(screen.getByLabelText('Team password'), 'pass1')
    await user.type(screen.getByLabelText('Password again'), 'pass1')
    await user.click(screen.getByRole('button', { name: 'Send request' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('That team name is taken')
  })

  it('lets the partner accept or decline, and the sender cancel', async () => {
    let accepted = false
    const { sent } = mockApi({
      ...common,
      'GET /registration/players/2': () =>
        accepted
          ? status({ player: players[1], team: { id: 9, name: 'Net Ninjas', number: null, group: null, center: 'North', status: 'active', lunch_start: null, players: [{ id: 1, name: 'Aarav Tester' }, { id: 2, name: 'Dev Tester' }] } })
          : status({ player: players[1], incoming: [request(5, players[0], players[1]), request(6, players[2], players[1])] }),
      'POST /registration/requests/6/decline': fail(409, 'This request was already cancelled'),
      'POST /registration/requests/5/accept': () => {
        accepted = true
        return {}
      },
    })
    const user = userEvent.setup()
    renderAt('/join?center=North&me=2')
    const declines = await screen.findAllByRole('button', { name: 'Decline' })
    await user.click(declines[1])
    expect(await screen.findByRole('alert')).toHaveTextContent('already cancelled')
    await user.click(screen.getAllByRole('button', { name: 'Accept' })[0])
    expect(await screen.findByRole('status')).toHaveTextContent('Team Net Ninjas is ready')
    expect(await screen.findByRole('heading', { name: 'Your team: Net Ninjas' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Team login' })).toHaveAttribute('href', '/login')
    expect(sent('POST', '/registration/requests/5/accept')[0].body).toEqual({ player_id: 2 })
  })

  it('lets the sender cancel and shows waitlisted teams', async () => {
    let cancelled = false
    mockApi({
      ...common,
      'GET /registration/players/1': () => (cancelled ? status() : status({ outgoing: request(5, players[0], players[1]) })),
      'POST /registration/requests/5/cancel': () => {
        cancelled = true
        return {}
      },
      'GET /registration/players/3': status({ player: players[2], team: { id: 4, name: 'Smashers', number: null, group: null, center: 'North', status: 'waitlist', lunch_start: null, players: [] } }),
    })
    const user = userEvent.setup()
    renderAt('/join?center=North&me=1')
    await user.click(await screen.findByRole('button', { name: 'Cancel request' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Send request' })).toBeInTheDocument())
    renderAt('/join?center=North&me=3')
    expect(await screen.findByText(/on the waitlist/)).toBeInTheDocument()
  })

  it('says when registration is closed or no players are loaded', async () => {
    mockApi({ ...common, 'GET /registration/status': { open: false, team_cap: 42, teams: 0 }, 'GET /registration/centers': [] })
    renderAt('/join')
    expect(await screen.findByText(/registration is closed/)).toBeInTheDocument()
    expect(await screen.findByText(/have not been loaded yet/)).toBeInTheDocument()
  })
})
