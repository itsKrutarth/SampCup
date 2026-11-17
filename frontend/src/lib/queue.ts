import { api, ApiError } from './api'
import { load, save } from './storage'
import type { Match } from './types'

export type Action = 'start' | 'score' | 'finish' | 'forfeit'
export type Queued = { matchId: number; action: Action; body?: Record<string, unknown> }
type State = { pending: number; error: string | null; offline: boolean }

const KEY = 'sampcup-judge-queue'

/**
 * Judge actions wait here until the server confirms them, so a score tapped with no
 * signal is sent later, in order. Stored in the browser so a reload keeps them.
 */
export class ActionQueue {
  private items: Queued[] = load<Queued[]>(KEY, [])
  private listeners = new Set<() => void>()
  private sending = false
  private state: State = { pending: this.items.length, error: null, offline: false }
  token: string | null = null
  onSent: ((match: Match) => void) | null = null

  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  getState = () => this.state

  private update(change: Partial<State>) {
    save(KEY, this.items)
    this.state = { ...this.state, ...change, pending: this.items.length }
    this.listeners.forEach((listener) => listener())
  }

  push(item: Queued): Promise<void> {
    if (item.action === 'score') {
      // only the latest score of a game matters
      this.items = this.items.filter((q) => !(q.action === 'score' && q.matchId === item.matchId))
    }
    this.items.push(item)
    this.update({})
    return this.flush()
  }

  async flush(): Promise<void> {
    if (this.sending || !this.token) return
    this.sending = true
    try {
      while (this.items.length) {
        const item = this.items[0]
        try {
          const match = await api<Match>(`/judge/matches/${item.matchId}/${item.action}`, {
            method: 'POST',
            body: item.body,
            token: this.token,
          })
          this.items.shift()
          this.update({ error: null, offline: false })
          this.onSent?.(match)
        } catch (e) {
          const error = e as ApiError
          if (error.status === 0 || error.status === 401) {
            this.update({ offline: true, error: error.status === 0 ? 'No connection. Scores are saved and will send automatically.' : 'Log in again to send saved scores.' })
            return
          }
          this.items.shift() // the server refused it; keeping it would block the queue
          this.update({ error: error.message, offline: false })
        }
      }
    } finally {
      this.sending = false
    }
  }

  clear() {
    this.items = []
    this.update({ error: null, offline: false })
  }
}

export const judgeQueue = new ActionQueue()
