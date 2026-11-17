from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import Db
from app.api.serializers import announcement_out, match_out, team_brief
from app.models import Announcement, Match, Team
from app.services import events
from app.services.errors import NotFound
from app.services.scoring import champion_id
from app.services.standings import group_standings
from app.services.tournament import get_tournament

router = APIRouter(prefix="/public", tags=["public"])


def phase(db: Db) -> str:
    statuses = dict(
        db.execute(
            select(Match.phase, func.count())
            .where(Match.status != "scheduled")
            .group_by(Match.phase)
        ).all()
    )
    if not db.scalar(select(func.count()).select_from(Match)):
        return "registration"
    if champion_id(db):
        return "finished"
    if statuses.get("knockout"):
        return "knockout"
    return "group_play" if statuses.get("group") else "scheduled"


@router.get("/overview")
def overview(db: Db) -> dict[str, Any]:
    tournament = get_tournament(db)
    counts = dict(db.execute(select(Team.status, func.count()).group_by(Team.status)).all())
    live = db.scalars(
        select(Match).where(Match.status == "in_progress").order_by(Match.court)
    ).all()
    upcoming = db.scalars(
        select(Match)
        .where(Match.status == "scheduled", Match.team_a_id.is_not(None))
        .order_by(Match.scheduled_at, Match.court)
        .limit(9)
    ).all()
    champion = champion_id(db)
    banners = db.scalars(
        select(Announcement).where(Announcement.active).order_by(Announcement.id.desc())
    ).all()
    db.commit()
    return {
        "tournament": {
            "name": tournament.name,
            "event_date": tournament.event_date.isoformat() if tournament.event_date else None,
            "timezone": tournament.timezone,
            "registration_open": tournament.registration_open,
            "team_cap": tournament.team_cap,
        },
        "phase": phase(db),
        "teams": counts.get("active", 0),
        "waitlist": counts.get("waitlist", 0),
        "announcements": [announcement_out(a) for a in banners],
        "live": [match_out(m) for m in live],
        "upcoming": [match_out(m) for m in upcoming],
        "champion": team_brief(db.get(Team, champion)) if champion else None,
    }


@router.get("/schedule")
def schedule(
    db: Db, group: str | None = None, court: int | None = None, team: int | None = None
) -> list[dict[str, Any]]:
    query = select(Match).order_by(Match.scheduled_at, Match.court)
    if group:
        query = query.where(Match.group == group.upper())
    if court:
        query = query.where(Match.court == court)
    if team:
        team_id = db.scalar(select(Team.id).where(Team.team_number == team))
        query = query.where((Match.team_a_id == team_id) | (Match.team_b_id == team_id))
    return [match_out(m) for m in db.scalars(query)]


@router.get("/standings")
def standings(db: Db) -> dict[str, Any]:
    return {"groups": group_standings(db)}


@router.get("/bracket")
def bracket(db: Db) -> dict[str, Any]:
    matches = db.scalars(
        select(Match).where(Match.phase == "knockout").order_by(Match.scheduled_at, Match.court)
    ).all()
    champion = champion_id(db)
    return {
        "matches": [match_out(m) for m in matches],
        "champion": team_brief(db.get(Team, champion)) if champion else None,
    }


@router.get("/teams")
def teams(db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Team).where(Team.status == "active").order_by(Team.team_number, Team.name)
    ).all()
    return [{**(team_brief(t) or {}), "center": t.center} for t in rows]


def team_page(db: Db, team: Team) -> dict[str, Any]:
    matches = db.scalars(
        select(Match)
        .where((Match.team_a_id == team.id) | (Match.team_b_id == team.id))
        .order_by(Match.scheduled_at)
    ).all()
    table = group_standings(db).get(team.group or "", {"rows": []})
    standing = next((r for r in table["rows"] if r["team_id"] == team.id), None)
    upcoming = next((m for m in matches if m.status in ("scheduled", "in_progress")), None)
    return {
        **(team_brief(team) or {}),
        "center": team.center,
        "status": team.status,
        "lunch_start": team.lunch_start.isoformat() if team.lunch_start else None,
        "matches": [match_out(m) for m in matches],
        "next_match": match_out(upcoming) if upcoming else None,
        "standing": standing,
    }


@router.get("/teams/{number}")
def team_by_number(number: int, db: Db) -> dict[str, Any]:
    team = db.scalar(select(Team).where(Team.team_number == number))
    if team is None:
        raise NotFound("No team has that number")
    return team_page(db, team)


@router.get("/stream")
async def stream() -> StreamingResponse:
    queue = events.broadcaster.subscribe()

    async def body():
        try:
            async for chunk in events.event_stream(queue):
                yield chunk
        finally:
            events.broadcaster.unsubscribe(queue)

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
