"""Admin commands: python -m app.cli create-admin | seed-demo."""

import argparse
import getpass
import os
import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import get_engine
from app.models import Player, Team
from app.services import schedule
from app.services.auth import create_staff
from app.services.tournament import get_tournament

DEMO_FIRST = [
    "Aarav",
    "Dev",
    "Jay",
    "Kiran",
    "Mihir",
    "Neel",
    "Om",
    "Parth",
    "Raj",
    "Sahil",
    "Tanay",
    "Veer",
    "Yash",
    "Arjun",
    "Harsh",
    "Ishan",
]
DEMO_LAST = ["Demo", "Sample", "Test", "Example", "Fake"]
DEMO_CENTERS = ["Center North", "Center South", "Center East", "Center West", "Center Lake"]


def seed_demo(db: Session, n_teams: int = 40, event_date: date | None = None) -> None:
    """Made-up players and teams (never real data), drawn and scheduled, for dry runs."""
    if db.scalar(select(Player.id).limit(1)):
        raise SystemExit("The database already has players; seed-demo only runs on an empty one")
    rng = random.Random(2026)  # noqa: S311 - demo data
    password = hash_password("demo")
    for t in range(n_teams):
        center = DEMO_CENTERS[t % len(DEMO_CENTERS)]
        team = Team(
            name=f"Demo Team {t + 1}",
            name_key=f"demo team {t + 1}",
            password_hash=password,
            center=center,
            checked_in=True,
        )
        db.add(team)
        db.flush()
        for k in range(2):
            db.add(
                Player(
                    mis_id=f"DEMO{t * 2 + k + 1:04d}",
                    first_name=rng.choice(DEMO_FIRST),
                    last_name=rng.choice(DEMO_LAST),
                    center=center,
                    zone="Demo",
                    team_id=team.id,
                )
            )
    get_tournament(db).event_date = event_date or date.today()
    db.commit()
    schedule.draw_numbers(db, seed=2026)
    schedule.generate_schedule(db)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="create an admin account")
    admin.add_argument("username")
    admin.add_argument("--name", default="")
    demo = commands.add_parser("seed-demo", help="fill an empty database with made-up teams")
    demo.add_argument("--teams", type=int, default=40)
    args = parser.parse_args(argv)
    with sessionmaker(bind=get_engine())() as db:
        if args.command == "create-admin":
            password = os.environ.get("SAMPCUP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
            user = create_staff(db, args.username, password, "admin", args.name)
            print(f"Created admin {user.username}")
        else:
            if get_settings().app_env == "production":
                raise SystemExit("seed-demo never runs in production")
            seed_demo(db, args.teams)
            print(f"Seeded {args.teams} demo teams; every demo team's password is 'demo'")


if __name__ == "__main__":  # pragma: no cover
    main()
