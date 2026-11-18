import csv
import io
from collections import Counter
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import Admin, Db
from app.api.public import ordered
from app.api.serializers import Lookup, announcement_out, iso, staff_out
from app.models import Announcement, Delay, Match, PartnerRequest, ScoreAudit, StaffUser
from app.services import accounts, auth, players, schedule, scoring, teams
from app.services.errors import NotFound, ServiceError
from app.services.tournament import get_tournament, schedule_exists

router = APIRouter(prefix="/admin", tags=["admin"])


class TournamentPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    subtitle: str | None = Field(default=None, max_length=80)
    venue_name: str | None = Field(default=None, max_length=80)
    venue_address: str | None = Field(default=None, max_length=160)
    age_group: str | None = Field(default=None, max_length=20)
    contacts: str | None = Field(default=None, max_length=500)
    event_date: date | None = None
    registration_open: bool | None = None
    team_cap: int | None = Field(default=None, ge=32, le=42)


class TeamCreate(BaseModel):
    name: str = Field(max_length=60)
    player_ids: list[int]
    status: str | None = None


class TeamPatch(BaseModel):
    name: str | None = Field(default=None, max_length=60)
    status: str | None = None
    checked_in: bool | None = None
    player_ids: list[int] | None = None


class PlayerLogin(BaseModel):
    username: str | None = Field(default=None, max_length=40)
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
    username: str | None = Field(default=None, max_length=40)
    court: int | None = None
    clear_court: bool = False
    active: bool | None = None
    password: str | None = Field(default=None, max_length=72)
    display_name: str | None = Field(default=None, max_length=80)


# ----------------------------------------------------------- tournament


@router.get("/summary")
def summary(_: Admin, store: Db) -> dict[str, Any]:
    tournament = get_tournament(store)
    look = Lookup(store)
    active_players = [p for p in look.players.values() if p.active]
    statuses = Counter(t.status for t in look.teams.values())
    pending = sum(r.status == "pending" for r in store.all(PartnerRequest))
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
            "draw_seed": tournament.draw_seed,
            "schedule_locked": tournament.schedule_locked,
            "schedule_exists": schedule_exists(store),
        },
        "players": len(active_players),
        "players_on_teams": sum(1 for p in active_players if p.team_id),
        "teams": {s: statuses.get(s, 0) for s in ("active", "waitlist", "withdrawn")},
        "checked_in": sum(t.status == "active" and t.checked_in for t in look.teams.values()),
        "pending_requests": pending,
        "tshirts": dict(sorted(Counter(p.tshirt_size or "?" for p in active_players).items())),
    }


@router.patch("/tournament")
def update_tournament(body: TournamentPatch, user: Admin, store: Db) -> dict[str, Any]:
    tournament = get_tournament(store)
    changes = body.model_dump(exclude_unset=True)
    if "event_date" in changes and schedule_exists(store):
        raise ServiceError("Clear the schedule before changing the date")
    for field, value in changes.items():
        if value is not None:
            setattr(tournament, field, value)
    store.save(tournament)
    return summary(user, store)


# ------------------------------------------------------------- players


@router.post("/players/import")
async def import_players(file: UploadFile, _: Admin, store: Db) -> dict[str, Any]:
    content = await file.read(players.MAX_BYTES + 1)
    return players.import_players(store, content)


@router.get("/players")
def list_players(_: Admin, store: Db) -> list[dict[str, Any]]:
    look = Lookup(store)
    rows = sorted(look.players.values(), key=lambda p: (p.center, p.first_name, p.last_name))
    return [look.player(p, admin=True) for p in rows]


@router.put("/players/{player_id}/login")
def set_player_login(player_id: int, body: PlayerLogin, _: Admin, store: Db) -> dict[str, Any]:
    """Create or reset a player's login; the password is temporary."""
    player = accounts.admin_set_login(store, player_id, body.username, body.password)
    return Lookup(store).player(player, admin=True)


@router.delete("/players/{player_id}/login")
def release_player_login(player_id: int, _: Admin, store: Db) -> dict[str, Any]:
    return Lookup(store).player(accounts.release_account(store, player_id), admin=True)


# --------------------------------------------------------------- teams


@router.get("/teams")
def list_teams(_: Admin, store: Db) -> list[dict[str, Any]]:
    look = Lookup(store)
    rows = sorted(
        look.teams.values(), key=lambda t: (t.team_number is None, t.team_number or 0, t.created_at)
    )
    return [look.team(t, admin=True) for t in rows]


@router.post("/teams", status_code=201)
def create_team(body: TeamCreate, _: Admin, store: Db) -> dict[str, Any]:
    team = teams.admin_create_team(store, body.name, body.player_ids, body.status)
    return Lookup(store).team(team, admin=True)


@router.patch("/teams/{team_id}")
def update_team(team_id: int, body: TeamPatch, _: Admin, store: Db) -> dict[str, Any]:
    team = teams.admin_update_team(store, team_id, **body.model_dump(exclude_unset=True))
    return Lookup(store).team(team, admin=True)


@router.delete("/teams/{team_id}", status_code=204)
def delete_team(team_id: int, _: Admin, store: Db) -> None:
    teams.admin_delete_team(store, team_id)


@router.get("/requests")
def list_requests(_: Admin, store: Db) -> list[dict[str, Any]]:
    look = Lookup(store)
    return [look.request(r) for r in store.all(PartnerRequest) if r.status == "pending"]


@router.post("/requests/{request_id}/cancel")
def cancel_request(request_id: int, _: Admin, store: Db) -> dict[str, Any]:
    return Lookup(store).request(teams.cancel_request(store, request_id, None))


# ------------------------------------------------------------ schedule


@router.post("/draw")
def draw(body: Draw, _: Admin, store: Db) -> list[dict[str, Any]]:
    drawn = schedule.draw_numbers(store, body.seed)
    look = Lookup(store)
    return [look.team(t, admin=True) for t in drawn]


@router.post("/schedule")
def generate(_: Admin, store: Db) -> dict[str, int]:
    return {"matches": schedule.generate_schedule(store)}


@router.delete("/schedule", status_code=204)
def clear(_: Admin, store: Db) -> None:
    schedule.clear_schedule(store)


@router.post("/schedule/lock")
def lock(body: Lock, _: Admin, store: Db) -> dict[str, bool]:
    schedule.set_locked(store, body.locked)
    return {"locked": body.locked}


@router.patch("/matches/{match_id}")
def move_court(match_id: int, body: CourtPatch, _: Admin, store: Db) -> dict[str, Any]:
    return Lookup(store).match(schedule.set_court(store, match_id, body.court))


@router.post("/matches/{match_id}/correct")
def correct(match_id: int, body: Correction, user: Admin, store: Db) -> dict[str, Any]:
    match, warnings = scoring.correct_match(
        store,
        match_id,
        body.score_a,
        body.score_b,
        body.end_reason,
        body.seconds,
        body.reason,
        user,
    )
    return {**Lookup(store).match(match), "warnings": warnings}


@router.post("/matches/{match_id}/reset")
def reset(match_id: int, body: Reset, user: Admin, store: Db) -> dict[str, Any]:
    match, warnings = scoring.reset_match(store, match_id, body.reason, user)
    return {**Lookup(store).match(match), "warnings": warnings}


@router.get("/delays")
def list_delays(_: Admin, store: Db) -> list[dict[str, Any]]:
    return [
        {
            "id": d.id,
            "minutes": d.minutes,
            "applied_from": iso(d.applied_from),
            "matches_moved": d.matches_moved,
            "created_by": d.created_by,
            "created_at": iso(d.created_at),
        }
        for d in reversed(store.all(Delay))
    ]


@router.post("/delays")
def add_delay(body: DelayIn, user: Admin, store: Db) -> dict[str, object]:
    if body.from_time.tzinfo is None:
        raise ServiceError("from_time needs a timezone")
    return schedule.apply_delay(store, body.minutes, body.from_time, user.username)


@router.get("/audit")
def audit(_: Admin, store: Db, limit: int = 200) -> list[dict[str, Any]]:
    rows = list(reversed(store.all(ScoreAudit)))[: min(limit, 1000)]
    return [
        {
            "id": a.id,
            "match": a.match_code,
            "action": a.action,
            "old": a.old_values,
            "new": a.new_values,
            "by": a.changed_by,
            "reason": a.reason,
            "at": iso(a.changed_at),
        }
        for a in rows
    ]


# -------------------------------------------------------- announcements


@router.get("/announcements")
def list_announcements(_: Admin, store: Db) -> list[dict[str, Any]]:
    return [announcement_out(a) for a in reversed(store.all(Announcement))]


@router.post("/announcements", status_code=201)
def add_announcement(body: AnnouncementIn, user: Admin, store: Db) -> dict[str, Any]:
    item = Announcement(
        id=store.next_id(Announcement), created_by=user.username, **body.model_dump()
    )
    store.save(item, create=True)
    return announcement_out(item)


def _announcement(store: Db, item_id: int) -> Announcement:
    item = store.get(Announcement, item_id)
    if item is None:
        raise NotFound("Announcement not found")
    return item


@router.patch("/announcements/{item_id}")
def edit_announcement(item_id: int, body: AnnouncementPatch, _: Admin, store: Db) -> dict[str, Any]:
    item = _announcement(store, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, field, value)
    store.save(item)
    return announcement_out(item)


@router.delete("/announcements/{item_id}", status_code=204)
def delete_announcement(item_id: int, _: Admin, store: Db) -> None:
    store.delete(_announcement(store, item_id))


# ---------------------------------------------------------------- staff


@router.get("/staff")
def list_staff(_: Admin, store: Db) -> list[dict[str, Any]]:
    return [staff_out(u) for u in sorted(store.all(StaffUser), key=lambda u: u.username)]


@router.post("/staff", status_code=201)
def add_staff(body: StaffIn, _: Admin, store: Db) -> dict[str, Any]:
    # The admin chose this password, so it is temporary.
    return staff_out(auth.create_staff(store, **body.model_dump(), must_change=True))


@router.patch("/staff/{user_id}")
def edit_staff(user_id: int, body: StaffPatch, user: Admin, store: Db) -> dict[str, Any]:
    if user_id == user.id and body.active is False:
        raise ServiceError("You cannot deactivate yourself")
    return staff_out(auth.update_staff(store, user_id, **body.model_dump(exclude_unset=True)))


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
def export_results(_: Admin, store: Db) -> Response:
    look = Lookup(store)
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
    for m in ordered(store.all(Match)):
        a, b = look.team_of(m.team_a_id), look.team_of(m.team_b_id)
        rows.append(
            [
                m.code,
                m.round_label,
                iso(m.scheduled_at),
                m.court,
                a.name if a else "",
                b.name if b else "",
                m.score_a,
                m.score_b,
                m.end_reason,
                m.seconds,
                m.status,
            ]
        )
    return _csv(rows, "sampcup-results.csv")
