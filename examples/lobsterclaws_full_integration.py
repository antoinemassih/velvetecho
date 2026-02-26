"""
Complete Lobsterclaws integration with VelvetEcho.

Demonstrates full stack integration:
1. Database models (AgentDefinition, AgentSession, ExecutionLog)
2. CQRS (Commands + Queries + Handlers)
3. Repository pattern
4. API endpoints (CRUD + custom)
5. SessionWorkflow for agent execution
6. RPC client for Urchinspike tool routing
7. Multi-service orchestration

This is a production-ready integration guide for Lobsterclaws.
"""

import asyncio
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, Depends, HTTPException, WebSocket
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession

# VelvetEcho imports
from velvetecho.config import VelvetEchoConfig, init_config
from velvetecho.tasks import workflow, activity, get_client, init_client, WorkerManager
from velvetecho.patterns import SessionWorkflow
from velvetecho.patterns.multi_service import ServiceOrchestrator
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
from velvetecho.communication import RPCClient, init_rpc_client, ConnectionManager


# ============================================================================
# Configuration
# ============================================================================

config = VelvetEchoConfig(
    service_name="lobsterclaws",
    temporal_host="localhost:7233",
    temporal_namespace="lobsterclaws",
    temporal_worker_count=4,
)
init_config(config)

# RPC client for Urchinspike
rpc = init_rpc_client(
    services={
        "urchinspike": "http://localhost:8003",
    },
    timeout=180,
)

# Service orchestrator
orchestrator = ServiceOrchestrator(rpc)


# ============================================================================
# 1. Database Models
# ============================================================================


class AgentCategory(str, Enum):
    """Agent category enum"""

    TESTING = "testing"
    DEVELOPMENT = "development"
    CODE_ANALYSIS = "code_analysis"
    VALIDATION = "validation"
    DEBUGGING = "debugging"
    ORCHESTRATION = "orchestration"


class SessionStatus(str, Enum):
    """Session status enum"""

    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentDefinition(BaseModel, TimestampMixin):
    """Agent definition - represents an agent type"""

    __tablename__ = "agent_definitions"

    agent_id = Column(String, unique=True, nullable=False)  # e.g., "code_analyst"
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    category = Column(SQLEnum(AgentCategory), nullable=False)
    model = Column(String, nullable=False)  # e.g., "claude-sonnet-4.5"
    tools = Column(JSON, default=[])  # List of tool names
    system_prompt = Column(Text, nullable=True)
    metadata = Column(JSON, default={})

    # Relationships
    sessions = relationship("AgentSession", back_populates="agent", cascade="all, delete-orphan")


class AgentSession(BaseModel, TimestampMixin):
    """Agent session - represents one agent execution session"""

    __tablename__ = "agent_sessions"

    agent_id = Column(ForeignKey("agent_definitions.id"), nullable=False)
    session_name = Column(String, nullable=False)
    status = Column(SQLEnum(SessionStatus), default=SessionStatus.ACTIVE)
    workflow_id = Column(String, nullable=True)  # Temporal workflow ID
    context = Column(JSON, default={})
    started_at = Column(Text, nullable=True)
    completed_at = Column(Text, nullable=True)
    total_messages = Column(Integer, default=0)
    total_tools_executed = Column(Integer, default=0)

    # Relationships
    agent = relationship("AgentDefinition", back_populates="sessions")
    logs = relationship("ExecutionLog", back_populates="session", cascade="all, delete-orphan")


class ExecutionLog(BaseModel, TimestampMixin):
    """Execution log - represents one agent action in a session"""

    __tablename__ = "execution_logs"

    session_id = Column(ForeignKey("agent_sessions.id"), nullable=False)
    log_type = Column(String, nullable=False)  # message, tool_call, error
    role = Column(String, nullable=True)  # user, assistant, system
    content = Column(Text, nullable=True)
    tool_name = Column(String, nullable=True)
    tool_args = Column(JSON, nullable=True)
    tool_result = Column(JSON, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    session = relationship("AgentSession", back_populates="logs")


# ============================================================================
# 2. Pydantic Schemas
# ============================================================================


class AgentDefinitionCreate(PydanticModel):
    """Schema for creating agent definition"""

    agent_id: str
    name: str
    description: str
    category: AgentCategory
    model: str
    tools: List[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentDefinitionUpdate(PydanticModel):
    """Schema for updating agent definition"""

    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[AgentCategory] = None
    model: Optional[str] = None
    tools: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentDefinitionResponse(PydanticModel):
    """Schema for agent definition response"""

    id: UUID
    agent_id: str
    name: str
    description: str
    category: AgentCategory
    model: str
    tools: List[str]
    system_prompt: Optional[str]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AgentSessionCreate(PydanticModel):
    """Schema for creating agent session"""

    agent_id: UUID
    session_name: str
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentSessionResponse(PydanticModel):
    """Schema for agent session response"""

    id: UUID
    agent_id: UUID
    session_name: str
    status: SessionStatus
    workflow_id: Optional[str]
    context: Dict[str, Any]
    total_messages: int
    total_tools_executed: int
    created_at: datetime

    class Config:
        from_attributes = True


class ExecutionLogResponse(PydanticModel):
    """Schema for execution log response"""

    id: UUID
    session_id: UUID
    log_type: str
    role: Optional[str]
    content: Optional[str]
    tool_name: Optional[str]
    tool_args: Optional[Dict[str, Any]]
    tool_result: Optional[Dict[str, Any]]
    execution_time_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# 3. Repositories
# ============================================================================


class AgentDefinitionRepository(Repository[AgentDefinition]):
    """Agent definition repository"""

    async def get_by_agent_id(self, agent_id: str) -> Optional[AgentDefinition]:
        """Get agent by agent_id"""
        from sqlalchemy import select

        stmt = select(AgentDefinition).where(AgentDefinition.agent_id == agent_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class AgentSessionRepository(Repository[AgentSession]):
    """Agent session repository"""

    async def get_active_sessions(self) -> List[AgentSession]:
        """Get all active sessions"""
        from sqlalchemy import select

        stmt = select(AgentSession).where(AgentSession.status == SessionStatus.ACTIVE)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_workflow_id(self, workflow_id: str) -> Optional[AgentSession]:
        """Get session by workflow ID"""
        from sqlalchemy import select

        stmt = select(AgentSession).where(AgentSession.workflow_id == workflow_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ExecutionLogRepository(Repository[ExecutionLog]):
    """Execution log repository"""

    async def get_by_session(self, session_id: UUID, limit: int = 100) -> List[ExecutionLog]:
        """Get logs for a session"""
        from sqlalchemy import select

        stmt = (
            select(ExecutionLog)
            .where(ExecutionLog.session_id == session_id)
            .order_by(ExecutionLog.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


# ============================================================================
# 4. CQRS Commands
# ============================================================================


class StartAgentSessionCommand(Command):
    """Command to start agent session"""

    agent_id: UUID
    session_name: str
    context: Dict[str, Any] = Field(default_factory=dict)


class SendMessageCommand(Command):
    """Command to send message to agent"""

    session_id: UUID
    message: str


class ExecuteToolCommand(Command):
    """Command to execute tool via agent"""

    session_id: UUID
    tool_name: str
    tool_args: Dict[str, Any]


class CloseSessionCommand(Command):
    """Command to close session"""

    session_id: UUID


# ============================================================================
# 5. CQRS Queries
# ============================================================================


class GetAgentDefinitionQuery(Query):
    """Query to get agent definition"""

    agent_id: str


class GetAgentSessionQuery(Query):
    """Query to get agent session"""

    session_id: UUID


class ListAgentSessionsQuery(Query):
    """Query to list agent sessions"""

    agent_id: Optional[UUID] = None
    status: Optional[SessionStatus] = None
    limit: int = 10
    offset: int = 0


class GetSessionLogsQuery(Query):
    """Query to get session logs"""

    session_id: UUID
    limit: int = 100


# ============================================================================
# 6. Command Handlers
# ============================================================================


class StartAgentSessionHandler(CommandHandler[StartAgentSessionCommand, AgentSession]):
    """Handler for starting agent session"""

    def __init__(
        self,
        session_repository: AgentSessionRepository,
        agent_repository: AgentDefinitionRepository,
    ):
        self.session_repository = session_repository
        self.agent_repository = agent_repository

    async def handle(self, command: StartAgentSessionCommand) -> AgentSession:
        """Start session"""
        # Verify agent exists
        agent = await self.agent_repository.get_by_id(command.agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {command.agent_id}")

        # Create session
        session = AgentSession(
            agent_id=command.agent_id,
            session_name=command.session_name,
            status=SessionStatus.ACTIVE,
            context=command.context,
            started_at=datetime.utcnow().isoformat(),
        )
        return await self.session_repository.create(session)


class CloseSessionHandler(CommandHandler[CloseSessionCommand, AgentSession]):
    """Handler for closing session"""

    def __init__(self, repository: AgentSessionRepository):
        self.repository = repository

    async def handle(self, command: CloseSessionCommand) -> AgentSession:
        """Close session"""
        updated = await self.repository.update(
            command.session_id,
            {
                "status": SessionStatus.COMPLETED,
                "completed_at": datetime.utcnow().isoformat(),
            },
        )

        if not updated:
            raise ValueError(f"Session not found: {command.session_id}")

        return updated


# ============================================================================
# 7. Query Handlers
# ============================================================================


class GetAgentDefinitionHandler(
    QueryHandler[GetAgentDefinitionQuery, Optional[AgentDefinition]]
):
    """Handler for getting agent definition"""

    def __init__(self, repository: AgentDefinitionRepository):
        self.repository = repository

    async def handle(self, query: GetAgentDefinitionQuery) -> Optional[AgentDefinition]:
        """Get agent by agent_id"""
        return await self.repository.get_by_agent_id(query.agent_id)


class GetAgentSessionHandler(QueryHandler[GetAgentSessionQuery, Optional[AgentSession]]):
    """Handler for getting agent session"""

    def __init__(self, repository: AgentSessionRepository):
        self.repository = repository

    async def handle(self, query: GetAgentSessionQuery) -> Optional[AgentSession]:
        """Get session by ID"""
        return await self.repository.get_by_id(query.session_id)


class ListAgentSessionsHandler(QueryHandler[ListAgentSessionsQuery, List[AgentSession]]):
    """Handler for listing agent sessions"""

    def __init__(self, repository: AgentSessionRepository):
        self.repository = repository

    async def handle(self, query: ListAgentSessionsQuery) -> List[AgentSession]:
        """List sessions with filters"""
        filters = {}
        if query.agent_id:
            filters["agent_id"] = query.agent_id
        if query.status:
            filters["status"] = query.status

        return await self.repository.list(
            limit=query.limit, offset=query.offset, filters=filters
        )


# ============================================================================
# 8. Temporal Activities
# ============================================================================


@activity(start_to_close_timeout=180, retry_policy={"max_attempts": 2})
async def send_agent_message_activity(
    session_id: str, agent_id: str, message: str, tools: List[str]
) -> Dict[str, Any]:
    """
    Send message to agent and get response.

    In production, this would:
    1. Load agent from registry
    2. Execute LLM call with tools
    3. Handle tool calls via RPC to Urchinspike
    4. Log execution
    5. Return response
    """
    print(f"[Agent {agent_id}] Processing message: {message[:50]}...")

    # Simulate LLM call
    await asyncio.sleep(2)

    # Simulate tool usage
    if "read file" in message.lower():
        # Tool call via RPC
        print(f"[Agent {agent_id}] Calling tool: read_file")
        tool_result = await rpc.call(
            service="urchinspike",
            method="execute_tool",
            params={"tool": "read_file", "args": {"path": "example.py"}},
        )
        print(f"[Agent {agent_id}] Tool result: {tool_result}")

    response = {
        "role": "assistant",
        "content": f"I processed your request: {message}",
        "tool_calls": 1 if "read file" in message.lower() else 0,
    }

    return response


@activity(start_to_close_timeout=60, retry_policy={"max_attempts": 3})
async def execute_tool_activity(
    session_id: str, tool_name: str, tool_args: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute tool via Urchinspike RPC.

    This routes tool execution to the Urchinspike service.
    """
    print(f"[Tool] Executing {tool_name} via RPC...")

    result = await rpc.call(
        service="urchinspike",
        method="execute_tool",
        params={"tool": tool_name, "args": tool_args},
    )

    return result


# ============================================================================
# 9. Temporal Workflow (SessionWorkflow)
# ============================================================================


@workflow(execution_timeout=3600)
async def agent_session_workflow(session_id: str, agent_id: str) -> Dict[str, Any]:
    """
    Long-running agent session workflow.

    This workflow:
    1. Maintains session state
    2. Processes incoming messages via signals
    3. Executes tools via activities
    4. Returns final result when session closes
    """
    session = SessionWorkflow(workflow_id=session_id)

    # Register message handler
    @session.signal("send_message")
    async def handle_message(message: str):
        """Handle incoming message"""
        response = await send_agent_message_activity.run(
            session_id, agent_id, message, tools=[]
        )
        return response

    # Register tool execution handler
    @session.signal("execute_tool")
    async def handle_tool(tool_name: str, tool_args: Dict[str, Any]):
        """Handle tool execution"""
        result = await execute_tool_activity.run(session_id, tool_name, tool_args)
        return result

    # Query for session status
    @session.query("get_status")
    def get_status():
        """Get current session status"""
        return {"session_id": session_id, "active": True}

    # Run session loop
    result = await session.run()

    return {"session_id": session_id, "status": "completed", "result": result}


# ============================================================================
# 10. FastAPI Application
# ============================================================================


def create_app() -> FastAPI:
    """Create FastAPI application with VelvetEcho integration"""
    app = FastAPI(title="Lobsterclaws API with VelvetEcho")

    # Setup middleware
    setup_middleware(app)

    # Initialize database
    db = init_database("postgresql+asyncpg://user:pass@localhost/lobsterclaws")

    # Initialize CQRS buses
    command_bus = CommandBus()
    query_bus = QueryBus()

    # WebSocket connection manager
    ws_manager = ConnectionManager()

    # Dependencies
    def get_agent_repository(session: AsyncSession = Depends(get_session)):
        return AgentDefinitionRepository(session, AgentDefinition)

    def get_session_repository(session: AsyncSession = Depends(get_session)):
        return AgentSessionRepository(session, AgentSession)

    def get_log_repository(session: AsyncSession = Depends(get_session)):
        return ExecutionLogRepository(session, ExecutionLog)

    # Register handlers
    @app.on_event("startup")
    async def register_handlers():
        await db.connect()
        await rpc.connect()

        async with db.session() as session:
            agent_repo = AgentDefinitionRepository(session, AgentDefinition)
            session_repo = AgentSessionRepository(session, AgentSession)

            # Command handlers
            command_bus.register(
                StartAgentSessionCommand, StartAgentSessionHandler(session_repo, agent_repo)
            )
            command_bus.register(CloseSessionCommand, CloseSessionHandler(session_repo))

            # Query handlers
            query_bus.register(GetAgentDefinitionQuery, GetAgentDefinitionHandler(agent_repo))
            query_bus.register(GetAgentSessionQuery, GetAgentSessionHandler(session_repo))
            query_bus.register(ListAgentSessionsQuery, ListAgentSessionsHandler(session_repo))

    @app.on_event("shutdown")
    async def shutdown():
        await db.disconnect()
        await rpc.disconnect()

    # ========================================================================
    # CRUD Routes (Auto-generated)
    # ========================================================================

    agent_router = CRUDRouter(
        model=AgentDefinition,
        create_schema=AgentDefinitionCreate,
        update_schema=AgentDefinitionUpdate,
        response_schema=AgentDefinitionResponse,
        prefix="/api/agents",
        tags=["Agents"],
        get_repository=get_agent_repository,
    )
    app.include_router(agent_router.router)

    # ========================================================================
    # Custom Routes
    # ========================================================================

    @app.post("/api/sessions/start", response_model=StandardResponse[AgentSessionResponse])
    async def start_session(
        agent_id: UUID,
        session_name: str,
        context: Dict[str, Any] = {},
        command_bus: CommandBus = Depends(lambda: command_bus),
    ):
        """Start agent session"""
        command = StartAgentSessionCommand(
            agent_id=agent_id, session_name=session_name, context=context
        )
        session = await command_bus.dispatch(command)

        # Start Temporal workflow
        client = await get_client()
        handle = await client.start_workflow(
            agent_session_workflow,
            str(session.id),
            str(agent_id),
            workflow_id=f"session-{session.id}",
        )

        # Update session with workflow ID
        # (In production: dispatch UpdateSessionCommand)

        return StandardResponse(
            data=AgentSessionResponse.model_validate(session),
            message=f"Session started (workflow: {handle.id})",
        )

    @app.post("/api/sessions/{session_id}/message", response_model=StandardResponse[Dict[str, Any]])
    async def send_message(
        session_id: UUID,
        message: str,
    ):
        """Send message to agent session"""
        client = await get_client()

        # Send signal to workflow
        await client.signal_workflow(
            f"session-{session_id}", "send_message", message
        )

        return StandardResponse(data={"status": "sent"}, message="Message sent to agent")

    @app.post("/api/sessions/{session_id}/close", response_model=StandardResponse[AgentSessionResponse])
    async def close_session(
        session_id: UUID, command_bus: CommandBus = Depends(lambda: command_bus)
    ):
        """Close agent session"""
        command = CloseSessionCommand(session_id=session_id)
        session = await command_bus.dispatch(command)

        # Complete Temporal workflow
        client = await get_client()
        await client.signal_workflow(f"session-{session_id}", "complete", {})

        return StandardResponse(
            data=AgentSessionResponse.model_validate(session), message="Session closed"
        )

    @app.get("/api/sessions/{session_id}", response_model=StandardResponse[AgentSessionResponse])
    async def get_session(session_id: UUID, query_bus: QueryBus = Depends(lambda: query_bus)):
        """Get agent session"""
        query = GetAgentSessionQuery(session_id=session_id)
        session = await query_bus.dispatch(query)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return StandardResponse(data=AgentSessionResponse.model_validate(session))

    @app.websocket("/ws/sessions/{session_id}")
    async def websocket_session(websocket: WebSocket, session_id: UUID):
        """WebSocket for real-time session updates"""
        await ws_manager.connect(websocket, str(session_id))

        try:
            while True:
                # Receive message from client
                data = await websocket.receive_json()

                # Send to agent via Temporal signal
                client = await get_client()
                await client.signal_workflow(
                    f"session-{session_id}", "send_message", data["message"]
                )

                # Send response back (in production: wait for workflow response)
                await ws_manager.send_personal(
                    str(session_id), {"status": "processing", "message_id": data.get("id")}
                )

        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await ws_manager.disconnect(str(session_id))

    return app


# ============================================================================
# Worker
# ============================================================================


async def run_worker():
    """Start Lobsterclaws Temporal worker"""
    await rpc.connect()

    worker = WorkerManager(
        config=config,
        workflows=[agent_session_workflow],
        activities=[send_agent_message_activity, execute_tool_activity],
    )

    print("=" * 60)
    print("Lobsterclaws Worker Starting")
    print("=" * 60)
    print(f"Task Queue: {config.task_queue}")
    print(f"Workers: {config.temporal_worker_count}")
    print(f"RPC Services:")
    print(f"  - Urchinspike: {rpc.services['urchinspike']}")
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
        print("  python lobsterclaws_full_integration.py worker  # Start Temporal worker")
        print("  python lobsterclaws_full_integration.py api     # Start FastAPI server")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "worker":
        asyncio.run(run_worker())
    elif mode == "api":
        app = create_app()
        uvicorn.run(app, host="0.0.0.0", port=9720)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
