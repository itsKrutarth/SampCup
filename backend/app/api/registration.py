"""Players form their own teams: pick yourself, pick a partner, the partner accepts."""

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import REGISTRATION_PER_IP, Db, limit
from app.api.serializers import Lookup
from app.models import PartnerRequest, Player
from app.services import teams
from app.services.tournament import get_tournament

router = APIRouter(prefix="/registration", tags=["registration"])


class NewRequest(BaseModel):
    from_player_id: int
    to_player_id: int
    team_name: str = Field(max_length=60)
    password: str = Field(max_length=72)


class Answer(BaseModel):
    player_id: int


@router.get("/status")
def status(store: Db) -> dict[str, Any]:
    tournament = get_tournament(store)
    return {
        "open": tournament.registration_open,
        "team_cap": tournament.team_cap,
        "teams": teams.active_team_count(store),
    }


@router.get("/centers")
def centers(store: Db) -> list[dict[str, Any]]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for player in store.all(Player):
        if player.active:
            counts[player.center][0] += 1
            counts[player.center][1] += player.team_id is not None
    return [{"center": c, "players": n, "on_teams": t} for c, (n, t) in sorted(counts.items())]


@router.get("/players")
def players(store: Db, center: str) -> list[dict[str, Any]]:
    look = Lookup(store)
    pending = {
        pid
        for r in store.all(PartnerRequest)
        if r.status == "pending"
        for pid in (r.from_player_id, r.to_player_id)
    }
    rows = sorted(
        (p for p in look.players.values() if p.active and p.center == center),
        key=lambda p: (p.first_name, p.last_name),
    )
    out = []
    for p in rows:
        team = look.team_of(p.team_id)
        state = "teamed" if team else "pending" if p.id in pending else "free"
        out.append({**look.player(p), "state": state, "team_name": team.name if team else None})
    return out


@router.get("/players/{player_id}")
def player_status(player_id: int, store: Db) -> dict[str, Any]:
    player = teams.get_player(store, player_id)
    look = Lookup(store)
    incoming, outgoing = teams.pending_requests(store, player)
    team = look.team_of(player.team_id)
    return {
        "player": look.player(player),
        "team": look.team(team) if team else None,
        "incoming": [look.request(r) for r in incoming],
        "outgoing": look.request(outgoing) if outgoing else None,
    }


@router.post("/requests", status_code=201)
def create_request(body: NewRequest, store: Db, request: Request) -> dict[str, Any]:
    limit(store, request, "register", REGISTRATION_PER_IP)
    created = teams.request_partner(
        store, body.from_player_id, body.to_player_id, body.team_name, body.password
    )
    return Lookup(store).request(created)


@router.post("/requests/{request_id}/accept")
def accept(request_id: int, body: Answer, store: Db) -> dict[str, Any]:
    team = teams.accept_request(store, request_id, body.player_id)
    return Lookup(store).team(team)


@router.post("/requests/{request_id}/decline")
def decline(request_id: int, body: Answer, store: Db) -> dict[str, Any]:
    return Lookup(store).request(teams.decline_request(store, request_id, body.player_id))


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: int, body: Answer, store: Db) -> dict[str, Any]:
    return Lookup(store).request(teams.cancel_request(store, request_id, body.player_id))
