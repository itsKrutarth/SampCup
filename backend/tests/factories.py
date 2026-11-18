"""Made-up test data (never real players)."""

import io
from datetime import date
from typing import Any, TypeVar

from openpyxl import Workbook

from app.cli import seed_demo
from app.core.security import hash_password
from app.models import Player, Team
from app.services.teams import NAME, name_key
from app.store import Record, Store

R = TypeVar("R", bound=Record)

HEADER = [
    "Region",
    "Event",
    "Center",
    "Zone",
    "FirstName",
    "LastName",
    "Gender",
    "MISID",
    "What is your TShirt Size?",
]
EVENT_DATE = date(2026, 12, 6)


def xlsx(rows: list[list[object]], header: list[str] = HEADER) -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def row(mis_id: object, first: str, last: str = "Tester", center: str = "North") -> list[object]:
    return ["Northeast", "Test Cup", center, "Zone 1", first, last, "Male", mis_id, "Large"]


_counter = iter(range(1, 100_000))


def make_player(store: Store, first: str = "Player", center: str = "North", **kw: Any) -> Player:
    n = next(_counter)
    player = Player(
        id=store.next_id(Player),
        mis_id=f"T{n:05d}",
        first_name=f"{first}{n}",
        last_name="Tester",
        center=center,
        **kw,
    )
    store.save(player)
    return player


def make_team(
    store: Store,
    name: str | None = None,
    status: str = "active",
    checked_in: bool = True,
    center: str = "North",
) -> Team:
    name = name or f"Team {next(_counter)}"
    team = Team(
        id=store.next_id(Team),
        name=name,
        name_key=name_key(name),
        center=center,
        status=status,
        checked_in=checked_in,
    )
    store.save(team)
    store.transact([store.tx_lock(NAME, team.name_key, f"team:{team.id}")])
    for _ in range(2):
        make_player(store, center=center, team_id=team.id)
    return team


def give_login(store: Store, player: Player, password: str = "secret1") -> str:
    """An account the player chose themselves (not a temporary one)."""
    from app.services.accounts import LOGIN

    player.username = f"user{player.id}"
    player.password_hash = hash_password(password)
    store.transact(
        [store.tx_put(player), store.tx_lock(LOGIN, player.username, f"player:{player.id}")]
    )
    return player.username


def player_headers(client: Any, store: Store, player: Player) -> dict[str, str]:
    username = player.username or give_login(store, player)
    response = client.post(
        "/api/auth/player-login", json={"username": username, "password": "secret1"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def members(store: Store, team: Team) -> list[Player]:
    return [p for p in store.all(Player) if p.team_id == team.id]


def find[R: Record](store: Store, cls: type[R], **attrs: Any) -> R:
    return next(r for r in store.all(cls) if all(getattr(r, k) == v for k, v in attrs.items()))


def seeded(store: Store, n_teams: int = 40) -> None:
    seed_demo(store, n_teams, EVENT_DATE)
