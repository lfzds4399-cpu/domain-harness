"""Sales: 域名挂牌出售 + AI 议价

平台支持：Dan.com / Afternic / Sedo（先做 stub，接 key 后激活）
默认策略：注册成本 × default_markup 倍起价；用户可单独覆盖。
DRY_RUN 时只更新 portfolio 中的 listed_price/listed_at。
"""
from __future__ import annotations
import os
import re
from datetime import datetime
from typing import Optional

import requests

from core import config, store, log


class ListingError(Exception):
    pass


def calc_price(domain_record: dict, override: float | None = None) -> float:
    if override is not None:
        return float(override)
    cfg = config.load()["sales"]
    cost = float(domain_record.get("cost_usd", 10))
    score = domain_record.get("score", 50)

    markup = cfg.get("default_markup", 50)
    strategy = cfg.get("pricing_strategy", "balanced")
    if strategy == "aggressive":
        markup *= 2
    elif strategy == "conservative":
        markup *= 0.5

    # 高分域名再加成
    if score >= 85:
        markup *= 2.5
    elif score >= 75:
        markup *= 1.5

    price = cost * markup
    return round(max(price, 99), 2)  # 最低 $99


# ---------------- Dan.com ----------------
def list_on_dan(domain: str, price: float) -> dict:
    api_key = os.environ.get("DAN_API_KEY", "")
    if not api_key:
        raise ListingError("DAN_API_KEY 未配置")
    # Dan 的 API 文档需登录后查；这里给占位结构
    r = requests.post(
        "https://api.dan.com/v1/domains",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"domain": domain, "price": price, "currency": "USD"},
        timeout=30,
    )
    if r.status_code >= 300:
        raise ListingError(f"dan: {r.status_code} {r.text[:200]}")
    return r.json()


def list_on_afternic(domain: str, price: float) -> dict:
    # Afternic 没有公开 REST API，通常用 Fast Transfer / GoDaddy 控制台
    raise ListingError("Afternic 暂未接入（需 GoDaddy Fast Transfer 配置）")


def list_on_sedo(domain: str, price: float) -> dict:
    # Sedo 有 SOAP API，需开发者账号
    raise ListingError("Sedo 暂未接入（需 SOAP API 凭据）")


PLATFORM_HANDLERS = {
    "dan": list_on_dan,
    "afternic": list_on_afternic,
    "sedo": list_on_sedo,
}


def list_for_sale(domain: str, price: float | None = None, platforms: list[str] | None = None) -> dict:
    p = store.portfolio()
    rec = next((x for x in p.get("owned", []) if x["domain"] == domain), None)
    if rec is None:
        raise ListingError(f"未持有：{domain}")

    final_price = calc_price(rec, override=price)

    cfg = config.load()["sales"]
    if platforms is None:
        platforms = [k for k, v in cfg.get("platforms", {}).items() if v.get("enabled")]

    results = {}
    if config.is_dry_run() or not platforms:
        log.dry("DRY_RUN 挂牌", domain=domain, price=final_price)
        results = {"dry_run": {"price": final_price}}
    else:
        for plat in platforms:
            handler = PLATFORM_HANDLERS.get(plat)
            if not handler:
                continue
            try:
                results[plat] = handler(domain, final_price)
                log.ok("挂牌成功", domain=domain, platform=plat, price=final_price)
            except Exception as e:
                log.warn("挂牌失败", domain=domain, platform=plat, err=str(e))
                results[plat] = {"error": str(e)}

    rec["listed_price_usd"] = final_price
    rec["listed_at"] = datetime.utcnow().isoformat()
    rec["listed_platforms"] = list(results.keys())
    store.save_portfolio(p)
    return {"domain": domain, "price_usd": final_price, "platforms": results}


# ---------------- AI 议价回复 ----------------
COUNTER_PROMPT = """你是域名经纪。买家询价了 {domain}，标价 ${listed_price}。
买家出价 ${buyer_offer}。
策略：{strategy}（aggressive=最多让 20%；balanced=最多让 35%；conservative=最多让 50%）。
请给出一句中文回复（最多 60 字），并给出本次还价 USD 金额。

严格 JSON 返回：{{"reply": "<一句话>", "counter_offer_usd": <int>}}"""


def negotiate_reply(domain: str, buyer_offer: float) -> dict:
    rec = next((x for x in store.portfolio().get("owned", []) if x["domain"] == domain), None)
    if rec is None or "listed_price_usd" not in rec:
        raise ListingError(f"{domain} 未挂牌")

    cfg = config.load()["sales"]
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    listed = rec["listed_price_usd"]

    if not api_key:
        # 无 AI 时退化到固定策略：50% 让步
        floor_map = {"aggressive": 0.8, "balanced": 0.65, "conservative": 0.5}
        floor = listed * floor_map.get(cfg.get("pricing_strategy", "balanced"), 0.65)
        counter = max(buyer_offer * 1.5, floor)
        return {
            "reply": f"感谢报价。最低可至 ${counter:.0f}，您看可以吗？",
            "counter_offer_usd": round(counter, 2),
            "ai": False,
        }

    prompt = COUNTER_PROMPT.format(
        domain=domain,
        listed_price=listed,
        buyer_offer=buyer_offer,
        strategy=cfg.get("pricing_strategy", "balanced"),
    )
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-opus-4-7",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    text = r.json()["content"][0]["text"]
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return {"reply": text[:120], "counter_offer_usd": listed, "ai": True, "raw": text}
    import json
    obj = json.loads(m.group(0))
    obj["ai"] = True
    return obj
