from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import RateLimiter
from app.db.session import get_db
from app.models import AuthSession, StaffUser, Team
from app.services.auth import session_for

Db = Annotated[Session, Depends(get_db)]

login_limiter = RateLimiter(limit=10, window=300)
registration_limiter = RateLimiter(limit=30, window=600)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def limit(limiter: RateLimiter, request: Request) -> None:
    if not limiter.allow(client_key(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries. Wait a few minutes."
        )


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in first")
    return token


def current_session(db: Db, token: Annotated[str, Depends(bearer_token)]) -> AuthSession:
    session = session_for(db, token)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your login has expired")
    return session


SessionDep = Annotated[AuthSession, Depends(current_session)]


def current_staff(session: SessionDep) -> StaffUser:
    if session.staff is None or not session.staff.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff only")
    return session.staff


def current_admin(user: Annotated[StaffUser, Depends(current_staff)]) -> StaffUser:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def current_team(session: SessionDep) -> Team:
    if session.team is None or session.team.status == "withdrawn":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teams only")
    return session.team


Staff = Annotated[StaffUser, Depends(current_staff)]
Admin = Annotated[StaffUser, Depends(current_admin)]
TeamDep = Annotated[Team, Depends(current_team)]
