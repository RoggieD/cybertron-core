import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.events.bus import event_bus
from backend.app.events.schema import CoreEvent
from backend.app.services.model_service import model_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


def build_messages(
    message: str,
    model: str,
) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are CyberTron, the local AI assistant running inside "
                "CyberTron C.O.R.E. "
                f"The active local model is {model}. "
                "Do not invent capabilities, infrastructure, security features, "
                "or model identity. If you do not know something, say so. "
                "Distinguish verified system facts from assumptions."
            ),
        },
        {
            "role": "user",
            "content": message,
        },
    ]


@router.post("")
async def chat(request: ChatRequest) -> dict:
    session_id = request.session_id or str(uuid4())
    trace_id = str(uuid4())
    model = model_service.active_model

    try:
        await event_bus.publish(
            CoreEvent(
                event_type="prompt.received",
                session_id=session_id,
                trace_id=trace_id,
                actor={
                    "type": "user",
                    "id": "local",
                },
                target={
                    "type": "core",
                    "id": "cybertron",
                },
                status="complete",
            )
        )

        await event_bus.publish(
            CoreEvent(
                event_type="model.request_started",
                session_id=session_id,
                trace_id=trace_id,
                actor={
                    "type": "core",
                    "id": "cybertron",
                },
                target={
                    "type": "model",
                    "id": model,
                },
                status="running",
            )
        )

        result = await model_service.provider.chat(
            model=model,
            messages=build_messages(
                request.message,
                model,
            ),
        )

        message = result.get("message", {})
        response_text = message.get("content", "")

        await event_bus.publish(
            CoreEvent(
                event_type="model.request_completed",
                session_id=session_id,
                trace_id=trace_id,
                actor={
                    "type": "model",
                    "id": model,
                },
                target={
                    "type": "core",
                    "id": "cybertron",
                },
                status="complete",
                metadata={
                    "total_duration": result.get(
                        "total_duration"
                    ),
                    "prompt_eval_count": result.get(
                        "prompt_eval_count"
                    ),
                    "eval_count": result.get(
                        "eval_count"
                    ),
                },
            )
        )

        await event_bus.publish(
            CoreEvent(
                event_type="response.generated",
                session_id=session_id,
                trace_id=trace_id,
                actor={
                    "type": "core",
                    "id": "cybertron",
                },
                target={
                    "type": "user",
                    "id": "local",
                },
                status="complete",
            )
        )

        return {
            "session_id": session_id,
            "trace_id": trace_id,
            "provider": "ollama",
            "model": model,
            "response": response_text,
            "done": result.get("done", False),
            "total_duration": result.get(
                "total_duration"
            ),
            "load_duration": result.get(
                "load_duration"
            ),
            "prompt_eval_count": result.get(
                "prompt_eval_count"
            ),
            "eval_count": result.get(
                "eval_count"
            ),
        }

    except Exception as exc:
        await event_bus.publish(
            CoreEvent(
                event_type="model.error",
                session_id=session_id,
                trace_id=trace_id,
                actor={
                    "type": "model",
                    "id": model,
                },
                status="error",
                metadata={
                    "error": str(exc),
                },
            )
        )

        raise HTTPException(
            status_code=503,
            detail=f"Chat inference failed: {exc}",
        ) from exc


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
) -> StreamingResponse:

    session_id = request.session_id or str(uuid4())
    trace_id = str(uuid4())
    model = model_service.active_model

    async def publish(
        event_type: str,
        *,
        actor: dict | None = None,
        target: dict | None = None,
        status: str | None = None,
        metadata: dict | None = None,
    ) -> CoreEvent:
        event = CoreEvent(
            event_type=event_type,
            session_id=session_id,
            trace_id=trace_id,
            actor=actor,
            target=target,
            status=status,
            metadata=metadata or {},
        )

        await event_bus.publish(event)

        return event

    async def event_stream():
        try:
            await publish(
                "prompt.received",
                actor={
                    "type": "user",
                    "id": "local",
                },
                target={
                    "type": "core",
                    "id": "cybertron",
                },
                status="complete",
            )

            await publish(
                "model.request_started",
                actor={
                    "type": "core",
                    "id": "cybertron",
                },
                target={
                    "type": "model",
                    "id": model,
                },
                status="running",
            )

            yield json.dumps(
                {
                    "event": "model.request_started",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "model": model,
                }
            ) + "\n"

            async for chunk in (
                model_service.provider.stream_chat(
                    model=model,
                    messages=build_messages(
                        request.message,
                        model,
                    ),
                )
            ):
                message = chunk.get("message", {})
                content = message.get("content", "")

                if content:
                    await publish(
                        "model.token",
                        actor={
                            "type": "model",
                            "id": model,
                        },
                        target={
                            "type": "core",
                            "id": "cybertron",
                        },
                        status="streaming",
                        metadata={
                            "content": content,
                        },
                    )

                    yield json.dumps(
                        {
                            "event": "model.token",
                            "session_id": session_id,
                            "trace_id": trace_id,
                            "model": model,
                            "content": content,
                        }
                    ) + "\n"

                if chunk.get("done"):
                    telemetry = {
                        "total_duration": chunk.get(
                            "total_duration"
                        ),
                        "load_duration": chunk.get(
                            "load_duration"
                        ),
                        "prompt_eval_count": chunk.get(
                            "prompt_eval_count"
                        ),
                        "eval_count": chunk.get(
                            "eval_count"
                        ),
                    }

                    await publish(
                        "model.request_completed",
                        actor={
                            "type": "model",
                            "id": model,
                        },
                        target={
                            "type": "core",
                            "id": "cybertron",
                        },
                        status="complete",
                        metadata=telemetry,
                    )

                    await publish(
                        "response.generated",
                        actor={
                            "type": "core",
                            "id": "cybertron",
                        },
                        target={
                            "type": "user",
                            "id": "local",
                        },
                        status="complete",
                    )

                    yield json.dumps(
                        {
                            "event":
                                "model.request_completed",
                            "session_id": session_id,
                            "trace_id": trace_id,
                            "model": model,
                            "done": True,
                            **telemetry,
                        }
                    ) + "\n"

        except Exception as exc:
            await publish(
                "model.error",
                actor={
                    "type": "model",
                    "id": model,
                },
                status="error",
                metadata={
                    "error": str(exc),
                },
            )

            yield json.dumps(
                {
                    "event": "model.error",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "model": model,
                    "error": str(exc),
                }
            ) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
    )
