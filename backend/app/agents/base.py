from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    name: str
    description: str
    instructions: str
