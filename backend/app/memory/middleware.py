from __future__ import annotations

import asyncio
import json

from backend.app.memory.conversation import capture_user_memory


def extract_user_message(payload):
    if not isinstance(payload, dict):
        return None

    message = payload.get("message")

    if isinstance(message, str) and message.strip():
        return message.strip()

    messages = payload.get("messages")

    if isinstance(messages, list):
        for item in reversed(messages):
            if (
                isinstance(item, dict)
                and str(item.get("role", "")).lower() == "user"
                and isinstance(item.get("content"), str)
                and item["content"].strip()
            ):
                return item["content"].strip()

    return None



def extract_agent_id(payload):
    if not isinstance(payload, dict):
        return "general"

    for key in (
        "agent_id",
        "agent",
    ):
        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return "general"


class ConversationMemoryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or "chat" not in str(scope.get("path", "")).lower()
        ):
            await self.app(scope, receive, send)
            return

        body = b""

        while True:
            event = await receive()

            if event["type"] != "http.request":
                continue

            body += event.get("body", b"")

            if not event.get("more_body", False):
                break

        try:
            payload = json.loads(body.decode("utf-8"))
            message = extract_user_message(payload)

            if message:
                await asyncio.to_thread(
                    capture_user_memory,
                    message,
                    agent_id="general",
                )
        except Exception:
            pass

        sent = False

        async def replay():
            nonlocal sent

            if not sent:
                sent = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }

            return {
                "type": "http.disconnect",
            }

        await self.app(scope, replay, send)
