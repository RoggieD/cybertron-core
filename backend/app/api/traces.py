from fastapi import APIRouter, Query

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
