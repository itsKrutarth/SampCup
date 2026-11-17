from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401 - registers every table on Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.types import UTCDateTime

target_metadata = Base.metadata


def render_item(kind: str, obj: object, _: object) -> str | bool:
    """Write UTCDateTime as a plain timestamptz so migrations do not import app code."""
    if kind == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations() -> None:
    """Run migrations online, against the database in DATABASE_URL."""
    url = context.config.attributes.get("url") or get_settings().database_url
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_item=render_item
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
