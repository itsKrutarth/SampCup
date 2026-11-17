"""Players form their own teams: pick yourself, pick a partner, the partner accepts."""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import Db, limit, registration_limiter
from app.api.serializers import player_out, request_out, team_out
from app.models import PartnerRequest, Player
from app.services import events, teams
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
def status(db: Db) -> dict[str, Any]:
    tournament = get_tournament(db)
    db.commit()
    return {
        "open": tournament.registration_open,
        "team_cap": tournament.team_cap,
        "teams": teams.active_team_count(db),
    }


@router.get("/centers")
def centers(db: Db) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Player.center, func.count(), func.count(Player.team_id))
        .where(Player.active)
        .group_by(Player.center)
        .order_by(Player.center)
    ).all()
    return [{"center": c, "players": n, "on_teams": t} for c, n, t in rows]


@router.get("/players")
def players(db: Db, center: str) -> list[dict[str, Any]]:
    pending = {
        pid
        for row in db.execute(
            select(PartnerRequest.from_player_id, PartnerRequest.to_player_id).where(
                PartnerRequest.status == "pending"
            )
        )
        for pid in row
    }
    rows = db.scalars(
        select(Player)
        .where(Player.active, Player.center == center)
        .order_by(Player.first_name, Player.last_name)
    ).all()
    return [
        {
            **player_out(p),
            "state": "teamed" if p.team_id else "pending" if p.id in pending else "free",
            "team_name": p.team.name if p.team else None,
        }
        for p in rows
    ]


@router.get("/players/{player_id}")
def player_status(player_id: int, db: Db) -> dict[str, Any]:
    player = teams.get_player(db, player_id)
    incoming, outgoing = teams.pending_requests(db, player)
    return {
        "player": player_out(player),
        "team": team_out(player.team) if player.team else None,
        "incoming": [request_out(r) for r in incoming],
        "outgoing": request_out(outgoing) if outgoing else None,
    }


@router.post("/requests", status_code=201)
def create_request(body: NewRequest, db: Db, request: Request) -> dict[str, Any]:
    limit(registration_limiter, request)
    created = teams.request_partner(
        db, body.from_player_id, body.to_player_id, body.team_name, body.password
    )
    events.broadcaster.publish("update", scope="registration")
    return request_out(created)


@router.post("/requests/{request_id}/accept")
def accept(request_id: int, body: Answer, db: Db) -> dict[str, Any]:
    team = teams.accept_request(db, request_id, body.player_id)
    events.broadcaster.publish("update", scope="teams")
    return team_out(team)


@router.post("/requests/{request_id}/decline")
def decline(request_id: int, body: Answer, db: Db) -> dict[str, Any]:
    out = request_out(teams.decline_request(db, request_id, body.player_id))
    events.broadcaster.publish("update", scope="registration")
    return out


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: int, body: Answer, db: Db) -> dict[str, Any]:
    out = request_out(teams.cancel_request(db, request_id, body.player_id))
    events.broadcaster.publish("update", scope="registration")
    return out
