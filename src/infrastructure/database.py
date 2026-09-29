from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..config import settings


# --- Technical-debt service's own database (read + write) -------------------
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# --- analysis-engine's database (READ ONLY) ---------------------------------
# Every connection is opened with default_transaction_read_only=on, so even a
# bug in this service cannot write to another service's tables.
analysis_engine = create_async_engine(
    settings.analysis_database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {"default_transaction_read_only": "on"}
    },
)

AnalysisSessionLocal = async_sessionmaker(
    analysis_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
