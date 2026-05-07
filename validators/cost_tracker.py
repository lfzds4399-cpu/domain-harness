"""cost_tracker — accumulate API spend across a pipeline run.

A small in-memory ledger that callers (valuation_council, AI generation,
LLM negotiation) feed token / dollar entries into. At end of pipeline,
``report()`` returns a structured summary; the harness writes it into the
manifest entry's ``extra``.

Why not just sum costs in each agent: there are several agents, each with
its own provider quirks (Claude per-1k pricing, DeepSeek per-token, AI
generation per-image). Centralising in one ledger means manifest entries
can compare day-over-day spend without each agent reinventing the wheel.

Pure-function module-level state — keeping it process-local is intentional;
domain-harness runs are short-lived. If we ever need cross-process tracking,
back this with SQLite without changing the public API.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

_lock = threading.RLock()  # reentrant — report() composes by_provider() / by_operation()
_entries: list["CostEntry"] = []


@dataclass(frozen=True)
class CostEntry:
    provider: str       # "anthropic", "deepseek", "openai-image", …
    operation: str      # "valuation", "generation", "negotiation", …
    usd: float
    tokens_in: int = 0
    tokens_out: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def record(provider: str, operation: str, usd: float, *,
           tokens_in: int = 0, tokens_out: int = 0, **extra: Any) -> None:
    """Add a cost entry to the ledger."""
    entry = CostEntry(
        provider=provider,
        operation=operation,
        usd=round(float(usd), 6),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        extra=extra,
    )
    with _lock:
        _entries.append(entry)


def reset() -> None:
    """Clear all entries (start of a new pipeline)."""
    with _lock:
        _entries.clear()


def total_usd() -> float:
    with _lock:
        return round(sum(e.usd for e in _entries), 4)


def by_provider() -> dict[str, float]:
    with _lock:
        out: dict[str, float] = {}
        for e in _entries:
            out[e.provider] = round(out.get(e.provider, 0.0) + e.usd, 4)
        return out


def by_operation() -> dict[str, float]:
    with _lock:
        out: dict[str, float] = {}
        for e in _entries:
            out[e.operation] = round(out.get(e.operation, 0.0) + e.usd, 4)
        return out


def report() -> dict[str, Any]:
    """Structured summary suitable for embedding in a manifest entry."""
    with _lock:
        return {
            "total_usd": round(sum(e.usd for e in _entries), 4),
            "calls": len(_entries),
            "by_provider": by_provider(),
            "by_operation": by_operation(),
            "tokens_in": sum(e.tokens_in for e in _entries),
            "tokens_out": sum(e.tokens_out for e in _entries),
        }
