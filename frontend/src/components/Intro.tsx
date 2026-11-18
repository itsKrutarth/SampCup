import { useEffect, useRef, useState } from 'react'

const SEEN = 'sampcup-intro-seen'
const LENGTH_MS = 2400

function shouldPlay(): boolean {
  try {
    if (sessionStorage.getItem(SEEN)) return false
  } catch {
    return false
  }
  return !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
}

/**
 * Opening animation, once per visit: a ball drops on a paddle, bounces once, is struck
 * toward the viewer and fills the screen, then dissolves into the page. Tap or Escape skips.
 */
export default function Intro() {
  const [playing, setPlaying] = useState(shouldPlay)
  const overlay = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!playing) return
    try {
      sessionStorage.setItem(SEEN, '1')
    } catch {
      // without storage it simply plays again next time
    }
    const stop = () => setPlaying(false)
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && stop()
    // only the overlay's own fade-out ends the intro, not the ball's or paddle's
    const node = overlay.current
    const onEnd = (event: Event) => event.target === node && stop()
    const timer = setTimeout(stop, LENGTH_MS + 200)
    window.addEventListener('keydown', onKey)
    node?.addEventListener('animationend', onEnd)
    return () => {
      clearTimeout(timer)
      window.removeEventListener('keydown', onKey)
      node?.removeEventListener('animationend', onEnd)
    }
  }, [playing])
  if (!playing) return null
  return (
    <div ref={overlay} className="intro" aria-hidden="true" data-testid="intro" onClick={() => setPlaying(false)}>
      <div className="intro-scene">
        <div className="intro-stage">
          <svg className="intro-paddle" viewBox="-70 -90 140 230" width="140" height="230">
            <rect x="-14" y="62" width="28" height="70" rx="9" fill="#14285a" />
            <path d="M-14 80h28M-14 96h28M-14 112h28" stroke="#0a1733" strokeWidth="4" />
            <rect x="-16" y="126" width="32" height="12" rx="6" fill="#e8b22e" />
            <rect x="-62" y="-86" width="124" height="156" rx="40" fill="#f4ead2" />
            <rect x="-56" y="-80" width="112" height="144" rx="35" fill="#a33c22" />
            <path d="M-40 -60q40 -18 80 0" stroke="#f4ead2" strokeOpacity="0.25" strokeWidth="6" fill="none" strokeLinecap="round" />
          </svg>
          <span className="intro-flash" />
          <span className="intro-trail intro-trail-1" />
          <span className="intro-trail intro-trail-2" />
          <div className="intro-ball-path">
            <div className="intro-ball">
              <span className="intro-holes" />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
