from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)
from app.models import Session, StaffUser
from app.services.errors import Conflict, NotFound, ServiceError
from app.store import ConflictError, Store

USERNAME = "USERNAME"  # lock kind: usernames are unique


class LoginFailed(ServiceError):
    status_code = 401


def new_session(store: Store, **owner: int) -> str:
    token = new_token()
    expires = datetime.now(UTC) + timedelta(hours=get_settings().session_hours)
    store.save(
        Session(id=token_digest(token), expires_at=expires, ttl=int(expires.timestamp()), **owner)
    )
    return token


def staff_login(store: Store, username: str, password: str) -> tuple[str, StaffUser]:
    wanted = username.strip().lower()
    user = next((u for u in store.all(StaffUser) if u.username == wanted), None)
    ok = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if not ok or user is None or not user.active:
        raise LoginFailed("Username or password is wrong")
    return new_session(store, staff_id=user.id), user


def session_for(store: Store, token: str) -> Session | None:
    session = store.get(Session, token_digest(token))
    if session is None or session.expires_at <= datetime.now(UTC):
        return None
    return session


def logout(store: Store, token: str) -> None:
    session = store.get(Session, token_digest(token))
    if session:
        store.delete(session)


def end_sessions(
    store: Store,
    *,
    team_id: int | None = None,
    staff_id: int | None = None,
    player_id: int | None = None,
) -> None:
    for session in store.all(Session):
        if (
            (team_id and session.team_id == team_id)
            or (staff_id and session.staff_id == staff_id)
            or (player_id and session.player_id == player_id)
        ):
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


def _check_password(role: str, password: str) -> None:
    if len(password) < 8 and role == "admin":
        raise ServiceError("Admin passwords need at least 8 characters")
    if len(password) < 4:
        raise ServiceError("Password must be at least 4 characters")


def create_staff(
    store: Store,
    username: str,
    password: str,
    role: str,
    display_name: str = "",
    court: int | None = None,
    must_change: bool = False,
) -> StaffUser:
    username = _check_staff(username, role, court)
    _check_password(role, password)
    user = StaffUser(
        id=store.next_id(StaffUser),
        username=username,
        display_name=display_name.strip() or username,
        role=role,
        password_hash=hash_password(password),
        court=court,
        must_change_password=must_change,
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
    username: str | None = None,
    court: int | None = None,
    clear_court: bool = False,
    active: bool | None = None,
    password: str | None = None,
    display_name: str | None = None,
) -> StaffUser:
    """Admin changes. A password set here is temporary: the user picks their own next login."""
    user = store.get(StaffUser, user_id)
    if user is None:
        raise NotFound("Staff user not found")
    old_username = user.username
    if username is not None:
        user.username = _check_staff(username, user.role, None)
    if court is not None:
        _check_staff(user.username, user.role, court)
        user.court = court
    if clear_court:
        user.court = None
    if display_name is not None:
        user.display_name = display_name.strip() or user.username
    if password is not None:
        _check_password(user.role, password)
        user.password_hash = hash_password(password)
        user.must_change_password = True
    if active is not None:
        user.active = active
    owner = f"staff:{user.id}"
    writes = [store.tx_put(user)]
    if user.username != old_username:
        writes += [
            store.tx_lock(USERNAME, user.username, owner),
            store.tx_unlock(USERNAME, old_username, owner),
        ]
    try:
        store.transact(writes)
    except ConflictError as exc:
        raise Conflict("That username is taken") from exc
    if password is not None or active is False:
        end_sessions(store, staff_id=user.id)
    return user


def change_own_password(store: Store, user: StaffUser, current: str, new: str) -> StaffUser:
    """The user replaces a password (for example the temporary one an admin set)."""
    if not verify_password(current, user.password_hash):
        raise ServiceError("Your current password or PIN is wrong")
    if new == current:
        raise ServiceError("Choose a password or PIN different from the one you were given")
    _check_password(user.role, new)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    store.save(user)
    return user
