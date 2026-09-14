from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class ModelProvider(ABC):

    @abstractmethod
    async def health(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[dict],
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
    ) -> AsyncIterator[dict]:
        raise NotImplementedError
