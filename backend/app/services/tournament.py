from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Match, Tournament


def get_tournament(db: Session) -> Tournament:
    tournament = db.scalar(select(Tournament).order_by(Tournament.id).limit(1))
    if tournament is None:
        tournament = Tournament()
        db.add(tournament)
        db.flush()
    return tournament


def local_to_utc(tournament: Tournament, day: date, hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    local = datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(tournament.timezone))
    return local.astimezone(UTC)


def schedule_exists(db: Session) -> bool:
    return bool(db.scalar(select(func.count()).select_from(Match)))
