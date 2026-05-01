"""商标黑名单守卫 — 防 UDRP 仲裁

含已知商标子串的域名一律拒绝。即使本地分再高、AI 再看好都不能买。
注：这只是最低限度防护，不能替代法律咨询。真正大规模商品化前应过律师。
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLACKLIST_PATH = ROOT / "data" / "trademark_blacklist.txt"


class TrademarkConflict(Exception):
    pass


@lru_cache(maxsize=1)
def _load() -> list[str]:
    if not BLACKLIST_PATH.exists():
        return []
    out = []
    with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip().lower()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


def find_conflict(domain: str) -> str | None:
    name = domain.lower().rsplit(".", 1)[0]
    for tm in _load():
        if tm in name:
            return tm
    return None


def check(domain: str) -> None:
    hit = find_conflict(domain)
    if hit:
        raise TrademarkConflict(f"含商标 '{hit}'：{domain}（UDRP 风险）")
