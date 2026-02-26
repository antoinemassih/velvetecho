"""Database connection management"""

from typing import AsyncIterator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
import structlog

logger = structlog.get_logger(__name__)


class DatabaseConnection:
    """
    Database connection manager with connection pooling.

    Example:
        db = DatabaseConnection("postgresql+asyncpg://user:pass@localhost/db")
        await db.connect()

        async with db.session() as session:
            result = await session.execute(select(Workspace))
            workspaces = result.scalars().all()

        await db.disconnect()
    """

    def __init__(
        self,
        database_url: str,
        pool_size: int = 20,
        max_overflow: int = 10,
        echo: bool = False,
    ):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.echo = echo
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None

    async def connect(self) -> None:
        """Initialize database engine and session factory"""
        if self._engine is not None:
            return

        logger.info(
            "Connecting to database",
            url=self.database_url.split("@")[-1],  # Hide credentials
            pool_size=self.pool_size,
        )

        self._engine = create_async_engine(
            self.database_url,
            echo=self.echo,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_pre_ping=True,  # Test connections before using
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        logger.info("Database connected")

    async def disconnect(self) -> None:
        """Close database connections"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database disconnected")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """
        Get a database session (context manager).

        Example:
            async with db.session() as session:
                result = await session.execute(select(Workspace))
        """
        if self._session_factory is None:
            raise RuntimeError("Database not connected. Call connect() first.")

        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @property
    def engine(self) -> AsyncEngine:
        """Get SQLAlchemy engine"""
        if self._engine is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._engine


# Global database instance
_db: Optional[DatabaseConnection] = None


def init_database(database_url: str, **kwargs) -> DatabaseConnection:
    """Initialize global database connection"""
    global _db
    _db = DatabaseConnection(database_url, **kwargs)
    return _db


def get_database() -> DatabaseConnection:
    """Get global database instance"""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _db


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency for database session.

    Example:
        @app.get("/workspaces")
        async def list_workspaces(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Workspace))
            return result.scalars().all()
    """
    db = get_database()
    async with db.session() as session:
        yield session
