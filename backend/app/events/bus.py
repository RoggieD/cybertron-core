import asyncio

from fastapi import WebSocket

from backend.app.events.schema import CoreEvent
from backend.app.traces.store import trace_store
from backend.app.memory.episode_capture import capture_episode
from backend.app.memory.episode_events import episode_from_event


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
        # High-frequency token telemetry is broadcast live but not
        # synchronously persisted. Lifecycle events remain durable.
        if event.event_type != "model.token":
            await trace_store.save(event)

        episode = episode_from_event(event)
        if episode is not None:
            # Episodic persistence must not block the async event bus on SQLite.
            await asyncio.to_thread(capture_episode, **episode)

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
                dead_connections.append(websocket)

        if dead_connections:
            async with self._lock:
                for websocket in dead_connections:
                    self._connections.discard(
                        websocket
                    )


event_bus = EventBus()
