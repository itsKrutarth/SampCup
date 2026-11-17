from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import Db, Staff
from app.api.serializers import match_out
from app.models import Match
from app.services import events, scoring

router = APIRouter(prefix="/judge", tags=["judge"])


class Score(BaseModel):
    score_a: int
    score_b: int


class Final(Score):
    end_reason: str
    sudden_death_winner: str | None = None


class Forfeit(BaseModel):
    winner: str


def _changed(match: Match, warnings: list[str] | None = None) -> dict[str, Any]:
    events.broadcaster.publish("update", scope="scores", match_id=match.id)
    return {**match_out(match), "warnings": warnings or []}


@router.get("/matches")
def matches(user: Staff, db: Db, court: int | None = None) -> dict[str, Any]:
    court = user.court if user.role == "judge" and user.court else court
    query = select(Match).order_by(Match.scheduled_at, Match.court)
    if court:
        query = query.where(Match.court == court)
    rows = db.scalars(query).all()
    current = next((m for m in rows if m.status == "in_progress"), None) or next(
        (m for m in rows if m.status == "scheduled" and m.team_a_id and m.team_b_id), None
    )
    return {
        "court": court,
        "current": match_out(current) if current else None,
        "matches": [match_out(m) for m in rows],
    }


@router.post("/matches/{match_id}/start")
def start(match_id: int, user: Staff, db: Db) -> dict[str, Any]:
    return _changed(scoring.start_match(db, match_id, user))


@router.post("/matches/{match_id}/score")
def score(match_id: int, body: Score, user: Staff, db: Db) -> dict[str, Any]:
    return _changed(scoring.live_score(db, match_id, body.score_a, body.score_b, user))


@router.post("/matches/{match_id}/finish")
def finish(match_id: int, body: Final, user: Staff, db: Db) -> dict[str, Any]:
    match, warnings = scoring.finish_match(
        db, match_id, body.score_a, body.score_b, body.end_reason, user, body.sudden_death_winner
    )
    return _changed(match, warnings)


@router.post("/matches/{match_id}/forfeit")
def forfeit(match_id: int, body: Forfeit, user: Staff, db: Db) -> dict[str, Any]:
    match, warnings = scoring.forfeit_match(db, match_id, body.winner, user)
    return _changed(match, warnings)
