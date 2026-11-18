"""Teams: the partner-request flow for players, and admin control of teams."""

import contextlib
from datetime import UTC, datetime
from typing import Any

from app.models import PartnerRequest, Player, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.tournament import get_tournament, schedule_exists
from app.store import ConflictError, Store

NAME = "TEAMNAME"  # lock kind: one team (or pending request) per team name
UNTEAMED = "attribute_not_exists(team_id) OR team_id = :none"
RETRY = "Someone else changed this at the same moment. Please try again."


def name_key(name: str) -> str:
    return " ".join(name.split()).casefold()


def clean_team_name(name: str) -> str:
    name = " ".join(name.split())
    if not 2 <= len(name) <= 40:
        raise ServiceError("Team name must be 2-40 characters")
    return name


def get_player(store: Store, player_id: int) -> Player:
    player = store.get(Player, player_id)
    if player is None or not player.active:
        raise NotFound("Player not found")
    return player


def team_players(store: Store, team: Team) -> list[Player]:
    return [p for p in store.all(Player) if p.team_id == team.id]


def ensure_name_free(store: Store, name: str, allowed_owner: str | None = None) -> str:
    key = name_key(name)
    owner = store.lock_owner(NAME, key)
    if owner and owner != allowed_owner:
        if owner.startswith("request:"):
            raise Conflict("That team name is waiting on another request")
        raise Conflict("That team name is taken")
    return key


def active_team_count(store: Store, teams: list[Team] | None = None) -> int:
    teams = store.all(Team) if teams is None else teams
    return sum(t.status == "active" for t in teams)


def pending_requests(
    store: Store, player: Player
) -> tuple[list[PartnerRequest], PartnerRequest | None]:
    rows = [r for r in store.all(PartnerRequest) if r.status == "pending"]
    incoming = [r for r in rows if r.to_player_id == player.id]
    outgoing = next((r for r in rows if r.from_player_id == player.id), None)
    return incoming, outgoing


def _player_put(store: Store, player: Player, allowed_team: int | None = None) -> dict[str, Any]:
    values: dict[str, Any] = {":none": None}
    condition = UNTEAMED
    if allowed_team is not None:
        condition += " OR team_id = :team"
        values[":team"] = allowed_team
    return store.tx_put(player, condition=condition, values=values)


def _pending_put(store: Store, request: PartnerRequest) -> dict[str, Any]:
    return store.tx_put(
        request, condition="#s = :pending", names={"#s": "status"}, values={":pending": "pending"}
    )


def request_partner(store: Store, from_id: int, to_id: int, team_name: str) -> PartnerRequest:
    tournament = get_tournament(store)
    if not tournament.registration_open:
        raise Conflict("Team registration is closed. Ask an admin.")
    me, partner = get_player(store, from_id), get_player(store, to_id)
    if me.id == partner.id:
        raise ServiceError("Pick someone else as your partner")
    if me.center != partner.center:
        raise ServiceError("Your partner must be from your center")
    if me.team_id or partner.team_id:
        raise Conflict("One of you is already on a team")
    if pending_requests(store, me)[1] is not None:
        raise Conflict("You already have a request waiting. Cancel it first.")
    name = clean_team_name(team_name)
    key = ensure_name_free(store, name)
    request = PartnerRequest(
        id=store.next_id(PartnerRequest),
        from_player_id=me.id,
        to_player_id=partner.id,
        team_name=name,
        name_key=key,
    )
    try:
        store.transact(
            [store.tx_put(request, create=True), store.tx_lock(NAME, key, f"request:{request.id}")]
        )
    except ConflictError as exc:
        raise Conflict("That team name was just taken") from exc
    return request


def _resolve(store: Store, request_id: int, player_id: int, as_sender: bool) -> PartnerRequest:
    request = store.get(PartnerRequest, request_id)
    if request is None:
        raise NotFound("Request not found")
    expected = request.from_player_id if as_sender else request.to_player_id
    if expected != player_id:
        raise ServiceError("This request is not yours to answer")
    if request.status != "pending":
        raise Conflict(f"This request was already {request.status}")
    return request


def _close(store: Store, request: PartnerRequest, status: str) -> None:
    request.status, request.resolved_at = status, datetime.now(UTC)
    try:
        store.transact(
            [
                _pending_put(store, request),
                store.tx_unlock(NAME, request.name_key, f"request:{request.id}"),
            ]
        )
    except ConflictError as exc:
        raise Conflict(RETRY) from exc


def accept_request(store: Store, request_id: int, player_id: int) -> Team:
    request = _resolve(store, request_id, player_id, as_sender=False)
    tournament = get_tournament(store)
    if not tournament.registration_open:
        raise Conflict("Team registration is closed. Ask an admin.")
    a, b = get_player(store, request.from_player_id), get_player(store, request.to_player_id)
    if a.team_id or b.team_id:
        raise Conflict("One of you is already on a team")
    owner = f"request:{request.id}"
    key = ensure_name_free(store, request.team_name, allowed_owner=owner)
    full = active_team_count(store) >= tournament.team_cap or schedule_exists(store)
    now = datetime.now(UTC)
    team = Team(
        id=store.next_id(Team),
        name=request.team_name,
        name_key=key,
        center=a.center,
        status="waitlist" if full else "active",
        created_at=now,
    )
    a.team_id = b.team_id = team.id
    request.status, request.resolved_at = "accepted", now
    try:
        store.transact(
            [
                store.tx_put(team, create=True),
                store.tx_lock(NAME, key, f"team:{team.id}", replaces=owner),
                _player_put(store, a),
                _player_put(store, b),
                _pending_put(store, request),
            ]
        )
    except ConflictError as exc:
        raise Conflict(RETRY) from exc
    for other in store.all(PartnerRequest):
        involved = {other.from_player_id, other.to_player_id} & {a.id, b.id}
        if other.status == "pending" and involved:
            with contextlib.suppress(Conflict):  # answered at the same moment
                _close(store, other, "cancelled")
    _enforce_cap(store, team, tournament.team_cap)
    return team


def _enforce_cap(store: Store, team: Team, cap: int) -> None:
    """Two acceptances at once can both see a free spot; the later team waits."""
    if team.status != "active":
        return
    active = sorted(
        (t for t in store.all(Team) if t.status == "active"), key=lambda t: (t.created_at, t.id)
    )
    if team.id in {t.id for t in active[cap:]}:
        team.status = "waitlist"
        store.save(team)


def decline_request(store: Store, request_id: int, player_id: int) -> PartnerRequest:
    request = _resolve(store, request_id, player_id, as_sender=False)
    _close(store, request, "declined")
    return request


def cancel_request(store: Store, request_id: int, player_id: int | None) -> PartnerRequest:
    """The sender cancels; an admin (player_id None) can cancel any pending request."""
    request = store.get(PartnerRequest, request_id)
    if request is not None and player_id is None:
        player_id = request.from_player_id
    request = _resolve(store, request_id, player_id or 0, as_sender=True)
    _close(store, request, "cancelled")
    return request


# ------------------------------------------------------------------ admin


def _new_members(store: Store, team: Team, player_ids: list[int]) -> list[Player]:
    """Players whose team changes; the team's center follows its first player."""
    if len(set(player_ids)) != 2:
        raise ServiceError("A team needs two different players")
    chosen = [get_player(store, pid) for pid in player_ids]
    for player in chosen:
        if player.team_id not in (None, team.id):
            raise Conflict(f"{player.full_name} is already on another team")
    leaving = [p for p in store.all(Player) if p.team_id == team.id and p.id not in player_ids]
    for player in leaving:
        player.team_id = None
    for player in chosen:
        player.team_id = team.id
    team.center = chosen[0].center
    return chosen + leaving


def _check_status(store: Store, team: Team, status: str) -> None:
    if status not in ("active", "waitlist", "withdrawn"):
        raise ServiceError("Status must be active, waitlist or withdrawn")
    if status == team.status:
        return
    if team.team_number is not None:
        raise Conflict("This team has a number in the draw. Clear the schedule and redraw first.")
    others = [t for t in store.all(Team) if t.id != team.id]
    if status == "active" and active_team_count(store, others) >= get_tournament(store).team_cap:
        raise Conflict("The tournament is full (team cap reached)")
    team.status = status


def get_team(store: Store, team_id: int) -> Team:
    team = store.get(Team, team_id)
    if team is None:
        raise NotFound("Team not found")
    return team


def admin_create_team(
    store: Store, name: str, player_ids: list[int], status: str | None = None
) -> Team:
    name = clean_team_name(name)
    key = ensure_name_free(store, name)
    cap = get_tournament(store).team_cap
    team = Team(
        id=store.next_id(Team),
        name=name,
        name_key=key,
        center="",
        status="waitlist",
    )
    players = _new_members(store, team, player_ids)
    if status is None:
        status = "waitlist" if active_team_count(store) >= cap else "active"
    _check_status(store, team, status)
    try:
        store.transact(
            [
                store.tx_put(team, create=True),
                store.tx_lock(NAME, key, f"team:{team.id}"),
                *(_player_put(store, p, team.id) for p in players),
            ]
        )
    except ConflictError as exc:
        raise Conflict(RETRY) from exc
    return team


def admin_update_team(
    store: Store,
    team_id: int,
    *,
    name: str | None = None,
    status: str | None = None,
    checked_in: bool | None = None,
    player_ids: list[int] | None = None,
) -> Team:
    team = get_team(store, team_id)
    writes: list[dict[str, Any]] = []
    owner = f"team:{team.id}"
    if name is not None:
        clean = clean_team_name(name)
        key = name_key(clean)
        if key != team.name_key:
            ensure_name_free(store, clean)
            writes += [store.tx_lock(NAME, key, owner), store.tx_unlock(NAME, team.name_key, owner)]
            team.name_key = key
        team.name = clean
    players = _new_members(store, team, player_ids) if player_ids is not None else []
    if status is not None:
        _check_status(store, team, status)
    if checked_in is not None:
        team.checked_in = checked_in
    writes += [store.tx_put(team), *(_player_put(store, p, team.id) for p in players)]
    try:
        store.transact(writes)
    except ConflictError as exc:
        raise Conflict(RETRY) from exc
    return team


def admin_delete_team(store: Store, team_id: int) -> None:
    team = get_team(store, team_id)
    if team.team_number is not None:
        raise Conflict("This team is in the draw. Withdraw it instead.")
    members = team_players(store, team)
    for player in members:
        player.team_id = None
    store.transact(
        [
            store.tx_delete(team),
            store.tx_unlock(NAME, team.name_key, f"team:{team.id}"),
            *(store.tx_put(p) for p in members),
        ]
    )
