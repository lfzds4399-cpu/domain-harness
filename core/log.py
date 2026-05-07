"""统一日志 — 控制台彩色 + 文件 jsonl.

quiet 模式（``-q`` / ``--quiet`` / env DOMAIN_HARNESS_QUIET=1）下控制台只
输出 WARN/ERR; INFO / OK / DRY 仍完整写到 ``logs/YYYY-MM-DD.jsonl``。设计意图
见 harness-engineering SKILL § 2.3 — 跑 CC 时不要污染主对话上下文，需要排查
直接看文件。
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime

from . import config


_COLORS = {
    "INFO": "\033[36m",
    "OK": "\033[32m",
    "WARN": "\033[33m",
    "ERR": "\033[31m",
    "DRY": "\033[35m",
}
_RESET = "\033[0m"

# Console 仅在 quiet 模式下沉默 INFO/OK/DRY; 文件日志永远完整。
_CONSOLE_QUIET_LEVELS = {"INFO", "OK", "DRY"}
_QUIET = os.getenv("DOMAIN_HARNESS_QUIET", "").lower() in {"1", "true", "yes"}


def set_quiet(quiet: bool = True) -> None:
    """Toggle console quiet mode globally. CLI's ``-q`` flag calls this."""
    global _QUIET
    _QUIET = quiet


def is_quiet() -> bool:
    return _QUIET


def _emit(level: str, msg: str, **kv):
    ts = datetime.now().strftime("%H:%M:%S")

    # File log — always written, regardless of quiet.
    log_file = config.logs_dir() / f"{datetime.now().date()}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "msg": msg,
            **kv,
        }, ensure_ascii=False) + "\n")

    if _QUIET and level in _CONSOLE_QUIET_LEVELS:
        return

    color = _COLORS.get(level, "")
    extras = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"{color}[{ts}] {level:<4}{_RESET} {msg} {extras}".rstrip())
    sys.stdout.flush()


def info(msg, **kv): _emit("INFO", msg, **kv)
def ok(msg, **kv): _emit("OK", msg, **kv)
def warn(msg, **kv): _emit("WARN", msg, **kv)
def err(msg, **kv): _emit("ERR", msg, **kv)
def dry(msg, **kv): _emit("DRY", msg, **kv)
