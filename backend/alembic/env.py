"""Alembic environment — wired to the app's async engine and ORM metadata.

Reuses `db.engine` (already normalized for asyncpg + SSL) and `db.Base.metadata`
so migrations target the exact same schema and connection as the app.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context

# Make the backend package importable (env.py lives in backend/alembic/).
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import db  # noqa: E402 — imports Base + engine and registers User/Report models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = db.Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live connection (`alembic upgrade --sql`)."""
    context.configure(
        url=db._url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    async with db.engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await db.engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
