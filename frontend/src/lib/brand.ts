import type { CSSProperties } from 'react'

const GROUP_COLORS: Record<string, string> = {
  A: 'var(--group-a)',
  B: 'var(--group-b)',
  C: 'var(--group-c)',
  D: 'var(--group-d)',
}

/** Inline style that sets the --accent color for a group (knockout games use the brand gradient). */
export function accent(group: string | null | undefined, knockout = false): CSSProperties | undefined {
  const color = group ? GROUP_COLORS[group] : knockout ? 'var(--gradient)' : undefined
  return color ? ({ '--accent': color } as CSSProperties) : undefined
}

export const TAGLINE = 'Unity in every rally'

/** The day plan from the tournament rules (venue time). */
export const DAY_PLAN = [
  ['9:00 AM', 'Breakfast and check-in'],
  ['9:45 AM', 'Aarti'],
  ['10:00 AM', 'First serve: group play on 9 courts'],
  ['12-2 PM', 'Rolling lunch (each team gets a 51-minute break)'],
  ['3:30 PM', 'Sabha'],
  ['4:30 PM', 'Round of 16, quarterfinals, semifinals'],
  ['5:55 PM', 'Best-of-3 Final on court 1'],
  ['7:00 PM', 'Wrap-up'],
] as const
