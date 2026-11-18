from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import Db, Staff
from app.api.public import ordered
from app.api.serializers import Lookup
from app.models import Match
from app.services import scoring

router = APIRouter(prefix="/judge", tags=["judge"])


class Score(BaseModel):
    score_a: int
    score_b: int


class Final(Score):
    end_reason: str
    sudden_death_winner: str | None = None


class Forfeit(BaseModel):
    winner: str


def _out(store: Db, match: Match, warnings: list[str] | None = None) -> dict[str, Any]:
    return {**Lookup(store).match(match), "warnings": warnings or []}


@router.get("/matches")
def matches(user: Staff, store: Db, court: int | None = None) -> dict[str, Any]:
    court = user.court if user.role == "judge" and user.court else court
    rows = ordered(store.all(Match))
    if court:
        rows = [m for m in rows if m.court == court]
    current = next((m for m in rows if m.status == "in_progress"), None) or next(
        (m for m in rows if m.status == "scheduled" and m.team_a_id and m.team_b_id), None
    )
    look = Lookup(store)
    return {
        "court": court,
        "current": look.match(current) if current else None,
        "matches": [look.match(m) for m in rows],
    }


@router.post("/matches/{match_id}/start")
def start(match_id: int, user: Staff, store: Db) -> dict[str, Any]:
    return _out(store, scoring.start_match(store, match_id, user))


@router.post("/matches/{match_id}/score")
def score(match_id: int, body: Score, user: Staff, store: Db) -> dict[str, Any]:
    return _out(store, scoring.live_score(store, match_id, body.score_a, body.score_b, user))


@router.post("/matches/{match_id}/finish")
def finish(match_id: int, body: Final, user: Staff, store: Db) -> dict[str, Any]:
    match, warnings = scoring.finish_match(
        store, match_id, body.score_a, body.score_b, body.end_reason, user, body.sudden_death_winner
    )
    return _out(store, match, warnings)


@router.post("/matches/{match_id}/forfeit")
def forfeit(match_id: int, body: Forfeit, user: Staff, store: Db) -> dict[str, Any]:
    match, warnings = scoring.forfeit_match(store, match_id, body.winner, user)
    return _out(store, match, warnings)
