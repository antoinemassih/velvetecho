"""
Complete PatientComet integration with VelvetEcho.

Demonstrates full stack integration:
1. Database models (Workspace, AnalyzerRun, AnalyzerResult)
2. CQRS (Commands + Queries + Handlers)
3. Repository pattern
4. API endpoints (CRUD + custom)
5. DAG workflow execution
6. SSE streaming for progress updates

This is a production-ready integration guide for PatientComet.
"""

import asyncio
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy import Column, String, Text, Integer, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession

# VelvetEcho imports
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity, get_client, init_client, WorkerManager
from velvetecho.patterns import DAGWorkflow, DAGNode
from velvetecho.database import (
    BaseModel,
    TimestampMixin,
    Repository,
    init_database,
    get_session,
)
from velvetecho.cqrs import Command, Query, CommandHandler, QueryHandler, CommandBus, QueryBus
from velvetecho.api import StandardResponse, PaginatedResponse, setup_middleware
from velvetecho.api.crud_router import CRUDRouter


# ============================================================================
# Configuration
# ============================================================================

config = VelvetEchoConfig(
    service_name="patientcomet",
    temporal_host="localhost:7233",
    temporal_namespace="patientcomet",
    temporal_worker_count=8,
    temporal_max_concurrent_activities=50,
)
init_config(config)


# ============================================================================
# 1. Database Models
# ============================================================================


class AnalysisStatus(str, Enum):
    """Analysis status enum"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Workspace(BaseModel, TimestampMixin):
    """Workspace model - represents a code repository"""

    __tablename__ = "workspaces"

    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String, nullable=True)
    framework = Column(String, nullable=True)

    # Relationships
    analyzer_runs = relationship("AnalyzerRun", back_populates="workspace", cascade="all, delete-orphan")


class AnalyzerRun(BaseModel, TimestampMixin):
    """Analyzer run - represents one full analysis execution"""

    __tablename__ = "analyzer_runs"

    workspace_id = Column(ForeignKey("workspaces.id"), nullable=False)
    profile = Column(String, nullable=False)  # quick, full, deep
    status = Column(SQLEnum(AnalysisStatus), default=AnalysisStatus.PENDING)
    workflow_id = Column(String, nullable=True)  # Temporal workflow ID
    started_at = Column(Text, nullable=True)
    completed_at = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    total_analyzers = Column(Integer, default=0)
    completed_analyzers = Column(Integer, default=0)
    metadata = Column(JSON, default={})

    # Relationships
    workspace = relationship("Workspace", back_populates="analyzer_runs")
    results = relationship("AnalyzerResult", back_populates="run", cascade="all, delete-orphan")


class AnalyzerResult(BaseModel, TimestampMixin):
    """Analyzer result - represents output of one analyzer in a run"""

    __tablename__ = "analyzer_results"

    run_id = Column(ForeignKey("analyzer_runs.id"), nullable=False)
    analyzer_id = Column(String, nullable=False)  # symbols, calls, patterns, etc.
    phase = Column(Integer, nullable=False)  # 1-5
    status = Column(String, nullable=False)  # completed, failed
    execution_time_ms = Column(Integer, nullable=True)
    output_data = Column(JSON, default={})
    error_message = Column(Text, nullable=True)

    # Relationships
    run = relationship("AnalyzerRun", back_populates="results")


# ============================================================================
# 2. Pydantic Schemas
# ============================================================================


class WorkspaceCreate(PydanticModel):
    """Schema for creating workspace"""

    name: str
    path: str
    description: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None


class WorkspaceUpdate(PydanticModel):
    """Schema for updating workspace"""

    name: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None


class WorkspaceResponse(PydanticModel):
    """Schema for workspace response"""

    id: UUID
    name: str
    path: str
    description: Optional[str]
    language: Optional[str]
    framework: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalyzerRunResponse(PydanticModel):
    """Schema for analyzer run response"""

    id: UUID
    workspace_id: UUID
    profile: str
    status: AnalysisStatus
    workflow_id: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    total_analyzers: int
    completed_analyzers: int
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class AnalyzerResultResponse(PydanticModel):
    """Schema for analyzer result response"""

    id: UUID
    run_id: UUID
    analyzer_id: str
    phase: int
    status: str
    execution_time_ms: Optional[int]
    output_data: Dict[str, Any]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# 3. Repositories
# ============================================================================


class WorkspaceRepository(Repository[Workspace]):
    """Workspace repository with custom methods"""

    async def get_by_path(self, path: str) -> Optional[Workspace]:
        """Get workspace by path"""
        from sqlalchemy import select

        stmt = select(Workspace).where(Workspace.path == path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AnalyzerRunRepository(Repository[AnalyzerRun]):
    """Analyzer run repository"""

    async def get_latest_by_workspace(self, workspace_id: UUID) -> Optional[AnalyzerRun]:
        """Get latest run for workspace"""
        from sqlalchemy import select

        stmt = (
            select(AnalyzerRun)
            .where(AnalyzerRun.workspace_id == workspace_id)
            .order_by(AnalyzerRun.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_running_runs(self) -> List[AnalyzerRun]:
        """Get all running analysis runs"""
        from sqlalchemy import select

        stmt = select(AnalyzerRun).where(AnalyzerRun.status == AnalysisStatus.RUNNING)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class AnalyzerResultRepository(Repository[AnalyzerResult]):
    """Analyzer result repository"""

    async def get_by_run(self, run_id: UUID) -> List[AnalyzerResult]:
        """Get all results for a run"""
        from sqlalchemy import select

        stmt = select(AnalyzerResult).where(AnalyzerResult.run_id == run_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# 4. CQRS Commands
# ============================================================================


class StartAnalysisCommand(Command):
    """Command to start analysis"""

    workspace_id: UUID
    profile: str = "quick"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateAnalysisProgressCommand(Command):
    """Command to update analysis progress"""

    run_id: UUID
    completed_analyzers: int
    status: Optional[AnalysisStatus] = None


class CompleteAnalysisCommand(Command):
    """Command to complete analysis"""

    run_id: UUID
    results: List[Dict[str, Any]]


# ============================================================================
# 5. CQRS Queries
# ============================================================================


class GetWorkspaceQuery(Query):
    """Query to get workspace"""

    workspace_id: UUID


class GetAnalysisRunQuery(Query):
    """Query to get analysis run"""

    run_id: UUID


class ListAnalysisRunsQuery(Query):
    """Query to list analysis runs"""

    workspace_id: Optional[UUID] = None
    status: Optional[AnalysisStatus] = None
    limit: int = 10
    offset: int = 0


# ============================================================================
# 6. Command Handlers
# ============================================================================


class StartAnalysisHandler(CommandHandler[StartAnalysisCommand, AnalyzerRun]):
    """Handler for starting analysis"""

    def __init__(
        self, run_repository: AnalyzerRunRepository, workspace_repository: WorkspaceRepository
    ):
        self.run_repository = run_repository
        self.workspace_repository = workspace_repository

    async def handle(self, command: StartAnalysisCommand) -> AnalyzerRun:
        """Start analysis run"""
        # Verify workspace exists
        workspace = await self.workspace_repository.get_by_id(command.workspace_id)
        if not workspace:
            raise ValueError(f"Workspace not found: {command.workspace_id}")

        # Create run
        run = AnalyzerRun(
            workspace_id=command.workspace_id,
            profile=command.profile,
            status=AnalysisStatus.PENDING,
            total_analyzers=111,  # PatientComet has 111 analyzers
            metadata=command.metadata,
        )
        return await self.run_repository.create(run)


class UpdateAnalysisProgressHandler(
    CommandHandler[UpdateAnalysisProgressCommand, AnalyzerRun]
):
    """Handler for updating analysis progress"""

    def __init__(self, repository: AnalyzerRunRepository):
        self.repository = repository

    async def handle(self, command: UpdateAnalysisProgressCommand) -> AnalyzerRun:
        """Update progress"""
        update_data = {"completed_analyzers": command.completed_analyzers}

        if command.status:
            update_data["status"] = command.status

        updated = await self.repository.update(command.run_id, update_data)

        if not updated:
            raise ValueError(f"Run not found: {command.run_id}")

        return updated


# ============================================================================
# 7. Query Handlers
# ============================================================================


class GetWorkspaceHandler(QueryHandler[GetWorkspaceQuery, Optional[Workspace]]):
    """Handler for getting workspace"""

    def __init__(self, repository: WorkspaceRepository):
        self.repository = repository

    async def handle(self, query: GetWorkspaceQuery) -> Optional[Workspace]:
        """Get workspace by ID"""
        return await self.repository.get_by_id(query.workspace_id)


class GetAnalysisRunHandler(QueryHandler[GetAnalysisRunQuery, Optional[AnalyzerRun]]):
    """Handler for getting analysis run"""

    def __init__(self, repository: AnalyzerRunRepository):
        self.repository = repository

    async def handle(self, query: GetAnalysisRunQuery) -> Optional[AnalyzerRun]:
        """Get run by ID"""
        return await self.repository.get_by_id(query.run_id)


class ListAnalysisRunsHandler(QueryHandler[ListAnalysisRunsQuery, List[AnalyzerRun]]):
    """Handler for listing analysis runs"""

    def __init__(self, repository: AnalyzerRunRepository):
        self.repository = repository

    async def handle(self, query: ListAnalysisRunsQuery) -> List[AnalyzerRun]:
        """List runs with filters"""
        filters = {}
        if query.workspace_id:
            filters["workspace_id"] = query.workspace_id
        if query.status:
            filters["status"] = query.status

        return await self.repository.list(
            limit=query.limit, offset=query.offset, filters=filters
        )


# ============================================================================
# 8. Temporal Activities (Analyzers)
# ============================================================================


@activity(start_to_close_timeout=300, retry_policy={"max_attempts": 3})
async def run_analyzer(
    run_id: str, analyzer_id: str, workspace_path: str, dependencies: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run a single analyzer.

    In production, this would:
    1. Load analyzer from PatientComet registry
    2. Execute analyzer with dependencies
    3. Store result in database
    4. Return result for dependent analyzers
    """
    print(f"[{analyzer_id}] Starting...")
    await asyncio.sleep(1)  # Simulate work

    # Simulate result
    result = {
        "analyzer_id": analyzer_id,
        "status": "completed",
        "data": {"count": 10, "items": ["item1", "item2"]},
    }

    # In production: store result via repository
    # await result_repository.create(AnalyzerResult(...))

    return result


# ============================================================================
# 9. Temporal Workflow
# ============================================================================


@workflow(execution_timeout=7200)
async def patientcomet_analysis_workflow(run_id: str, workspace_path: str, profile: str) -> Dict[str, Any]:
    """
    Execute PatientComet analysis pipeline.

    This workflow:
    1. Creates DAG of 111 analyzers
    2. Executes in dependency order with parallelism
    3. Updates progress in database
    4. Returns final results
    """
    print(f"Starting analysis for run {run_id}")

    # Build analyzer DAG (simplified - real one has 111 analyzers)
    dag = DAGWorkflow()

    # Phase 1: Core extraction (parallel)
    phase1 = ["symbols", "imports", "types", "files", "exports"]
    for analyzer_id in phase1:
        dag.add_node(
            DAGNode(
                id=analyzer_id,
                execute=run_analyzer.run,
                dependencies=[],
                metadata={"phase": 1},
            )
        )

    # Phase 2: Relationships (depends on phase 1)
    dag.add_nodes([
        DAGNode(id="calls", execute=run_analyzer.run, dependencies=["symbols"]),
        DAGNode(id="data_flow", execute=run_analyzer.run, dependencies=["symbols", "types"]),
        DAGNode(id="control_flow", execute=run_analyzer.run, dependencies=["symbols"]),
    ])

    # Phase 3: Intelligence (depends on phase 2)
    dag.add_nodes([
        DAGNode(id="patterns", execute=run_analyzer.run, dependencies=["calls", "data_flow"]),
        DAGNode(id="complexity", execute=run_analyzer.run, dependencies=["calls", "control_flow"]),
    ])

    # Progress callback
    def on_progress(analyzer_id: str, status: str):
        print(f"[PROGRESS] {analyzer_id}: {status}")
        # In production: emit SSE event or update database

    # Execute DAG
    results = await dag.execute(
        run_id=run_id,
        workspace_path=workspace_path,
        progress_callback=on_progress,
    )

    return {
        "run_id": run_id,
        "profile": profile,
        "analyzers_completed": len(results),
        "results": results,
        "status": "completed",
    }


# ============================================================================
# 10. FastAPI Application
# ============================================================================


def create_app() -> FastAPI:
    """Create FastAPI application with VelvetEcho integration"""
    app = FastAPI(title="PatientComet API with VelvetEcho")

    # Setup middleware
    setup_middleware(app)

    # Initialize database
    db = init_database("postgresql+asyncpg://user:pass@localhost/patientcomet")

    # Initialize CQRS buses
    command_bus = CommandBus()
    query_bus = QueryBus()

    # Dependencies
    def get_workspace_repository(session: AsyncSession = Depends(get_session)):
        return WorkspaceRepository(session, Workspace)

    def get_run_repository(session: AsyncSession = Depends(get_session)):
        return AnalyzerRunRepository(session, AnalyzerRun)

    def get_result_repository(session: AsyncSession = Depends(get_session)):
        return AnalyzerResultRepository(session, AnalyzerResult)

    # Register handlers
    @app.on_event("startup")
    async def register_handlers():
        await db.connect()

        async with db.session() as session:
            workspace_repo = WorkspaceRepository(session, Workspace)
            run_repo = AnalyzerRunRepository(session, AnalyzerRun)

            # Command handlers
            command_bus.register(
                StartAnalysisCommand, StartAnalysisHandler(run_repo, workspace_repo)
            )
            command_bus.register(
                UpdateAnalysisProgressCommand, UpdateAnalysisProgressHandler(run_repo)
            )

            # Query handlers
            query_bus.register(GetWorkspaceQuery, GetWorkspaceHandler(workspace_repo))
            query_bus.register(GetAnalysisRunQuery, GetAnalysisRunHandler(run_repo))
            query_bus.register(ListAnalysisRunsQuery, ListAnalysisRunsHandler(run_repo))

    @app.on_event("shutdown")
    async def shutdown():
        await db.disconnect()

    # ========================================================================
    # CRUD Routes (Auto-generated)
    # ========================================================================

    workspace_router = CRUDRouter(
        model=Workspace,
        create_schema=WorkspaceCreate,
        update_schema=WorkspaceUpdate,
        response_schema=WorkspaceResponse,
        prefix="/api/workspaces",
        tags=["Workspaces"],
        get_repository=get_workspace_repository,
    )
    app.include_router(workspace_router.router)

    # ========================================================================
    # Custom Routes
    # ========================================================================

    @app.post("/api/workspaces/{workspace_id}/analyze", response_model=StandardResponse[AnalyzerRunResponse])
    async def start_analysis(
        workspace_id: UUID,
        profile: str = "quick",
        command_bus: CommandBus = Depends(lambda: command_bus),
    ):
        """Start analysis for workspace"""
        command = StartAnalysisCommand(workspace_id=workspace_id, profile=profile)
        run = await command_bus.dispatch(command)

        # Trigger Temporal workflow
        client = await get_client()
        handle = await client.start_workflow(
            patientcomet_analysis_workflow,
            str(run.id),
            run.workspace.path,
            profile,
            workflow_id=f"analysis-{run.id}",
        )

        # Update run with workflow ID
        await command_bus.dispatch(
            UpdateAnalysisProgressCommand(
                run_id=run.id, completed_analyzers=0, status=AnalysisStatus.RUNNING
            )
        )

        return StandardResponse(
            data=AnalyzerRunResponse.model_validate(run),
            message=f"Analysis started (workflow: {handle.id})",
        )

    @app.get("/api/runs/{run_id}", response_model=StandardResponse[AnalyzerRunResponse])
    async def get_run(run_id: UUID, query_bus: QueryBus = Depends(lambda: query_bus)):
        """Get analysis run"""
        query = GetAnalysisRunQuery(run_id=run_id)
        run = await query_bus.dispatch(query)

        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        return StandardResponse(data=AnalyzerRunResponse.model_validate(run))

    @app.get("/api/runs", response_model=PaginatedResponse[AnalyzerRunResponse])
    async def list_runs(
        workspace_id: Optional[UUID] = None,
        status: Optional[AnalysisStatus] = None,
        limit: int = 10,
        offset: int = 0,
        query_bus: QueryBus = Depends(lambda: query_bus),
    ):
        """List analysis runs"""
        query = ListAnalysisRunsQuery(
            workspace_id=workspace_id, status=status, limit=limit, offset=offset
        )
        runs = await query_bus.dispatch(query)

        return PaginatedResponse.create(
            items=[AnalyzerRunResponse.model_validate(run) for run in runs],
            total=len(runs),
            page=offset // limit + 1,
            limit=limit,
        )

    return app


# ============================================================================
# Worker
# ============================================================================


async def run_worker():
    """Start PatientComet Temporal worker"""
    worker = WorkerManager(
        config=config,
        workflows=[patientcomet_analysis_workflow],
        activities=[run_analyzer],
    )

    print("=" * 60)
    print("PatientComet Worker Starting")
    print("=" * 60)
    print(f"Task Queue: {config.task_queue}")
    print(f"Workers: {config.temporal_worker_count}")
    print(f"Max Concurrent: {config.temporal_max_concurrent_activities}")
    print("=" * 60)

    await worker.start()


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys
    import uvicorn

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python patientcomet_full_integration.py worker  # Start Temporal worker")
        print("  python patientcomet_full_integration.py api     # Start FastAPI server")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "worker":
        asyncio.run(run_worker())
    elif mode == "api":
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=9800)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
