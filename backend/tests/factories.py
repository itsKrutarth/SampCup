"""Made-up test data (never real players)."""

import io
from datetime import date

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.cli import seed_demo
from app.core.security import hash_password
from app.models import Player, Team

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
EVENT_DATE = date(2026, 12, 12)


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


_counter = iter(range(1, 10_000))


def make_player(db: Session, first: str = "Player", center: str = "North", **kw: object) -> Player:
    n = next(_counter)
    player = Player(
        mis_id=f"T{n:05d}", first_name=f"{first}{n}", last_name="Tester", center=center, **kw
    )
    db.add(player)
    db.commit()
    return player


_hash = hash_password("pass")


def make_team(
    db: Session,
    name: str | None = None,
    status: str = "active",
    checked_in: bool = True,
    center: str = "North",
) -> Team:
    n = next(_counter)
    name = name or f"Team {n}"
    team = Team(
        name=name,
        name_key=name.casefold(),
        password_hash=_hash,
        center=center,
        status=status,
        checked_in=checked_in,
    )
    db.add(team)
    db.flush()
    for _ in range(2):
        make_player(db, center=center).team_id = team.id
    db.commit()
    return team


def seeded(db: Session, n_teams: int = 40) -> None:
    seed_demo(db, n_teams, EVENT_DATE)
