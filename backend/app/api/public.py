"""Read-only pages for everyone. CloudFront caches these for a few seconds."""

from typing import Any

from fastapi import APIRouter

from app.api.deps import Db
from app.api.serializers import Lookup, announcement_out, team_brief
from app.models import Announcement, Match, Team
from app.services.errors import NotFound
from app.services.scoring import champion_id
from app.services.standings import group_standings
from app.services.tournament import get_tournament
from app.store import Store

router = APIRouter(prefix="/public", tags=["public"])


def ordered(matches: list[Match]) -> list[Match]:
    return sorted(matches, key=lambda m: (m.scheduled_at, m.court))


def phase(matches: list[Match], champion: int | None) -> str:
    if not matches:
        return "registration"
    if champion:
        return "finished"
    started = {m.phase for m in matches if m.status != "scheduled"}
    if "knockout" in started:
        return "knockout"
    return "group_play" if "group" in started else "scheduled"


@router.get("/overview")
def overview(store: Db) -> dict[str, Any]:
    tournament = get_tournament(store)
    look = Lookup(store)
    matches = ordered(store.all(Match))
    champion = champion_id(store, matches)
    statuses = [t.status for t in look.teams.values()]
    banners = [a for a in store.all(Announcement) if a.active]
    upcoming = [m for m in matches if m.status == "scheduled" and m.team_a_id][:9]
    return {
        "tournament": {
            "name": tournament.name,
            "subtitle": tournament.subtitle,
            "venue_name": tournament.venue_name,
            "venue_address": tournament.venue_address,
            "age_group": tournament.age_group,
            "contacts": tournament.contacts,
            "event_date": tournament.event_date.isoformat() if tournament.event_date else None,
            "timezone": tournament.timezone,
            "registration_open": tournament.registration_open,
            "team_cap": tournament.team_cap,
        },
        "phase": phase(matches, champion),
        "teams": statuses.count("active"),
        "waitlist": statuses.count("waitlist"),
        "announcements": [announcement_out(a) for a in reversed(banners)],
        "live": [
            look.match(m)
            for m in sorted(matches, key=lambda m: m.court)
            if m.status == "in_progress"
        ],
        "upcoming": [look.match(m) for m in upcoming],
        "champion": team_brief(look.team_of(champion)),
    }


@router.get("/schedule")
def schedule(
    store: Db, group: str | None = None, court: int | None = None, team: int | None = None
) -> list[dict[str, Any]]:
    look = Lookup(store)
    matches = ordered(store.all(Match))
    if group:
        matches = [m for m in matches if m.group == group.upper()]
    if court:
        matches = [m for m in matches if m.court == court]
    if team:
        team_id = next((t.id for t in look.teams.values() if t.team_number == team), None)
        matches = [m for m in matches if team_id in (m.team_a_id, m.team_b_id)]
    return [look.match(m) for m in matches]


@router.get("/standings")
def standings(store: Db) -> dict[str, Any]:
    return {"groups": group_standings(store)}


@router.get("/bracket")
def bracket(store: Db) -> dict[str, Any]:
    look = Lookup(store)
    matches = ordered(store.all(Match))
    return {
        "matches": [look.match(m) for m in matches if m.phase == "knockout"],
        "champion": team_brief(look.team_of(champion_id(store, matches))),
    }


@router.get("/teams")
def teams(store: Db) -> list[dict[str, Any]]:
    rows = sorted(
        (t for t in store.all(Team) if t.status == "active"),
        key=lambda t: (t.team_number is None, t.team_number or 0, t.name),
    )
    return [{**(team_brief(t) or {}), "center": t.center} for t in rows]


def team_page(store: Store, team: Team) -> dict[str, Any]:
    look = Lookup(store)
    all_matches = store.all(Match)
    matches = ordered([m for m in all_matches if team.id in (m.team_a_id, m.team_b_id)])
    table = group_standings(store, list(look.teams.values()), all_matches).get(
        team.group or "", {"rows": []}
    )
    standing = next((r for r in table["rows"] if r["team_id"] == team.id), None)
    upcoming = next((m for m in matches if m.status in ("scheduled", "in_progress")), None)
    return {
        **(team_brief(team) or {}),
        "center": team.center,
        "status": team.status,
        "lunch_start": team.lunch_start.isoformat() if team.lunch_start else None,
        "matches": [look.match(m) for m in matches],
        "next_match": look.match(upcoming) if upcoming else None,
        "standing": standing,
    }


@router.get("/teams/{number}")
def team_by_number(number: int, store: Db) -> dict[str, Any]:
    team = next((t for t in store.all(Team) if t.team_number == number), None)
    if team is None:
        raise NotFound("No team has that number")
    return team_page(store, team)
