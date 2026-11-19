export type TeamBrief = { id: number; name: string; number: number | null; group: string | null }

export type Match = {
  id: number
  code: string
  phase: 'group' | 'knockout'
  group: string | null
  round: string
  court: number
  scheduled_at: string
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled'
  team_a: TeamBrief | null
  team_b: TeamBrief | null
  source_a: string | null
  source_b: string | null
  score_a: number | null
  score_b: number | null
  end_reason: string | null
  seconds: number | null
  winner_id: number | null
  started_at: string | null
  ended_at: string | null
  prereqs: string[]
  version: number
  warnings?: string[]
}

export type Announcement = { id: number; title: string; body: string; active: boolean; created_at: string }

export type Overview = {
  tournament: {
    name: string
    subtitle: string
    venue_name: string
    venue_address: string
    age_group: string
    contacts: string
    event_date: string | null
    timezone: string
    registration_open: boolean
    team_cap: number
  }
  phase: 'registration' | 'scheduled' | 'group_play' | 'knockout' | 'finished'
  teams: number
  waitlist: number
  announcements: Announcement[]
  live: Match[]
  upcoming: Match[]
  /** Each court's game now, else its next one; courts with nothing left are missing. */
  courts: CourtGame[]
  champion: TeamBrief | null
}

export type CourtGame = { court: number; match: Match }

export type StandingRow = {
  rank: number
  team_id: number
  team_number: number
  team_name: string
  played: number
  wins: number
  losses: number
  points_for: number
  points_against: number
  avg_seconds: number
  decided_by: string
}

export type GroupTable = { complete: boolean; played: number; total: number; rows: StandingRow[] }

export type TeamPage = TeamBrief & {
  center: string
  status: string
  lunch_start: string | null
  matches: Match[]
  next_match: Match | null
  standing: StandingRow | null
  players?: { id: number; name: string }[]
}

export type PlayerLite = {
  id: number
  first_name: string
  last_name: string
  center: string
  zone: string
  state?: 'free' | 'pending' | 'teamed'
  team_name?: string | null
}

export type PartnerRequest = {
  id: number
  team_name: string
  status: string
  from: PlayerLite
  to: PlayerLite
  created_at: string
}

export type TeamOut = TeamBrief & {
  center: string
  status: 'active' | 'waitlist' | 'withdrawn'
  lunch_start: string | null
  players: { id: number; name: string }[]
  checked_in?: boolean
}
