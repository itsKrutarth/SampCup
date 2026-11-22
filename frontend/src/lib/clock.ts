import { createContext, useContext, useEffect, useState } from 'react'

/** A mock run's fast clock, as the server sends it; null outside a mock run. */
export type MockClock = { started_at: string; day_start: string; speed: number }

/** Set by the page layout from the public overview, so every page shows the same time. */
export const MockClockContext = createContext<MockClock | null>(null)

/** The tournament's time (ms) at a real time (ms): the same, or the mock run's fast clock. */
export function venueNow(realMs: number, mock: MockClock | null): number {
  if (!mock) return realMs
  return Date.parse(mock.day_start) + (realMs - Date.parse(mock.started_at)) * mock.speed
}

/** The current time (ms), refreshed every `everyMs`. */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs)
    return () => clearInterval(id)
  }, [everyMs])
  return now
}

/** The tournament's current time (ms): real time, or the mock clock during a mock run. */
export function useVenueNow(everyMs = 1000): number {
  return venueNow(useNow(everyMs), useContext(MockClockContext))
}
