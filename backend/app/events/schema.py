from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class CoreEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    session_id: str | None = None
    trace_id: str | None = None
    parent_event_id: str | None = None

    actor: dict[str, Any] | None = None
    target: dict[str, Any] | None = None

    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
