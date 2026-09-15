from backend.app.memory.context_budget import (
    ContextBudget,
    allocate_context_budget,
    estimate_tokens,
    trim_to_token_budget,
)


def test_default_budget_reserves_response_capacity():
    budget = ContextBudget()
    assert budget.max_tokens == 32768
    assert budget.response_reserve_tokens == 8192
    assert budget.prompt_budget_tokens == 24576


def test_allocations_fit_exactly_inside_prompt_budget():
    allocation = allocate_context_budget()
    parts = (
        allocation["instructions"]
        + allocation["tool_evidence"]
        + allocation["conversation"]
        + allocation["persistent_memory"]
        + allocation["knowledge"]
    )
    assert parts == allocation["prompt_total"] == 24576


def test_verified_tool_evidence_has_largest_reserved_slice():
    allocation = allocate_context_budget()
    assert allocation["tool_evidence"] > allocation["conversation"]
    assert allocation["tool_evidence"] > allocation["persistent_memory"]
    assert allocation["tool_evidence"] > allocation["knowledge"]


def test_token_estimate_uses_four_character_heuristic():
    assert estimate_tokens("a" * 16) == 4
    assert estimate_tokens("x") == 1
    assert estimate_tokens("") == 0


def test_conversation_trim_keeps_recent_tail():
    text = "old-" + ("x" * 20) + "-recent"
    trimmed = trim_to_token_budget(text, 3, keep="end")
    assert len(trimmed) <= 12
    assert trimmed.endswith("-recent")


def test_instruction_trim_keeps_prefix():
    text = "SYSTEM-RULES-" + ("x" * 30)
    trimmed = trim_to_token_budget(text, 3, keep="start")
    assert len(trimmed) <= 12
    assert trimmed.startswith("SYSTEM-RULE")
