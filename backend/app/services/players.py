"""Import registrations from the registration system's export (.xlsx or .csv).

Every column is kept (owner, 2026-11-23). A player is recognised by first name + last name +
registration email, which is also how they create their account (app.services.accounts). Rows
or older records without an email fall back to name + center, then MISID or BAPS ID, then a
name that is unique. Empty cells never erase what the app has. A row without a center comes in
with a blank center: an admin sets it in the Players tab, and until then the player can't pick a
partner. A preview shows every change before anything is saved, and a file that would switch
off most players is refused.
"""

import csv
import datetime as dt
import hashlib
import io
import re
from collections import Counter
from typing import Any

from openpyxl import load_workbook

from app.models import Player, Team
from app.services.errors import NotFound, ServiceError
from app.store import Store

FIELDS = {
    "misid": "mis_id",
    "bapsid": "baps_id",
    "bapsidmetadata": "baps_id",
    "email": "email",
    "customeremail": "email",
    "cardname": "card_name",
    "createddate": "registered_at",
    "createddateutc": "registered_at",
    "firstname": "first_name",
    "lastname": "last_name",
    "center": "center",
    "zone": "zone",
    "region": "region",
    "gender": "gender",
}
REQUIRED = ("first_name", "last_name")
IDS = ("mis_id", "baps_id", "email_key")
MAX_BYTES = 5 * 1024 * 1024


def email_key(email: str) -> str:
    """The email as matching compares it (spaces and capitals don't count), as a fingerprint:
    the first import of 2026-11-23 kept only this."""
    clean = email.strip().casefold()
    return hashlib.sha256(clean.encode()).hexdigest()[:32] if clean else ""


def _fold(value: str) -> str:
    return " ".join(value.split()).casefold()


def _name(item: dict[str, Any]) -> tuple[str, str]:
    return _fold(item["first_name"]), _fold(item["last_name"])


def _conflict(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Both carry the same kind of ID with different values: two different people."""
    return any(a.get(f) and b.get(f) and a[f] != b[f] for f in IDS)


def _shared_id(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return any(a.get(f) and a.get(f) == b.get(f) for f in IDS)


def _key(header: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header or "").lower())


def _text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, dt.datetime):
        value = value.strftime("%Y-%m-%d %H:%M")
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


def _same_person(record: dict[str, str], earlier: list[dict[str, str]]) -> int | None:
    """The earlier row of the same person: the same name, no ID telling them apart (two
    different BAPS IDs are two people, whatever the email), and a shared ID or the same
    center. (A shared email alone is not enough across names: families share one.)"""
    for other in earlier:
        if _name(other) != _name(record) or _conflict(record, other):
            continue
        same_center = _fold(other.get("center", "")) == _fold(record.get("center", ""))
        if _shared_id(record, other) or same_center:
            return int(other["_row"])
    return None


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
    players: list[dict[str, str]] = []
    skipped: list[dict[str, Any]] = []
    for number, row in enumerate(rows[1:], start=2):
        record = {field: _text(row[i]) if i < len(row) else "" for i, field in columns.items()}
        if not any(record.values()):
            continue
        record["email_key"] = email_key(record.get("email", ""))
        empty = [f for f in REQUIRED if not record.get(f)]
        if empty:
            skipped.append({"row": number, "reason": f"missing {', '.join(empty)}"})
            continue
        same = _same_person(record, players)
        if same:
            skipped.append({"row": number, "reason": f"same person as row {same}"})
            continue
        record["_row"] = str(number)
        players.append(record)
    return players, skipped


def _match(record: dict[str, str], pool: list[Player], in_file: Counter[Any]) -> Player | None:
    """The existing player this row is. First the key, name + email (a different email is a
    different person). For a row or record without an email: name + center; the same name with
    a shared MISID or BAPS ID; a personal ID used once in the file (a corrected name); the name
    alone when it is unique in both the app and the file."""
    named = [p for p in pool if _name(vars(p)) == _name(record) and not _conflict(record, vars(p))]
    if record.get("email_key"):
        keyed = [p for p in named if p.email_key == record["email_key"]]
        if keyed:
            return _one_of(record, keyed)
    center = _fold(record.get("center", ""))
    if center:
        here = [p for p in named if _fold(p.center) == center]
        if here:
            return _one_of(record, here)
    by_id = [p for p in named if _shared_id(record, vars(p))]
    if len(by_id) == 1:
        return by_id[0]
    for field in ("mis_id", "baps_id"):
        value = record.get(field)
        if value and in_file[(field, value)] == 1:
            same = [p for p in pool if getattr(p, field) == value]
            if len(same) == 1:
                return same[0]
    if len(named) == 1 and in_file[_name(record)] == 1:
        return named[0]
    return None


def _one_of(record: dict[str, str], found: list[Player]) -> Player | None:
    """One of several same-name players: a shared ID tells; when nothing does and none of them
    has a login or a team (nothing to mix up), the file's rows pair with them in order."""
    if len(found) == 1:
        return found[0]
    by_id = [p for p in found if _shared_id(record, vars(p))]
    if len(by_id) == 1:
        return by_id[0]
    if not by_id and not any(p.username or p.team_id for p in found):
        return found[0]
    return None


def _apply(player: Player, record: dict[str, str]) -> list[str]:
    """Copy the row onto the player; empty cells never erase what the app has."""
    changed = []
    for field, value in record.items():
        if field.startswith("_") or not value or getattr(player, field) == value:
            continue
        setattr(player, field, value)
        changed.append(field)
    return changed


def import_players(store: Store, content: bytes, preview: bool = False) -> dict[str, Any]:
    """Add or update players from the export. Players missing from the file are deactivated,
    never deleted, so teams and history stay intact. With `preview`, nothing is saved."""
    records, skipped = parse_players(content)
    if not records:
        raise ServiceError(
            "No usable rows in this file: it needs FirstName and LastName columns with names "
            "in them. Nothing was changed."
        )
    players = store.all(Player)
    teams = {t.id: t for t in store.all(Team)}
    active_before = sum(p.active for p in players)
    in_file: Counter[Any] = Counter(_name(r) for r in records)
    in_file.update((f, r[f]) for r in records for f in ("mis_id", "baps_id") if r.get(f))
    pool = list(players)
    report: dict[str, Any] = {"preview": preview, "added": 0, "updated": 0, "unchanged": 0}
    report |= {"deactivated": 0, "added_names": [], "updated_names": [], "center_changes": []}
    changed: list[Player] = []
    new: list[dict[str, str]] = []
    matched: set[int] = set()
    for record in records:
        player = _match(record, pool, in_file)
        if player is None:
            new.append(record)
            continue
        pool.remove(player)
        matched.add(player.id)
        before = player.center
        fields = _apply(player, record)
        if "center" in fields:
            was = before or "no center"
            report["center_changes"].append(f"{player.full_name}: {was} -> {player.center}")
        if fields or not player.active:
            player.active = True
            changed.append(player)
            report["updated"] += 1
            report["updated_names"].append(player.full_name)
        else:
            report["unchanged"] += 1
    leaving = [p for p in players if p.id not in matched and p.active]
    if active_before >= 6 and len(leaving) > active_before / 2:
        raise ServiceError(
            f"This file would switch off {len(leaving)} of the {active_before} active players: it "
            "may be the wrong file, or its name or center columns are empty. Nothing was changed."
        )
    next_id = store.next_id(Player, len(new)) if new and not preview else 0
    for record in new:
        fields = {k: v for k, v in record.items() if not k.startswith("_")}
        player = Player(id=next_id, **fields)
        next_id += 1
        players.append(player)
        changed.append(player)
        report["added"] += 1
        report["added_names"].append(f"{player.full_name} ({player.center or 'no center'})")
    teams_affected = set()
    report["deactivated_names"] = []
    for player in leaving:
        player.active = False
        changed.append(player)
        report["deactivated"] += 1
        report["deactivated_names"].append(f"{player.full_name} ({player.center or 'no center'})")
        if player.team_id in teams:
            teams_affected.add(teams[player.team_id].name)
    if not preview:
        store.save_many(changed)
    names = Counter(
        (p.first_name.casefold(), p.last_name.casefold(), p.center) for p in players if p.active
    )
    report["possible_duplicates"] = sorted(
        f"{first.title()} {last.title()} ({center or 'no center'})"
        for (first, last, center), count in names.items()
        if count > 1
    )
    active = [p for p in players if p.active]
    report["no_center"] = sorted(p.full_name for p in active if not p.center)
    # they can't create their own account: an admin sets their login
    report["no_email"] = sorted(p.full_name for p in active if not p.email_key)
    report["skipped"] = skipped
    report["teams_with_removed_players"] = sorted(teams_affected)
    return report


def set_center(store: Store, player_id: int, center: str) -> Player:
    """An admin sets a player's center (for example one the registration didn't have)."""
    player = store.get(Player, player_id)
    if player is None:
        raise NotFound("Player not found")
    center = " ".join(center.split())
    if not center:
        raise ServiceError("Give a center")
    player.center = center
    store.save(player)
    return player
