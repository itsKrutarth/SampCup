"""Take back what organizers recorded in the backup Google Sheet while the app was down.

The sheet (tools/backup-sheet/Code.gs) sends every row changed in it: results, and new times
or courts for games not yet played. Games are applied in the app's schedule order, so a
group result lands before the Round of 16 it decides, and each round's winners fill the
next round before its results arrive. Nothing is guessed: a game whose teams differ from
the app's, or that the app cannot take, is reported back to the sheet, not changed.
"""

import re
from datetime import UTC, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from app.models import Match, StaffUser, Team
from app.services import scoring
from app.services.errors import ServiceError
from app.services.schedule import save_match
from app.services.tournament import get_tournament
from app.store import Store

REASON = "From the backup sheet"
CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*([AaPp][Mm])?\s*$")


def venue_time(text: str, day_of: datetime, timezone: str) -> datetime | None:
    """ "10:15 AM" on the same day as `day_of`, at the venue; None for "" or nonsense.
    Without AM/PM, 7-11 is morning and 12-6 afternoon (the day runs 9 AM to about 8 PM)."""
    match = CLOCK.match(text or "")
    if not match:
        return None
    hour, minute, half = int(match[1]), int(match[2]), (match[3] or "").upper()
    if not (1 <= hour <= 12 and minute < 60):
        return None
    if half:
        hour = hour % 12 + (12 if half == "PM" else 0)
    elif hour < 7:
        hour += 12
    zone = ZoneInfo(timezone)
    day = day_of.astimezone(zone).date()
    return datetime.combine(day, time(hour, minute), tzinfo=zone).astimezone(UTC)


def _apply(
    store: Store, match_id: int, game: dict[str, Any], numbers: dict[int, int], user: StaffUser
) -> dict[str, Any]:
    match = store.get(Match, match_id)  # fresh: earlier games may have filled its teams
    if match is None:  # pragma: no cover - deleted while importing
        return {"applied": [], "skipped": "no such game in the app"}
    timezone = get_tournament(store).timezone
    done: list[str] = []
    if match.status == "scheduled":  # a new court or time only for a game not under way
        when = venue_time(game.get("time") or "", match.scheduled_at, timezone)
        court = game.get("court")
        if (court and court != match.court) or (when and when != match.scheduled_at):
            if court and court != match.court:
                match.court = court
                done.append(f"court {court}")
            if when and when != match.scheduled_at:
                match.scheduled_at = when
                done.append("new time")
            save_match(store, match)
    score_a, score_b, reason = game.get("score_a"), game.get("score_b"), game.get("end_reason")
    if score_a is None or score_b is None or not reason:
        return {"applied": done, "skipped": None if done else "nothing to take"}
    want = (numbers.get(game.get("team_a") or -1), numbers.get(game.get("team_b") or -1))
    if match.team_a_id is None or match.team_b_id is None:
        return {"applied": done, "skipped": "the app does not know this game's teams yet"}
    if (match.team_a_id, match.team_b_id) != want:
        return {"applied": done, "skipped": "the sheet has other teams for this game than the app"}
    seconds = game.get("seconds")
    try:
        if match.status == "completed":
            same = (match.score_a, match.score_b, match.end_reason) == (score_a, score_b, reason)
            if same and (seconds is None or seconds == match.seconds or reason != "reached_11"):
                return {"applied": done, "skipped": None if done else "already in the app"}
            scoring.correct_match(store, match.id, score_a, score_b, reason, seconds, REASON, user)
            done.append("result corrected")
        elif match.status == "cancelled":
            return {"applied": done, "skipped": "the app has this game as not needed"}
        else:
            scoring.record_result(store, match.id, score_a, score_b, reason, seconds, user)
            done.append("result")
    except ServiceError as exc:
        return {"applied": done, "skipped": str(exc)}
    return {"applied": done, "skipped": None}


def import_games(store: Store, games: list[dict[str, Any]], user: StaffUser) -> dict[str, Any]:
    """Apply the sheet's rows; `taken` lists the games the sheet can stop flagging."""
    matches = {m.code: m for m in store.all(Match)}
    numbers = {t.team_number: t.id for t in store.all(Team) if t.team_number is not None}
    report = [
        {"code": g["code"], "applied": [], "skipped": "no such game in the app"}
        for g in games
        if g["code"] not in matches
    ]
    known = sorted(
        (g for g in games if g["code"] in matches),
        key=lambda g: (matches[g["code"]].scheduled_at, matches[g["code"]].court),
    )
    for game in known:
        outcome = _apply(store, matches[game["code"]].id, game, numbers, user)
        report.append({"code": game["code"], **outcome})
    fine = (None, "already in the app", "nothing to take")
    return {
        "games": report,
        "taken": [r["code"] for r in report if r["skipped"] in fine],
        "skipped": [r for r in report if r["skipped"] not in fine],
    }
