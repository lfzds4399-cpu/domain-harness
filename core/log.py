"""统一日志 — 控制台彩色 + 文件 jsonl"""
from __future__ import annotations
import json
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


def _emit(level: str, msg: str, **kv):
    ts = datetime.now().strftime("%H:%M:%S")
    color = _COLORS.get(level, "")
    extras = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"{color}[{ts}] {level:<4}{_RESET} {msg} {extras}".rstrip())
    sys.stdout.flush()

    log_file = config.logs_dir() / f"{datetime.now().date()}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.utcnow().isoformat(),
            "level": level,
            "msg": msg,
            **kv,
        }, ensure_ascii=False) + "\n")


def info(msg, **kv): _emit("INFO", msg, **kv)
def ok(msg, **kv): _emit("OK", msg, **kv)
def warn(msg, **kv): _emit("WARN", msg, **kv)
def err(msg, **kv): _emit("ERR", msg, **kv)
def dry(msg, **kv): _emit("DRY", msg, **kv)
