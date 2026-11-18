"""Import registrations from the registration system's export (.xlsx or .csv)."""

import csv
import io
import re
from collections import Counter
from typing import Any

from openpyxl import load_workbook

from app.models import Player, Team
from app.services.errors import ServiceError
from app.store import Store

FIELDS = {
    "misid": "mis_id",
    "firstname": "first_name",
    "lastname": "last_name",
    "center": "center",
    "zone": "zone",
    "region": "region",
    "gender": "gender",
}
REQUIRED = ("mis_id", "first_name", "last_name", "center")
MAX_BYTES = 5 * 1024 * 1024


def _key(header: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header or "").lower())


def _text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return " ".join(str(value if value is not None else "").split())


def read_rows(content: bytes) -> list[list[object]]:
    if len(content) > MAX_BYTES:
        raise ServiceError("File is larger than 5 MB")
    if content[:2] == b"PK":
        try:
            sheet = load_workbook(io.BytesIO(content), read_only=True, data_only=True).worksheets[0]
        except Exception as exc:
            raise ServiceError("Could not read the Excel file") from exc
        return [list(row) for row in sheet.iter_rows(values_only=True)]
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ServiceError("Upload the .xlsx or .csv export") from exc
    return [list(row) for row in csv.reader(io.StringIO(text))]


def parse_players(content: bytes) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    rows = read_rows(content)
    if not rows:
        raise ServiceError("The file is empty")
    columns: dict[int, str] = {}
    for i, header in enumerate(rows[0]):
        key = _key(header)
        if key in FIELDS:
            columns[i] = FIELDS[key]
        elif "shirt" in key:
            columns[i] = "tshirt_size"
    missing = [f for f in REQUIRED if f not in columns.values()]
    if missing:
        raise ServiceError(f"Missing columns: {', '.join(missing)}")
    players, skipped, seen = [], [], set()
    for number, row in enumerate(rows[1:], start=2):
        record = {field: _text(row[i]) if i < len(row) else "" for i, field in columns.items()}
        if not any(record.values()):
            continue
        empty = [f for f in REQUIRED if not record[f]]
        if empty:
            skipped.append({"row": number, "reason": f"missing {', '.join(empty)}"})
        elif record["mis_id"] in seen:
            skipped.append({"row": number, "reason": f"MISID {record['mis_id']} repeated"})
        else:
            seen.add(record["mis_id"])
            players.append(record)
    return players, skipped


def import_players(store: Store, content: bytes) -> dict[str, Any]:
    """Add or update players by MISID. Players missing from the file are deactivated,
    never deleted, so teams and history stay intact."""
    records, skipped = parse_players(content)
    players = store.all(Player)
    existing = {p.mis_id: p for p in players}
    teams = {t.id: t for t in store.all(Team)}
    report: dict[str, Any] = {"added": 0, "updated": 0, "unchanged": 0, "deactivated": 0}
    changed: list[Player] = []
    new = [r for r in records if r["mis_id"] not in existing]
    next_id = store.next_id(Player, len(new)) if new else 0
    for record in records:
        player = existing.get(record["mis_id"])
        if player is None:
            player = Player(id=next_id, **record)
            next_id += 1
            players.append(player)
            changed.append(player)
            report["added"] += 1
            continue
        if not player.active or any(getattr(player, f) != v for f, v in record.items()):
            for field, value in record.items():
                setattr(player, field, value)
            player.active = True
            changed.append(player)
            report["updated"] += 1
        else:
            report["unchanged"] += 1
    present = {r["mis_id"] for r in records}
    teams_affected = set()
    for player in existing.values():
        if player.mis_id not in present and player.active:
            player.active = False
            changed.append(player)
            report["deactivated"] += 1
            if player.team_id in teams:
                teams_affected.add(teams[player.team_id].name)
    store.save_many(changed)
    names = Counter(
        (p.first_name.casefold(), p.last_name.casefold(), p.center) for p in players if p.active
    )
    report["possible_duplicates"] = sorted(
        f"{first.title()} {last.title()} ({center})"
        for (first, last, center), count in names.items()
        if count > 1
    )
    report["skipped"] = skipped
    report["teams_with_removed_players"] = sorted(teams_affected)
    return report
