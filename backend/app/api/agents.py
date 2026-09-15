from fastapi import APIRouter

from backend.app.agents.registry import list_agents


router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def agents() -> dict:
    available = [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
        }
        for agent in list_agents()
    ]
    return {
        "count": len(available),
        "agents": available,
        "default_mode": "auto",
    }
