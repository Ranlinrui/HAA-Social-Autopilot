from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_legacy_columns(conn)


async def _ensure_legacy_columns(conn):
    async def add_column_if_missing(table: str, column: str, ddl: str):
        rows = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing = {row[1] for row in rows.fetchall()}
        if column in existing:
            return
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    await add_column_if_missing("tweets", "account_key", "VARCHAR(100)")
    await add_column_if_missing("monitored_accounts", "account_key", "VARCHAR(100)")
    await add_column_if_missing("monitor_notifications", "account_key", "VARCHAR(100)")
    await add_column_if_missing("conversation_threads", "account_key", "VARCHAR(100)")
