import { Clock } from 'lucide-react'

import { useNow } from '../lib/clock'
import { time } from '../lib/format'

/** The time at the venue, small in the header, so phones, courts and the schedule agree. */
export default function VenueClock() {
  const now = new Date(useNow())
  const [hm, period] = time(now.toISOString()).split(/\s/)
  return (
    <time className="venue-clock" dateTime={now.toISOString()} title="Time at the venue">
      <Clock size={15} aria-hidden="true" />
      <span>{hm}</span>
      <small>{period}</small>
    </time>
  )
}
