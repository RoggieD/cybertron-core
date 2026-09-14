from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app.security_policy import security_policy_store
from backend.app.tools.listeners import listener_inventory


router = APIRouter(prefix="/api/security", tags=["security"])


class ApproveLearnedRequest(BaseModel):
    confirm: bool
    approved_by: str = "local-admin"


@router.get("/policy/{hostname}")
async def get_security_policy(hostname: str) -> dict:
    return await security_policy_store.status(hostname)


@router.get("/policy/{hostname}/evaluate")
async def evaluate_security_policy(hostname: str) -> dict:
    listeners = await listener_inventory()
    return await security_policy_store.evaluate(
        hostname,
        listeners.get("listeners", []),
    )


@router.post("/policy/{hostname}/approve-learned")
async def approve_learned_policy(
    hostname: str,
    request: ApproveLearnedRequest,
) -> dict:
    if request.confirm is not True:
        raise HTTPException(
            status_code=400,
            detail=(
                "Explicit confirmation is required before converting the learned "
                "listener baseline into administrator-approved policy."
            ),
        )

    try:
        result = await security_policy_store.approve_learned(
            hostname,
            approved_by=request.approved_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "status": "approved",
        "policy": result,
    }
