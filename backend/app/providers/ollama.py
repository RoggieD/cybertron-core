import json
from collections.abc import AsyncIterator

import httpx

from backend.app.core.config import get_settings
from backend.app.providers.base import ModelProvider


class OllamaProvider(ModelProvider):

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()

        data = response.json()
        return data.get("models", [])

    async def chat(
        self,
        model: str,
        messages: list[dict],
    ) -> dict:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            # C.O.R.E. needs a user-visible answer in message.content.
            # Thinking-capable Ollama models can otherwise spend the whole
            # generation in message.thinking and finish with empty content,
            # which makes the Dashboard appear to receive no response even
            # though inference completed successfully.
            "think": False,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()

        return response.json()

    async def stream_chat(
        self,
        model: str,
        messages: list[dict],
    ) -> AsyncIterator[dict]:

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            # Keep streaming output in message.content for the C.O.R.E. UI.
            # Internal model thinking is not used as the user-facing reply.
            "think": False,
        }

        timeout = httpx.Timeout(
            connect=10.0,
            read=None,
            write=30.0,
            pool=30.0,
        )

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:

                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    yield json.loads(line)
