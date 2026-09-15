"""Opaque receipts for source metadata actually packed into a prior answer."""
from contextvars import ContextVar
import json
from pathlib import Path
import re
from secrets import token_urlsafe
import sqlite3

DATABASE = Path("data/cybertron.db")
_receipt: ContextVar[str | None] = ContextVar("reference_receipt", default=None)


def is_citation_followup(message: str) -> bool:
    text = message.lower().strip()
    citation = re.search(r"\b(cite|citations?|sources?|references?|chunk ids?)\b", text)
    previous = re.search(r"\b(?:(?:previous|prior|last|your|that)\s+(?:answer|response|reply|explanation)|above)\b", text)
    previous = previous or re.search(r"\b(?:what|which) (?:sources|references) did you use\b", text)
    short = re.fullmatch(r"(?:please\s+)?(?:sources|references|citations)(?:\s+please)?[?.!]*", text)
    return bool(citation and (previous or short))


def reset_receipt() -> None:
    _receipt.set(None)


def take_receipt() -> str | None:
    value = _receipt.get()
    _receipt.set(None)
    return value


def _connect():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute("CREATE TABLE IF NOT EXISTS reference_receipts (token TEXT PRIMARY KEY, sources TEXT NOT NULL)")
    return connection


def retain_sources(sources: list[dict], trace_id: str | None) -> None:
    if not sources:
        return
    rows = [{key: row.get(key) for key in ("kb", "name", "path", "section", "chunk_id", "excerpt_shortened")} |
            {"origin_trace_id": row.get("origin_trace_id") or trace_id} for row in sources[:25]]
    token = token_urlsafe(32)
    with _connect() as connection:
        connection.execute("INSERT INTO reference_receipts VALUES (?, ?)", (token, json.dumps(rows)))
    connection.close()
    _receipt.set(token)


def recall_sources(token: str | None) -> list[dict]:
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return []
    with _connect() as connection:
        row = connection.execute("SELECT sources FROM reference_receipts WHERE token = ?", (token,)).fetchone()
    connection.close()
    return json.loads(row[0]) if row else []
