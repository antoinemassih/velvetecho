"""WebSocket connection management"""

import asyncio
from typing import Dict, Set, Optional, Any
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections for real-time communication.

    Features:
    - Connection tracking
    - Broadcast to all connections
    - Room/channel support
    - Heartbeat/keepalive
    - Graceful disconnect handling

    Example:
        manager = ConnectionManager()

        @app.websocket("/ws/{client_id}")
        async def websocket_endpoint(websocket: WebSocket, client_id: str):
            await manager.connect(websocket, client_id)
            try:
                while True:
                    data = await websocket.receive_text()
                    await manager.broadcast(f"Client {client_id}: {data}")
            except WebSocketDisconnect:
                await manager.disconnect(client_id)
    """

    def __init__(self):
        # Map client_id -> WebSocket
        self._connections: Dict[str, WebSocket] = {}

        # Map room -> set of client_ids
        self._rooms: Dict[str, Set[str]] = defaultdict(set)

        # Heartbeat tracking
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        heartbeat_interval: Optional[int] = None,
    ) -> None:
        """
        Accept and track a new WebSocket connection.

        Args:
            websocket: FastAPI WebSocket
            client_id: Unique client identifier
            heartbeat_interval: Optional heartbeat interval in seconds
        """
        await websocket.accept()
        self._connections[client_id] = websocket

        logger.info("WebSocket connected", client_id=client_id, total=len(self._connections))

        # Start heartbeat if enabled
        if heartbeat_interval:
            task = asyncio.create_task(self._heartbeat(client_id, heartbeat_interval))
            self._heartbeat_tasks[client_id] = task

    async def disconnect(self, client_id: str) -> None:
        """
        Disconnect and clean up a client.

        Args:
            client_id: Client identifier
        """
        # Remove from connections
        if client_id in self._connections:
            del self._connections[client_id]

        # Remove from all rooms
        for room_clients in self._rooms.values():
            room_clients.discard(client_id)

        # Cancel heartbeat
        if client_id in self._heartbeat_tasks:
            self._heartbeat_tasks[client_id].cancel()
            del self._heartbeat_tasks[client_id]

        logger.info("WebSocket disconnected", client_id=client_id, total=len(self._connections))

    async def send_personal(self, client_id: str, message: Any) -> bool:
        """
        Send message to a specific client.

        Args:
            client_id: Target client
            message: Message to send (JSON serializable)

        Returns:
            True if sent, False if client not found
        """
        websocket = self._connections.get(client_id)
        if not websocket:
            return False

        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.error("Failed to send message", client_id=client_id, error=str(e))
            await self.disconnect(client_id)
            return False

    async def broadcast(self, message: Any, exclude: Optional[Set[str]] = None) -> int:
        """
        Broadcast message to all connected clients.

        Args:
            message: Message to send (JSON serializable)
            exclude: Optional set of client_ids to exclude

        Returns:
            Number of clients message was sent to
        """
        exclude = exclude or set()
        sent_count = 0

        # Get all client IDs to send to
        target_clients = [
            client_id for client_id in self._connections.keys() if client_id not in exclude
        ]

        # Send concurrently
        tasks = [self.send_personal(client_id, message) for client_id in target_clients]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sent_count = sum(1 for result in results if result is True)

        logger.debug("Broadcast message", sent=sent_count, total=len(target_clients))

        return sent_count

    async def join_room(self, client_id: str, room: str) -> None:
        """Add client to a room"""
        self._rooms[room].add(client_id)
        logger.info("Client joined room", client_id=client_id, room=room)

    async def leave_room(self, client_id: str, room: str) -> None:
        """Remove client from a room"""
        self._rooms[room].discard(client_id)
        logger.info("Client left room", client_id=client_id, room=room)

    async def broadcast_to_room(self, room: str, message: Any) -> int:
        """
        Broadcast message to all clients in a room.

        Args:
            room: Room name
            message: Message to send

        Returns:
            Number of clients message was sent to
        """
        client_ids = self._rooms.get(room, set())

        tasks = [self.send_personal(client_id, message) for client_id in client_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        sent_count = sum(1 for result in results if result is True)

        logger.debug("Broadcast to room", room=room, sent=sent_count, total=len(client_ids))

        return sent_count

    def get_room_clients(self, room: str) -> Set[str]:
        """Get all client IDs in a room"""
        return self._rooms.get(room, set()).copy()

    def get_client_rooms(self, client_id: str) -> Set[str]:
        """Get all rooms a client is in"""
        return {room for room, clients in self._rooms.items() if client_id in clients}

    async def _heartbeat(self, client_id: str, interval: int) -> None:
        """Send periodic heartbeat to client"""
        try:
            while True:
                await asyncio.sleep(interval)

                success = await self.send_personal(
                    client_id, {"type": "heartbeat", "timestamp": asyncio.get_event_loop().time()}
                )

                if not success:
                    break
        except asyncio.CancelledError:
            pass


class WebSocketManager:
    """
    High-level WebSocket manager with room support.

    Convenience wrapper around ConnectionManager.

    Example:
        manager = WebSocketManager()

        @app.websocket("/ws")
        async def endpoint(websocket: WebSocket):
            client_id = str(uuid.uuid4())
            await manager.connect(websocket, client_id)

            try:
                while True:
                    data = await websocket.receive_json()

                    if data["action"] == "join":
                        await manager.join_room(client_id, data["room"])
                    elif data["action"] == "message":
                        await manager.send_to_room(data["room"], data["message"])
            except WebSocketDisconnect:
                await manager.disconnect(client_id)
    """

    def __init__(self):
        self._manager = ConnectionManager()

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        heartbeat_interval: Optional[int] = 30,
    ) -> None:
        """Connect a new client"""
        await self._manager.connect(websocket, client_id, heartbeat_interval)

    async def disconnect(self, client_id: str) -> None:
        """Disconnect a client"""
        await self._manager.disconnect(client_id)

    async def send(self, client_id: str, message: Any) -> bool:
        """Send message to specific client"""
        return await self._manager.send_personal(client_id, message)

    async def broadcast(self, message: Any) -> int:
        """Broadcast to all clients"""
        return await self._manager.broadcast(message)

    async def join_room(self, client_id: str, room: str) -> None:
        """Add client to room"""
        await self._manager.join_room(client_id, room)

    async def leave_room(self, client_id: str, room: str) -> None:
        """Remove client from room"""
        await self._manager.leave_room(client_id, room)

    async def send_to_room(self, room: str, message: Any) -> int:
        """Send message to all clients in room"""
        return await self._manager.broadcast_to_room(room, message)

    def get_room_clients(self, room: str) -> Set[str]:
        """Get clients in room"""
        return self._manager.get_room_clients(room)

    @property
    def connection_count(self) -> int:
        """Get total number of connections"""
        return len(self._manager._connections)
