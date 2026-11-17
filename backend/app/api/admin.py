import csv
import io
from collections import Counter
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import Admin, Db
from app.api.serializers import (
    announcement_out,
    iso,
    match_out,
    player_out,
    request_out,
    staff_out,
    team_out,
)
from app.models import (
    Announcement,
    Delay,
    Match,
    PartnerRequest,
    Player,
    ScoreAudit,
    StaffUser,
    Team,
)
from app.services import auth, events, players, schedule, scoring, teams
from app.services.errors import NotFound, ServiceError
from app.services.tournament import get_tournament, schedule_exists

router = APIRouter(prefix="/admin", tags=["admin"])


def _publish(scope: str) -> None:
    events.broadcaster.publish("update", scope=scope)


class TournamentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    event_date: date | None = None
    registration_open: bool | None = None
    team_cap: int | None = Field(default=None, ge=32, le=42)


class TeamCreate(BaseModel):
    name: str = Field(max_length=60)
    password: str = Field(max_length=72)
    player_ids: list[int]
    status: str | None = None


class TeamPatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    status: str | None = None
    checked_in: bool | None = None
    player_ids: list[int] | None = None
    password: str | None = Field(default=None, max_length=72)


class Draw(BaseModel):
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)


class Lock(BaseModel):
    locked: bool


class CourtPatch(BaseModel):
    court: int


class Correction(BaseModel):
    score_a: int
    score_b: int
    end_reason: str
    seconds: int | None = Field(default=None, ge=0, le=3600)
    reason: str = Field(max_length=500)


class Reset(BaseModel):
    reason: str = Field(max_length=500)


class DelayIn(BaseModel):
    minutes: int
    from_time: datetime


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=2000)
    active: bool = True


class AnnouncementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class StaffIn(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=72)
    role: str
    display_name: str = Field(default="", max_length=80)
    court: int | None = None


class StaffPatch(BaseModel):
    court: int | None = None
    clear_court: bool = False
    active: bool | None = None
    password: str | None = Field(default=None, max_length=72)
    display_name: str | None = Field(default=None, max_length=80)


# ----------------------------------------------------------- tournament


@router.get("/summary")
def summary(_: Admin, db: Db) -> dict[str, Any]:
    tournament = get_tournament(db)
    active_players = db.scalars(select(Player).where(Player.active)).all()
    team_counts = dict(db.execute(select(Team.status, func.count()).group_by(Team.status)).all())
    checked_in = db.scalar(
        select(func.count()).select_from(Team).where(Team.status == "active", Team.checked_in)
    )
    pending = db.scalar(
        select(func.count()).select_from(PartnerRequest).where(PartnerRequest.status == "pending")
    )
    db.commit()
    return {
        "tournament": {
            "name": tournament.name,
            "event_date": tournament.event_date.isoformat() if tournament.event_date else None,
            "timezone": tournament.timezone,
            "registration_open": tournament.registration_open,
            "team_cap": tournament.team_cap,
            "draw_seed": tournament.draw_seed,
            "schedule_locked": tournament.schedule_locked,
            "schedule_exists": schedule_exists(db),
        },
        "players": len(active_players),
        "players_on_teams": sum(1 for p in active_players if p.team_id),
        "teams": {s: team_counts.get(s, 0) for s in ("active", "waitlist", "withdrawn")},
        "checked_in": checked_in,
        "pending_requests": pending,
        "tshirts": dict(sorted(Counter(p.tshirt_size or "?" for p in active_players).items())),
    }


@router.patch("/tournament")
def update_tournament(body: TournamentPatch, _: Admin, db: Db) -> dict[str, Any]:
    tournament = get_tournament(db)
    changes = body.model_dump(exclude_unset=True)
    if "event_date" in changes and schedule_exists(db):
        raise ServiceError("Clear the schedule before changing the date")
    for field, value in changes.items():
        if value is not None:
            setattr(tournament, field, value)
    db.commit()
    _publish("tournament")
    return summary(_, db)


# ------------------------------------------------------------- players


@router.post("/players/import")
async def import_players(file: UploadFile, _: Admin, db: Db) -> dict[str, Any]:
    content = await file.read(players.MAX_BYTES + 1)
    report = players.import_players(db, content)
    _publish("registration")
    return report


@router.get("/players")
def list_players(_: Admin, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(select(Player).order_by(Player.center, Player.first_name, Player.last_name))
    return [player_out(p, admin=True) for p in rows]


# --------------------------------------------------------------- teams


@router.get("/teams")
def list_teams(_: Admin, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(select(Team).order_by(Team.team_number, Team.created_at))
    return [team_out(t, admin=True) for t in rows]


@router.post("/teams", status_code=201)
def create_team(body: TeamCreate, _: Admin, db: Db) -> dict[str, Any]:
    team = teams.admin_create_team(db, body.name, body.password, body.player_ids, body.status)
    _publish("teams")
    return team_out(team, admin=True)


@router.patch("/teams/{team_id}")
def update_team(team_id: int, body: TeamPatch, _: Admin, db: Db) -> dict[str, Any]:
    team = teams.admin_update_team(db, team_id, **body.model_dump(exclude_unset=True))
    _publish("teams")
    return team_out(team, admin=True)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, _: Admin, db: Db) -> None:
    teams.admin_delete_team(db, team_id)
    _publish("teams")


@router.get("/requests")
def list_requests(_: Admin, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(PartnerRequest).where(PartnerRequest.status == "pending").order_by(PartnerRequest.id)
    )
    return [request_out(r) for r in rows]


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: int, _: Admin, db: Db) -> dict[str, Any]:
    out = request_out(teams.cancel_request(db, request_id, None))
    _publish("registration")
    return out


# ------------------------------------------------------------ schedule


@router.post("/draw")
def draw(body: Draw, _: Admin, db: Db) -> list[dict[str, Any]]:
    drawn = schedule.draw_numbers(db, body.seed)
    _publish("teams")
    return [team_out(t, admin=True) for t in drawn]


@router.post("/schedule")
def generate(_: Admin, db: Db) -> dict[str, int]:
    count = schedule.generate_schedule(db)
    _publish("schedule")
    return {"matches": count}


@router.delete("/schedule", status_code=204)
def clear(_: Admin, db: Db) -> None:
    schedule.clear_schedule(db)
    _publish("schedule")


@router.post("/schedule/lock")
def lock(body: Lock, _: Admin, db: Db) -> dict[str, bool]:
    schedule.set_locked(db, body.locked)
    return {"locked": body.locked}


@router.patch("/matches/{match_id}")
def move_court(match_id: int, body: CourtPatch, _: Admin, db: Db) -> dict[str, Any]:
    match = schedule.set_court(db, match_id, body.court)
    _publish("schedule")
    return match_out(match)


@router.post("/matches/{match_id}/correct")
def correct(match_id: int, body: Correction, user: Admin, db: Db) -> dict[str, Any]:
    match, warnings = scoring.correct_match(
        db, match_id, body.score_a, body.score_b, body.end_reason, body.seconds, body.reason, user
    )
    _publish("scores")
    return {**match_out(match), "warnings": warnings}


@router.post("/matches/{match_id}/reset")
def reset(match_id: int, body: Reset, user: Admin, db: Db) -> dict[str, Any]:
    match, warnings = scoring.reset_match(db, match_id, body.reason, user)
    _publish("scores")
    return {**match_out(match), "warnings": warnings}


@router.get("/delays")
def list_delays(_: Admin, db: Db) -> list[dict[str, Any]]:
    rows = db.scalars(select(Delay).order_by(Delay.id.desc()))
    return [
        {
            "id": d.id,
            "minutes": d.minutes,
            "applied_from": iso(d.applied_from),
            "matches_moved": d.matches_moved,
            "created_by": d.created_by,
            "created_at": iso(d.created_at),
        }
        for d in rows
    ]


@router.post("/delays")
def add_delay(body: DelayIn, user: Admin, db: Db) -> dict[str, object]:
    if body.from_time.tzinfo is None:
        raise ServiceError("from_time needs a timezone")
    result = schedule.apply_delay(db, body.minutes, body.from_time, user.username)
    _publish("schedule")
    return result


@router.get("/audit")
def audit(_: Admin, db: Db, limit: int = 200) -> list[dict[str, Any]]:
    rows = db.execute(
        select(ScoreAudit, Match.code)
        .join(Match, Match.id == ScoreAudit.match_id)
        .order_by(ScoreAudit.id.desc())
        .limit(min(limit, 1000))
    ).all()
    return [
        {
            "id": a.id,
            "match": code,
            "action": a.action,
            "old": a.old_values,
            "new": a.new_values,
            "by": a.changed_by,
            "reason": a.reason,
            "at": iso(a.changed_at),
        }
        for a, code in rows
    ]


# -------------------------------------------------------- announcements


@router.get("/announcements")
def list_announcements(_: Admin, db: Db) -> list[dict[str, Any]]:
    return [
        announcement_out(a)
        for a in db.scalars(select(Announcement).order_by(Announcement.id.desc()))
    ]


@router.post("/announcements", status_code=201)
def add_announcement(body: AnnouncementIn, user: Admin, db: Db) -> dict[str, Any]:
    item = Announcement(**body.model_dump(), created_by=user.username)
    db.add(item)
    db.commit()
    _publish("announcements")
    return announcement_out(item)


def _announcement(db: Db, item_id: int) -> Announcement:
    item = db.get(Announcement, item_id)
    if item is None:
        raise NotFound("Announcement not found")
    return item


@router.patch("/announcements/{item_id}")
def edit_announcement(item_id: int, body: AnnouncementPatch, _: Admin, db: Db) -> dict[str, Any]:
    item = _announcement(db, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, field, value)
    db.commit()
    _publish("announcements")
    return announcement_out(item)


@router.delete("/announcements/{item_id}", status_code=204)
def delete_announcement(item_id: int, _: Admin, db: Db) -> None:
    db.delete(_announcement(db, item_id))
    db.commit()
    _publish("announcements")


# ---------------------------------------------------------------- staff


@router.get("/staff")
def list_staff(_: Admin, db: Db) -> list[dict[str, Any]]:
    return [staff_out(u) for u in db.scalars(select(StaffUser).order_by(StaffUser.username))]


@router.post("/staff", status_code=201)
def add_staff(body: StaffIn, _: Admin, db: Db) -> dict[str, Any]:
    return staff_out(auth.create_staff(db, **body.model_dump()))


@router.patch("/staff/{user_id}")
def edit_staff(user_id: int, body: StaffPatch, user: Admin, db: Db) -> dict[str, Any]:
    if user_id == user.id and body.active is False:
        raise ServiceError("You cannot deactivate yourself")
    return staff_out(auth.update_staff(db, user_id, **body.model_dump(exclude_unset=True)))


# --------------------------------------------------------------- export


def _csv(rows: list[list[Any]], name: str) -> Response:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/export/results.csv")
def export_results(_: Admin, db: Db) -> Response:
    rows: list[list[Any]] = [
        [
            "code",
            "round",
            "time_utc",
            "court",
            "team_a",
            "team_b",
            "score_a",
            "score_b",
            "end_reason",
            "seconds",
            "status",
        ]
    ]
    for m in db.scalars(select(Match).order_by(Match.scheduled_at, Match.court)):
        rows.append(
            [
                m.code,
                m.round_label,
                iso(m.scheduled_at),
                m.court,
                m.team_a.name if m.team_a else "",
                m.team_b.name if m.team_b else "",
                m.score_a,
                m.score_b,
                m.end_reason,
                m.seconds,
                m.status,
            ]
        )
    return _csv(rows, "sampcup-results.csv")
