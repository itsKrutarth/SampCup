from datetime import datetime
from functools import cached_property
from typing import Any

from app.models import Announcement, Match, PartnerRequest, Player, StaffUser, Team
from app.store import Store

PLACES = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def describe(ref: str | None) -> str | None:
    if not ref:
        return None
    if ref.startswith("W:"):
        return f"Winner of {ref[2:]}"
    return f"Group {ref[0]} {PLACES.get(ref[1:], ref[1:])}"


def team_brief(team: Team | None) -> dict[str, Any] | None:
    if team is None:
        return None
    return {"id": team.id, "name": team.name, "number": team.team_number, "group": team.group}


def player_out(player: Player, admin: bool = False, team: Team | None = None) -> dict[str, Any]:
    out = {
        "id": player.id,
        "first_name": player.first_name,
        "last_name": player.last_name,
        "center": player.center,
        "zone": player.zone,
    }
    if admin:
        out |= {
            "mis_id": player.mis_id,
            "baps_id": player.baps_id,
            "region": player.region,
            "gender": player.gender,
            "tshirt_size": player.tshirt_size,
            "active": player.active,
            "team": team_brief(team),
            "username": player.username,
            "must_change_password": player.must_change_password,
        }
    return out


def staff_out(user: StaffUser) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "court": user.court,
        "active": user.active,
        "must_change_password": user.must_change_password,
    }


def announcement_out(item: Announcement) -> dict[str, Any]:
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "active": item.active,
        "created_at": iso(item.created_at),
    }


class Lookup:
    """Per-request access to teams and players, loaded once, for building responses."""

    def __init__(self, store: Store) -> None:
        self.store = store

    @cached_property
    def teams(self) -> dict[int, Team]:
        return {t.id: t for t in self.store.all(Team)}

    @cached_property
    def players(self) -> dict[int, Player]:
        return {p.id: p for p in self.store.all(Player)}

    def team_of(self, team_id: int | None) -> Team | None:
        return self.teams.get(team_id) if team_id else None

    def team(self, team: Team, admin: bool = False) -> dict[str, Any]:
        members = [p for p in self.players.values() if p.team_id == team.id]
        out = {
            **(team_brief(team) or {}),
            "center": team.center,
            "status": team.status,
            "lunch_start": iso(team.lunch_start),
            "players": [{"id": p.id, "name": p.full_name} for p in members],
        }
        if admin:
            out["checked_in"] = team.checked_in
            out["created_at"] = iso(team.created_at)
        return out

    def player(self, player: Player, admin: bool = False) -> dict[str, Any]:
        return player_out(player, admin, self.team_of(player.team_id))

    def request(self, request: PartnerRequest) -> dict[str, Any]:
        return {
            "id": request.id,
            "team_name": request.team_name,
            "status": request.status,
            "from": player_out(self.players[request.from_player_id]),
            "to": player_out(self.players[request.to_player_id]),
            "created_at": iso(request.created_at),
        }

    def match(self, match: Match) -> dict[str, Any]:
        return {
            "id": match.id,
            "code": match.code,
            "phase": match.phase,
            "group": match.group,
            "round": match.round_label,
            "court": match.court,
            "scheduled_at": iso(match.scheduled_at),
            "status": match.status,
            "team_a": team_brief(self.team_of(match.team_a_id)),
            "team_b": team_brief(self.team_of(match.team_b_id)),
            "source_a": describe(match.source_a),
            "source_b": describe(match.source_b),
            "score_a": match.score_a,
            "score_b": match.score_b,
            "end_reason": match.end_reason,
            "seconds": match.seconds,
            "winner_id": match.winner_id,
            "started_at": iso(match.started_at),
            "ended_at": iso(match.ended_at),
            "prereqs": match.prereqs,
            "version": match.version,
        }
