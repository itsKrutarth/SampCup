from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    """Run migrations online, against the database in DATABASE_URL."""
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
