"""DynamoDB storage: one table; every record is keyed by (pk = record kind, sk = id).

The whole tournament is a few hundred small records, so services read a kind's records
in one query and filter in Python. Writes that must not race use conditions or
transactions, and raise ConflictError when someone else changed the data first.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import time
from collections.abc import Iterable
from decimal import Decimal
from functools import cache, lru_cache
from typing import Any, ClassVar, TypeVar, get_type_hints

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.core.config import get_settings

R = TypeVar("R", bound="Record")
CONFLICT_CODES = {"ConditionalCheckFailedException", "TransactionCanceledException"}


class ConflictError(Exception):
    """A conditional write failed: the data changed since it was read."""


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def _stored(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            raise ValueError("naive datetime: give it a timezone")
        return value.astimezone(dt.UTC).isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_stored(v) for v in value]
    if isinstance(value, dict):
        return {k: _stored(v) for k, v in value.items()}
    return value


@cache
def _time_fields(cls: type) -> dict[str, str]:
    kinds = {}
    for name, hint in get_type_hints(cls).items():
        text = str(hint)
        if "datetime.datetime" in text:
            kinds[name] = "datetime"
        elif "datetime.date" in text:
            kinds[name] = "date"
    return kinds


@dataclasses.dataclass(kw_only=True)
class Record:
    KIND: ClassVar[str]
    id: Any

    @property
    def key(self) -> dict[str, str]:
        return {"pk": self.KIND, "sk": str(self.id)}

    def to_item(self) -> dict[str, Any]:
        fields = {f.name: _stored(getattr(self, f.name)) for f in dataclasses.fields(self)}
        return {**self.key, **fields}

    @classmethod
    def from_item(cls: type[R], item: dict[str, Any]) -> R:
        times = _time_fields(cls)
        values = {}
        for field in dataclasses.fields(cls):
            if field.name not in item:
                continue
            value = _plain(item[field.name])
            if isinstance(value, str) and times.get(field.name) == "datetime":
                value = dt.datetime.fromisoformat(value)
            elif isinstance(value, str) and times.get(field.name) == "date":
                value = dt.date.fromisoformat(value)
            values[field.name] = value
        return cls(**values)


class Store:
    def __init__(self, table: Any) -> None:
        self.table = table
        self.client = table.meta.client

    # ----------------------------------------------------------------- reads

    def get(self, cls: type[R], record_id: Any) -> R | None:
        item = self.table.get_item(
            Key={"pk": cls.KIND, "sk": str(record_id)}, ConsistentRead=True
        ).get("Item")
        return cls.from_item(item) if item else None

    def _query(self, pk: str, **extra: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs = {"KeyConditionExpression": Key("pk").eq(pk), "ConsistentRead": True, **extra}
        while True:
            page = self.table.query(**kwargs)
            items += page["Items"]
            if "LastEvaluatedKey" not in page:
                return items
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def all(self, cls: type[R]) -> list[R]:
        records = [cls.from_item(item) for item in self._query(cls.KIND)]
        return sorted(records, key=lambda r: r.id)

    def exists(self, cls: type[Record]) -> bool:
        page = self.table.query(KeyConditionExpression=Key("pk").eq(cls.KIND), Limit=1)
        return bool(page["Items"])

    # ---------------------------------------------------------------- writes

    def next_id(self, cls: type[Record], count: int = 1) -> int:
        """Reserve `count` ids for a kind; returns the first."""
        out = self.table.update_item(
            Key={"pk": "COUNTER", "sk": cls.KIND},
            UpdateExpression="ADD n :count",
            ExpressionAttributeValues={":count": count},
            ReturnValues="UPDATED_NEW",
        )
        return int(out["Attributes"]["n"]) - count + 1

    def save(self, record: Record, *, create: bool = False, version: int | None = None) -> None:
        """Write a record. `create` fails if it exists; `version` fails if it changed."""
        kwargs: dict[str, Any] = {}
        if create:
            kwargs["ConditionExpression"] = "attribute_not_exists(pk)"
        elif version is not None:
            kwargs["ConditionExpression"] = "#v = :v"
            kwargs["ExpressionAttributeNames"] = {"#v": "version"}
            kwargs["ExpressionAttributeValues"] = {":v": version}
        try:
            self.table.put_item(Item=record.to_item(), **kwargs)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in CONFLICT_CODES:
                raise ConflictError(str(exc)) from exc
            raise

    def save_many(self, records: Iterable[Record]) -> None:
        with self.table.batch_writer() as batch:
            for record in records:
                batch.put_item(Item=record.to_item())

    def delete(self, record: Record) -> None:
        self.table.delete_item(Key=record.key)

    def delete_kind(self, cls: type[Record]) -> None:
        keys = self._query(cls.KIND, ProjectionExpression="pk, sk")
        with self.table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key={"pk": key["pk"], "sk": key["sk"]})

    # ---------------------------------------------------------- transactions

    def transact(self, writes: list[dict[str, Any]]) -> None:
        try:
            self.client.transact_write_items(TransactItems=writes)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in CONFLICT_CODES:
                raise ConflictError(str(exc)) from exc
            raise

    def tx_put(
        self,
        record: Record,
        *,
        create: bool = False,
        condition: str | None = None,
        names: dict[str, str] | None = None,
        values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        put: dict[str, Any] = {"TableName": self.table.name, "Item": record.to_item()}
        if create:
            condition = "attribute_not_exists(pk)"
        if condition:
            put["ConditionExpression"] = condition
        if names:
            put["ExpressionAttributeNames"] = names
        if values:
            put["ExpressionAttributeValues"] = values
        return {"Put": put}

    def tx_delete(self, record: Record) -> dict[str, Any]:
        return {"Delete": {"TableName": self.table.name, "Key": record.key}}

    # Locks make a value unique (a team name, a username): one item per value.

    def lock_owner(self, kind: str, value: str) -> str | None:
        item = self.table.get_item(Key={"pk": f"LOCK#{kind}", "sk": value}, ConsistentRead=True)
        return item.get("Item", {}).get("owner")

    def tx_lock(
        self, kind: str, value: str, owner: str, replaces: str | None = None
    ) -> dict[str, Any]:
        put: dict[str, Any] = {
            "TableName": self.table.name,
            "Item": {"pk": f"LOCK#{kind}", "sk": value, "owner": owner},
            "ConditionExpression": "attribute_not_exists(pk)",
        }
        if replaces:
            put["ConditionExpression"] += " OR #o = :o"
            put["ExpressionAttributeNames"] = {"#o": "owner"}
            put["ExpressionAttributeValues"] = {":o": replaces}
        return {"Put": put}

    def tx_unlock(self, kind: str, value: str, owner: str) -> dict[str, Any]:
        return {
            "Delete": {
                "TableName": self.table.name,
                "Key": {"pk": f"LOCK#{kind}", "sk": value},
                "ConditionExpression": "attribute_not_exists(pk) OR #o = :o",
                "ExpressionAttributeNames": {"#o": "owner"},
                "ExpressionAttributeValues": {":o": owner},
            }
        }

    # -------------------------------------------------------------- limits

    def hit(self, key: str, window: int, clock: float | None = None) -> int:
        """Count one hit for `key` in the current fixed window; returns hits so far.
        Old windows expire through the table's TTL."""
        bucket = int((clock if clock is not None else time.time()) // window)
        out = self.table.update_item(
            Key={"pk": "RATE", "sk": f"{key}#{bucket}"},
            UpdateExpression="ADD hits :one SET #t = if_not_exists(#t, :ttl)",
            ExpressionAttributeNames={"#t": "ttl"},
            ExpressionAttributeValues={":one": 1, ":ttl": (bucket + 2) * window},
            ReturnValues="UPDATED_NEW",
        )
        return int(out["Attributes"]["hits"])

    # --------------------------------------------------------------- admin

    def wipe(self, keep: tuple[str, ...] = ()) -> int:
        """Delete every item except kinds in `keep` (and their locks). Returns the count."""
        removed, kwargs = 0, {"ProjectionExpression": "pk, sk"}
        with self.table.batch_writer() as batch:
            while True:
                page = self.table.scan(**kwargs)
                for item in page["Items"]:
                    pk = item["pk"]
                    if pk in keep or pk.removeprefix("LOCK#") in keep:
                        continue
                    if pk == "COUNTER" and item["sk"] in keep:
                        continue
                    batch.delete_item(Key={"pk": pk, "sk": item["sk"]})
                    removed += 1
                if "LastEvaluatedKey" not in page:
                    return removed
                kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def create_table(resource: Any, name: str) -> Any:
    """Make the table (tests and local development; production uses Terraform)."""
    table = resource.create_table(
        TableName=name,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    table.wait_until_exists()
    return table


def dynamodb_resource() -> Any:
    settings = get_settings()
    return boto3.resource(
        "dynamodb", region_name=settings.aws_region, endpoint_url=settings.dynamodb_endpoint
    )


@lru_cache
def get_table() -> Any:
    return dynamodb_resource().Table(get_settings().table_name)


def get_store() -> Store:
    """FastAPI dependency."""
    return Store(get_table())
