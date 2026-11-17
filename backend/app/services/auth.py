from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.models import AuthSession, StaffUser, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.teams import name_key


class LoginFailed(ServiceError):
    status_code = 401


def _new_session(db: Session, **owner: int) -> str:
    token = new_token()
    now = datetime.now(UTC)
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now))
    db.add(
        AuthSession(
            token_hash=token_digest(token),
            expires_at=now + timedelta(hours=get_settings().session_hours),
            **owner,
        )
    )
    db.commit()
    return token


def team_login(db: Session, team_name: str, password: str) -> tuple[str, Team]:
    team = db.scalar(select(Team).where(Team.name_key == name_key(team_name)))
    if not verify_password(password, team.password_hash if team else DUMMY_HASH) or not team:
        raise LoginFailed("Team name or password is wrong")
    if team.status == "withdrawn":
        raise LoginFailed("This team has withdrawn. Ask an admin.")
    return _new_session(db, team_id=team.id), team


def staff_login(db: Session, username: str, password: str) -> tuple[str, StaffUser]:
    user = db.scalar(select(StaffUser).where(StaffUser.username == username.strip().lower()))
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not ok or user is None or not user.active:
        raise LoginFailed("Username or password is wrong")
    return _new_session(db, staff_id=user.id), user


def session_for(db: Session, token: str) -> AuthSession | None:
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if session is None or session.expires_at <= datetime.now(UTC):
        return None
    return session


def logout(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    db.commit()


def end_team_sessions(db: Session, team_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.team_id == team_id))


def _check_staff(username: str, role: str, court: int | None) -> str:
    username = username.strip().lower()
    if not username.isascii() or not username.replace("-", "").replace("_", "").isalnum():
        raise ServiceError("Username may use letters, numbers, - and _")
    if role not in ("admin", "judge"):
        raise ServiceError("Role must be admin or judge")
    if court is not None and not 1 <= court <= 9:
        raise ServiceError("Court must be 1-9")
    return username


def create_staff(
    db: Session,
    username: str,
    password: str,
    role: str,
    display_name: str = "",
    court: int | None = None,
) -> StaffUser:
    username = _check_staff(username, role, court)
    if len(password) < 8 and role == "admin":
        raise ServiceError("Admin passwords need at least 8 characters")
    if len(password) < 4:
        raise ServiceError("Password must be at least 4 characters")
    if db.scalar(select(StaffUser.id).where(StaffUser.username == username)):
        raise Conflict("That username is taken")
    user = StaffUser(
        username=username,
        display_name=display_name.strip() or username,
        role=role,
        password_hash=hash_password(password),
        court=court,
    )
    db.add(user)
    db.commit()
    return user


def update_staff(
    db: Session,
    user_id: int,
    *,
    court: int | None = None,
    clear_court: bool = False,
    active: bool | None = None,
    password: str | None = None,
    display_name: str | None = None,
) -> StaffUser:
    user = db.get(StaffUser, user_id)
    if user is None:
        raise NotFound("Staff user not found")
    if court is not None:
        _check_staff(user.username, user.role, court)
        user.court = court
    if clear_court:
        user.court = None
    if display_name is not None:
        user.display_name = display_name.strip() or user.username
    if password is not None:
        if len(password) < (8 if user.role == "admin" else 4):
            raise ServiceError("Password is too short")
        user.password_hash = hash_password(password)
    if active is not None:
        user.active = active
    if password is not None or active is False:
        db.execute(delete(AuthSession).where(AuthSession.staff_id == user.id))
    db.commit()
    return user
