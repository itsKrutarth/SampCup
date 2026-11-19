import type { GroupTable, Match, Overview, TeamBrief, TeamPage } from '../lib/types'

export const team = (id: number, name = `Team ${id}`): TeamBrief => ({ id, name, number: id, group: 'A' })

export function match(overrides: Partial<Match> = {}): Match {
  return {
    id: 1,
    code: 'G001',
    phase: 'group',
    group: 'A',
    round: 'Group A',
    court: 1,
    scheduled_at: '2026-12-12T15:00:00+00:00',
    status: 'scheduled',
    team_a: team(1, 'Net Ninjas'),
    team_b: team(2, 'Dink Squad'),
    source_a: null,
    source_b: null,
    score_a: null,
    score_b: null,
    end_reason: null,
    seconds: null,
    winner_id: null,
    started_at: null,
    ended_at: null,
    prereqs: [],
    version: 1,
    ...overrides,
  }
}

export function overview(overrides: Partial<Overview> = {}): Overview {
  return {
    tournament: {
      name: 'SAMP Cup 2026',
      subtitle: 'Yuvak Mandal',
      venue_name: 'Rt. 12 Pickle',
      venue_address: '184 W. Boylston St, West Boylston, MA 01583',
      age_group: '22-35',
      contacts: '',
      event_date: '2026-12-12',
      timezone: 'America/New_York',
      registration_open: true,
      team_cap: 42,
    },
    phase: 'registration',
    teams: 12,
    waitlist: 0,
    announcements: [],
    live: [],
    upcoming: [],
    courts: [],
    champion: null,
    ...overrides,
  }
}

export const groups: Record<string, GroupTable> = {
  A: {
    complete: false,
    played: 3,
    total: 40,
    rows: [
      { rank: 1, team_id: 1, team_number: 1, team_name: 'Net Ninjas', played: 2, wins: 2, losses: 0, points_for: 22, points_against: 9, avg_seconds: 400, decided_by: '' },
      { rank: 2, team_id: 2, team_number: 2, team_name: 'Dink Squad', played: 2, wins: 1, losses: 1, points_for: 18, points_against: 15, avg_seconds: 500, decided_by: 'wins' },
    ],
  },
}

export function teamPage(overrides: Partial<TeamPage> = {}): TeamPage {
  return {
    ...team(1, 'Net Ninjas'),
    center: 'North',
    status: 'active',
    lunch_start: '2026-12-12T17:50:00+00:00',
    matches: [match()],
    next_match: match(),
    standing: groups.A.rows[0],
    ...overrides,
  }
}
