from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow

TEAM_STATUSES = ("active", "waitlist", "withdrawn")
REQUEST_STATUSES = ("pending", "accepted", "declined", "cancelled")
MATCH_STATUSES = ("scheduled", "in_progress", "completed", "cancelled")
ROLES = ("admin", "judge")


class Tournament(Base):
    """The one tournament this deployment runs."""

    __tablename__ = "tournament"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), default="SAMP Cup 2026")
    event_date: Mapped[date | None]
    timezone: Mapped[str] = mapped_column(String(50), default="America/New_York")
    registration_open: Mapped[bool] = mapped_column(default=True)
    team_cap: Mapped[int] = mapped_column(default=42)
    draw_seed: Mapped[int | None]
    schedule_locked: Mapped[bool] = mapped_column(default=False)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    mis_id: Mapped[str] = mapped_column(String(32), unique=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    center: Mapped[str] = mapped_column(String(80), index=True)
    zone: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    gender: Mapped[str] = mapped_column(String(20), default="")
    tshirt_size: Mapped[str] = mapped_column(String(20), default="")
    active: Mapped[bool] = mapped_column(default=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    team: Mapped["Team | None"] = relationship(back_populates="players")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    name_key: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    center: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="active")
    checked_in: Mapped[bool] = mapped_column(default=False)
    team_number: Mapped[int | None] = mapped_column(unique=True)
    group: Mapped[str | None] = mapped_column(String(1))
    lunch_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    players: Mapped[list[Player]] = relationship(back_populates="team", order_by=Player.id)


class PartnerRequest(Base):
    """Player A asks player B to form a team; the team exists once B accepts."""

    __tablename__ = "partner_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    to_player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    team_name: Mapped[str] = mapped_column(String(40))
    name_key: Mapped[str] = mapped_column(String(40))
    password_hash: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    from_player: Mapped[Player] = relationship(foreign_keys=[from_player_id])
    to_player: Mapped[Player] = relationship(foreign_keys=[to_player_id])


class StaffUser(Base):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(10))
    password_hash: Mapped[str] = mapped_column(String(200))
    court: Mapped[int | None]
    active: Mapped[bool] = mapped_column(default=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id", ondelete="CASCADE"))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    staff: Mapped[StaffUser | None] = relationship()
    team: Mapped[Team | None] = relationship()


class Match(Base):
    """One game: a group game, a knockout game, or one game of the best-of-3 Final."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    phase: Mapped[str] = mapped_column(String(10))
    group: Mapped[str | None] = mapped_column(String(1))
    round_label: Mapped[str] = mapped_column(String(40))
    slot: Mapped[int | None]
    court: Mapped[int]
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    source_a: Mapped[str | None] = mapped_column(String(10))
    source_b: Mapped[str | None] = mapped_column(String(10))
    team_a_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    team_b_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    prereqs: Mapped[list[str]] = mapped_column(JSON, default=list)
    winner_goes_to: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    score_a: Mapped[int | None]
    score_b: Mapped[int | None]
    end_reason: Mapped[str | None] = mapped_column(String(20))
    seconds: Mapped[int | None]
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    version: Mapped[int] = mapped_column(default=1)

    team_a: Mapped[Team | None] = relationship(foreign_keys=[team_a_id])
    team_b: Mapped[Team | None] = relationship(foreign_keys=[team_b_id])


class ScoreAudit(Base):
    """Append-only record of every result change."""

    __tablename__ = "score_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20))
    old_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    new_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text, default="")
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Delay(Base):
    __tablename__ = "delays"

    id: Mapped[int] = mapped_column(primary_key=True)
    minutes: Mapped[int]
    applied_from: Mapped[datetime] = mapped_column(UTCDateTime)
    matches_moved: Mapped[int]
    created_by: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
