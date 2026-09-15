from datetime import datetime, timedelta, timezone

from backend.app.memory.salience import relevance_salience_score, salience_score


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


def entry(*, days=0, pain=5, importance=5, recurrence=1):
    return {
        "timestamp": (NOW - timedelta(days=days)).isoformat(),
        "pain_score": pain,
        "importance": importance,
        "recurrence_count": recurrence,
    }


def test_recent_important_recurring_memory_scores_higher():
    routine = entry(days=10, pain=2, importance=3, recurrence=1)
    operational = entry(days=1, pain=8, importance=9, recurrence=3)
    assert salience_score(operational, now=NOW) > salience_score(routine, now=NOW)


def test_missing_timestamp_scores_zero():
    assert salience_score({"importance": 10}, now=NOW) == 0.0


def test_future_timestamp_does_not_inflate_recency():
    future = entry(days=-2, pain=10, importance=10, recurrence=3)
    same_day = entry(days=0, pain=10, importance=10, recurrence=3)
    assert salience_score(future, now=NOW) == salience_score(same_day, now=NOW)


def test_relevance_modulates_salience_without_zeroing_it():
    memory = entry(days=0, pain=8, importance=8, recurrence=2)
    irrelevant = relevance_salience_score(0.0, memory, now=NOW)
    relevant = relevance_salience_score(1.0, memory, now=NOW)
    assert irrelevant > 0
    assert relevant > irrelevant
