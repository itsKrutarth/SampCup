import { Clock } from 'lucide-react'
import { useContext } from 'react'

import { MockClockContext, useVenueNow } from '../lib/clock'
import { time } from '../lib/format'

/**
 * The time at the venue, small in the header, so phones, courts and the schedule agree.
 * During a mock run it shows the mock's fast clock instead, marked "Mock".
 */
export default function VenueClock() {
  const mock = useContext(MockClockContext)
  const now = new Date(useVenueNow())
  const [hm, period] = time(now.toISOString()).split(/\s/)
  return (
    <time
      className={mock ? 'venue-clock mock' : 'venue-clock'}
      dateTime={now.toISOString()}
      title={mock ? `Mock tournament time (${mock.speed}x speed)` : 'Time at the venue'}
    >
      <Clock size={15} aria-hidden="true" />
      {mock && <em>Mock</em>}
      <span>{hm}</span>
      <small>{period}</small>
    </time>
  )
}
