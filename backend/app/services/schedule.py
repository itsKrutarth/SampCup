"""Team-number draw, loading a precomputed schedule, court changes and delays."""

import random
import secrets
from datetime import datetime, timedelta

from app.models import Delay, Match, ScoreAudit, Team
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.tournament import get_tournament, local_to_utc, schedule_exists
from app.store import ConflictError, Store
from app.tournament.templates import MAX_TEAMS, MIN_TEAMS, load_template

CHANGED = "This game was just changed on another device. Reload and try again."


def draw_numbers(store: Store, seed: int | None = None) -> list[Team]:
    """Randomly number the checked-in active teams 1..N; numbers decide the groups."""
    tournament = get_tournament(store)
    if schedule_exists(store):
        raise Conflict("Clear the schedule before drawing again")
    all_teams = store.all(Team)
    teams = [t for t in all_teams if t.status == "active" and t.checked_in]
    if not MIN_TEAMS <= len(teams) <= MAX_TEAMS:
        raise ServiceError(
            f"{len(teams)} active teams are checked in; the draw needs {MIN_TEAMS}-{MAX_TEAMS}"
        )
    for team in all_teams:
        team.team_number, team.group = None, None
    seed = secrets.randbelow(2**31) if seed is None else seed
    order = list(teams)
    random.Random(seed).shuffle(order)  # noqa: S311 - a fair, repeatable draw; seed is stored
    groups = load_template(len(order))["groups"]
    group_of = {number: letter for letter, numbers in groups.items() for number in numbers}
    for number, team in enumerate(order, start=1):
        team.team_number, team.group = number, group_of[number]
    store.save_many(all_teams)
    tournament.draw_seed = seed
    store.save(tournament)
    return order


def _clear_matches(store: Store, teams: list[Team]) -> None:
    store.delete_kind(ScoreAudit)
    store.delete_kind(Match)
    cleared = [t for t in teams if t.lunch_start is not None]
    for team in cleared:
        team.lunch_start = None
    store.save_many(cleared)


def generate_schedule(store: Store) -> int:
    tournament = get_tournament(store)
    if tournament.schedule_locked:
        raise Conflict("The schedule is locked")
    if tournament.event_date is None:
        raise ServiceError("Set the event date first")
    teams = [t for t in store.all(Team) if t.team_number is not None]
    if not teams:
        raise ServiceError("Draw team numbers first")
    template = load_template(len(teams))
    by_number = {t.team_number: t for t in teams}
    if sorted(by_number) != list(range(1, len(teams) + 1)):
        raise ServiceError("Team numbers have gaps; draw again")
    _clear_matches(store, teams)
    day = tournament.event_date

    def when(hhmm: str) -> datetime:
        return local_to_utc(tournament, day, hhmm)

    total = len(template["pool"]) + len(template["knockout"])
    next_id = store.next_id(Match, total)
    matches = []
    for i, row in enumerate(template["pool"], start=1):
        matches.append(
            Match(
                id=next_id + i - 1,
                code=f"G{i:03d}",
                phase="group",
                group=row["group"],
                round_label=f"Group {row['group']}",
                slot=row["slot"],
                court=row["court"],
                scheduled_at=when(row["time"]),
                team_a_id=by_number[row["team_a"]].id,
                team_b_id=by_number[row["team_b"]].id,
            )
        )
    for j, row in enumerate(template["knockout"]):
        matches.append(
            Match(
                id=next_id + len(template["pool"]) + j,
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
    store.save_many(matches)
    for number, team in by_number.items():
        team.lunch_start = when(template["lunch"][str(number)])
    store.save_many(teams)
    return total


def clear_schedule(store: Store) -> None:
    if get_tournament(store).schedule_locked:
        raise Conflict("The schedule is locked")
    _clear_matches(store, store.all(Team))


def set_locked(store: Store, locked: bool) -> None:
    tournament = get_tournament(store)
    if locked and not schedule_exists(store):
        raise ServiceError("Generate the schedule first")
    if not locked and any(m.status != "scheduled" for m in store.all(Match)):
        raise Conflict("Games have started; the schedule stays locked")
    tournament.schedule_locked = locked
    store.save(tournament)


def save_match(store: Store, match: Match) -> None:
    """Write a changed game unless someone else changed it since it was read."""
    old = match.version
    match.version += 1
    try:
        store.save(match, version=old)
    except ConflictError as exc:
        raise Conflict(CHANGED) from exc


def set_court(store: Store, match_id: int, court: int) -> Match:
    match = store.get(Match, match_id)
    if match is None:
        raise NotFound("Match not found")
    if not 1 <= court <= 9:
        raise ServiceError("Court must be 1-9")
    if match.status in ("completed", "cancelled"):
        raise Conflict("This game is over")
    match.court = court
    save_match(store, match)
    return match


def apply_delay(store: Store, minutes: int, from_time: datetime, by: str) -> dict[str, object]:
    """Push every not-yet-started game at or after `from_time` by `minutes`."""
    if minutes == 0 or not -60 <= minutes <= 120:
        raise ServiceError("Delay must be between -60 and 120 minutes, and not 0")
    tournament = get_tournament(store)
    matches = store.all(Match)
    if tournament.event_date is None or not matches:
        raise ServiceError("There is no schedule to shift")
    shift = timedelta(minutes=minutes)
    moved, skipped = [], 0
    for match in matches:
        if match.status == "scheduled" and match.scheduled_at >= from_time:
            match.scheduled_at += shift
            try:
                save_match(store, match)  # a game starting right now keeps its time
                moved.append(match)
            except Conflict:
                skipped += 1
    store.save(
        Delay(
            id=store.next_id(Delay),
            minutes=minutes,
            applied_from=from_time,
            matches_moved=len(moved),
            created_by=by,
        )
    )
    numbered = sum(t.team_number is not None for t in store.all(Team))
    template = load_template(numbered)
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
    if skipped:
        warnings.append(f"{skipped} game(s) started while shifting and kept their time")
    return {"moved": len(moved), "warnings": warnings}
