from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def salience_score(entry: dict[str, Any], *, now: datetime | None = None) -> float:
    """Rank memory using the proven Agentic Stack salience formula.

    recent + painful + important + recurring memories surface first.
    Missing timestamps intentionally score zero so ungrounded records do not
    outrank timestamped operational history.
    """
    timestamp = entry.get("timestamp") or entry.get("updated_at") or entry.get("created_at")
    if not timestamp:
        return 0.0

    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age_days = max(0, (current - parsed).days)
    except (TypeError, ValueError):
        age_days = 999

    pain = _bounded_number(entry.get("pain_score", 5), 0.0, 10.0, 5.0)
    importance = _bounded_number(entry.get("importance", 5), 0.0, 10.0, 5.0)
    recurrence = _bounded_number(entry.get("recurrence_count", 1), 0.0, 3.0, 1.0)
    recency = max(0.0, min(10.0, 10.0 - age_days * 0.3))

    return recency * (pain / 10.0) * (importance / 10.0) * recurrence


def relevance_salience_score(
    relevance: float,
    entry: dict[str, Any],
    *,
    relevance_floor: float = 0.3,
    now: datetime | None = None,
) -> float:
    """Combine query relevance with salience using the Agentic Stack pattern."""
    relevance = max(0.0, min(1.0, float(relevance)))
    floor = max(0.0, min(1.0, float(relevance_floor)))
    relevance_weight = floor + (1.0 - floor) * relevance
    return salience_score(entry, now=now) * relevance_weight


def _bounded_number(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))
