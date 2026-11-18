from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.models import Session, StaffUser, Team
from app.services.auth import session_for
from app.store import Store, get_store

Db = Annotated[Store, Depends(get_store)]

# (hits, seconds) per client IP. Players at the venue share one Wi-Fi address, so the
# login limit counts per IP *and* account name; the per-IP limits stay generous.
LOGIN_PER_ACCOUNT = (10, 300)
LOGIN_PER_IP = (300, 300)
REGISTRATION_PER_IP = (300, 600)


def client_ip(request: Request) -> str:
    """The visitor's address. Behind CloudFront the function URL sees CloudFront, so use
    the entry CloudFront added to X-Forwarded-For (second from the end)."""
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",")]
    forwarded = [p for p in forwarded if p]
    if get_settings().origin_secret and forwarded:
        return forwarded[-2] if len(forwarded) >= 2 else forwarded[0]
    return request.client.host if request.client else "unknown"


def limit(
    store: Store, request: Request, name: str, rule: tuple[int, int], extra: str = ""
) -> None:
    hits, window = rule
    key = f"{name}:{client_ip(request)}" + (f":{extra}" if extra else "")
    if store.hit(key, window) > hits:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many tries. Wait a few minutes."
        )


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Log in first")
    return token


def current_session(store: Db, token: Annotated[str, Depends(bearer_token)]) -> Session:
    session = session_for(store, token)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your login has expired")
    return session


SessionDep = Annotated[Session, Depends(current_session)]


def current_staff(store: Db, session: SessionDep) -> StaffUser:
    user = store.get(StaffUser, session.staff_id) if session.staff_id else None
    if user is None or not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Staff only")
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choose your own password first")
    return user


def current_admin(user: Annotated[StaffUser, Depends(current_staff)]) -> StaffUser:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def current_team(store: Db, session: SessionDep) -> Team:
    team = store.get(Team, session.team_id) if session.team_id else None
    if team is None or team.status == "withdrawn":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teams only")
    return team


Staff = Annotated[StaffUser, Depends(current_staff)]
Admin = Annotated[StaffUser, Depends(current_admin)]
TeamDep = Annotated[Team, Depends(current_team)]
