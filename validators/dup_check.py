"""防重复买入 / 防黑名单"""
from __future__ import annotations

from core import store


class DuplicateError(Exception):
    pass


def check(domain: str) -> None:
    domain = domain.lower().strip()
    if store.is_owned(domain):
        raise DuplicateError(f"已持有：{domain}")
    if store.is_blacklisted(domain):
        raise DuplicateError(f"在黑名单：{domain}")
