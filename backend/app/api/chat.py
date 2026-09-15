import json
import asyncio
from contextlib import aclosing
import anyio
from uuid import uuid4
from secrets import token_urlsafe

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.app.agents.router import route_agent
from backend.app.agents.registry import get_agent
from backend.app.agents.base import AgentDefinition
from backend.app.agents.context import format_tool_context
from backend.app.agents.tools import run_agent_tool
from backend.app.events.bus import event_bus
from backend.app.events.schema import CoreEvent
from backend.app.services.model_service import model_service
from backend.app.tools.renderers import (
    render_verified_tool_result,
    should_return_verified_only,
)
from backend.app.tools.docker_health_renderer import render_docker_health_summary
from backend.app.memory.context import format_memory_context

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Opaque capability tokens are returned only to the initiating stream, never
# broadcast in traces. This registry is process-local (single-worker runtime).
active_requests: dict[str, dict] = {}


def render_tool_result(tool_id: str | None, result: dict | None) -> str | None:
    if tool_id == "docker.health_summary" and result is not None:
        return render_docker_health_summary(result)
    return render_verified_tool_result(tool_id, result)


def verified_only_for(message: str, tool_id: str | None) -> bool:
    if tool_id == "docker.health_summary":
        return True
    return should_return_verified_only(message, tool_id)


class CancelRequest(BaseModel):
    token: str


@router.post("/cancel")
async def cancel_request(request: CancelRequest) -> dict:
    entry = active_requests.get(request.token)
    if entry is None:
        raise HTTPException(status_code=404, detail="Request not found")
    task = entry["task"]
    if not task.done() and not entry["cancel_requested"]:
        entry["cancel_requested"] = True
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(entry["finished"].wait()), 10)
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=409, detail="Cancellation still pending") from exc
    return {"status": entry["status"]}


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    agent_id: str | None = None


def build_messages(
    message: str,
    model: str,
    agent_name: str,
    agent_instructions: str,
    tool_id: str | None = None,
    tool_result: dict | None = None,
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
) -> list[dict]:
    tool_context = format_tool_context(
        tool_id,
        tool_result,
    )
    memory_context = format_memory_context(
        message,
        session_id=session_id,
        trace_id=trace_id,
    )

    system_prompt = (
        "You are CyberTron C.O.R.E., a local-first AI orchestration system. "
        f"Active model: {model}. "
        f"Active agent: {agent_name}. "
        f"Agent instructions: {agent_instructions} "
        "Be operationally precise, distinguish verified observations from "
        "inference, and never claim a tool action occurred unless tool context "
        "is explicitly provided."
    )

    if memory_context:
        system_prompt += (
            "\n\n"
            + memory_context
        )

    if tool_context:
        system_prompt += (
            "\n\n"
            + tool_context
        )

    return [
        {
            "role": "system",
            "content": system_prompt,
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
    model = await model_service.get_active_model()
    selection_mode = "manual" if request.agent_id else "auto"
    agent = (
        get_agent(request.agent_id)
        if request.agent_id
        else route_agent(request.message)
    )

    await event_bus.publish(
        CoreEvent(
            event_type="prompt.received",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "user", "id": "local"},
            target={"type": "core", "id": "cybertron"},
            status="received",
            metadata={"message": request.message},
        )
    )
    await event_bus.publish(
        CoreEvent(
            event_type="router.started",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "core", "id": "cybertron"},
            target={"type": "router", "id": "agent-router"},
            status="running",
            metadata={"mode": selection_mode},
        )
    )
    await event_bus.publish(
        CoreEvent(
            event_type="agent.selected",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "router", "id": "agent-router"},
            target={"type": "agent", "id": agent.id},
            status="complete",
            metadata={"agent_name": agent.name, "selection_mode": selection_mode},
        )
    )
    await event_bus.publish(
        CoreEvent(
            event_type="agent.started",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "agent", "id": agent.id},
            target={"type": "model", "id": model},
            status="running",
        )
    )

    tool_id, tool_result = await run_agent_tool(agent, request.message)
    verified_output = render_tool_result(tool_id, tool_result)
    verified_only = verified_only_for(request.message, tool_id)

    if tool_id:
        await event_bus.publish(
            CoreEvent(
                event_type="tool.started",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "agent", "id": agent.id},
                target={"type": "tool", "id": tool_id},
                status="running",
            )
        )
        await event_bus.publish(
            CoreEvent(
                event_type="tool.completed",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "tool", "id": tool_id},
                target={"type": "agent", "id": agent.id},
                status="complete",
                metadata={"result": tool_result},
            )
        )

    if verified_only and verified_output:
        await event_bus.publish(
            CoreEvent(
                event_type="agent.completed",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "agent", "id": agent.id},
                target={"type": "core", "id": "cybertron"},
                status="complete",
            )
        )
        await event_bus.publish(
            CoreEvent(
                event_type="response.generated",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "core", "id": "cybertron"},
                target={"type": "user", "id": "local"},
                status="complete",
            )
        )
        return {
            "session_id": session_id,
            "trace_id": trace_id,
            "provider": "tool",
            "model": None,
            "agent": agent.id,
            "agent_name": agent.name,
            "response": verified_output,
            "done": True,
        }

    await event_bus.publish(
        CoreEvent(
            event_type="model.request_started",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "agent", "id": agent.id},
            target={"type": "model", "id": model},
            status="running",
        )
    )

    result = await model_service.provider.chat(
        model=model,
        messages=build_messages(
            request.message,
            model,
            agent.name,
            agent.instructions,
            tool_id,
            tool_result,
            session_id=session_id,
            trace_id=trace_id,
        ),
    )
    message = result.get("message", {})
    model_response = message.get("content", "")
    response_text = (
        f"{verified_output}\n\nANALYSIS\n{model_response}"
        if verified_output
        else model_response
    )

    await event_bus.publish(
        CoreEvent(
            event_type="model.request_completed",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "model", "id": model},
            target={"type": "agent", "id": agent.id},
            status="complete",
        )
    )
    await event_bus.publish(
        CoreEvent(
            event_type="agent.completed",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "agent", "id": agent.id},
            target={"type": "core", "id": "cybertron"},
            status="complete",
        )
    )
    await event_bus.publish(
        CoreEvent(
            event_type="response.generated",
            session_id=session_id,
            trace_id=trace_id,
            actor={"type": "core", "id": "cybertron"},
            target={"type": "user", "id": "local"},
            status="complete",
        )
    )

    return {
        "session_id": session_id,
        "trace_id": trace_id,
        "provider": model_service.provider.name,
        "model": model,
        "agent": agent.id,
        "agent_name": agent.name,
        "response": response_text,
        "done": True,
    }


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    trace_id = str(uuid4())
    cancel_token = token_urlsafe(24)

    async def generate():
        async with aclosing(_stream_request(request, session_id, trace_id, cancel_token)) as stream:
            async for item in stream:
                yield item

    return StreamingResponse(generate(), media_type="application/x-ndjson")


async def _stream_request(request: ChatRequest, session_id: str, trace_id: str, cancel_token: str):
    entry = {
        "task": asyncio.current_task(),
        "cancel_requested": False,
        "status": "running",
        "finished": asyncio.Event(),
    }
    active_requests[cancel_token] = entry

    try:
        yield json.dumps({
            "event": "request.accepted",
            "session_id": session_id,
            "trace_id": trace_id,
            "cancel_token": cancel_token,
        }) + "\n"

        model = await model_service.get_active_model()
        selection_mode = "manual" if request.agent_id else "auto"
        agent = (
            get_agent(request.agent_id)
            if request.agent_id
            else route_agent(request.message)
        )

        async def publish(event_type: str, **kwargs):
            await event_bus.publish(
                CoreEvent(
                    event_type=event_type,
                    session_id=session_id,
                    trace_id=trace_id,
                    **kwargs,
                )
            )

        await publish(
            "prompt.received",
            actor={"type": "user", "id": "local"},
            target={"type": "core", "id": "cybertron"},
            status="received",
            metadata={"message": request.message},
        )
        await publish(
            "router.started",
            actor={"type": "core", "id": "cybertron"},
            target={"type": "router", "id": "agent-router"},
            status="running",
            metadata={"mode": selection_mode},
        )
        await publish(
            "agent.selected",
            actor={"type": "router", "id": "agent-router"},
            target={"type": "agent", "id": agent.id},
            status="complete",
            metadata={"agent_name": agent.name, "selection_mode": selection_mode},
        )
        await publish(
            "agent.started",
            actor={"type": "agent", "id": agent.id},
            target={"type": "model", "id": model},
            status="running",
        )

        tool_id, tool_result = await run_agent_tool(agent, request.message)
        verified_output = render_tool_result(tool_id, tool_result)
        verified_only = verified_only_for(request.message, tool_id)

        if tool_id:
            await publish(
                "tool.started",
                actor={"type": "agent", "id": agent.id},
                target={"type": "tool", "id": tool_id},
                status="running",
            )
            await publish(
                "tool.completed",
                actor={"type": "tool", "id": tool_id},
                target={"type": "agent", "id": agent.id},
                status="complete",
                metadata={"result": tool_result},
            )

        if verified_output and not verified_only:
            yield json.dumps(
                {
                    "event": "tool.result",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "tool": tool_id,
                    "verified": True,
                    "content": verified_output + "\n\nANALYSIS\n",
                }
            ) + "\n"

        if verified_only and verified_output:
            yield json.dumps(
                {
                    "event": "tool.result",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "tool": tool_id,
                    "verified": True,
                    "content": verified_output,
                }
            ) + "\n"
            await publish(
                "agent.completed",
                actor={"type": "agent", "id": agent.id},
                target={"type": "core", "id": "cybertron"},
                status="complete",
            )
            await publish(
                "response.generated",
                actor={"type": "core", "id": "cybertron"},
                target={"type": "user", "id": "local"},
                status="complete",
            )
            return

        await publish(
            "model.request_started",
            actor={"type": "agent", "id": agent.id},
            target={"type": "model", "id": model},
            status="running",
        )
        yield json.dumps(
            {
                "event": "model.request_started",
                "session_id": session_id,
                "trace_id": trace_id,
                "model": model,
                "agent": agent.id,
                "agent_name": agent.name,
            }
        ) + "\n"

        messages = build_messages(
            request.message,
            model,
            agent.name,
            agent.instructions,
            tool_id,
            tool_result,
            session_id=session_id,
            trace_id=trace_id,
        )

        final_text = ""

        async with aclosing(
            model_service.provider.stream_chat(
                model=model,
                messages=messages,
            )
        ) as provider_stream:
            async for chunk in provider_stream:
                content = chunk.get("message", {}).get("content", "")
                if content:
                    final_text += content
                    yield json.dumps(
                        {
                            "event": "model.token",
                            "session_id": session_id,
                            "trace_id": trace_id,
                            "model": model,
                            "content": content,
                        }
                    ) +