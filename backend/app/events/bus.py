import asyncio

from fastapi import WebSocket

from backend.app.events.schema import CoreEvent
from backend.app.traces.store import trace_store


class EventBus:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
    ) -> None:
        await websocket.accept()

        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(
        self,
        websocket: WebSocket,
    ) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def publish(
        self,
        event: CoreEvent,
    ) -> None:
        # Persist first so anything shown live is also auditable.
        await trace_store.save(event)

        payload = event.model_dump(mode="json")

        async with self._lock:
            connections = list(
                self._connections
            )

        dead_connections: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(
                    payload
                )
            except Exception:
                dead_connections.append(
                    websocket
                )

        if dead_connections:
            async with self._lock:
                for websocket in dead_connections:
                    self._connections.discard(
                        websocket
                    )


event_bus = EventBus()
