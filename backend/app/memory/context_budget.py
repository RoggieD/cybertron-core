from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MAX_CONTEXT_TOKENS = 32768
DEFAULT_RESPONSE_RESERVE_TOKENS = 8192
DEFAULT_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class ContextBudget:
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    response_reserve_tokens: int = DEFAULT_RESPONSE_RESERVE_TOKENS
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN

    @property
    def prompt_budget_tokens(self) -> int:
        return max(0, self.max_tokens - self.response_reserve_tokens)

    @property
    def prompt_budget_chars(self) -> int:
        return self.prompt_budget_tokens * self.chars_per_token


def estimate_tokens(text: str, *, chars_per_token: int = DEFAULT_CHARS_PER_TOKEN) -> int:
    """Cheap deterministic estimate retained from the Agentic Stack design."""
    if not text:
        return 0
    divisor = max(1, int(chars_per_token))
    return max(1, (len(text) + divisor - 1) // divisor)


def trim_to_token_budget(
    text: str,
    token_budget: int,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    keep: str = "end",
) -> str:
    """Trim text to an estimated token budget without invoking a tokenizer.

    keep='end' is appropriate for conversation history because recent turns are
    generally more useful. keep='start' protects headers/instructions.
    """
    if not text or token_budget <= 0:
        return ""

    char_budget = token_budget * max(1, int(chars_per_token))
    if len(text) <= char_budget:
        return text

    if keep == "start":
        return text[:char_budget]
    if keep == "end":
        return text[-char_budget:]
    raise ValueError("keep must be 'start' or 'end'")


def allocate_context_budget(
    *,
    max_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    response_reserve_tokens: int = DEFAULT_RESPONSE_RESERVE_TOKENS,
) -> dict[str, int]:
    """Allocate prompt capacity by C.O.R.E. context priority.

    Fixed/verified context is protected first. Flexible retrieval layers share
    the remaining budget and may be trimmed by callers.
    """
    prompt = max(0, max_tokens - response_reserve_tokens)

    # Percentages intentionally sum to 100. Tool evidence gets the largest
    # protected slice because verified observations must not be displaced by
    # lower-authority remembered context.
    allocations = {
        "instructions": int(prompt * 0.20),
        "tool_evidence": int(prompt * 0.30),
        "conversation": int(prompt * 0.25),
        "persistent_memory": int(prompt * 0.15),
    }
    allocations["knowledge"] = max(0, prompt - sum(allocations.values()))
    allocations["prompt_total"] = prompt
    allocations["response_reserve"] = max(0, response_reserve_tokens)
    return allocations
