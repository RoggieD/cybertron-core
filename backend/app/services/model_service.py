import asyncio

from backend.app.providers.ollama import OllamaProvider


class ModelService:
    def __init__(self) -> None:
        self.provider = OllamaProvider()
        self.default_model = "qwen3.5:9b"
        self.active_model = self.default_model
        self._lock = asyncio.Lock()

    async def get_state(self) -> dict:
        models = await self.provider.list_models()

        return {
            "provider": "ollama",
            "default_model": self.default_model,
            "active_model": self.active_model,
            "available_models": [
                model["name"]
                for model in models
            ],
        }

    async def set_active_model(self, model_name: str) -> dict:
        models = await self.provider.list_models()

        available_models = {
            model["name"]
            for model in models
        }

        if model_name not in available_models:
            raise ValueError(
                f"Model '{model_name}' is not available."
            )

        async with self._lock:
            self.active_model = model_name

        return await self.get_state()


model_service = ModelService()
