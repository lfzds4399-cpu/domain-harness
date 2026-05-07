"""Discovery: 过期域名抓榜

数据源：ExpiredDomains.net 的公开榜单 / RSS。
没有 API key，用 HTML 解析。注意 robots.txt 和频率。

DRY_RUN 时如果抓不到（被墙/限流），降级到本地 sample 数据让流程跑通。
"""
from __future__ import annotations
import re

import requests
from bs4 import BeautifulSoup

from core import config, log


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; domain-harness/0.1; research)",
}

# 公开榜单 — 不需要登录的几个入口
PUBLIC_LISTS = [
    "https://www.expireddomains.net/expired-domains/",
    "https://www.expireddomains.net/deleted-com-domains/",
]

DOMAIN_RE = re.compile(r"^[a-z0-9-]{1,63}\.[a-z]{2,10}$", re.I)


def _parse_html(html: str, source: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # ExpiredDomains 通常是 table.base1 / tbody > tr
    for tr in soup.select("table tr")[:200]:
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        # 第一格通常是域名
        text = tds[0].get_text(strip=True).lower()
        if not DOMAIN_RE.match(text):
            continue
        name, _, tld = text.rpartition(".")
        rows.append({
            "domain": text,
            "raw_name": name,
            "tld": tld,
            "source": source,
            "pattern": "expired",
        })
    return rows


def _fallback_sample() -> list[dict]:
    """抓不到时用一批结构化 sample 让 pipeline 跑通"""
    samples = ["nexora.com", "kyto.io", "lumio.ai", "zappi.co", "pivox.app"]
    out = []
    for d in samples:
        name, _, tld = d.rpartition(".")
        out.append({
            "domain": d,
            "raw_name": name,
            "tld": tld,
            "source": "expired_fallback_sample",
            "pattern": "expired",
        })
    return out


def run(limit: int | None = None) -> list[dict]:
    cfg = config.load()
    src = cfg["sources"]["expired_domains"]
    if not src.get("enabled"):
        return []

    limit = limit or src.get("daily_limit", 500)
    rows: list[dict] = []
    for url in PUBLIC_LISTS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                log.warn(f"expired list HTTP {r.status_code}", url=url)
                continue
            parsed = _parse_html(r.text, source=url)
            log.info(f"expired source 抓到 {len(parsed)}", url=url)
            rows.extend(parsed)
        except Exception as e:
            log.warn("expired source 抓取失败", url=url, err=str(e))

    if not rows:
        log.warn("expired 数据源全部失败，降级 sample")
        rows = _fallback_sample()

    # 去重
    seen = set()
    deduped = []
    for r in rows:
        if r["domain"] in seen:
            continue
        seen.add(r["domain"])
        deduped.append(r)
    return deduped[:limit]


if __name__ == "__main__":
    rs = run(limit=20)
    for r in rs:
        print(r)
