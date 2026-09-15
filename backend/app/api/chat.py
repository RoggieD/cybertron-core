from backend.app.knowledge.citations import take_receipt
from backend.app.knowledge.telemetry import flush_knowledge_telemetry
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
from backend.app.memory.context import format_memory_context
from backend.app.memory.episodic_retrieval import flush_episodic_telemetry
from backend.app.tools.docker_health_renderer import render_docker_health_summary

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Opaque capability tokens are returned only to the initiating stream, never
# broadcast in traces. This registry is process-local (single-worker runtime).
active_requests: dict[str, dict] = {}


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
    reference_receipt: str | None = None


def select_agent(request: ChatRequest) -> tuple[AgentDefinition, str]:
    if not request.agent_id or request.agent_id == "auto":
        return route_agent(request.message), "auto"

    try:
        return get_agent(request.agent_id), "manual"
    except KeyError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown agent override: {request.agent_id}",
        ) from exc


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
    reference_receipt: str | None = None,
) -> list[dict]:
    memory_context = format_memory_context(
        message,
        session_id=session_id,
        trace_id=trace_id,
        reference_receipt=reference_receipt,
    )

    return [
        {
            "role": "system",
            "content": (
                "You are CyberTron, the local AI assistant running inside "
                "CyberTron C.O.R.E. "
                f"The active local model is {model}. "
                f"The selected agent is {agent_name}. "
                f"Agent instructions: {agent_instructions} "
                "Do not invent capabilities, infrastructure, security features, "
                "or model identity. If you do not know something, say so. "
                "Distinguish verified system facts from assumptions. "
                "Verified tool results override model assumptions. "
                "Only tool results supplied in THIS request may be described as live, verified, observed, inspected, measured, or confirmed system state. "
                "If no tool result is supplied in this request, do not claim that C.O.R.E. inspected, scanned, measured, observed, or verified any current system, network, container, listener, security, or service state. "
                "Conversation history, persistent memory, historical operational episodes, and knowledge-base material are context only and must never be presented as current live observations. "
                "Reference citations and retained source metadata may be cited without a live tool result. "
                "When asked for citations, report the supplied source paths and chunk IDs; do not invent them. "
                "Never change counts, states, names, or measurements supplied "
                "by a tool. "
                + ("\n\n" + memory_context if memory_context else "")
                + (
                    "\n\n" + format_tool_context(tool_id, tool_result)
                    if tool_id and tool_result is not None
                    else ""
                )
            ),
        },
        {"role": "user", "content": message},
    ]


@router.post("")
async def chat(request: ChatRequest) -> dict:
    session_id = request.session_id or str(uuid4())
    trace_id = str(uuid4())
    model = model_service.active_model
    agent, selection_mode = select_agent(request)

    try:
        await event_bus.publish(
            CoreEvent(
                event_type="prompt.received",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "user", "id": "local"},
                target={"type": "core", "id": "cybertron"},
                status="complete",
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
        verified_output = (render_docker_health_summary(tool_result) if tool_id == "docker.health_summary" and tool_result is not None else render_verified_tool_result(tool_id, tool_result))
        verified_only = (tool_id == "docker.health_summary" or should_return_verified_only(request.message, tool_id))

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

        messages = build_messages(
            request.message, model, agent.name, agent.instructions,
            tool_id, tool_result, session_id=session_id, trace_id=trace_id,
            reference_receipt=request.reference_receipt,
        )
        reference_receipt = take_receipt()
        await flush_episodic_telemetry()
        await flush_knowledge_telemetry()
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
            messages=messages,
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
                metadata={
                    "total_duration": result.get("total_duration"),
                    "prompt_eval_count": result.get("prompt_eval_count"),
                    "eval_count": result.get("eval_count"),
                },
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
            "reference_receipt": reference_receipt,
            "provider": "ollama",
            "model": model,
            "agent": agent.id,
            "agent_name": agent.name,
            "response": response_text,
            "done": result.get("done", False),
            "total_duration": result.get("total_duration"),
            "load_duration": result.get("load_duration"),
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
        }

    except Exception as exc:
        await event_bus.publish(
            CoreEvent(
                event_type="model.error",
                session_id=session_id,
                trace_id=trace_id,
                actor={"type": "model", "id": model},
                status="error",
                metadata={"error": str(exc)},
            )
        )
        raise HTTPException(
            status_code=503,
            detail=f"Chat inference failed: {exc}",
        ) from exc


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    session_id = request.session_id or str(uuid4())
    trace_id = str(uuid4())
    model = model_service.active_model
    agent, selection_mode = select_agent(request)

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
                actor={"type": "user", "id": "local"},
                target={"type": "core", "id": "cybertron"},
                status="complete",
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
            verified_output = (render_docker_health_summary(tool_result) if tool_id == "docker.health_summary" and tool_result is not None else render_verified_tool_result(tool_id, tool_result))
            verified_only = (tool_id == "docker.health_summary" or should_return_verified_only(request.message, tool_id))

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

            messages = build_messages(
                request.message, model, agent.name, agent.instructions,
                tool_id, tool_result, session_id=session_id, trace_id=trace_id,
                reference_receipt=request.reference_receipt,
            )
            reference_receipt = take_receipt()
            await flush_episodic_telemetry()
            await flush_knowledge_telemetry()
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

            async for chunk in model_service.provider.stream_chat(
                model=model,
                messages=messages,
            ):
                message = chunk.get("message", {})
                content = message.get("content", "")

                if content:
                    await publish(
                        "model.token",
                        actor={"type": "model", "id": model},
                        target={"type": "agent", "id": agent.id},
                        status="streaming",
                    )
                    yield json.dumps(
                        {
                            "event": "model.token",
                            "session_id": session_id,
                            "trace_id": trace_id,
                            "model": model,
                            "agent": agent.id,
                            "content": content,
                        }
                    ) + "\n"

                if chunk.get("done"):
                    telemetry = {
                        "total_duration": chunk.get("total_duration"),
                        "load_duration": chunk.get("load_duration"),
                        "prompt_eval_count": chunk.get("prompt_eval_count"),
                        "eval_count": chunk.get("eval_count"),
                    }
                    await publish(
                        "model.request_completed",
                        actor={"type": "model", "id": model},
                        target={"type": "agent", "id": agent.id},
                        status="complete",
                        metadata=telemetry,
                    )
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
                    yield json.dumps(
                        {
                            "event": "model.request_completed",
                            "session_id": session_id,
                            "trace_id": trace_id,
                            "model": model,
                            "agent": agent.id,
                            "agent_name": agent.name,
                            "reference_receipt": reference_receipt,
                            "done": True,
                            **telemetry,
                        }
                    ) + "\n"

        except Exception as exc:
            await publish(
                "model.error",
                actor={"type": "model", "id": model},
                status="error",
                metadata={"error": str(exc)},
            )
            yield json.dumps(
                {
                    "event": "model.error",
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "model": model,
                    "agent": agent.id,
                    "error": str(exc),
                }
            ) + "\n"

    async def lifecycle_stream():
        terminal = "request.failed"
        try:
            async with aclosing(event_stream()) as stream:
                async for line in stream:
                    event = json.loads(line)
                    if event.get("event") == "model.error":
                        terminal = "request.failed"
                        yield line
                        return
                    yield line
            terminal = "request.completed"
        except (asyncio.CancelledError, GeneratorExit):
            terminal = "request.cancelled"
            raise
        finally:
            # Starlette cancels the streaming task when the client disconnects.
            # Shield only the terminal audit write, never inference/tool work.
            with anyio.CancelScope(shield=True):
                await publish(
                    terminal,
                    actor={"type": "core", "id": "cybertron"},
                    status=terminal.split(".")[1],
                    metadata={"agent_id": agent.id, "model": model},
                )

    async def controlled_stream():
        token = token_urlsafe(32)
        queue = asyncio.Queue()
        entry = {"task": None, "cancel_requested": False,
                 "finished": asyncio.Event(), "status": "running"}

        async def produce():
            try:
                async with aclosing(lifecycle_stream()) as stream:
                    async for line in stream:
                        if json.loads(line).get("event") == "model.error":
                            entry["status"] = "failed"
                        await queue.put(line)
                if entry["status"] == "running":
                    entry["status"] = "completed"
            except asyncio.CancelledError:
                entry["status"] = "cancelled"
            except Exception:
                entry["status"] = "failed"
            finally:
                entry["finished"].set()
                queue.put_nowait(None)

        task = asyncio.create_task(produce())
        entry["task"] = task
        active_requests[token] = entry
        try:
            # Allow the producer to start before advertising cancellation.
            await asyncio.sleep(0)
            yield json.dumps({"event": "request.accepted", "cancel_token": token,
                              "trace_id": trace_id}) + "\n"
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line
            yield json.dumps({"event": "request." + entry["status"]}) + "\n"
        finally:
            if not task.done():
                if not entry["cancel_requested"]:
                    entry["cancel_requested"] = True
                    task.cancel()
                with anyio.CancelScope(shield=True):
                    await task
            # Briefly retain the outcome for cancel/completion races.
            asyncio.get_running_loop().call_later(60, active_requests.pop, token, None)

    return StreamingResponse(
        controlled_stream(),
        media_type="application/x-ndjson",
    )
