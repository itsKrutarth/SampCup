"""Teams: the partner-request flow for players, and admin control of teams."""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import PartnerRequest, Player, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.tournament import get_tournament, schedule_exists


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def clean_team_name(name: str) -> str:
    name = " ".join(name.split())
    if not 2 <= len(name) <= 40:
        raise ServiceError("Team name must be 2-40 characters")
    return name


def check_password(password: str) -> None:
    if not 4 <= len(password) <= 72:
        raise ServiceError("Password must be 4-72 characters")


def get_player(db: Session, player_id: int) -> Player:
    player = db.get(Player, player_id)
    if player is None or not player.active:
        raise NotFound("Player not found")
    return player


def ensure_name_free(db: Session, name: str, ignore_request: int | None = None) -> str:
    key = name_key(name)
    if db.scalar(select(Team.id).where(Team.name_key == key)):
        raise Conflict("That team name is taken")
    pending = select(PartnerRequest.id).where(
        PartnerRequest.name_key == key, PartnerRequest.status == "pending"
    )
    if ignore_request is not None:
        pending = pending.where(PartnerRequest.id != ignore_request)
    if db.scalar(pending):
        raise Conflict("That team name is waiting on another request")
    return key


def active_team_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Team).where(Team.status == "active")) or 0


def pending_requests(
    db: Session, player: Player
) -> tuple[list[PartnerRequest], PartnerRequest | None]:
    rows = db.scalars(
        select(PartnerRequest)
        .where(
            PartnerRequest.status == "pending",
            or_(
                PartnerRequest.to_player_id == player.id,
                PartnerRequest.from_player_id == player.id,
            ),
        )
        .order_by(PartnerRequest.id)
    ).all()
    incoming = [r for r in rows if r.to_player_id == player.id]
    outgoing = next((r for r in rows if r.from_player_id == player.id), None)
    return incoming, outgoing


def request_partner(
    db: Session, from_id: int, to_id: int, team_name: str, password: str
) -> PartnerRequest:
    tournament = get_tournament(db)
    if not tournament.registration_open:
        raise Conflict("Team registration is closed. Ask an admin.")
    me, partner = get_player(db, from_id), get_player(db, to_id)
    if me.id == partner.id:
        raise ServiceError("Pick someone else as your partner")
    if me.center != partner.center:
        raise ServiceError("Your partner must be from your center")
    if me.team_id or partner.team_id:
        raise Conflict("One of you is already on a team")
    if pending_requests(db, me)[1] is not None:
        raise Conflict("You already have a request waiting. Cancel it first.")
    name = clean_team_name(team_name)
    check_password(password)
    request = PartnerRequest(
        from_player_id=me.id,
        to_player_id=partner.id,
        team_name=name,
        name_key=ensure_name_free(db, name),
        password_hash=hash_password(password),
    )
    db.add(request)
    db.commit()
    return request


def _resolve(db: Session, request_id: int, player_id: int, as_sender: bool) -> PartnerRequest:
    request = db.get(PartnerRequest, request_id)
    if request is None:
        raise NotFound("Request not found")
    expected = request.from_player_id if as_sender else request.to_player_id
    if expected != player_id:
        raise ServiceError("This request is not yours to answer")
    if request.status != "pending":
        raise Conflict(f"This request was already {request.status}")
    return request


def accept_request(db: Session, request_id: int, player_id: int) -> Team:
    request = _resolve(db, request_id, player_id, as_sender=False)
    tournament = get_tournament(db)
    if not tournament.registration_open:
        raise Conflict("Team registration is closed. Ask an admin.")
    a, b = get_player(db, request.from_player_id), get_player(db, request.to_player_id)
    if a.team_id or b.team_id:
        raise Conflict("One of you is already on a team")
    key = ensure_name_free(db, request.team_name, ignore_request=request.id)
    full = active_team_count(db) >= tournament.team_cap or schedule_exists(db)
    team = Team(
        name=request.team_name,
        name_key=key,
        password_hash=request.password_hash,
        center=a.center,
        status="waitlist" if full else "active",
    )
    db.add(team)
    db.flush()
    a.team_id = b.team_id = team.id
    now = datetime.now(UTC)
    request.status, request.resolved_at = "accepted", now
    for other in db.scalars(
        select(PartnerRequest).where(
            PartnerRequest.status == "pending",
            PartnerRequest.id != request.id,
            or_(
                PartnerRequest.from_player_id.in_([a.id, b.id]),
                PartnerRequest.to_player_id.in_([a.id, b.id]),
            ),
        )
    ):
        other.status, other.resolved_at = "cancelled", now
    db.commit()
    return team


def decline_request(db: Session, request_id: int, player_id: int) -> PartnerRequest:
    request = _resolve(db, request_id, player_id, as_sender=False)
    request.status, request.resolved_at = "declined", datetime.now(UTC)
    db.commit()
    return request


def cancel_request(db: Session, request_id: int, player_id: int | None) -> PartnerRequest:
    """The sender cancels; an admin (player_id None) can cancel any pending request."""
    request = db.get(PartnerRequest, request_id)
    if request is not None and player_id is None:
        player_id = request.from_player_id
    request = _resolve(db, request_id, player_id or 0, as_sender=True)
    request.status, request.resolved_at = "cancelled", datetime.now(UTC)
    db.commit()
    return request


# ------------------------------------------------------------------ admin


def _set_players(db: Session, team: Team, player_ids: list[int]) -> None:
    if len(set(player_ids)) != 2:
        raise ServiceError("A team needs two different players")
    players = [get_player(db, pid) for pid in player_ids]
    for player in players:
        if player.team_id not in (None, team.id):
            raise Conflict(f"{player.full_name} is already on another team")
    for player in list(team.players):
        if player.id not in player_ids:
            player.team_id = None
    for player in players:
        player.team_id = team.id
    team.center = players[0].center
    db.flush()
    db.refresh(team)


def admin_create_team(
    db: Session, name: str, password: str, player_ids: list[int], status: str | None = None
) -> Team:
    name = clean_team_name(name)
    check_password(password)
    key = ensure_name_free(db, name)
    tournament = get_tournament(db)
    if status is None:
        status = "waitlist" if active_team_count(db) >= tournament.team_cap else "active"
    team = Team(name=name, name_key=key, password_hash=hash_password(password), center="")
    db.add(team)
    db.flush()
    _set_players(db, team, player_ids)
    _set_status(db, team, status)
    db.commit()
    return team


def _set_status(db: Session, team: Team, status: str) -> None:
    if status not in ("active", "waitlist", "withdrawn"):
        raise ServiceError("Status must be active, waitlist or withdrawn")
    if status == team.status:
        return
    if team.team_number is not None:
        raise Conflict("This team has a number in the draw. Clear the schedule and redraw first.")
    if status == "active" and active_team_count(db) >= get_tournament(db).team_cap:
        raise Conflict("The tournament is full (team cap reached)")
    team.status = status


def get_team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise NotFound("Team not found")
    return team


def admin_update_team(
    db: Session,
    team_id: int,
    *,
    name: str | None = None,
    status: str | None = None,
    checked_in: bool | None = None,
    player_ids: list[int] | None = None,
    password: str | None = None,
) -> Team:
    team = get_team(db, team_id)
    if name is not None and name_key(name) != team.name_key:
        team.name = clean_team_name(name)
        team.name_key = ensure_name_free(db, team.name)
    elif name is not None:
        team.name = clean_team_name(name)
    if player_ids is not None:
        _set_players(db, team, player_ids)
    if status is not None:
        _set_status(db, team, status)
    if checked_in is not None:
        team.checked_in = checked_in
    if password is not None:
        check_password(password)
        team.password_hash = hash_password(password)
        from app.services.auth import end_team_sessions

        end_team_sessions(db, team.id)
    db.commit()
    return team


def admin_delete_team(db: Session, team_id: int) -> None:
    team = get_team(db, team_id)
    if team.team_number is not None:
        raise Conflict("This team is in the draw. Withdraw it instead.")
    for player in list(team.players):
        player.team_id = None
    db.delete(team)
    db.commit()
