SERVICES = {
    "ollama": {
        "name": "Ollama",
        "target": "http://localhost:11434",
    },
    "open webui": {
        "name": "Open WebUI",
        "target": "http://localhost:3000",
    },
    "open-webui": {
        "name": "Open WebUI",
        "target": "http://localhost:3000",
    },
    "searxng": {
        "name": "SearXNG",
        "target": "http://localhost:8081",
    },
}


def resolve_service(message: str) -> dict | None:
    normalized = message.lower()

    for key, service in SERVICES.items():
        if key in normalized:
            return service

    return None
