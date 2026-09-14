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

    "langfuse": {
        "name": "Langfuse",
        "target": "http://localhost:3100",
    },

    "kokoro": {
        "name": "Kokoro FastAPI",
        "scope": "docker",
        "container": "kokoro-fastapi",
        "port": 8880,
        "protocol": "http",
        "health_path": "/health",
    },
    "kokoro fastapi": {
        "name": "Kokoro FastAPI",
        "scope": "docker",
        "container": "kokoro-fastapi",
        "port": 8880,
        "protocol": "http",
        "health_path": "/health",
    },
    "kokoro-fastapi": {
        "name": "Kokoro FastAPI",
        "scope": "docker",
        "container": "kokoro-fastapi",
        "port": 8880,
        "protocol": "http",
        "health_path": "/health",
    },


    "frontend": {
        "name": "CyberTron C.O.R.E. Frontend",
        "target": "http://localhost:5173",
    },
    "core frontend": {
        "name": "CyberTron C.O.R.E. Frontend",
        "target": "http://localhost:5173",
    },

    "backend": {
        "name": "CyberTron C.O.R.E. Backend",
        "target": "http://localhost:8000/api/health",
    },
    "core backend": {
        "name": "CyberTron C.O.R.E. Backend",
        "target": "http://localhost:8000/api/health",
    },
}


def resolve_service(message: str) -> dict | None:
    normalized = message.lower()

    # Prefer longer aliases first so "core backend"
    # wins before a shorter substring such as "backend".
    for key in sorted(
        SERVICES,
        key=len,
        reverse=True,
    ):
        if key in normalized:
            return SERVICES[key]

    return None
