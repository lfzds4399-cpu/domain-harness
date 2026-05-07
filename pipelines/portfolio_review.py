"""月度持仓回顾 pipeline

对每个 owned domain：
- 检查到期日（≤30 天）→ 评估保留 vs drop
- 持有 ≥ 90 天且未挂牌 → 自动挂牌
- 已挂牌 ≥ 180 天且无询价 → 调降 20% 或转其他平台
"""
from __future__ import annotations
from datetime import datetime

from core import store, log
from agents import sales


def run() -> dict:
    now = datetime.utcnow()
    p = store.portfolio()
    owned = p.get("owned", [])

    actions = []
    for rec in owned:
        domain = rec["domain"]
        registered_at = datetime.fromisoformat(rec["registered_at"].replace("Z", ""))
        expires_at = datetime.fromisoformat(rec["expires_at"].replace("Z", ""))
        held_days = (now - registered_at).days
        days_to_expire = (expires_at - now).days

        # 1) 到期警告
        if days_to_expire <= 30:
            actions.append({
                "domain": domain,
                "action": "expiry_warning",
                "days_to_expire": days_to_expire,
                "score": rec.get("score"),
                "suggestion": "保留" if (rec.get("score") or 0) >= 70 else "考虑 drop",
            })

        # 2) 未挂牌且持有 ≥90 天 → 挂牌
        if held_days >= 90 and "listed_price_usd" not in rec:
            try:
                r = sales.list_for_sale(domain)
                actions.append({"domain": domain, "action": "listed", **r})
            except Exception as e:
                actions.append({"domain": domain, "action": "list_failed", "err": str(e)})

        # 3) 挂牌 ≥180 天无询价 → 调降 20%
        if "listed_at" in rec:
            listed_at = datetime.fromisoformat(rec["listed_at"].replace("Z", ""))
            if (now - listed_at).days >= 180:
                new_price = round(rec["listed_price_usd"] * 0.8, 2)
                rec["listed_price_usd"] = new_price
                rec["last_repriced_at"] = now.isoformat()
                actions.append({
                    "domain": domain,
                    "action": "repriced",
                    "new_price": new_price,
                })

    store.save_portfolio(p)

    summary = {
        "ts": now.isoformat(),
        "owned_count": len(owned),
        "actions": actions,
    }
    log.ok("===== portfolio_review 完成 =====",
           owned=len(owned), actions=len(actions))

    from core import manifest
    manifest.update(
        manifest.STAGE_PORTFOLIO_REVIEW,
        status="done",
        owned=len(owned),
        actions=len(actions),
    )
    return summary


if __name__ == "__main__":
    import json
    s = run()
    print(json.dumps(s, indent=2, default=str))
