from __future__ import annotations

from contextvars import ContextVar, Token


ConversationExchange = dict[str, str]

_conversation_history: ContextVar[tuple[ConversationExchange, ...]] = ContextVar(
    "cybertron_conversation_history",
    default=(),
)


def normalize_conversation_history(value, *, limit: int = 12) -> list[ConversationExchange]:
    if not isinstance(value, list):
        return []

    normalized: list[ConversationExchange] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        prompt = item.get("prompt")
        response = item.get("response")
        if not isinstance(prompt, str) or not isinstance(response, str):
            continue
        prompt = prompt.strip()
        response = response.strip()
        if not prompt or not response:
            continue
        normalized.append({"prompt": prompt, "response": response})

    return normalized[-limit:]


def set_conversation_history(value) -> Token:
    history = tuple(normalize_conversation_history(value))
    return _conversation_history.set(history)


def reset_conversation_history(token: Token) -> None:
    _conversation_history.reset(token)


def get_conversation_history() -> list[ConversationExchange]:
    return [dict(exchange) for exchange in _conversation_history.get()]


def format_conversation_context() -> str:
    history = get_conversation_history()
    if not history:
        return ""

    lines = [
        "RECENT CONVERSATION — SHORT-TERM CONTEXT",
        "Use these prior exchanges to resolve follow-up questions and references.",
        "This is browser-provided conversation context, not persistent memory or live system evidence.",
    ]
    for exchange in history:
        lines.append(f"USER: {exchange['prompt']}")
        lines.append(f"ASSISTANT: {exchange['response']}")

    return "\n".join(lines)
