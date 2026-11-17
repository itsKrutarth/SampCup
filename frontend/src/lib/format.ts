export const TIME_ZONE = 'America/New_York'

const timeFormat = new Intl.DateTimeFormat('en-US', {
  hour: 'numeric',
  minute: '2-digit',
  timeZone: TIME_ZONE,
})

export function time(iso: string | null | undefined): string {
  return iso ? timeFormat.format(new Date(iso)) : ''
}

export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export function dateLong(isoDate: string | null | undefined): string {
  if (!isoDate) return 'Date to be announced'
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function offsetMinutes(utcMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).formatToParts(new Date(utcMs))
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
  return (Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute')) - utcMs) / 60000
}

/** "2026-12-12" + "14:30" at the venue -> ISO time in UTC. */
export function venueTimeToIso(isoDate: string, hhmm: string, timeZone = TIME_ZONE): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const [h, min] = hhmm.split(':').map(Number)
  const guess = Date.UTC(y, m - 1, d, h, min)
  return new Date(guess - offsetMinutes(guess, timeZone) * 60000).toISOString()
}
