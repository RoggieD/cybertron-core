from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from backend.app.memory import (
    MemoryWriteOrchestrator,
)


router = APIRouter(
    prefix="/api/memory",
    tags=["memory"],
)


def _orchestrator() -> MemoryWriteOrchestrator:
    return MemoryWriteOrchestrator(
        "data/cybertron.db"
    )


@router.get("/proposals")
async def list_memory_proposals(
    status: str | None = Query(
        default=None,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
) -> dict:
    try:
        proposals = (
            _orchestrator().list_proposals(
                status=status,
                limit=limit,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "status_filter": status,
        "count": len(proposals),
        "proposals": proposals,
    }


@router.get(
    "/proposals/{proposal_id}"
)
async def get_memory_proposal(
    proposal_id: str,
) -> dict:
    orchestrator = _orchestrator()

    proposal = orchestrator.get(
        proposal_id
    )

    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail="Memory proposal not found.",
        )

    return proposal


@router.get(
    "/proposals/{proposal_id}/audit"
)
async def get_memory_proposal_audit(
    proposal_id: str,
) -> dict:
    orchestrator = _orchestrator()

    proposal = orchestrator.get(
        proposal_id
    )

    if proposal is None:
        raise HTTPException(
            status_code=404,
            detail="Memory proposal not found.",
        )

    events = orchestrator.audit_history(
        proposal_id
    )

    return {
        "proposal_id": proposal_id,
        "count": len(events),
        "events": events,
    }


@router.post(
    "/proposals/{proposal_id}/approve"
)
async def approve_memory_proposal(
    proposal_id: str,
) -> dict:
    orchestrator = _orchestrator()

    try:
        proposal = orchestrator.decide(
            proposal_id,
            approved=True,
            actor_type="user",
            actor_id="local-operator",
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        ValueError,
        PermissionError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "action": "approved",
        "proposal": proposal,
    }


@router.post(
    "/proposals/{proposal_id}/reject"
)
async def reject_memory_proposal(
    proposal_id: str,
) -> dict:
    orchestrator = _orchestrator()

    try:
        proposal = orchestrator.decide(
            proposal_id,
            approved=False,
            actor_type="user",
            actor_id="local-operator",
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except (
        ValueError,
        PermissionError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return {
        "action": "rejected",
        "proposal": proposal,
    }
