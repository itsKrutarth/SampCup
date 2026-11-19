import { useNow } from '../lib/clock'
import { venueTimeToIso } from '../lib/format'

/** Days, hours, minutes and seconds to the first serve; nothing once it has started. */
export default function Countdown({ eventDate }: { eventDate: string }) {
  const now = useNow()
  const left = Math.floor((Date.parse(venueTimeToIso(eventDate, '10:00')) - now) / 1000)
  if (left <= 0) return null
  const parts = [
    [Math.floor(left / 86400), 'days'],
    [Math.floor((left % 86400) / 3600), 'hours'],
    [Math.floor((left % 3600) / 60), 'min'],
    [left % 60, 'sec'],
  ] as const
  return (
    <div className="countdown" role="timer" aria-label="Countdown to the first serve">
      {parts.map(([value, unit]) => (
        <div key={unit}>
          <strong>{String(value).padStart(2, '0')}</strong>
          <span>{unit}</span>
        </div>
      ))}
    </div>
  )
}
