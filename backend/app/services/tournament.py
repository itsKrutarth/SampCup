from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.models import Match, Tournament
from app.store import ConflictError, Store


def get_tournament(store: Store) -> Tournament:
    tournament = store.get(Tournament, 1)
    if tournament is None:
        tournament = Tournament()
        try:
            store.save(tournament, create=True)
        except ConflictError:  # pragma: no cover - two first requests at once
            tournament = store.get(Tournament, 1) or tournament
    return tournament


def local_to_utc(tournament: Tournament, day: date, hhmm: str) -> datetime:
    hour, minute = map(int, hhmm.split(":"))
    local = datetime.combine(day, time(hour, minute), tzinfo=ZoneInfo(tournament.timezone))
    return local.astimezone(UTC)


def schedule_exists(store: Store) -> bool:
    return store.exists(Match)
