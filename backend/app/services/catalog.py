from backend.app.core.config import get_settings


SERVICES = {
    "ollama": {
        "name": "Ollama",
        "scope": "host",
        "target": "http://localhost:11434",
    },

    "open webui": {
        "name": "Open WebUI",
        "scope": "host",
        "target": "http://localhost:3000",
    },
    "open-webui": {
        "name": "Open WebUI",
        "scope": "host",
        "target": "http://localhost:3000",
    },

    "searxng": {
        "name": "SearXNG",
        "scope": "host",
        "target": "http://localhost:8081",
    },

    "langfuse": {
        "name": "Langfuse",
        "scope": "host",
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
        "scope": "host",
        "target": get_settings().frontend_health_url,
        "ca_file": get_settings().frontend_health_ca_file,
    },
    "core frontend": {
        "name": "CyberTron C.O.R.E. Frontend",
        "scope": "host",
        "target": get_settings().frontend_health_url,
        "ca_file": get_settings().frontend_health_ca_file,
    },

    "backend": {
        "name": "CyberTron C.O.R.E. Backend",
        "scope": "host",
        "target": "http://localhost:8000/api/health",
    },
    "core backend": {
        "name": "CyberTron C.O.R.E. Backend",
        "scope": "host",
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
