"""Transaction management utilities"""

from typing import AsyncIterator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """
    Transaction context manager with automatic commit/rollback.

    Example:
        async with transaction(session) as tx:
            workspace = Workspace(name="test")
            tx.add(workspace)
            # Auto-commits on exit

        # Or with error handling:
        try:
            async with transaction(session) as tx:
                workspace = Workspace(name="test")
                tx.add(workspace)
                raise ValueError("Error!")
        except ValueError:
            # Auto-rolls back on exception
            pass
    """
    try:
        yield session
        await session.commit()
        logger.debug("Transaction committed")
    except Exception as e:
        await session.rollback()
        logger.error("Transaction rolled back", error=str(e))
        raise
