"""Acquisition: 域名注册下单 — 多注册商适配层

支持：Porkbun / Cloudflare / Namecheap / GoDaddy
策略：按 manifest.priority 顺序尝试，第一个成功即返回。
DRY_RUN 模式下不真实下单，只记录日志和 portfolio。

每次下单前：
1) dup_check（不重复买）
2) whois_check（确认可注册）
3) budget_guard（预算守卫）
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta
from typing import Optional

import requests

from core import config, store, log
from validators import budget_guard, dup_check, whois_check, trademark_check


class RegistrationError(Exception):
    pass


# ---------------- Porkbun ----------------
class PorkbunClient:
    BASE = "https://api.porkbun.com/api/json/v3"

    def __init__(self, api_key: str, secret: str):
        self.api_key = api_key
        self.secret = secret

    def _post(self, path: str, payload: dict) -> dict:
        body = {"apikey": self.api_key, "secretapikey": self.secret, **payload}
        r = requests.post(f"{self.BASE}{path}", json=body, timeout=30)
        return r.json()

    def check_price(self, tld: str) -> Optional[float]:
        r = requests.get(f"{self.BASE}/pricing/get", timeout=15).json()
        if r.get("status") != "SUCCESS":
            return None
        price = r["pricing"].get(tld, {}).get("registration")
        return float(price) if price else None

    def register(self, domain: str, years: int = 1) -> dict:
        # Porkbun 注册 API：/domain/register（需要账号有支付方式）
        r = self._post("/domain/register", {"domain": domain, "years": years})
        if r.get("status") != "SUCCESS":
            raise RegistrationError(f"porkbun: {r.get('message')}")
        return r


# ---------------- Cloudflare ----------------
class CloudflareClient:
    """注：Cloudflare 不接 drop catch，只能续费/迁入。"""
    BASE = "https://api.cloudflare.com/client/v4"

    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id

    def register(self, domain: str, years: int = 1) -> dict:
        # Cloudflare Registrar 的注册接口需要账号绑定支付且已验证
        r = requests.post(
            f"{self.BASE}/accounts/{self.account_id}/registrar/domains",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={"name": domain, "auto_renew": False, "years": years},
            timeout=30,
        )
        data = r.json()
        if not data.get("success"):
            raise RegistrationError(f"cloudflare: {data.get('errors')}")
        return data


# ---------------- 工厂 ----------------
def get_clients() -> list[tuple[str, object]]:
    cfg = config.load()["registrars"]
    out = []
    pb = cfg.get("porkbun", {})
    if pb.get("enabled") and pb.get("api_key"):
        out.append(("porkbun", PorkbunClient(pb["api_key"], pb["secret_key"])))
    cf = cfg.get("cloudflare", {})
    if cf.get("enabled") and cf.get("api_token"):
        out.append(("cloudflare", CloudflareClient(cf["api_token"], cf["account_id"])))
    out.sort(key=lambda x: cfg[x[0]].get("priority", 999))
    return out


# ---------------- 主入口 ----------------
def buy(domain: str, max_price: float, score_meta: dict | None = None) -> dict:
    """
    走完所有 validators，再调注册商 API。
    DRY_RUN 时跳过真实 API，但仍写入 portfolio + budget。
    """
    domain = domain.lower().strip()

    trademark_check.check(domain)  # 法律红线 — 含商标直接拒
    dup_check.check(domain)
    whois_check.check(domain)
    budget_guard.check(max_price, domain, kind="register")

    if config.is_dry_run():
        log.dry("DRY_RUN 注册", domain=domain, max_price=max_price)
        cost = max_price
        registrar = "dry_run"
    else:
        clients = get_clients()
        if not clients:
            raise RegistrationError("没有可用的注册商（manifest 中 enabled=true 且填了 key）")
        last_err = None
        registrar = None
        for name, client in clients:
            try:
                client.register(domain, years=1)
                registrar = name
                cost = max_price  # 实际成本以注册商账单为准
                log.ok("注册成功", domain=domain, registrar=name)
                break
            except Exception as e:
                last_err = e
                log.warn(f"{name} 注册失败", domain=domain, err=str(e))
        if registrar is None:
            raise RegistrationError(f"所有注册商均失败：{last_err}")

    record = {
        "domain": domain,
        "registrar": registrar,
        "registered_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
        "cost_usd": cost,
        "score": (score_meta or {}).get("score"),
        "council_score": (score_meta or {}).get("council_score"),
        "source": (score_meta or {}).get("source"),
    }
    store.add_owned(record)
    store.record_spend(cost, domain, kind="register")
    return record
