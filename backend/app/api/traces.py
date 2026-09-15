from fastapi import APIRouter, HTTPException, Query

from backend.app.traces.store import trace_store

router = APIRouter(
    prefix="/api/traces",
    tags=["traces"],
)


@router.get("/recent")
async def recent_traces(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
) -> dict:
    events = await trace_store.recent(limit)

    return {
        "count": len(events),
        "events": events,
    }


@router.get("/summaries")
async def recent_trace_summaries(
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
) -> dict:
    traces = await trace_store.recent_trace_summaries(limit)

    return {
        "count": len(traces),
        "traces": traces,
    }


@router.get("/{trace_id}")
async def trace_detail(
    trace_id: str,
    limit: int = Query(
        default=1000,
        ge=1,
        le=5000,
    ),
) -> dict:
    events = await trace_store.by_trace(trace_id, limit)
    if not events:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "trace_id": trace_id,
        "count": len(events),
        "started_at": events[0]["timestamp"],
        "ended_at": events[-1]["timestamp"],
        "completed": any(event["event_type"] in {"response.generated", "infrastructure.snapshot"} for event in events),
        "errored": any(event["event_type"] == "model.error" for event in events),
        "events": events,
    }
