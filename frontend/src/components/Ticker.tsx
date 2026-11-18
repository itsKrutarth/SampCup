import type { Match } from '../lib/types'

function line(m: Match): string {
  return `Court ${m.court} · ${m.team_a?.name ?? '?'} ${m.score_a ?? 0} - ${m.score_b ?? 0} ${m.team_b?.name ?? '?'}`
}

/** A broadcast-style strip of live scores that scrolls across the page. */
export default function Ticker({ matches }: { matches: Match[] }) {
  const items = matches.map((m) => (
    <span key={m.id} className="ticker-item">
      {line(m)}
    </span>
  ))
  return (
    <div className="ticker" role="marquee" aria-label="Live scores">
      <span className="ticker-label">
        <span className="live-dot" /> Live
      </span>
      <div className="ticker-track">
        <div className="ticker-move">
          {items}
          <span aria-hidden="true">{items}</span>
        </div>
      </div>
    </div>
  )
}
