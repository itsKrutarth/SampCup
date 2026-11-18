"""Admin commands, run with AWS credentials (or against DynamoDB Local):

python -m app.cli create-admin <username>      # asks for the password
python -m app.cli create-judges [--courts 9]   # court-1..court-9 with random PINs
python -m app.cli reset-data --yes [--keep-staff] [--event-date 2026-12-06]
python -m app.cli seed-demo [--teams 40]       # made-up teams, never real data
python -m app.cli create-table                 # DynamoDB Local only
"""

import argparse
import getpass
import os
import random
import secrets
from datetime import date

from app.core.config import get_settings
from app.models import Player, StaffUser, Team
from app.services import schedule
from app.services.auth import USERNAME, create_staff
from app.services.errors import Conflict
from app.services.teams import NAME
from app.services.tournament import get_tournament
from app.store import Store, create_table, dynamodb_resource, get_table

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


def seed_demo(store: Store, n_teams: int = 40, event_date: date | None = None) -> None:
    """Made-up players and teams (never real data), drawn and scheduled, for dry runs."""
    if store.exists(Player):
        raise SystemExit("The table already has players; seed-demo only runs on an empty one")
    rng = random.Random(2026)  # noqa: S311 - demo data
    team_id = store.next_id(Team, n_teams)
    player_id = store.next_id(Player, n_teams * 2)
    teams, players, locks = [], [], []
    for t in range(n_teams):
        center = DEMO_CENTERS[t % len(DEMO_CENTERS)]
        team = Team(
            id=team_id + t,
            name=f"Demo Team {t + 1}",
            name_key=f"demo team {t + 1}",
            center=center,
            checked_in=True,
        )
        teams.append(team)
        locks.append(team)
        for k in range(2):
            players.append(
                Player(
                    id=player_id + t * 2 + k,
                    mis_id=f"DEMO{t * 2 + k + 1:04d}",
                    first_name=rng.choice(DEMO_FIRST),
                    last_name=rng.choice(DEMO_LAST),
                    center=center,
                    zone="Demo",
                    team_id=team.id,
                )
            )
    store.save_many(teams + players)
    with store.table.batch_writer() as batch:
        for team in locks:
            batch.put_item(
                Item={"pk": f"LOCK#{NAME}", "sk": team.name_key, "owner": f"team:{team.id}"}
            )
    tournament = get_tournament(store)
    tournament.event_date = event_date or date.today()
    store.save(tournament)
    schedule.draw_numbers(store, seed=2026)
    schedule.generate_schedule(store)


def create_judges(store: Store, courts: int = 9) -> list[tuple[str, str]]:
    """One judge per court with a random 4-digit PIN; existing usernames are skipped."""
    made = []
    for court in range(1, courts + 1):
        pin = f"{secrets.randbelow(10_000):04d}"
        try:
            create_staff(
                store,
                f"court-{court}",
                pin,
                "judge",
                f"Court {court} judge",
                court,
                must_change=True,
            )
        except Conflict:
            continue
        made.append((f"court-{court}", pin))
    return made


def reset_data(store: Store, keep_staff: bool, event_date: date | None) -> int:
    """Delete players, teams, games and logs. Staff accounts stay if asked."""
    keep = (StaffUser.KIND, USERNAME) if keep_staff else ()
    removed = store.wipe(keep=keep)
    tournament = get_tournament(store)
    tournament.event_date = event_date
    store.save(tournament)
    return removed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="create an admin account")
    admin.add_argument("username")
    admin.add_argument("--name", default="")
    judges = commands.add_parser("create-judges", help="one judge account per court")
    judges.add_argument("--courts", type=int, default=9)
    reset = commands.add_parser("reset-data", help="delete all tournament data")
    reset.add_argument("--yes", action="store_true", help="really delete")
    reset.add_argument("--keep-staff", action="store_true")
    reset.add_argument("--event-date", type=date.fromisoformat)
    demo = commands.add_parser("seed-demo", help="fill an empty table with made-up teams")
    demo.add_argument("--teams", type=int, default=40)
    commands.add_parser("create-table", help="create the table in DynamoDB Local")
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "create-table":
        if not settings.dynamodb_endpoint:
            raise SystemExit("create-table is for DynamoDB Local; AWS tables come from Terraform")
        resource = dynamodb_resource()
        if settings.table_name in [t.name for t in resource.tables.all()]:
            print(f"Table {settings.table_name} already exists")
        else:
            create_table(resource, settings.table_name)
            print(f"Created table {settings.table_name}")
        return
    store = Store(get_table())
    if args.command == "create-admin":
        password = os.environ.get("SAMPCUP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
        user = create_staff(store, args.username, password, "admin", args.name)
        print(f"Created admin {user.username}")
    elif args.command == "create-judges":
        for username, pin in create_judges(store, args.courts):
            print(f"{username}  PIN {pin}")
    elif args.command == "reset-data":
        if not args.yes:
            raise SystemExit(f"This deletes all data in {settings.table_name}. Add --yes.")
        removed = reset_data(store, args.keep_staff, args.event_date)
        print(f"Deleted {removed} items from {settings.table_name}")
    else:
        seed_demo(store, args.teams)
        print(f"Seeded {args.teams} demo teams; every demo team's password is 'demo'")


if __name__ == "__main__":  # pragma: no cover
    main()
