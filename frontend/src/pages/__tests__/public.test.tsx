import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { groups, match, overview, team, teamPage } from '../../test/data'
import { ADMIN, fail, JUDGE, mockApi, PLAYER, renderAt } from '../../test/utils'

describe('home page', () => {
  it('invites players to join while registration is open', async () => {
    mockApi({ 'GET /public/overview': overview({ waitlist: 2 }) })
    renderAt('/')
    expect(await screen.findByRole('heading', { name: 'SAMP Cup 2026' })).toBeInTheDocument()
    expect(screen.getByText('December 12')).toBeInTheDocument()
    expect(screen.getByText('Saturday · Age 22-35')).toBeInTheDocument()
    expect(screen.getByText('Yuvak Mandal')).toBeInTheDocument()
    expect(screen.getByText('Pickleball Tournament')).toBeInTheDocument()
    expect(screen.getByText('Rt. 12 Pickle')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Directions' })).toHaveAttribute(
      'href',
      expect.stringContaining('184%20W.%20Boylston%20St'),
    )
    expect(screen.getByText(/Registered on the MySatsang app/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Questions')).not.toBeInTheDocument()
    const glance = screen.getByRole('list', { name: 'At a glance' })
    expect(within(glance).getByText('Knockout spots')).toBeInTheDocument()
    expect(screen.queryByText(/teams formed/)).not.toBeInTheDocument() // only staff see counts
    expect(screen.getByRole('img', { name: 'Bhagwan Swaminarayan' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /BAPS Swaminarayan Sanstha/ })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Courts' })).not.toBeInTheDocument()
    expect(screen.getByRole('timer', { name: 'Countdown to the first serve' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create your account' })).toHaveAttribute('href', '/join')
  })

  it('shows live games, what is next, banners and the champion', async () => {
    mockApi({
      'GET /public/overview': overview({
        phase: 'finished',
        tournament: { ...overview().tournament, contacts: 'Organizer (555) 010-0100' },
        announcements: [{ id: 1, title: 'Awards at 6:45', body: 'Main hall', active: true, created_at: '' }],
        live: [match({ id: 5, status: 'in_progress', score_a: 4, score_b: 2 })],
        upcoming: [match({ id: 6, code: 'R16-1', phase: 'knockout', round: 'Round of 16', team_a: null, source_a: 'Group A 1st' })],
        champion: team(1, 'Net Ninjas'),
      }),
    })
    renderAt('/')
    expect(await screen.findByText('Tournament complete')).toBeInTheDocument()
    const banner = await screen.findByRole('region', { name: 'Announcements' })
    expect(within(banner).getByText('Awards at 6:45')).toBeInTheDocument()
    expect(screen.getByText('Champions')).toBeInTheDocument()
    expect(screen.queryByRole('timer')).not.toBeInTheDocument()
    expect(screen.getByText('Organizer (555) 010-0100')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Up next' })).getByText('Group A 1st')).toBeInTheDocument()
  })

  it('shows a live ticker, every court and the leaderboard during play', async () => {
    mockApi({
      'GET /public/overview': overview({
        phase: 'group_play',
        live: [match({ id: 5, status: 'in_progress', score_a: 4, score_b: 2 })],
        upcoming: [
          match({ id: 6, court: 2 }),
          match({ id: 7, code: 'R16-1', phase: 'knockout', group: null, round: 'Round of 16', court: 3, team_a: null, team_b: null, source_a: 'Group A 1st', source_b: 'Group B 4th' }),
        ],
      }),
      'GET /public/standings': { groups },
    })
    renderAt('/')
    expect(await screen.findByRole('marquee', { name: 'Live scores' })).toHaveTextContent('Court 1 · Net Ninjas 4 - 2 Dink Squad')
    const court1 = screen.getByRole('article', { name: 'Court 1' })
    expect(within(court1).getByText('Live')).toBeInTheDocument()
    expect(within(court1).getByText('4')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Court 2' })).getByText('Next')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Court 3' })).getByText('Group B 4th')).toBeInTheDocument()
    expect(within(screen.getByRole('article', { name: 'Court 9' })).getByText('Free')).toBeInTheDocument()
    const board = await screen.findByRole('region', { name: 'Leaderboard' })
    expect(within(board).getByText('2-0')).toBeInTheDocument()
    expect(within(board).getByRole('heading', { name: 'Group A' })).toBeInTheDocument()
  })

  it('shows an error when the server is down', async () => {
    mockApi({ 'GET /public/overview': fail(500, 'Server error') })
    renderAt('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('Server error')
  })
})

describe('navigation', () => {
  it.each([
    [undefined, 'Join', '/join'],
    [PLAYER, 'My team', '/my-team'],
    [JUDGE, 'Judge', '/judge'],
    [ADMIN, 'Admin', '/admin'],
  ])('links to the right account page', async (auth, label, href) => {
    mockApi({})
    renderAt('/nowhere', auth)
    expect(screen.getByText('Page not found.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href)
  })
})

describe('schedule page', () => {
  it('filters by group, court and team number', async () => {
    const { calls } = mockApi({
      'GET /public/schedule': [match()],
      'GET /public/schedule?group=B': [],
      'GET /public/schedule?group=B&court=3': [],
      'GET /public/schedule?group=B&court=3&team=7': [match({ id: 9 })],
    })
    const user = userEvent.setup()
    renderAt('/schedule')
    expect(await screen.findByText('Net Ninjas')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '10:00 AM' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Group B' }))
    expect(screen.getByRole('button', { name: 'Group B' })).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByText(/No games yet/)).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Court'), '3')
    await user.type(screen.getByLabelText('Team #'), '7x')
    await waitFor(() => expect(calls.at(-1)?.path).toBe('/public/schedule?group=B&court=3&team=7'))
    await user.click(screen.getByRole('button', { name: 'All groups' }))
    await waitFor(() => expect(calls.at(-1)?.path).toBe('/public/schedule?court=3&team=7'))
  })
})

describe('standings and bracket', () => {
  it('shows each group with how ties were placed', async () => {
    mockApi({ 'GET /public/standings': { groups } })
    renderAt('/standings')
    const table = await screen.findByRole('region', { name: 'Group A' })
    expect(within(table).getByText('3 of 40 games played')).toBeInTheDocument()
    expect(within(table).getByText('wins')).toBeInTheDocument()
  })

  it('explains empty standings and an empty bracket', async () => {
    mockApi({ 'GET /public/standings': { groups: { B: { ...groups.A, complete: true } } }, 'GET /public/bracket': { matches: [], champion: null } })
    renderAt('/standings')
    expect(await screen.findByText('Complete')).toBeInTheDocument()
    mockApi({ 'GET /public/standings': { groups: {} }, 'GET /public/bracket': { matches: [], champion: null } })
    renderAt('/bracket')
    expect(await screen.findByText(/fills in after group play/)).toBeInTheDocument()
  })

  it('lays the knockout out by round', async () => {
    mockApi({
      'GET /public/bracket': {
        matches: [
          match({ id: 1, code: 'R16-1', phase: 'knockout', round: 'Round of 16' }),
          match({ id: 2, code: 'F-1', phase: 'knockout', round: 'Final game 1', status: 'completed', score_a: 11, score_b: 5, winner_id: 1 }),
          match({ id: 3, code: 'F-3', phase: 'knockout', round: 'Final game 3 (if needed)', status: 'cancelled' }),
        ],
        champion: team(1, 'Net Ninjas'),
      },
    })
    renderAt('/bracket')
    const final = await screen.findByRole('region', { name: 'Final (best of 3)' })
    expect(within(final).getByText('Not needed')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Round of 16' })).getByText('Court 1')).toBeInTheDocument()
    expect(screen.getByText('Champions')).toBeInTheDocument()
  })
})

describe('team page and projector', () => {
  it('shows a team with lunch, rank and next game', async () => {
    mockApi({ 'GET /public/teams/1': teamPage() })
    renderAt('/teams/1')
    expect(await screen.findByRole('heading', { name: 'Net Ninjas' })).toBeInTheDocument()
    expect(screen.getByText('Team #1 · Group A')).toBeInTheDocument()
    expect(screen.getByText('12:50 PM, 51 min')).toBeInTheDocument()
    expect(screen.getByText('1st · 2-0')).toBeInTheDocument()
    expect(screen.getByText('6:40')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Next game' })).toBeInTheDocument()
  })

  it('shows a waitlisted team before the draw', async () => {
    mockApi({ 'GET /public/teams/2': teamPage({ number: null, group: null, status: 'waitlist', lunch_start: null, standing: null, next_match: null, matches: [] }) })
    renderAt('/teams/2')
    expect(await screen.findByText('On the waitlist')).toBeInTheDocument()
    expect(screen.getByText(/appear here after the draw/)).toBeInTheDocument()
  })

  it('shows a withdrawn team and a missing team', async () => {
    mockApi({ 'GET /public/teams/3': teamPage({ status: 'withdrawn' }), 'GET /public/teams/9': fail(404, 'No team has that number') })
    renderAt('/teams/3')
    expect(await screen.findByText('Withdrawn')).toBeInTheDocument()
    renderAt('/teams/9')
    expect(await screen.findByText('No team has that number')).toBeInTheDocument()
  })

  it('projector shows live courts and standings without menus', async () => {
    mockApi({
      'GET /public/overview': overview({ live: [match({ status: 'in_progress' })], upcoming: [match({ id: 2 })], champion: team(2, 'Dink Squad') }),
      'GET /public/standings': { groups },
    })
    renderAt('/display')
    expect(await screen.findByRole('heading', { name: 'SAMP Cup 2026' })).toBeInTheDocument()
    expect(await screen.findByRole('region', { name: 'Group A' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    expect(within(screen.getByRole('status')).getByText('Dink Squad')).toBeInTheDocument()
  })
})
