"""数据持久化 — portfolio / budget / 候选历史"""
from __future__ import annotations
import json
from datetime import datetime, date
from pathlib import Path
from typing import Any

from . import config


def _read(name: str) -> dict:
    p = config.data_dir() / name
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(name: str, payload: dict) -> None:
    p = config.data_dir() / name
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# -------- portfolio --------
def portfolio() -> dict:
    p = _read("portfolio.json")
    p.setdefault("owned", [])
    p.setdefault("watchlist", [])
    p.setdefault("blacklist", [])
    return p


def save_portfolio(p: dict) -> None:
    _write("portfolio.json", p)


def add_owned(record: dict) -> None:
    p = portfolio()
    p.setdefault("owned", []).append(record)
    save_portfolio(p)


def add_watchlist(record: dict) -> None:
    p = portfolio()
    existing = {x["domain"] for x in p.get("watchlist", [])}
    if record["domain"] in existing:
        return
    p.setdefault("watchlist", []).append(record)
    save_portfolio(p)


def is_blacklisted(domain: str) -> bool:
    p = portfolio()
    return any(x["domain"] == domain for x in p.get("blacklist", []))


def is_owned(domain: str) -> bool:
    p = portfolio()
    return any(x["domain"] == domain for x in p.get("owned", []))


# -------- budget --------
def budget() -> dict:
    b = _read("budget_state.json")
    b.setdefault("lifetime", {"total_spent_usd": 0, "domains_bought": 0})
    return b


def save_budget(b: dict) -> None:
    _write("budget_state.json", b)


def record_spend(amount_usd: float, domain: str, kind: str) -> None:
    b = budget()
    today = date.today().isoformat()
    month = today[:7]

    if b.get("today", {}).get("date") != today:
        b["today"] = {"date": today, "spent_usd": 0, "transactions": []}
    if b.get("this_month", {}).get("month") != month:
        b["this_month"] = {"month": month, "spent_usd": 0, "transactions": []}

    txn = {
        "ts": datetime.utcnow().isoformat(),
        "domain": domain,
        "kind": kind,
        "amount_usd": amount_usd,
    }
    b["today"]["spent_usd"] += amount_usd
    b["today"]["transactions"].append(txn)
    b["this_month"]["spent_usd"] += amount_usd
    b["this_month"]["transactions"].append(txn)
    b["lifetime"]["total_spent_usd"] = b["lifetime"].get("total_spent_usd", 0) + amount_usd
    b["lifetime"]["domains_bought"] = b["lifetime"].get("domains_bought", 0) + 1
    save_budget(b)


# -------- 候选历史（每日 scan 输出）--------
def append_scan_log(rows: list[dict]) -> None:
    p = config.data_dir() / "scan_history.jsonl"
    with open(p, "a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
