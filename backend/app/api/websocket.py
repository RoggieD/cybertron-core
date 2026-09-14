from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.events.bus import event_bus
from backend.app.events.schema import CoreEvent

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await event_bus.connect(websocket)

    connected_event = CoreEvent(
        event_type="core.connected",
        actor={
            "type": "core",
            "id": "cybertron",
        },
        status="online",
        metadata={
            "service": "CyberTron C.O.R.E.",
        },
    )

    await websocket.send_json(
        connected_event.model_dump(mode="json")
    )

    try:
        while True:
            message = await websocket.receive_text()

            await websocket.send_json(
                CoreEvent(
                    event_type="core.echo",
                    actor={
                        "type": "client",
                        "id": "browser",
                    },
                    target={
                        "type": "core",
                        "id": "cybertron",
                    },
                    status="complete",
                    metadata={
                        "message": message,
                    },
                ).model_dump(mode="json")
            )

    except WebSocketDisconnect:
        await event_bus.disconnect(websocket)
