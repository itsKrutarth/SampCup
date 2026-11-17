from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import Db, SessionDep, TeamDep, bearer_token, limit, login_limiter
from app.api.public import team_page
from app.api.serializers import staff_out, team_out
from app.services import auth

router = APIRouter(tags=["auth"])


class TeamLogin(BaseModel):
    team_name: str = Field(max_length=60)
    password: str = Field(max_length=72)


class StaffLogin(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=72)


@router.post("/auth/team-login")
def team_login(body: TeamLogin, db: Db, request: Request) -> dict[str, Any]:
    limit(login_limiter, request)
    token, team = auth.team_login(db, body.team_name, body.password)
    return {"token": token, "kind": "team", "team": team_out(team)}


@router.post("/auth/staff-login")
def staff_login(body: StaffLogin, db: Db, request: Request) -> dict[str, Any]:
    limit(login_limiter, request)
    token, user = auth.staff_login(db, body.username, body.password)
    return {"token": token, "kind": "staff", "user": staff_out(user)}


@router.post("/auth/logout", status_code=204)
def logout(db: Db, token: Annotated[str, Depends(bearer_token)]) -> None:
    auth.logout(db, token)


@router.get("/auth/me")
def me(session: SessionDep) -> dict[str, Any]:
    if session.staff is not None:
        return {"kind": "staff", "user": staff_out(session.staff)}
    return {"kind": "team", "team": team_out(session.team)} if session.team else {"kind": "none"}


@router.get("/team/me")
def my_team(team: TeamDep, db: Db) -> dict[str, Any]:
    return {**team_page(db, team), "players": team_out(team)["players"]}
