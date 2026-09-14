import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.services.model_service import model_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


def build_messages(message: str, model: str) -> list[dict]:
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
    try:
        model = model_service.active_model

        result = await model_service.provider.chat(
            model=model,
            messages=build_messages(request.message, model),
        )

        message = result.get("message", {})

        return {
            "provider": "ollama",
            "model": model,
            "response": message.get("content", ""),
            "done": result.get("done", False),
            "total_duration": result.get("total_duration"),
            "load_duration": result.get("load_duration"),
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Chat inference failed: {exc}",
        ) from exc


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:

    model = model_service.active_model

    async def event_stream():
        try:
            yield json.dumps(
                {
                    "event": "model.request_started",
                    "model": model,
                }
            ) + "\n"

            async for chunk in model_service.provider.stream_chat(
                model=model,
                messages=build_messages(request.message, model),
            ):
                message = chunk.get("message", {})
                content = message.get("content", "")

                if content:
                    yield json.dumps(
                        {
                            "event": "model.token",
                            "model": model,
                            "content": content,
                        }
                    ) + "\n"

                if chunk.get("done"):
                    yield json.dumps(
                        {
                            "event": "model.request_completed",
                            "model": model,
                            "done": True,
                            "total_duration": chunk.get("total_duration"),
                            "load_duration": chunk.get("load_duration"),
                            "prompt_eval_count": chunk.get("prompt_eval_count"),
                            "eval_count": chunk.get("eval_count"),
                        }
                    ) + "\n"

        except Exception as exc:
            yield json.dumps(
                {
                    "event": "model.error",
                    "model": model,
                    "error": str(exc),
                }
            ) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
    )
