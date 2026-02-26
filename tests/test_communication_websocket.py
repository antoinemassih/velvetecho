"""Tests for WebSocket manager"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from velvetecho.communication.websocket import ConnectionManager


@pytest.mark.asyncio
async def test_connection_manager_connect():
    """Test connecting a client"""
    manager = ConnectionManager()
    websocket = AsyncMock()

    await manager.connect(websocket, "client-1")

    websocket.accept.assert_called_once()
    assert len(manager._connections) == 1
    assert "client-1" in manager._connections


@pytest.mark.asyncio
async def test_connection_manager_disconnect():
    """Test disconnecting a client"""
    manager = ConnectionManager()
    websocket = AsyncMock()

    await manager.connect(websocket, "client-1")
    await manager.disconnect("client-1")

    assert len(manager._connections) == 0
    assert "client-1" not in manager._connections


@pytest.mark.asyncio
async def test_connection_manager_send_personal():
    """Test sending message to specific client"""
    manager = ConnectionManager()
    websocket = AsyncMock()

    await manager.connect(websocket, "client-1")

    result = await manager.send_personal("client-1", {"message": "hello"})

    assert result is True
    websocket.send_json.assert_called_once_with({"message": "hello"})


@pytest.mark.asyncio
async def test_connection_manager_send_to_nonexistent_client():
    """Test sending to client that doesn't exist"""
    manager = ConnectionManager()

    result = await manager.send_personal("nonexistent", {"message": "hello"})

    assert result is False


@pytest.mark.asyncio
async def test_connection_manager_broadcast():
    """Test broadcasting to all clients"""
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.connect(ws2, "client-2")

    sent_count = await manager.broadcast({"message": "hello"})

    assert sent_count == 2
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_broadcast_with_exclude():
    """Test broadcasting with exclusion"""
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.connect(ws2, "client-2")

    sent_count = await manager.broadcast({"message": "hello"}, exclude={"client-1"})

    assert sent_count == 1
    ws1.send_json.assert_not_called()
    ws2.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_rooms():
    """Test room functionality"""
    manager = ConnectionManager()
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws3 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.connect(ws2, "client-2")
    await manager.connect(ws3, "client-3")

    # Join rooms
    await manager.join_room("client-1", "room-A")
    await manager.join_room("client-2", "room-A")
    await manager.join_room("client-3", "room-B")

    # Broadcast to room-A
    sent_count = await manager.broadcast_to_room("room-A", {"message": "hello"})

    assert sent_count == 2
    ws1.send_json.assert_called_once()
    ws2.send_json.assert_called_once()
    ws3.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_connection_manager_leave_room():
    """Test leaving a room"""
    manager = ConnectionManager()
    ws1 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.join_room("client-1", "room-A")

    # Verify in room
    assert "client-1" in manager.get_room_clients("room-A")

    # Leave room
    await manager.leave_room("client-1", "room-A")

    # Verify not in room
    assert "client-1" not in manager.get_room_clients("room-A")


@pytest.mark.asyncio
async def test_connection_manager_get_client_rooms():
    """Test getting rooms a client is in"""
    manager = ConnectionManager()
    ws1 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.join_room("client-1", "room-A")
    await manager.join_room("client-1", "room-B")

    rooms = manager.get_client_rooms("client-1")

    assert rooms == {"room-A", "room-B"}


@pytest.mark.asyncio
async def test_connection_manager_disconnect_removes_from_rooms():
    """Test that disconnect removes client from all rooms"""
    manager = ConnectionManager()
    ws1 = AsyncMock()

    await manager.connect(ws1, "client-1")
    await manager.join_room("client-1", "room-A")
    await manager.join_room("client-1", "room-B")

    await manager.disconnect("client-1")

    assert "client-1" not in manager.get_room_clients("room-A")
    assert "client-1" not in manager.get_room_clients("room-B")
