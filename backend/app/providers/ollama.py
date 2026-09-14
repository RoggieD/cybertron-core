import json
from collections.abc import AsyncIterator

import httpx

from backend.app.core.config import get_settings
from backend.app.providers.base import ModelProvider


class OllamaProvider(ModelProvider):

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")

    def _chat_payload(
        self,
        model: str,
        messages: list[dict],
        *,
        stream: bool,
    ) -> dict:
        return {
            "model": model,
            "messages": messages,
            "stream": stream,
            # Keep the reply in message.content for the C.O.R.E. UI.
            "think": False,
            # Security/posture reports can be longer than Ollama's default
            # generation budget. Make the response budget explicit and
            # configurable so reports do not stop in the middle of a sentence.
            "options": {
                "num_predict": self.settings.ollama_num_predict,
            },
        }

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
        payload = self._chat_payload(
            model,
            messages,
            stream=False,
        )

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

        payload = self._chat_payload(
            model,
            messages,
            stream=True,
        )

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
