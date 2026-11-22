from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.models import Match, Tournament
from app.store import ConflictError, Store

# A mock run's clock switches itself off after this long, so a forgotten one never reaches
# the real day (restoring the pre-mock snapshot also removes it).
MOCK_CLOCK_LIMIT = timedelta(hours=6)


def _mock_run(tournament: Tournament, real: datetime) -> tuple[datetime, datetime] | None:
    start, day = tournament.mock_started_at, tournament.mock_day_start
    if start and day and start <= real < start + MOCK_CLOCK_LIMIT:
        return start, day
    return None


def tournament_time(tournament: Tournament, real: datetime) -> datetime:
    """The tournament's time at a real time: the same, or a mock run's fast clock."""
    run = _mock_run(tournament, real)
    return run[1] + (real - run[0]) * tournament.mock_speed if run else real


def mock_clock(tournament: Tournament, real: datetime) -> dict[str, Any] | None:
    """A running mock clock for the site to show, else None."""
    run = _mock_run(tournament, real)
    if run is None:
        return None
    started, day = run
    return {
        "started_at": started.isoformat(),
        "day_start": day.isoformat(),
        "speed": tournament.mock_speed,
    }


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
