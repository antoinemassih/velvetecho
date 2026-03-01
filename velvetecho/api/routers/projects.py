"""
Project API Router

Auto-generated CRUD routes for Projects with workspace relationship.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel as PydanticModel
from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from datetime import datetime

from velvetecho.database import BaseModel, TimestampMixin, Repository, get_session
from velvetecho.api import StandardResponse
from velvetecho.api.crud_router import CRUDRouter
from velvetecho.api.exceptions import NotFoundException

# Router configuration
PREFIX = "/api/projects"
TAGS = ["Projects"]

# ============================================================================
# Database Model
# ============================================================================


class Project(BaseModel, TimestampMixin):
    """Project database model"""

    __tablename__ = "projects"

    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    workspace_id = Column(PGUUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    status = Column(String, default="active")  # active, archived, completed


# ============================================================================
# Pydantic Schemas
# ============================================================================


class ProjectCreate(PydanticModel):
    """Schema for creating project"""

    name: str
    description: Optional[str] = None
    workspace_id: UUID
    status: str = "active"


class ProjectUpdate(PydanticModel):
    """Schema for updating project"""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(PydanticModel):
    """Schema for project response"""

    id: UUID
    name: str
    description: Optional[str]
    workspace_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Custom Repository
# ============================================================================


class ProjectRepository(Repository[Project]):
    """Custom repository for projects"""

    async def list_by_workspace(self, workspace_id: UUID) -> list[Project]:
        """Get all projects in a workspace"""
        from sqlalchemy import select

        stmt = select(Project).where(Project.workspace_id == workspace_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_status(self, status: str) -> list[Project]:
        """Get all projects with specific status"""
        from sqlalchemy import select

        stmt = select(Project).where(Project.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# Router Setup
# ============================================================================

router = APIRouter()


def get_project_repository(session: AsyncSession = Depends(get_session)):
    return ProjectRepository(session, Project)


# ============================================================================
# Auto-Generated CRUD Routes
# ============================================================================

crud_router = CRUDRouter(
    model=Project,
    create_schema=ProjectCreate,
    update_schema=ProjectUpdate,
    response_schema=ProjectResponse,
    prefix="",
    get_repository=get_project_repository,
)

router.include_router(crud_router.router)

# ============================================================================
# Custom Routes
# ============================================================================


@router.get("/workspace/{workspace_id}", response_model=StandardResponse[list[ProjectResponse]])
async def get_workspace_projects(
    workspace_id: UUID,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """Get all projects in a workspace"""
    projects = await repo.list_by_workspace(workspace_id)

    return StandardResponse(
        data=[ProjectResponse.model_validate(p) for p in projects],
        message=f"Found {len(projects)} projects",
    )


@router.get("/status/{status}", response_model=StandardResponse[list[ProjectResponse]])
async def get_projects_by_status(
    status: str,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """Get all projects with specific status"""
    projects = await repo.list_by_status(status)

    return StandardResponse(
        data=[ProjectResponse.model_validate(p) for p in projects],
        message=f"Found {len(projects)} {status} projects",
    )


@router.post("/{id}/complete", response_model=StandardResponse[ProjectResponse])
async def complete_project(
    id: UUID,
    repo: ProjectRepository = Depends(get_project_repository),
):
    """Mark project as completed"""
    project = await repo.update(id, {"status": "completed"})

    if not project:
        raise NotFoundException("Project", id)

    return StandardResponse(
        data=ProjectResponse.model_validate(project),
        message="Project marked as completed",
    )
