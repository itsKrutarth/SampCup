"""Restore prod from the pre-mock snapshot, keeping what real people did during the mock.

Kept from the live table: real players' account claims and password changes (login fields
plus their username lock), changes to real staff (judge PIN changes, renames) and their
username locks, partner-request changes and their team-name locks, and new logins of real
players and staff (so nobody is logged out). Everything the mock made goes.

    python tools/mock_restore.py ~/dev/sampcup-snapshot-before-mock.json --dry-run   # look first
    python tools/mock_restore.py ~/dev/sampcup-snapshot-before-mock.json

The table comes from TABLE_NAME (default sampcup-prod), like tools/snapshot.py.
"""

import json
import sys
from pathlib import Path

import boto3
from boto3.dynamodb.types import TypeDeserializer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot  # noqa: E402

SNAP = Path(next(a for a in sys.argv[1:] if not a.startswith("--"))).expanduser()
DRY = "--dry-run" in sys.argv
LOGIN = ("username", "password_hash", "must_change_password")
NAME_LOCKS = ("LOCK#PLAYERNAME", "LOCK#USERNAME", "LOCK#TEAMNAME")

table = boto3.resource("dynamodb", region_name="us-east-1").Table(snapshot.TABLE)
client = boto3.client("dynamodb", region_name="us-east-1")
d = TypeDeserializer()

saved = [{k: d.deserialize(v) for k, v in i.items()} for i in json.loads(SNAP.read_text())]
current = [{k: d.deserialize(v) for k, v in i.items()} for i in snapshot.scan(client)]
before = {(i["pk"], i["sk"]): i for i in saved}
now = {(i["pk"], i["sk"]): i for i in current}

real_players = {int(i["id"]) for i in saved if i["pk"] == "PLAYER" and i.get("zone") != "Mock"}
real_staff = {int(i["id"]) for i in saved if i["pk"] == "STAFF"}
real_requests = {int(i["id"]) for i in saved if i["pk"] == "REQUEST"}


def real_owner(owner: str) -> bool:
    kind, _, ident = owner.partition(":")
    return ident.isdigit() and int(ident) in {
        "player": real_players, "staff": real_staff, "request": real_requests}.get(kind, set())


keep, drop, notes = [], [], []
for key, item in now.items():
    pk, old = key[0], before.get(key)
    if pk == "PLAYER" and old and int(item["id"]) in real_players:
        login = {k: item.get(k) for k in LOGIN}
        # a re-saved player gains must_change_password=False where the snapshot had no field
        if login | {"must_change_password": bool(login["must_change_password"])} != {
                k: old.get(k) for k in LOGIN} | {"must_change_password": bool(old.get("must_change_password"))}:
            keep.append(old | login)  # the snapshot's team, the live login
            notes.append(f"player {item['id']}: account claimed or password changed")
    elif pk == "STAFF" and int(item["id"]) in real_staff and item != old:
        keep.append(item)
        notes.append(f"staff {item['username']}: changed (PIN or name)")
    elif pk == "REQUEST" and int(item["id"]) in real_requests and item != old:
        keep.append(item)
        notes.append(f"partner request {item['id']}: now {item['status']}")
    elif pk in NAME_LOCKS and old is None and real_owner(item.get("owner", "")):
        keep.append(item)
        notes.append(f"{pk} {item['sk']}: new, owned by {item['owner']}")
    elif pk == "SESSION" and old is None and (
            (item.get("player_id") is not None and int(item["player_id"]) in real_players)
            or (item.get("staff_id") is not None and int(item["staff_id"]) in real_staff)):
        keep.append(item)
for key, item in before.items():
    if key[0] in NAME_LOCKS and key not in now and real_owner(item.get("owner", "")):
        drop.append(key)
        notes.append(f"{key[0]} {key[1]}: released during the mock")

sessions = sum(1 for i in keep if i["pk"] == "SESSION")
print(f"snapshot {len(saved)} items, live {len(current)} items")
print(f"keeping {len(keep) - sessions} real changes and {sessions} new real logins; dropping {len(drop)} released locks")
for note in notes:
    print("  -", note)
if DRY:
    sys.exit(0)

snapshot.main.__globals__["sys"].argv = ["snapshot.py", "restore", str(SNAP)]
snapshot.main()
with table.batch_writer() as batch:
    for item in keep:
        batch.put_item(Item=item)
    for pk, sk in drop:
        batch.delete_item(Key={"pk": pk, "sk": sk})
print("restored, with the real changes carried over")
