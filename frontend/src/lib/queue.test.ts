import { describe, expect, it, vi } from 'vitest'

import { fail, mockApi } from '../test/utils'
import { match } from '../test/data'
import { ActionQueue } from './queue'

describe('judge action queue', () => {
  it('sends actions in order and reports each confirmed game', async () => {
    const { calls } = mockApi({
      'POST /judge/matches/1/start': match({ status: 'in_progress' }),
      'POST /judge/matches/1/score': match({ status: 'in_progress', score_a: 2 }),
    })
    const queue = new ActionQueue()
    const sent = vi.fn()
    queue.onSent = sent
    queue.token = 'tok'
    await queue.push({ matchId: 1, action: 'start' })
    await queue.push({ matchId: 1, action: 'score', body: { score_a: 2, score_b: 0 } })
    expect(calls.map((c) => c.path)).toEqual(['/judge/matches/1/start', '/judge/matches/1/score'])
    expect(sent).toHaveBeenCalledTimes(2)
    expect(queue.getState()).toEqual({ pending: 0, error: null, offline: false })
  })

  it('keeps actions while offline, keeps only the latest score, and resumes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')))
    const queue = new ActionQueue()
    const listener = vi.fn()
    queue.subscribe(listener)
    await queue.push({ matchId: 1, action: 'score', body: { score_a: 1, score_b: 0 } })
    expect(queue.getState().pending).toBe(1) // no token yet: nothing sent
    queue.token = 'tok'
    await queue.push({ matchId: 1, action: 'score', body: { score_a: 2, score_b: 0 } })
    expect(queue.getState()).toMatchObject({ pending: 1, offline: true })
    expect(queue.getState().error).toMatch(/No connection/)
    expect(new ActionQueue().getState().pending).toBe(1) // saved in the browser
    const { calls } = mockApi({ 'POST /judge/matches/1/score': match() })
    await queue.flush()
    expect(calls[0].body).toEqual({ score_a: 2, score_b: 0 })
    expect(queue.getState().pending).toBe(0)
    expect(listener).toHaveBeenCalled()
  })

  it('drops an action the server refuses, and waits on an expired login', async () => {
    mockApi({
      'POST /judge/matches/1/finish': fail(409, 'This game is already final'),
      'POST /judge/matches/2/start': fail(401, 'expired'),
    })
    const queue = new ActionQueue()
    queue.token = 'tok'
    await queue.push({ matchId: 1, action: 'finish' })
    expect(queue.getState()).toMatchObject({ pending: 0, error: 'This game is already final' })
    await queue.push({ matchId: 2, action: 'start' })
    expect(queue.getState()).toMatchObject({ pending: 1, error: 'Log in again to send saved scores.' })
    queue.clear()
    expect(queue.getState().pending).toBe(0)
  })
})
