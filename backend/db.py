"""Database layer: async SQLAlchemy engine, ORM models, and session wiring.

Postgres-first but SQLite-friendly. `DATABASE_URL` selects the backend:
  - unset            → local SQLite file (sqlite+aiosqlite:///app.db) for dev
  - postgres://...   → normalized to the asyncpg driver for production

The report payloads use JSONB on Postgres and plain JSON on SQLite via a
type variant, so the same models work on both.
"""
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import JSON, ForeignKey, false, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import config

# JSONB on Postgres (indexable, binary); generic JSON elsewhere (e.g. SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _normalize_url(url: str) -> tuple[str, dict]:
    """Return an asyncpg-compatible URL + connect_args.

    Managed Postgres URLs often look like `postgres://…?sslmode=require`.
    asyncpg needs the `postgresql+asyncpg` driver scheme and does not accept
    `sslmode` in the query string, so we lift it into connect_args.
    """
    connect_args: dict = {}
    parts = urlsplit(url)
    scheme = parts.scheme

    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        if sslmode and sslmode != "disable":
            connect_args["ssl"] = True
        parts = parts._replace(scheme=scheme, query=urlencode(query))
        return urlunsplit(parts), connect_args

    return url, connect_args


_url, _connect_args = _normalize_url(config.DATABASE_URL)
engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Invitation(Base):
    """A single-use, expiring invite. Registration requires a valid one."""
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str | None]  # optional note of who it's for
    grants_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]  # None = still pending


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # First matched thumbnail — a lightweight preview for the history list.
    preview_image_url: Mapped[str | None]
    listings: Mapped[list] = mapped_column(JSONType)  # raw SerpApi matches
    report: Mapped[dict] = mapped_column(JSONType)     # ProductIntelligenceReport
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


async def get_session() -> AsyncSession:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as session:
        yield session
