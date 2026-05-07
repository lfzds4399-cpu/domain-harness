"""Manifest — pipeline stage 状态追踪 (harness-engineering SKILL § 2.4).

domain-harness 的业务状态分散在多个 JSON (portfolio / budget_state / scan_history)，
每个文件管自己那块。Manifest 是更上层的视图，回答 "今天/本周哪些 stage 跑了、跑成什么样"，
不复制业务数据，只引用其更新时间和最后 outcome。

举例:

    >>> from core import manifest
    >>> manifest.update("daily_scan", status="done", count=42, top_score=87)
    >>> print(manifest.summary())
    daily_scan         done      42 候选 · top=87 · 2026-05-07T10:30:00
    auto_register      pending
    portfolio_review   done      0 个动作 · 2026-05-07T08:00:00
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from . import config

MANIFEST_FILE = "manifest.json"

Status = str  # "pending" | "running" | "done" | "failed"


@dataclass
class StageEntry:
    name: str
    status: Status = "pending"
    updated_at: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _path() -> Path:
    return config.data_dir() / MANIFEST_FILE


def load() -> dict[str, StageEntry]:
    """Load manifest from disk. Returns ``{stage_name: StageEntry}``."""
    p = _path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, StageEntry] = {}
    for name, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        out[name] = StageEntry(
            name=name,
            status=payload.get("status", "pending"),
            updated_at=payload.get("updated_at"),
            extra=payload.get("extra", {}),
        )
    return out


def save(entries: dict[str, StageEntry]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {name: entry.to_dict() for name, entry in entries.items()}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def update(stage: str, *, status: Status = "done", **extra: Any) -> StageEntry:
    """Record a stage run. ``extra`` is free-form (count, top_score, error, …)."""
    entries = load()
    entry = entries.get(stage) or StageEntry(name=stage)
    entry.status = status
    entry.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if extra:
        # Merge — let callers report incremental fields without losing prior context.
        entry.extra = {**entry.extra, **extra}
    entries[stage] = entry
    save(entries)
    return entry


def get(stage: str) -> Optional[StageEntry]:
    return load().get(stage)


def summary() -> str:
    """One-line-per-stage textual summary, ordered by stage name."""
    entries = load()
    if not entries:
        return "(no stages recorded yet — run scan / auto-register / review)"
    lines = []
    for name in sorted(entries):
        e = entries[name]
        bits = [f"{e.name:<22}", f"{e.status:<8}"]
        if e.extra:
            bits.append(" · ".join(f"{k}={v}" for k, v in e.extra.items()))
        if e.updated_at:
            bits.append(e.updated_at)
        lines.append(" ".join(bits))
    return "\n".join(lines)


# Known stages — kept here so consumers can reference a constant rather than
# scatter string literals. Add to this list when introducing a new pipeline.
STAGE_DAILY_SCAN = "daily_scan"
STAGE_AUTO_REGISTER = "auto_register"
STAGE_PORTFOLIO_REVIEW = "portfolio_review"
STAGE_SIMULATE = "simulate"
