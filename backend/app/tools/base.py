from dataclasses import dataclass
from typing import Awaitable, Callable


ToolHandler = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    name: str
    description: str
    permission_level: int
    read_only: bool
    handler: ToolHandler
