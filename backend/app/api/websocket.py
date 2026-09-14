from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    await websocket.send_json(
        {
            "event_type": "core.connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "service": "CyberTron C.O.R.E.",
                "status": "online",
            },
        }
    )

    try:
        while True:
            message = await websocket.receive_text()

            await websocket.send_json(
                {
                    "event_type": "core.echo",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "payload": {
                        "message": message,
                    },
                }
            )

    except WebSocketDisconnect:
        return
