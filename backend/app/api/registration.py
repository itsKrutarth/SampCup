"""Players claim their account, then pair up: invite a partner, the partner accepts."""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.api.deps import REGISTRATION_PER_IP, Db, PlayerDep, limit
from app.api.serializers import Lookup
from app.models import PartnerRequest, Player
from app.services import accounts, auth, teams
from app.services.tournament import get_tournament

router = APIRouter(tags=["registration"])


class Claim(BaseModel):
    first_name: str = Field(max_length=80)
    last_name: str = Field(max_length=80)
    email: str = Field(max_length=254)
    username: str = Field(max_length=40)
    password: str = Field(max_length=72)


class NewRequest(BaseModel):
    to_player_id: int
    team_name: str = Field(max_length=60)


@router.get("/registration/status")
def status(store: Db) -> dict[str, Any]:
    tournament = get_tournament(store)
    loaded = any(p.active for p in store.all(Player))
    return {"open": tournament.registration_open, "team_cap": tournament.team_cap, "loaded": loaded}


@router.post("/players/claim", status_code=201)
def claim(body: Claim, store: Db, request: Request) -> dict[str, Any]:
    limit(store, request, "claim", REGISTRATION_PER_IP)
    player = accounts.claim_account(
        store, body.first_name, body.last_name, body.email, body.username, body.password
    )
    token = auth.new_session(store, player_id=player.id)
    return {"token": token, "kind": "player", "player": Lookup(store).player(player)}


@router.get("/registration/players")
def players(me: PlayerDep, store: Db) -> list[dict[str, Any]]:
    """Players at my own center, for picking a partner (none until my center is set)."""
    look = Lookup(store)
    pending = {
        pid
        for r in store.all(PartnerRequest)
        if r.status == "pending"
        for pid in (r.from_player_id, r.to_player_id)
    }
    rows = sorted(
        (
            p
            for p in look.players.values()
            if p.active and me.center and p.center == me.center and p.id != me.id
        ),
        key=lambda p: (p.first_name, p.last_name),
    )
    out = []
    for p in rows:
        team = look.team_of(p.team_id)
        state = "teamed" if team else "pending" if p.id in pending else "free"
        out.append({**look.player(p), "state": state, "team_name": team.name if team else None})
    return out


@router.post("/registration/requests", status_code=201)
def create_request(body: NewRequest, me: PlayerDep, store: Db, request: Request) -> dict[str, Any]:
    limit(store, request, "register", REGISTRATION_PER_IP)
    created = teams.request_partner(store, me.id, body.to_player_id, body.team_name)
    return Lookup(store).request(created)


@router.post("/registration/requests/{request_id}/accept")
def accept(request_id: int, me: PlayerDep, store: Db) -> dict[str, Any]:
    team = teams.accept_request(store, request_id, me.id)
    return Lookup(store).team(team)


@router.post("/registration/requests/{request_id}/decline")
def decline(request_id: int, me: PlayerDep, store: Db) -> dict[str, Any]:
    return Lookup(store).request(teams.decline_request(store, request_id, me.id))


@router.post("/registration/requests/{request_id}/cancel")
def cancel(request_id: int, me: PlayerDep, store: Db) -> dict[str, Any]:
    return Lookup(store).request(teams.cancel_request(store, request_id, me.id))
