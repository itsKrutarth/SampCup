"""Judges' game actions, admin corrections, and moving winners through the bracket."""

from datetime import UTC, datetime
from typing import Any

from app.models import Match, ScoreAudit, StaffUser
from app.services.errors import Conflict, NotFound, ServiceError
from app.services.schedule import save_match
from app.services.standings import group_standings
from app.store import ConflictError, Store
from app.tournament.ranking import CLOCK_CAP, check_game, resolve_clock_end

FIELDS = ("status", "score_a", "score_b", "end_reason", "seconds", "winner_id")


def get_match(store: Store, match_id: int) -> Match:
    match = store.get(Match, match_id)
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
    store: Store, match: Match, action: str, old: dict[str, Any], by: str, reason: str = ""
) -> None:
    store.save(
        ScoreAudit(
            id=store.next_id(ScoreAudit),
            match_id=match.id,
            match_code=match.code,
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


def start_match(store: Store, match_id: int, user: StaffUser) -> Match:
    match = get_match(store, match_id)
    check_court(user, match)
    if match.status == "in_progress":
        return match
    if match.status != "scheduled":
        raise Conflict(f"This game is {match.status}")
    if match.team_a_id is None or match.team_b_id is None:
        raise Conflict("The teams for this game are not known yet")
    if match.prereqs:
        by_code = {m.code: m for m in store.all(Match)}
        for code in match.prereqs:
            before = by_code.get(code)
            if before is not None and before.status not in ("completed", "cancelled"):
                raise Conflict(f"Finish {code} first")
    old = _snapshot(match)
    match.status, match.started_at = "in_progress", datetime.now(UTC)
    match.score_a = match.score_b = 0
    save_match(store, match)
    _audit(store, match, "start", old, user.username)
    return match


def live_score(store: Store, match_id: int, score_a: int, score_b: int, user: StaffUser) -> Match:
    match = get_match(store, match_id)
    check_court(user, match)
    if match.status != "in_progress":
        raise Conflict("Start the game first")
    if not (0 <= score_a <= 11 and 0 <= score_b <= 11):
        raise ServiceError("Scores run from 0 to 11")
    match.score_a, match.score_b = score_a, score_b
    save_match(store, match)
    return match


def finish_match(
    store: Store,
    match_id: int,
    score_a: int,
    score_b: int,
    end_reason: str,
    user: StaffUser,
    sudden_death_winner: str | None = None,
) -> tuple[Match, list[str]]:
    match = get_match(store, match_id)
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
        match = start_match(store, match_id, user)
    elif match.status != "in_progress":
        raise Conflict(f"This game is {match.status}")
    old = _snapshot(match)
    now = datetime.now(UTC)
    elapsed = int((now - match.started_at).total_seconds()) if match.started_at else CLOCK_CAP
    match.ended_at = now
    _set_result(match, score_a, score_b, end_reason, elapsed)
    save_match(store, match)
    _audit(store, match, "final", old, user.username)
    return match, refresh_bracket(store)


def forfeit_match(
    store: Store, match_id: int, winner: str, user: StaffUser
) -> tuple[Match, list[str]]:
    match = get_match(store, match_id)
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
    save_match(store, match)
    _audit(store, match, "forfeit", old, user.username)
    return match, refresh_bracket(store)


def correct_match(
    store: Store,
    match_id: int,
    score_a: int,
    score_b: int,
    end_reason: str,
    seconds: int | None,
    reason: str,
    user: StaffUser,
) -> tuple[Match, list[str]]:
    match = get_match(store, match_id)
    if match.status != "completed":
        raise Conflict("Only final results can be corrected")
    if not reason.strip():
        raise ServiceError("Say why the result is being corrected")
    _validate(score_a, score_b, end_reason)
    old = _snapshot(match)
    kept = seconds if seconds is not None else match.seconds or CLOCK_CAP
    _set_result(match, score_a, score_b, end_reason, kept)
    save_match(store, match)
    _audit(store, match, "correct", old, user.username, reason.strip())
    return match, refresh_bracket(store)


def reset_match(
    store: Store, match_id: int, reason: str, user: StaffUser
) -> tuple[Match, list[str]]:
    """Put a game back to not started (wrong game started, or a result entered by mistake)."""
    match = get_match(store, match_id)
    if match.status == "scheduled":
        return match, []
    if not reason.strip():
        raise ServiceError("Say why the game is being reset")
    old = _snapshot(match)
    match.status = "scheduled"
    match.score_a = match.score_b = match.end_reason = match.seconds = match.winner_id = None
    match.started_at = match.ended_at = None
    save_match(store, match)
    _audit(store, match, "reset", old, user.username, reason.strip())
    return match, refresh_bracket(store)


def _bracket_changes(store: Store) -> tuple[list[Match], list[str]]:
    matches = store.all(Match)
    group_games = [m for m in matches if m.phase == "group"]
    complete = {m.group for m in group_games} - {
        m.group for m in group_games if m.status != "completed"
    }
    places = {}
    if complete:  # standings matter here only once a whole group has finished
        for group, table in group_standings(store, matches=matches).items():
            if group in complete:
                for row in table["rows"][:4]:
                    places[f"{group}{row['rank']}"] = row["team_id"]
    knockout = [m for m in matches if m.phase == "knockout"]
    by_code = {m.code: m for m in knockout}

    def resolve(ref: str | None) -> int | None:
        if ref and ref.startswith("W:"):
            source = by_code.get(ref[2:])
            return source.winner_id if source and source.status == "completed" else None
        return places.get(ref or "")

    changed, warnings = [], []
    for match in sorted(knockout, key=lambda m: (m.scheduled_at, m.court)):
        want = (resolve(match.source_a), resolve(match.source_b))
        if (match.team_a_id, match.team_b_id) == want:
            continue
        if match.status in ("scheduled", "cancelled"):
            match.team_a_id, match.team_b_id = want
            changed.append(match)
        else:
            status = match.status.replace("_", " ")
            warnings.append(f"{match.code} is {status} with other teams; check it")
    f1, f2, f3 = (by_code.get(c) for c in ("F-1", "F-2", "F-3"))
    if f1 and f2 and f3:
        decided = f1.status == f2.status == "completed" and f1.winner_id == f2.winner_id
        if decided and f3.status == "scheduled":
            f3.status = "cancelled"
            changed.append(f3)
        elif not decided and f3.status == "cancelled":
            f3.status = "scheduled"
            changed.append(f3)
    return list({m.id: m for m in changed}.values()), warnings


def refresh_bracket(store: Store, attempts: int = 3) -> list[str]:
    """Fill knockout games from group standings and earlier winners.

    Only games that have not started change. A started game whose teams no longer match
    is reported, not changed, so an admin decides. If two results land at once, the
    later refresh sees both, and a stale write is refused and recomputed."""
    for _ in range(attempts):
        changed, warnings = _bracket_changes(store)
        try:
            for match in changed:
                old = match.version
                match.version += 1
                store.save(match, version=old)
        except ConflictError:
            continue
        return warnings
    return ["The bracket is busy; it updates with the next result"]


def champion_id(store: Store, matches: list[Match] | None = None) -> int | None:
    wins: dict[int, int] = {}
    for match in store.all(Match) if matches is None else matches:
        if match.code in ("F-1", "F-2", "F-3") and match.status == "completed" and match.winner_id:
            wins[match.winner_id] = wins.get(match.winner_id, 0) + 1
    return next((team for team, count in wins.items() if count >= 2), None)
