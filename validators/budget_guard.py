"""预算守卫 — 三层硬刹车（日/月/单域名）

每次买入前必过此关。任何一层超限直接 raise BudgetExceeded。
"""
from __future__ import annotations
from datetime import date

from core import config, store, log


class BudgetExceeded(Exception):
    pass


def check(amount_usd: float, domain: str, kind: str = "register") -> None:
    """
    kind: "register" | "auction" | "renew"
    """
    cfg = config.load()["budget"]
    b = store.budget()

    today = date.today().isoformat()
    month = today[:7]
    today_spent = b.get("today", {}).get("spent_usd", 0) if b.get("today", {}).get("date") == today else 0
    month_spent = b.get("this_month", {}).get("spent_usd", 0) if b.get("this_month", {}).get("month") == month else 0

    # 1) 单域名上限
    cap_key = "per_domain_auction" if kind == "auction" else "per_domain_register"
    cap = cfg.get(cap_key, 0)
    if amount_usd > cap:
        raise BudgetExceeded(
            f"单域名 {kind} 上限 ${cap}，本次 ${amount_usd}（{domain}）"
        )

    # 2) 日上限
    if today_spent + amount_usd > cfg["daily_limit"]:
        raise BudgetExceeded(
            f"日预算 ${cfg['daily_limit']} 超限：今日已花 ${today_spent}，本次 ${amount_usd}"
        )

    # 3) 月上限
    if month_spent + amount_usd > cfg["monthly_limit"]:
        raise BudgetExceeded(
            f"月预算 ${cfg['monthly_limit']} 超限：本月已花 ${month_spent}，本次 ${amount_usd}"
        )

    log.info(
        "budget OK",
        domain=domain,
        amount=amount_usd,
        today=f"{today_spent + amount_usd}/{cfg['daily_limit']}",
        month=f"{month_spent + amount_usd}/{cfg['monthly_limit']}",
    )


def remaining() -> dict:
    cfg = config.load()["budget"]
    b = store.budget()
    today = date.today().isoformat()
    month = today[:7]
    today_spent = b.get("today", {}).get("spent_usd", 0) if b.get("today", {}).get("date") == today else 0
    month_spent = b.get("this_month", {}).get("spent_usd", 0) if b.get("this_month", {}).get("month") == month else 0
    return {
        "daily_remaining": cfg["daily_limit"] - today_spent,
        "monthly_remaining": cfg["monthly_limit"] - month_spent,
        "currency": cfg.get("currency", "USD"),
    }
