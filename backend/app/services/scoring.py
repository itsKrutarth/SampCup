"""Judges' game actions, admin corrections, and moving winners through the bracket."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Match, ScoreAudit, StaffUser
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.standings import group_standings
from app.tournament.ranking import CLOCK_CAP, check_game, resolve_clock_end

FIELDS = ("status", "score_a", "score_b", "end_reason", "seconds", "winner_id")


def get_match(db: Session, match_id: int) -> Match:
    match = db.get(Match, match_id)
    if match is None:
        raise NotFound("Match not found")
    return match


def check_court(user: StaffUser, match: Match) -> None:
    if user.role == "judge" and user.court is not None and user.court != match.court:
        raise ServiceError(
            f"You are judging court {user.court}; this game is on court {match.court}"
        )


def _snapshot(match: Match) -> dict[str, Any]:
    return {f: getattr(match, f) for f in FIELDS}


def _audit(
    db: Session, match: Match, action: str, old: dict[str, Any], by: str, reason: str = ""
) -> None:
    db.add(
        ScoreAudit(
            match_id=match.id,
            action=action,
            old_values=old,
            new_values=_snapshot(match),
            changed_by=by,
            reason=reason,
        )
    )


def _validate(score_a: int, score_b: int, end_reason: str) -> None:
    try:
        check_game({"score_a": score_a, "score_b": score_b, "end_reason": end_reason})
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc


def _set_result(match: Match, score_a: int, score_b: int, end_reason: str, seconds: int) -> None:
    match.score_a, match.score_b, match.end_reason = score_a, score_b, end_reason
    match.seconds = seconds if end_reason == "reached_11" else CLOCK_CAP
    match.winner_id = match.team_a_id if score_a > score_b else match.team_b_id
    match.status = "completed"
    match.version += 1


def start_match(db: Session, match_id: int, user: StaffUser) -> Match:
    match = get_match(db, match_id)
    check_court(user, match)
    if match.status == "in_progress":
        return match
    if match.status != "scheduled":
        raise Conflict(f"This game is {match.status}")
    if match.team_a_id is None or match.team_b_id is None:
        raise Conflict("The teams for this game are not known yet")
    for code in match.prereqs:
        before = db.scalar(select(Match).where(Match.code == code))
        if before is not None and before.status not in ("completed", "cancelled"):
            raise Conflict(f"Finish {code} first")
    old = _snapshot(match)
    match.status, match.started_at = "in_progress", datetime.now(UTC)
    match.score_a = match.score_b = 0
    match.version += 1
    _audit(db, match, "start", old, user.username)
    db.commit()
    return match


def live_score(db: Session, match_id: int, score_a: int, score_b: int, user: StaffUser) -> Match:
    match = get_match(db, match_id)
    check_court(user, match)
    if match.status != "in_progress":
        raise Conflict("Start the game first")
    if not (0 <= score_a <= 11 and 0 <= score_b <= 11):
        raise ServiceError("Scores run from 0 to 11")
    match.score_a, match.score_b = score_a, score_b
    match.version += 1
    db.commit()
    return match


def finish_match(
    db: Session,
    match_id: int,
    score_a: int,
    score_b: int,
    end_reason: str,
    user: StaffUser,
    sudden_death_winner: str | None = None,
) -> tuple[Match, list[str]]:
    match = get_match(db, match_id)
    check_court(user, match)
    if end_reason == "forfeit":
        raise ServiceError("Use the forfeit action")
    if end_reason in ("clock_lead", "sudden_death"):
        try:
            score_a, score_b = resolve_clock_end(score_a, score_b, sudden_death_winner)
        except ValueError as exc:
            raise ServiceError(str(exc)) from exc
        if sudden_death_winner in ("a", "b"):
            end_reason = "sudden_death"
    _validate(score_a, score_b, end_reason)
    if match.status == "completed":
        if (match.score_a, match.score_b, match.end_reason) == (score_a, score_b, end_reason):
            return match, []  # the same result sent twice (offline retry)
        raise Conflict("This game is already final. Ask an admin to correct it.")
    if match.status == "scheduled":
        start_match(db, match_id, user)
    elif match.status != "in_progress":
        raise Conflict(f"This game is {match.status}")
    old = _snapshot(match)
    now = datetime.now(UTC)
    elapsed = int((now - match.started_at).total_seconds()) if match.started_at else CLOCK_CAP
    match.ended_at = now
    _set_result(match, score_a, score_b, end_reason, elapsed)
    _audit(db, match, "final", old, user.username)
    warnings = refresh_bracket(db)
    db.commit()
    return match, warnings


def forfeit_match(
    db: Session, match_id: int, winner: str, user: StaffUser
) -> tuple[Match, list[str]]:
    match = get_match(db, match_id)
    check_court(user, match)
    if winner not in ("a", "b"):
        raise ServiceError("Winner must be a or b")
    if match.status in ("completed", "cancelled"):
        raise Conflict(f"This game is {match.status}")
    if match.team_a_id is None or match.team_b_id is None:
        raise Conflict("The teams for this game are not known yet")
    old = _snapshot(match)
    match.ended_at = datetime.now(UTC)
    _set_result(match, *((11, 0) if winner == "a" else (0, 11)), "forfeit", CLOCK_CAP)
    _audit(db, match, "forfeit", old, user.username)
    warnings = refresh_bracket(db)
    db.commit()
    return match, warnings


def correct_match(
    db: Session,
    match_id: int,
    score_a: int,
    score_b: int,
    end_reason: str,
    seconds: int | None,
    reason: str,
    user: StaffUser,
) -> tuple[Match, list[str]]:
    match = get_match(db, match_id)
    if match.status != "completed":
        raise Conflict("Only final results can be corrected")
    if not reason.strip():
        raise ServiceError("Say why the result is being corrected")
    _validate(score_a, score_b, end_reason)
    old = _snapshot(match)
    _set_result(
        match,
        score_a,
        score_b,
        end_reason,
        seconds if seconds is not None else match.seconds or CLOCK_CAP,
    )
    _audit(db, match, "correct", old, user.username, reason.strip())
    warnings = refresh_bracket(db)
    db.commit()
    return match, warnings


def reset_match(
    db: Session, match_id: int, reason: str, user: StaffUser
) -> tuple[Match, list[str]]:
    """Put a game back to not started (wrong game started, or a result entered by mistake)."""
    match = get_match(db, match_id)
    if match.status == "scheduled":
        return match, []
    if not reason.strip():
        raise ServiceError("Say why the game is being reset")
    old = _snapshot(match)
    match.status = "scheduled"
    match.score_a = match.score_b = match.end_reason = match.seconds = match.winner_id = None
    match.started_at = match.ended_at = None
    match.version += 1
    _audit(db, match, "reset", old, user.username, reason.strip())
    warnings = refresh_bracket(db)
    db.commit()
    return match, warnings


def refresh_bracket(db: Session) -> list[str]:
    """Fill knockout games from group standings and earlier winners.

    Only games that have not started change. A started game whose teams no longer match
    is reported, not changed, so an admin decides."""
    db.flush()
    places = {}
    for group, table in group_standings(db).items():
        if table["complete"]:
            for row in table["rows"][:4]:
                places[f"{group}{row['rank']}"] = row["team_id"]
    knockout = db.scalars(select(Match).where(Match.phase == "knockout")).all()
    by_code = {m.code: m for m in knockout}

    def resolve(ref: str | None) -> int | None:
        if ref and ref.startswith("W:"):
            source = by_code.get(ref[2:])
            return source.winner_id if source and source.status == "completed" else None
        return places.get(ref or "")

    warnings = []
    for match in sorted(knockout, key=lambda m: (m.scheduled_at, m.court)):
        want = (resolve(match.source_a), resolve(match.source_b))
        if (match.team_a_id, match.team_b_id) == want:
            continue
        if match.status in ("scheduled", "cancelled"):
            match.team_a_id, match.team_b_id = want
            match.version += 1
        else:
            warnings.append(
                f"{match.code} is {match.status.replace('_', ' ')} with other teams; check it"
            )
    f1, f2, f3 = (by_code.get(c) for c in ("F-1", "F-2", "F-3"))
    if f1 and f2 and f3:
        decided = f1.status == f2.status == "completed" and f1.winner_id == f2.winner_id
        if decided and f3.status == "scheduled":
            f3.status = "cancelled"
            f3.version += 1
        elif not decided and f3.status == "cancelled":
            f3.status = "scheduled"
            f3.version += 1
    db.flush()
    return warnings


def champion_id(db: Session) -> int | None:
    wins: dict[int, int] = {}
    for match in db.scalars(select(Match).where(Match.code.in_(["F-1", "F-2", "F-3"]))):
        if match.status == "completed" and match.winner_id:
            wins[match.winner_id] = wins.get(match.winner_id, 0) + 1
    return next((team for team, count in wins.items() if count >= 2), None)
