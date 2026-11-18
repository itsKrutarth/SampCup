from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import (
    LOGIN_PER_ACCOUNT,
    LOGIN_PER_IP,
    Db,
    PlayerDep,
    SessionDep,
    bearer_token,
    limit,
)
from app.api.public import team_page
from app.api.serializers import Lookup, staff_out
from app.models import Player, StaffUser
from app.services import accounts, auth, teams

router = APIRouter(tags=["auth"])


class TeamLogin(BaseModel):
    team_name: str = Field(max_length=60)
    password: str = Field(max_length=72)


class StaffLogin(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=72)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=72)
    new_password: str = Field(max_length=72)


@router.post("/auth/player-login")
def player_login(body: StaffLogin, store: Db, request: Request) -> dict[str, Any]:
    limit(store, request, "login-ip", LOGIN_PER_IP)
    limit(store, request, "login", LOGIN_PER_ACCOUNT, f"player:{body.username.strip().lower()}")
    token, player = accounts.player_login(store, body.username, body.password)
    return {"token": token, "kind": "player", "player": Lookup(store).player(player, admin=True)}


@router.post("/auth/staff-login")
def staff_login(body: StaffLogin, store: Db, request: Request) -> dict[str, Any]:
    limit(store, request, "login-ip", LOGIN_PER_IP)
    limit(store, request, "login", LOGIN_PER_ACCOUNT, body.username.strip().lower())
    token, user = auth.staff_login(store, body.username, body.password)
    return {"token": token, "kind": "staff", "user": staff_out(user)}


@router.post("/auth/change-password")
def change_password(body: PasswordChange, store: Db, session: SessionDep) -> dict[str, Any]:
    if session.player_id and (player := store.get(Player, session.player_id)):
        player = accounts.change_own_password(
            store, player, body.current_password, body.new_password
        )
        return {"player": Lookup(store).player(player, admin=True)}
    user = store.get(StaffUser, session.staff_id) if session.staff_id else None
    if user is None or not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff only")
    user = auth.change_own_password(store, user, body.current_password, body.new_password)
    return {"user": staff_out(user)}


@router.post("/auth/logout", status_code=204)
def logout(store: Db, token: Annotated[str, Depends(bearer_token)]) -> None:
    auth.logout(store, token)


@router.get("/auth/me")
def me(store: Db, session: SessionDep) -> dict[str, Any]:
    if session.staff_id and (user := store.get(StaffUser, session.staff_id)):
        return {"kind": "staff", "user": staff_out(user)}
    if session.player_id and (player := store.get(Player, session.player_id)):
        return {"kind": "player", "player": Lookup(store).player(player, admin=True)}
    return {"kind": "none"}


@router.get("/player/me")
def my_page(me: PlayerDep, store: Db) -> dict[str, Any]:
    """Everything a logged-in player sees: their team, or their invitations."""
    look = Lookup(store)
    incoming, outgoing = teams.pending_requests(store, me)
    team = look.team_of(me.team_id)
    return {
        "player": look.player(me),
        "team": team_page(store, team) if team else None,
        "incoming": [look.request(r) for r in incoming],
        "outgoing": look.request(outgoing) if outgoing else None,
    }
