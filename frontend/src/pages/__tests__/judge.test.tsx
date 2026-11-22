import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { match, overview } from '../../test/data'
import { ADMIN, fail, JUDGE, mockApi, renderAt } from '../../test/utils'
import { untilStart } from '../Judge'

// the server's clock: by default well after the 10:00 AM (15:00 UTC) test game
const board = (current = match(), extra = [match({ id: 2, code: 'G002' })], more: { now?: string; waiting?: string | null } = {}) => ({
  court: 1,
  now: '2026-12-12T23:00:00Z',
  waiting: null,
  current,
  matches: [current, ...extra],
  ...more,
})

describe('judge screen', () => {
  it('needs a staff login', async () => {
    mockApi({})
    renderAt('/judge')
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
  })

  it('starts a game, counts points and sends the final score', async () => {
    const { calls } = mockApi({
      'GET /judge/matches?court=1': board(),
      'POST /judge/matches/1/start': match({ status: 'in_progress' }),
      'POST /judge/matches/1/score': match({ status: 'in_progress' }),
      'POST /judge/matches/1/finish': match({ status: 'completed' }),
    })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    expect(await screen.findByRole('heading', { name: 'Court 1' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Later on this court' })).toHaveTextContent('#1 Net Ninjas vs #2 Dink Squad')
    await user.click(await screen.findByRole('button', { name: 'Start game' }))
    expect(screen.getByLabelText('Time left')).toHaveTextContent(/^1[12]:/)
    const point = screen.getByRole('button', { name: 'Point to #1 Net Ninjas' })
    const final = screen.getByRole('button', { name: 'Final: reached 11' })
    expect(final).toBeDisabled()
    for (let i = 0; i < 12; i++) if (!(point as HTMLButtonElement).disabled) await user.click(point)
    expect(screen.getByLabelText('#1 Net Ninjas score')).toHaveTextContent('11')
    expect(point).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Point to #2 Dink Squad' }))
    await user.click(screen.getByRole('button', { name: 'Take a point from #2 Dink Squad' }))
    await user.click(screen.getByRole('button', { name: 'Point to #2 Dink Squad' }))
    await user.click(final)
    expect(await screen.findByText(/Result sent/)).toBeInTheDocument()
    await waitFor(() => expect(calls.filter((c) => c.path === '/judge/matches/1/finish')).toHaveLength(1))
    const finish = calls.find((c) => c.path === '/judge/matches/1/finish')
    expect(finish?.body).toEqual({ score_a: 11, score_b: 1, end_reason: 'reached_11' })
    expect(calls.filter((c) => c.path === '/judge/matches?court=1').length).toBeGreaterThan(1) // reloaded
  })

  it('settles a tie at the clock with sudden death', async () => {
    const { sent } = mockApi({
      'GET /judge/matches?court=1': board(match({ status: 'in_progress', started_at: new Date(Date.now() - 800_000).toISOString(), score_a: 7, score_b: 7 })),
      'POST /judge/matches/1/finish': match({ status: 'completed' }),
    })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    expect(await screen.findByLabelText('Time left')).toHaveTextContent('Time!')
    await user.click(screen.getByRole('button', { name: 'Clock ended' }))
    await user.click(screen.getByRole('button', { name: 'Back' }))
    await user.click(screen.getByRole('button', { name: 'Clock ended' }))
    await user.click(screen.getByRole('button', { name: '#2 Dink Squad' }))
    await waitFor(() => expect(sent('POST', '/judge/matches/1/finish')[0]?.body).toEqual({
      score_a: 7, score_b: 7, end_reason: 'clock_lead', sudden_death_winner: 'b',
    }))
  })

  it('ends on the clock with a leader, or by forfeit', async () => {
    const { sent } = mockApi({
      'GET /judge/matches?court=1': board(match({ status: 'in_progress', started_at: new Date().toISOString(), score_a: 9, score_b: 4 })),
      'POST /judge/matches/1/finish': match({ status: 'completed' }),
    })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    await user.click(await screen.findByRole('button', { name: 'Clock ended' }))
    await waitFor(() => expect(sent('POST', '/judge/matches/1/finish')[0]?.body).toMatchObject({ end_reason: 'clock_lead' }))
  })

  it('records a forfeit before the game starts', async () => {
    const { sent } = mockApi({
      'GET /judge/matches?court=1': board(),
      'POST /judge/matches/1/forfeit': match({ status: 'completed' }),
    })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    await user.click(await screen.findByRole('button', { name: 'Forfeit…' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await user.click(screen.getByRole('button', { name: 'Forfeit…' }))
    await user.click(screen.getByRole('button', { name: '#2 Dink Squad wins' }))
    await waitFor(() => expect(sent('POST', '/judge/matches/1/forfeit')[0]?.body).toEqual({ winner: 'b' }))
  })

  it('keeps scores while offline and says so', async () => {
    mockApi({ 'GET /judge/matches?court=1': board(match({ status: 'in_progress', started_at: new Date().toISOString(), score_a: 0, score_b: 0 })) })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    const point = await screen.findByRole('button', { name: 'Point to #1 Net Ninjas' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await user.click(point)
    expect(await screen.findByText('1 update(s) waiting to send')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('No connection')
    mockApi({ 'GET /judge/matches?court=1': board(), 'POST /judge/matches/1/score': match() })
    await act(async () => {
      window.dispatchEvent(new Event('online'))
    })
    await waitFor(() => expect(screen.queryByText(/waiting to send/)).not.toBeInTheDocument())
  })

  it('waits for the game time, counting down by the server clock', async () => {
    mockApi({ 'GET /judge/matches?court=1': board(match(), [], { now: '2026-12-12T14:55:00Z' }) })
    renderAt('/judge', JUDGE)
    const start = await screen.findByRole('button', { name: 'Start at 10:00 AM' })
    expect(start).toBeDisabled()
    expect(screen.getByRole('timer', { name: 'Time until this game starts' })).toHaveTextContent(/Starts in (5:00|4:5\d)/)
    expect(screen.queryByRole('button', { name: 'Start early (admin)' })).not.toBeInTheDocument()
  })

  it('follows the mock clock during a mock run', async () => {
    const now = new Date().toISOString()
    // the mock clock reads 10:00:30 AM, just past the game's 10:00 AM, though it is weeks early
    const mock_clock = { started_at: now, day_start: '2026-12-12T15:00:30Z', speed: 30 }
    mockApi({
      'GET /public/overview': overview({ tournament: { ...overview().tournament, mock_clock } }),
      'GET /judge/matches?court=1': board(match(), [], { now }),
    })
    renderAt('/judge', JUDGE)
    expect(await screen.findByRole('button', { name: 'Start game' })).toBeEnabled()
    expect(screen.getByTitle('Mock tournament time (30x speed)')).toHaveTextContent(/Mock\s*10:0\d\s*AM/)
  })

  it('lets only an admin start a game early', async () => {
    const { sent } = mockApi({
      'GET /judge/matches?court=1': board(match(), [], { now: '2026-12-12T12:45:00Z' }),
      'POST /judge/matches/1/start': match({ status: 'in_progress' }),
    })
    const user = userEvent.setup()
    renderAt('/judge?court=1', ADMIN)
    expect(await screen.findByRole('timer')).toHaveTextContent('Starts in 2h 15m')
    await user.click(screen.getByRole('button', { name: 'Start early (admin)' }))
    expect(await screen.findByLabelText('Time left')).toBeInTheDocument()
    await waitFor(() => expect(sent('POST', '/judge/matches/1/start')[0]?.body).toEqual({ early: true }))
  })

  it('holds the game while a team is still playing on another court', async () => {
    mockApi({ 'GET /judge/matches?court=1': board(match(), [], { waiting: 'Dink Squad is still playing on court 4' }) })
    renderAt('/judge', JUDGE)
    expect(await screen.findByRole('status')).toHaveTextContent('Dink Squad is still playing on court 4')
    expect(screen.getByRole('button', { name: 'Start game' })).toBeDisabled()
  })

  it('puts the Start button back when the server refuses the start', async () => {
    mockApi({
      'GET /judge/matches?court=1': board(),
      'POST /judge/matches/1/start': fail(409, 'Net Ninjas is still playing on court 4'),
    })
    const user = userEvent.setup()
    renderAt('/judge', JUDGE)
    await user.click(await screen.findByRole('button', { name: 'Start game' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Net Ninjas is still playing on court 4')
    expect(await screen.findByRole('button', { name: 'Start game' })).toBeEnabled()
    expect(screen.queryByLabelText('Time left')).not.toBeInTheDocument()
  })

  it('formats the wait before a game', () => {
    expect(untilStart(65)).toBe('1:05')
    expect(untilStart(3 * 3600 + 120)).toBe('3h 2m')
  })

  it('lets a floating judge or admin pick a court', async () => {
    mockApi({
      'GET /judge/matches': { court: null, current: null, matches: [] },
      'GET /judge/matches?court=4': { court: 4, current: null, matches: [] },
    })
    const user = userEvent.setup()
    renderAt('/judge', ADMIN)
    expect(await screen.findByText(/No game is ready/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Court'), '4')
    expect(await screen.findByRole('heading', { name: 'Court 4' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Court'), '')
    expect(await screen.findByRole('heading', { name: 'Judge' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Staff login' })).toBeInTheDocument()
  })
})
