import { useId } from 'react'

/** The SAMP Cup crest: a pickleball held by two arcs that meet ("Samp" means unity). */
export default function Logo({ size = 40 }: { size?: number }) {
  const id = useId()
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff7a1a" />
          <stop offset="1" stopColor="#e8336d" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="60" height="60" rx="18" fill={`url(#${id})`} />
      <path d="M13 41c3-13 13-22 27-23" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" fill="none" />
      <path d="M51 23c-3 13-13 22-27 23" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" fill="none" opacity="0.85" />
      <circle cx="32" cy="32" r="11.5" fill="#c6f135" stroke="#0b1020" strokeOpacity="0.15" />
      <g fill="#0b1020" fillOpacity="0.22">
        <circle cx="28" cy="27.5" r="1.8" />
        <circle cx="35.5" cy="27" r="1.8" />
        <circle cx="38" cy="33.5" r="1.8" />
        <circle cx="32" cy="37.5" r="1.8" />
        <circle cx="26" cy="34" r="1.8" />
        <circle cx="32" cy="31.5" r="1.4" />
      </g>
    </svg>
  )
}
