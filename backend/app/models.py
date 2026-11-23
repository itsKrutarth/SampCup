"""Tournament records (stored in DynamoDB through app.store)."""

import dataclasses
import datetime as dt
from typing import Any

from app.store import Record, utcnow

TEAM_STATUSES = ("active", "waitlist", "withdrawn")


@dataclasses.dataclass(kw_only=True)
class Tournament(Record):
    """The one tournament this deployment runs (id 1)."""

    KIND = "TOURNAMENT"
    id: int = 1
    name: str = "SAMP Cup 2026"
    subtitle: str = "Yuvak Mandal"
    venue_name: str = "Rt. 12 Pickle"
    venue_address: str = "184 W. Boylston St, West Boylston, MA 01583"
    age_group: str = "22-35"
    # Who to ask, as the admin types it (kept in the database, not in the public repo).
    contacts: str = ""
    event_date: dt.date | None = None
    timezone: str = "America/New_York"
    registration_open: bool = True
    team_cap: int = 42
    draw_seed: int | None = None
    schedule_locked: bool = False
    # A mock run's fast clock (tools/mock_tournament.py): from mock_started_at (real time) the
    # tournament's time reads mock_day_start, running mock_speed times faster. Unset otherwise.
    mock_started_at: dt.datetime | None = None
    mock_day_start: dt.datetime | None = None
    mock_speed: float = 1.0
    # The backup Google Sheet (tools/backup-sheet), linked from Admin > Overview. Admins only.
    backup_sheet_url: str = ""


@dataclasses.dataclass(kw_only=True)
class Player(Record):
    KIND = "PLAYER"
    id: int
    first_name: str
    last_name: str
    center: str
    # The export's identifiers, each optional (owner, 2026-11-23: the key is first name, last
    # name and center; these only tell apart people that key cannot). Email is kept only as a
    # one-way fingerprint (app.services.players.email_key), never as readable text.
    mis_id: str = ""
    baps_id: str = ""
    email_key: str = ""
    zone: str = ""
    region: str = ""
    gender: str = ""
    tshirt_size: str = ""
    active: bool = True
    team_id: int | None = None
    # The player's own login, set when they claim their account (or by an admin).
    username: str | None = None
    password_hash: str | None = None
    must_change_password: bool = False

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclasses.dataclass(kw_only=True)
class Team(Record):
    KIND = "TEAM"
    id: int
    name: str
    name_key: str
    center: str
    password_hash: str = ""  # unused: players log in with their own accounts
    status: str = "active"
    checked_in: bool = False
    team_number: int | None = None
    group: str | None = None
    lunch_start: dt.datetime | None = None
    created_at: dt.datetime = dataclasses.field(default_factory=utcnow)


@dataclasses.dataclass(kw_only=True)
class PartnerRequest(Record):
    """Player A asks player B to form a team; the team exists once B accepts."""

    KIND = "REQUEST"
    id: int
    from_player_id: int
    to_player_id: int
    team_name: str
    name_key: str
    password_hash: str = ""  # unused: players log in with their own accounts
    status: str = "pending"
    created_at: dt.datetime = dataclasses.field(default_factory=utcnow)
    resolved_at: dt.datetime | None = None


@dataclasses.dataclass(kw_only=True)
class StaffUser(Record):
    KIND = "STAFF"
    id: int
    username: str
    display_name: str
    role: str
    password_hash: str
    court: int | None = None
    active: bool = True
    # Set when an admin chooses the password: the user must pick their own at next login.
    must_change_password: bool = False


@dataclasses.dataclass(kw_only=True)
class Session(Record):
    """A login. `id` is the SHA-256 of the token; `ttl` lets DynamoDB expire it."""

    KIND = "SESSION"
    id: str
    staff_id: int | None = None
    team_id: int | None = None
    player_id: int | None = None
    expires_at: dt.datetime
    ttl: int


@dataclasses.dataclass(kw_only=True)
class Match(Record):
    """One game: a group game, a knockout game, or one game of the best-of-3 Final."""

    KIND = "MATCH"
    id: int
    code: str
    phase: str
    group: str | None = None
    round_label: str
    slot: int | None = None
    court: int
    scheduled_at: dt.datetime
    source_a: str | None = None
    source_b: str | None = None
    team_a_id: int | None = None
    team_b_id: int | None = None
    prereqs: list[str] = dataclasses.field(default_factory=list)
    winner_goes_to: str | None = None
    status: str = "scheduled"
    score_a: int | None = None
    score_b: int | None = None
    end_reason: str | None = None
    seconds: int | None = None
    winner_id: int | None = None
    started_at: dt.datetime | None = None
    ended_at: dt.datetime | None = None
    version: int = 1


@dataclasses.dataclass(kw_only=True)
class ScoreAudit(Record):
    """Append-only record of every result change."""

    KIND = "AUDIT"
    id: int
    match_id: int
    match_code: str
    action: str
    old_values: dict[str, Any]
    new_values: dict[str, Any]
    changed_by: str
    reason: str = ""
    changed_at: dt.datetime = dataclasses.field(default_factory=utcnow)


@dataclasses.dataclass(kw_only=True)
class Announcement(Record):
    KIND = "ANNOUNCEMENT"
    id: int
    title: str
    body: str = ""
    active: bool = True
    created_by: str
    created_at: dt.datetime = dataclasses.field(default_factory=utcnow)


@dataclasses.dataclass(kw_only=True)
class Delay(Record):
    KIND = "DELAY"
    id: int
    minutes: int
    applied_from: dt.datetime
    matches_moved: int
    created_by: str
    created_at: dt.datetime = dataclasses.field(default_factory=utcnow)
