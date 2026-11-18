from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.models import Session, StaffUser, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.teams import name_key
from app.store import ConflictError, Store

USERNAME = "USERNAME"  # lock kind: usernames are unique


class LoginFailed(ServiceError):
    status_code = 401


def _new_session(store: Store, **owner: int) -> str:
    token = new_token()
    expires = datetime.now(UTC) + timedelta(hours=get_settings().session_hours)
    store.save(
        Session(id=token_digest(token), expires_at=expires, ttl=int(expires.timestamp()), **owner)
    )
    return token


def team_login(store: Store, team_name: str, password: str) -> tuple[str, Team]:
    key = name_key(team_name)
    team = next((t for t in store.all(Team) if t.name_key == key), None)
    if not verify_password(password, team.password_hash if team else DUMMY_HASH) or not team:
        raise LoginFailed("Team name or password is wrong")
    if team.status == "withdrawn":
        raise LoginFailed("This team has withdrawn. Ask an admin.")
    return _new_session(store, team_id=team.id), team


def staff_login(store: Store, username: str, password: str) -> tuple[str, StaffUser]:
    wanted = username.strip().lower()
    user = next((u for u in store.all(StaffUser) if u.username == wanted), None)
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not ok or user is None or not user.active:
        raise LoginFailed("Username or password is wrong")
    return _new_session(store, staff_id=user.id), user


def session_for(store: Store, token: str) -> Session | None:
    session = store.get(Session, token_digest(token))
    if session is None or session.expires_at <= datetime.now(UTC):
        return None
    return session


def logout(store: Store, token: str) -> None:
    session = store.get(Session, token_digest(token))
    if session:
        store.delete(session)


def end_sessions(store: Store, *, team_id: int | None = None, staff_id: int | None = None) -> None:
    for session in store.all(Session):
        if (team_id and session.team_id == team_id) or (staff_id and session.staff_id == staff_id):
            store.delete(session)


def end_team_sessions(store: Store, team_id: int) -> None:
    end_sessions(store, team_id=team_id)


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
    store: Store,
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
    user = StaffUser(
        id=store.next_id(StaffUser),
        username=username,
        display_name=display_name.strip() or username,
        role=role,
        password_hash=hash_password(password),
        court=court,
    )
    try:
        store.transact(
            [store.tx_put(user, create=True), store.tx_lock(USERNAME, username, f"staff:{user.id}")]
        )
    except ConflictError as exc:
        raise Conflict("That username is taken") from exc
    return user


def update_staff(
    store: Store,
    user_id: int,
    *,
    court: int | None = None,
    clear_court: bool = False,
    active: bool | None = None,
    password: str | None = None,
    display_name: str | None = None,
) -> StaffUser:
    user = store.get(StaffUser, user_id)
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
    store.save(user)
    if password is not None or active is False:
        end_sessions(store, staff_id=user.id)
    return user
