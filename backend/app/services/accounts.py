"""Player accounts: a registered player claims their account once, then logs in."""

import re

from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models import Player
from app.services.auth import LoginFailed, end_sessions, new_session
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.players import email_key
from app.store import ConflictError, Store

LOGIN = "PLAYERNAME"  # lock kind: player usernames are unique
USERNAME_RULE = re.compile(r"^[a-z0-9._-]{3,30}$")
UNCLAIMED = "attribute_not_exists(username) OR username = :none"


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def clean_username(username: str) -> str:
    username = username.strip().lower()
    if not USERNAME_RULE.match(username):
        raise ServiceError("Username: 3-30 letters, numbers, dots, dashes or underscores")
    return username


def check_password(password: str) -> None:
    if not 6 <= len(password) <= 72:
        raise ServiceError("Password must be 6-72 characters")


def find_player(store: Store, first_name: str, last_name: str, email: str) -> Player:
    """The one active registered player with this name and registration email. The center comes
    from the registration, so players don't pick it."""
    wanted = (_norm(first_name), _norm(last_name))
    key = email_key(email)
    matches = [
        p
        for p in store.all(Player)
        if p.active
        and key
        and p.email_key == key
        and (_norm(p.first_name), _norm(p.last_name)) == wanted
    ]
    if not matches:
        raise NotFound(
            "We couldn't find a registration with this name and email. Use the email you "
            "registered with, or ask your coordinator."
        )
    if len(matches) > 1:
        raise Conflict(
            "More than one registration has this name and email. "
            "Ask an admin to set up your account."
        )
    return matches[0]


def _owner(player: Player) -> str:
    return f"player:{player.id}"


def claim_account(
    store: Store, first_name: str, last_name: str, email: str, username: str, password: str
) -> Player:
    player = find_player(store, first_name, last_name, email)
    if player.username:
        raise Conflict(
            "This player already has an account. Log in, or ask an admin if that wasn't you."
        )
    username = clean_username(username)
    check_password(password)
    if store.lock_owner(LOGIN, username):
        raise Conflict("That username is taken")
    player.username = username
    player.password_hash = hash_password(password)
    player.must_change_password = False
    try:
        store.transact(
            [
                store.tx_put(player, condition=UNCLAIMED, values={":none": None}),
                store.tx_lock(LOGIN, username, _owner(player)),
            ]
        )
    except ConflictError as exc:
        raise Conflict("Someone just claimed this account or username. Try again.") from exc
    return player


def player_login(store: Store, username: str, password: str) -> tuple[str, Player]:
    wanted = username.strip().lower()
    player = next((p for p in store.all(Player) if p.username == wanted), None)
    stored = player.password_hash if player and player.password_hash else DUMMY_HASH
    if not verify_password(password, stored) or player is None or not player.active:
        raise LoginFailed("Username or password is wrong")
    return new_session(store, player_id=player.id), player


def change_own_password(store: Store, player: Player, current: str, new: str) -> Player:
    if not verify_password(current, player.password_hash or DUMMY_HASH):
        raise ServiceError("Your current password is wrong")
    if new == current:
        raise ServiceError("Choose a password different from the one you were given")
    check_password(new)
    player.password_hash = hash_password(new)
    player.must_change_password = False
    store.save(player)
    return player


def _get(store: Store, player_id: int) -> Player:
    player = store.get(Player, player_id)
    if player is None:
        raise NotFound("Player not found")
    return player


def admin_set_login(
    store: Store, player_id: int, username: str | None, password: str | None
) -> Player:
    """Create or change a player's login. A password set here is temporary."""
    player = _get(store, player_id)
    old = player.username
    if username is not None:
        player.username = clean_username(username)
    if not player.username:
        raise ServiceError("Give the player a username")
    if not old and password is None:
        raise ServiceError("Give the player a temporary password")
    if password is not None:
        check_password(password)
        player.password_hash = hash_password(password)
        player.must_change_password = True
    writes = [store.tx_put(player)]
    if player.username != old:
        writes.append(store.tx_lock(LOGIN, player.username, _owner(player)))
        if old:
            writes.append(store.tx_unlock(LOGIN, old, _owner(player)))
    try:
        store.transact(writes)
    except ConflictError as exc:
        raise Conflict("That username is taken") from exc
    if password is not None:
        end_sessions(store, player_id=player.id)
    return player


def release_account(store: Store, player_id: int) -> Player:
    """Undo a claim (for example someone claimed the wrong player). The team stays."""
    player = _get(store, player_id)
    if not player.username:
        return player
    old = player.username
    player.username = player.password_hash = None
    player.must_change_password = False
    store.transact([store.tx_put(player), store.tx_unlock(LOGIN, old, _owner(player))])
    end_sessions(store, player_id=player.id)
    return player
