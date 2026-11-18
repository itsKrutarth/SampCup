/** The SAMP Cup crest, in the flyer's style: crossed paddles, a gold ball and a navy shield
 * with the red ribbon. */
export default function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <g stroke="#060f24" strokeWidth="2.2" strokeLinejoin="round">
        <rect x="6" y="5" width="21" height="27" rx="7" transform="rotate(-24 16.5 18.5)" fill="#a33c22" />
        <rect x="35" y="4" width="21" height="27" rx="7" transform="rotate(22 45.5 17.5)" fill="#f4ead2" />
        <circle cx="49" cy="24" r="8" fill="#e8b22e" />
        <path d="M13 27h38v10c0 12-9 19-19 23-10-4-19-11-19-23z" fill="#102349" />
      </g>
      <g fill="#060f24">
        <circle cx="45" cy="20.5" r="1.3" />
        <circle cx="50.5" cy="19.5" r="1.3" />
        <circle cx="53.5" cy="24.5" r="1.3" />
        <circle cx="47.5" cy="25" r="1.3" />
        <circle cx="50" cy="29.5" r="1.3" />
      </g>
      <path d="M22 29a10 10 0 0 1 20 0z" fill="#d8283c" />
      <path d="M7 38h50l-3 4 3 4H7l3-4z" fill="#d8283c" stroke="#060f24" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M18 31.5h28" stroke="#f4ead2" strokeWidth="2.6" strokeLinecap="round" />
      <path d="M24 51h16" stroke="#f4ead2" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
    </svg>
  )
}
