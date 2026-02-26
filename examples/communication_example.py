"""
Example demonstrating all communication patterns.

Shows:
1. Event Bus - Pub/sub for service events
2. RPC Client - Service-to-service calls
3. WebSocket Manager - Real-time communication
"""

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from velvetecho.communication import (
    EventBus,
    Event,
    RPCClient,
    WebSocketManager,
)

# ============================================================================
# 1. Event Bus Example
# ============================================================================


async def event_bus_example():
    """Example: Using event bus for service events"""
    print("\n=== Event Bus Example ===\n")

    bus = EventBus()

    # Subscribe to events
    @bus.subscribe("workflow.started")
    async def on_workflow_started(event: Event):
        print(f"[Subscriber 1] Workflow started: {event.data}")

    @bus.subscribe("workflow.started")
    async def send_notification(event: Event):
        print(f"[Subscriber 2] Sending notification for workflow {event.data['workflow_id']}")

    @bus.subscribe("workflow.completed")
    async def on_workflow_completed(event: Event):
        print(f"[Subscriber] Workflow completed: {event.data}")

    # Publish events
    print("Publishing workflow.started event...")
    await bus.publish(
        "workflow.started",
        {"workflow_id": "wf-123", "name": "Data Pipeline"},
    )

    await asyncio.sleep(0.2)

    print("\nPublishing workflow.completed event...")
    await bus.publish(
        "workflow.completed",
        {"workflow_id": "wf-123", "status": "success", "duration": 42},
    )

    await asyncio.sleep(0.2)


# ============================================================================
# 2. RPC Client Example
# ============================================================================


async def rpc_client_example():
    """Example: Service-to-service RPC calls"""
    print("\n=== RPC Client Example ===\n")

    # Initialize RPC client with service registry
    rpc = RPCClient(
        services={
            "patientcomet": "http://localhost:9800",
            "whalefin": "http://localhost:8002",
            "urchinspike": "http://localhost:8003",
        },
        timeout=30,
    )

    await rpc.connect()

    try:
        # Call PatientComet
        print("Calling PatientComet: run_analysis")
        result = await rpc.call(
            service="patientcomet",
            method="run_analysis",
            params={"workspace_id": "ws-123", "profile": "quick"},
        )
        print(f"Result: {result}\n")

    except Exception as e:
        print(f"RPC call failed: {e}\n")

    try:
        # Call Whalefin
        print("Calling Whalefin: list_agents")
        agents = await rpc.call(
            service="whalefin",
            method="list_agents",
            params={},
        )
        print(f"Agents: {agents}\n")

    except Exception as e:
        print(f"RPC call failed: {e}\n")

    # Batch calls (parallel)
    print("Making batch RPC calls...")
    results = await rpc.call_batch(
        [
            {"service": "patientcomet", "method": "get_workspace", "params": {"id": "1"}},
            {"service": "whalefin", "method": "get_agent", "params": {"id": "agent-1"}},
        ]
    )
    print(f"Batch results: {results}\n")

    await rpc.disconnect()


# ============================================================================
# 3. WebSocket Manager Example
# ============================================================================


def websocket_example():
    """Example: WebSocket real-time communication"""
    print("\n=== WebSocket Manager Example ===\n")

    app = FastAPI()
    manager = WebSocketManager()

    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        """WebSocket endpoint with room support"""
        print(f"Client {client_id} connecting...")
        await manager.connect(websocket, client_id, heartbeat_interval=30)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()

                if data["action"] == "join":
                    # Join a room
                    room = data["room"]
                    await manager.join_room(client_id, room)
                    print(f"Client {client_id} joined room {room}")

                    # Notify room
                    await manager.send_to_room(
                        room, {"type": "user_joined", "client_id": client_id}
                    )

                elif data["action"] == "leave":
                    # Leave a room
                    room = data["room"]
                    await manager.leave_room(client_id, room)
                    print(f"Client {client_id} left room {room}")

                    # Notify room
                    await manager.send_to_room(
                        room, {"type": "user_left", "client_id": client_id}
                    )

                elif data["action"] == "message":
                    # Send message to room
                    room = data["room"]
                    message = data["message"]

                    await manager.send_to_room(
                        room,
                        {
                            "type": "message",
                            "from": client_id,
                            "message": message,
                        },
                    )

                elif data["action"] == "broadcast":
                    # Broadcast to all clients
                    message = data["message"]
                    await manager.broadcast(
                        {"type": "broadcast", "from": client_id, "message": message}
                    )

        except WebSocketDisconnect:
            print(f"Client {client_id} disconnected")
            await manager.disconnect(client_id)

    print("WebSocket server ready at ws://localhost:8000/ws/{client_id}")
    print("\nExample client code:")
    print("""
    import websockets
    import json

    async def client():
        uri = "ws://localhost:8000/ws/client-1"
        async with websockets.connect(uri) as websocket:
            # Join a room
            await websocket.send(json.dumps({
                "action": "join",
                "room": "chat-room"
            }))

            # Send message to room
            await websocket.send(json.dumps({
                "action": "message",
                "room": "chat-room",
                "message": "Hello, room!"
            }))

            # Receive messages
            while True:
                message = await websocket.recv()
                print(f"Received: {message}")
    """)


# ============================================================================
# 4. Real-World Integration Example
# ============================================================================


async def lobsterclaws_urchinspike_example():
    """
    Example: Lobsterclaws calling Urchinspike tools via RPC.

    This shows how Whalefin/Lobsterclaws would execute Urchinspike tools
    in the background and communicate results.
    """
    print("\n=== Lobsterclaws → Urchinspike Example ===\n")

    # Initialize components
    bus = EventBus()
    rpc = RPCClient(services={"urchinspike": "http://localhost:8003"})
    await rpc.connect()

    # Subscribe to tool execution events
    @bus.subscribe("tool.started")
    async def on_tool_started(event: Event):
        print(f"[Event] Tool started: {event.data['tool_name']}")

    @bus.subscribe("tool.completed")
    async def on_tool_completed(event: Event):
        print(f"[Event] Tool completed: {event.data['tool_name']}")
        print(f"[Event] Result: {event.data['result']}")

    # Lobsterclaws receives request from user
    print("User request: Execute 'read_file' tool")

    # Emit event
    await bus.publish("tool.started", {"tool_name": "read_file", "args": {"path": "/tmp/test.txt"}})
    await asyncio.sleep(0.1)

    try:
        # Call Urchinspike via RPC
        print("\nCalling Urchinspike to execute tool...")
        result = await rpc.call(
            service="urchinspike",
            method="execute_tool",
            params={"tool_name": "read_file", "args": {"path": "/tmp/test.txt"}},
        )

        # Emit completion event
        await bus.publish(
            "tool.completed", {"tool_name": "read_file", "result": result, "status": "success"}
        )
        await asyncio.sleep(0.1)

    except Exception as e:
        # Emit failure event
        await bus.publish(
            "tool.completed", {"tool_name": "read_file", "error": str(e), "status": "failed"}
        )
        await asyncio.sleep(0.1)

    await rpc.disconnect()


# ============================================================================
# Main
# ============================================================================


async def main():
    """Run all examples"""
    print("=" * 60)
    print("VelvetEcho Communication Examples")
    print("=" * 60)

    # Run examples
    await event_bus_example()
    # await rpc_client_example()  # Requires services running
    # await lobsterclaws_urchinspike_example()  # Requires services running

    # WebSocket example (needs FastAPI server)
    # websocket_example()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
