"""Generic repository pattern for CRUD operations"""

from typing import Generic, TypeVar, Type, Optional, List, Any, Dict
from uuid import UUID
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from velvetecho.database.base import BaseModel

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class Repository(Generic[T]):
    """
    Generic repository for CRUD operations.

    Example:
        class WorkspaceRepository(Repository[Workspace]):
            async def get_by_name(self, name: str) -> Optional[Workspace]:
                stmt = select(Workspace).where(Workspace.name == name)
                result = await self.session.execute(stmt)
                return result.scalar_one_or_none()

        repo = WorkspaceRepository(session)
        workspace = await repo.get_by_id(workspace_id)
        workspaces = await repo.list(limit=10, offset=0)
        await repo.create(Workspace(name="test"))
        await repo.update(workspace_id, {"name": "updated"})
        await repo.delete(workspace_id)
    """

    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get model by ID"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
    ) -> List[T]:
        """
        List models with pagination and filtering.

        Args:
            limit: Maximum results to return
            offset: Number of results to skip
            filters: Dictionary of field: value filters
            order_by: Field name to order by (prefix with - for descending)
        """
        stmt = select(self.model)

        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        # Apply ordering
        if order_by:
            if order_by.startswith("-"):
                # Descending
                field = order_by[1:]
                if hasattr(self.model, field):
                    stmt = stmt.order_by(getattr(self.model, field).desc())
            else:
                # Ascending
                if hasattr(self.model, order_by):
                    stmt = stmt.order_by(getattr(self.model, order_by))

        # Apply pagination
        stmt = stmt.limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count models with optional filters"""
        from sqlalchemy import func

        stmt = select(func.count(self.model.id))

        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field):
                    stmt = stmt.where(getattr(self.model, field) == value)

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def create(self, model: T) -> T:
        """Create a new model"""
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)

        logger.info(
            "Created model",
            model=self.model.__name__,
            id=model.id,
        )

        return model

    async def update(self, id: UUID, data: Dict[str, Any]) -> Optional[T]:
        """Update a model by ID"""
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
            .returning(self.model)
        )

        result = await self.session.execute(stmt)
        updated = result.scalar_one_or_none()

        if updated:
            logger.info(
                "Updated model",
                model=self.model.__name__,
                id=id,
            )

        return updated

    async def delete(self, id: UUID) -> bool:
        """Delete a model by ID"""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)

        deleted = result.rowcount > 0

        if deleted:
            logger.info(
                "Deleted model",
                model=self.model.__name__,
                id=id,
            )

        return deleted

    async def bulk_create(self, models: List[T]) -> List[T]:
        """Bulk create multiple models"""
        self.session.add_all(models)
        await self.session.flush()

        for model in models:
            await self.session.refresh(model)

        logger.info(
            "Bulk created models",
            model=self.model.__name__,
            count=len(models),
        )

        return models

    async def exists(self, id: UUID) -> bool:
        """Check if model exists by ID"""
        from sqlalchemy import func

        stmt = select(func.count(self.model.id)).where(self.model.id == id)
        result = await self.session.execute(stmt)
        count = result.scalar() or 0
        return count > 0
