"""Save or restore every item of a SampCup DynamoDB table (for example around a mock run).

    python tools/snapshot.py save ~/dev/sampcup-snapshot.json
    python tools/snapshot.py restore ~/dev/sampcup-snapshot.json

The table comes from TABLE_NAME (default sampcup-prod). A snapshot holds real player data:
keep it outside the repo, readable only by you, and delete it after restoring.
"""

import json
import os
import sys
from pathlib import Path

import boto3

TABLE = os.environ.get("TABLE_NAME", "sampcup-prod")


def scan(client) -> list[dict]:
    items, kwargs = [], {"TableName": TABLE}
    while True:
        page = client.scan(**kwargs)
        items += page["Items"]
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def write(client, requests: list[dict]) -> None:
    for i in range(0, len(requests), 25):
        batch = {TABLE: requests[i : i + 25]}
        while batch:
            batch = client.batch_write_item(RequestItems=batch).get("UnprocessedItems") or {}


def main() -> None:
    action, path = sys.argv[1], Path(sys.argv[2]).expanduser()
    client = boto3.client("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    if action == "save":
        items = scan(client)
        path.touch(mode=0o600, exist_ok=True)
        path.write_text(json.dumps(items))
        print(f"Saved {len(items)} items from {TABLE} to {path}")
    elif action == "restore":
        saved = json.loads(path.read_text())
        current = scan(client)
        write(client, [{"DeleteRequest": {"Key": {"pk": i["pk"], "sk": i["sk"]}}} for i in current])
        write(client, [{"PutRequest": {"Item": item}} for item in saved])
        print(f"Restored {len(saved)} items to {TABLE} (removed {len(current)} first)")
    else:
        raise SystemExit("usage: snapshot.py save|restore PATH")


if __name__ == "__main__":
    main()
