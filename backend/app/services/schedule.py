"""Team-number draw, loading a precomputed schedule, court changes and delays."""

import random
import secrets
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Delay, Match, ScoreAudit, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.tournament import get_tournament, local_to_utc, schedule_exists
from app.tournament.templates import MAX_TEAMS, MIN_TEAMS, load_template


def draw_numbers(db: Session, seed: int | None = None) -> list[Team]:
    """Randomly number the checked-in active teams 1..N; numbers decide the groups."""
    tournament = get_tournament(db)
    if schedule_exists(db):
        raise Conflict("Clear the schedule before drawing again")
    teams = db.scalars(
        select(Team).where(Team.status == "active", Team.checked_in).order_by(Team.id)
    ).all()
    if not MIN_TEAMS <= len(teams) <= MAX_TEAMS:
        raise ServiceError(
            f"{len(teams)} active teams are checked in; the draw needs {MIN_TEAMS}-{MAX_TEAMS}"
        )
    for team in db.scalars(select(Team).where(Team.team_number.is_not(None))):
        team.team_number, team.group = None, None
    db.flush()
    seed = secrets.randbelow(2**31) if seed is None else seed
    order = list(teams)
    random.Random(seed).shuffle(order)  # noqa: S311 - a fair, repeatable draw; seed is stored
    groups = load_template(len(order))["groups"]
    group_of = {number: letter for letter, numbers in groups.items() for number in numbers}
    for number, team in enumerate(order, start=1):
        team.team_number, team.group = number, group_of[number]
    tournament.draw_seed = seed
    db.commit()
    return sorted(order, key=lambda t: t.team_number or 0)


def _clear_matches(db: Session) -> None:
    db.execute(delete(ScoreAudit))
    db.execute(delete(Match))
    for team in db.scalars(select(Team).where(Team.lunch_start.is_not(None))):
        team.lunch_start = None


def generate_schedule(db: Session) -> int:
    tournament = get_tournament(db)
    if tournament.schedule_locked:
        raise Conflict("The schedule is locked")
    if tournament.event_date is None:
        raise ServiceError("Set the event date first")
    teams = db.scalars(select(Team).where(Team.team_number.is_not(None))).all()
    if not teams:
        raise ServiceError("Draw team numbers first")
    template = load_template(len(teams))
    by_number = {t.team_number: t for t in teams}
    if sorted(by_number) != list(range(1, len(teams) + 1)):
        raise ServiceError("Team numbers have gaps; draw again")
    _clear_matches(db)
    day = tournament.event_date

    def when(hhmm: str) -> datetime:
        return local_to_utc(tournament, day, hhmm)

    for i, row in enumerate(template["pool"], start=1):
        db.add(
            Match(
                code=f"G{i:03d}",
                phase="group",
                group=row["group"],
                round_label=f"Group {row['group']}",
                slot=row["slot"],
                court=row["court"],
                scheduled_at=when(row["time"]),
                team_a_id=by_number[row["team_a"]].id,
                team_b_id=by_number[row["team_b"]].id,
                prereqs=[],
            )
        )
    for row in template["knockout"]:
        db.add(
            Match(
                code=row["code"],
                phase="knockout",
                round_label=row["round"],
                court=row["court"],
                scheduled_at=when(row["time"]),
                source_a=row["source_a"],
                source_b=row["source_b"],
                prereqs=row["prereqs"],
                winner_goes_to=row["winner_goes_to"],
            )
        )
    for number, team in by_number.items():
        team.lunch_start = when(template["lunch"][str(number)])
    db.commit()
    return len(template["pool"]) + len(template["knockout"])


def clear_schedule(db: Session) -> None:
    if get_tournament(db).schedule_locked:
        raise Conflict("The schedule is locked")
    _clear_matches(db)
    db.commit()


def set_locked(db: Session, locked: bool) -> None:
    tournament = get_tournament(db)
    if locked and not schedule_exists(db):
        raise ServiceError("Generate the schedule first")
    if not locked and db.scalar(select(Match.id).where(Match.status != "scheduled").limit(1)):
        raise Conflict("Games have started; the schedule stays locked")
    tournament.schedule_locked = locked
    db.commit()


def set_court(db: Session, match_id: int, court: int) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise NotFound("Match not found")
    if not 1 <= court <= 9:
        raise ServiceError("Court must be 1-9")
    if match.status in ("completed", "cancelled"):
        raise Conflict("This game is over")
    match.court = court
    match.version += 1
    db.commit()
    return match


def apply_delay(db: Session, minutes: int, from_time: datetime, by: str) -> dict[str, object]:
    """Push every not-yet-started game at or after `from_time` by `minutes`."""
    if minutes == 0 or not -60 <= minutes <= 120:
        raise ServiceError("Delay must be between -60 and 120 minutes, and not 0")
    tournament = get_tournament(db)
    if tournament.event_date is None or not schedule_exists(db):
        raise ServiceError("There is no schedule to shift")
    moved = db.scalars(
        select(Match).where(Match.status == "scheduled", Match.scheduled_at >= from_time)
    ).all()
    shift = timedelta(minutes=minutes)
    for match in moved:
        match.scheduled_at += shift
        match.version += 1
    db.add(Delay(minutes=minutes, applied_from=from_time, matches_moved=len(moved), created_by=by))
    teams = db.scalars(select(Team).where(Team.team_number.is_not(None))).all()
    template = load_template(len(teams))
    game = timedelta(minutes=template["game_minutes"])
    day = tournament.event_date
    sabha_start = local_to_utc(tournament, day, template["sabha"][0])
    sabha_end = local_to_utc(tournament, day, template["sabha"][1])
    day_end = local_to_utc(tournament, day, "18:40")
    warnings = []
    for match in sorted(moved, key=lambda m: m.scheduled_at):
        start, end = match.scheduled_at, match.scheduled_at + game
        if start < sabha_end and end > sabha_start:
            warnings.append(f"{match.code} now overlaps Sabha")
        elif end > day_end:
            warnings.append(f"{match.code} now ends after 6:40 PM")
    db.commit()
    return {"moved": len(moved), "warnings": warnings}
