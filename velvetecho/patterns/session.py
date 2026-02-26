"""Session workflow pattern for long-running interactive sessions with queuing"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from temporalio import workflow


@dataclass
class SessionState:
    """State of a session workflow"""

    session_id: str
    agent_id: str
    requests: List[Dict[str, Any]] = field(default_factory=list)  # Queue
    history: List[Dict[str, Any]] = field(default_factory=list)   # Completed
    current_request: Optional[Dict[str, Any]] = None
    status: str = "active"  # active, paused, terminated
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionWorkflow:
    """
    Helper for building long-running session workflows.

    Features:
    - Request queuing (FIFO)
    - Signal handlers for adding requests
    - Query handlers for state inspection
    - Pause/resume support
    - Clean termination

    Example:
        @workflow
        async def agent_session(session_id: str, agent_id: str):
            session = SessionWorkflow(session_id, agent_id)

            # Register signal/query handlers
            session.register_handlers()

            # Run session loop
            async for request in session.request_loop():
                result = await execute_request.run(
                    session_id=session_id,
                    request=request,
                )
                session.add_to_history(request, result)

            return session.get_state()
    """

    def __init__(self, session_id: str, agent_id: str, initial_request: Optional[Dict] = None):
        self.state = SessionState(
            session_id=session_id,
            agent_id=agent_id,
        )

        if initial_request:
            self.state.requests.append(initial_request)

    def register_handlers(self):
        """Register signal and query handlers with Temporal workflow"""

        @workflow.signal
        def add_request(request: Dict[str, Any]):
            """Add request to queue"""
            self.state.requests.append(request)

        @workflow.signal
        def pause():
            """Pause session"""
            self.state.status = "paused"

        @workflow.signal
        def resume():
            """Resume session"""
            if self.state.status == "paused":
                self.state.status = "active"

        @workflow.signal
        def terminate():
            """Terminate session"""
            self.state.status = "terminated"

        @workflow.query
        def get_state():
            """Get current session state"""
            return {
                "session_id": self.state.session_id,
                "agent_id": self.state.agent_id,
                "status": self.state.status,
                "queued_requests": len(self.state.requests),
                "completed_requests": len(self.state.history),
                "current_request": self.state.current_request,
                "metadata": self.state.metadata,
            }

        @workflow.query
        def get_history():
            """Get request history"""
            return self.state.history

    async def request_loop(self):
        """
        Async generator that yields requests from the queue.

        Handles:
        - Waiting for new requests when queue is empty
        - Respecting pause/terminate status
        - Updating current_request state

        Usage:
            async for request in session.request_loop():
                result = await process_request(request)
                session.add_to_history(request, result)
        """
        while self.state.status != "terminated":
            # Wait if paused
            if self.state.status == "paused":
                await workflow.wait_condition(lambda: self.state.status != "paused")
                continue

            # Wait for requests
            if not self.state.requests:
                await workflow.wait_condition(
                    lambda: len(self.state.requests) > 0 or self.state.status == "terminated"
                )
                continue

            # Get next request
            if self.state.requests and self.state.status == "active":
                request = self.state.requests.pop(0)
                self.state.current_request = request
                yield request
                self.state.current_request = None

    def add_to_history(
        self,
        request: Dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ):
        """Add completed request to history"""
        self.state.history.append({
            "request": request,
            "result": result,
            "error": error,
            "status": "success" if error is None else "failed",
        })

    def get_state(self) -> Dict[str, Any]:
        """Get current state as dict"""
        return {
            "session_id": self.state.session_id,
            "agent_id": self.state.agent_id,
            "status": self.state.status,
            "requests": self.state.requests,
            "history": self.state.history,
            "metadata": self.state.metadata,
        }

    def set_metadata(self, key: str, value: Any):
        """Set metadata field"""
        self.state.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata field"""
        return self.state.metadata.get(key, default)
