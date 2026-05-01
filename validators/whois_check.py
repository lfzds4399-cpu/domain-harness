"""WHOIS 可注册检查 — DNS + RDAP 双确认

DRY_RUN 模式下用 DNS + 简单 RDAP 查询；live 模式建议接注册商 API 的 check 接口。
"""
from __future__ import annotations
import socket
from typing import Optional

import requests

from core import log


class NotAvailable(Exception):
    pass


RDAP_BOOTSTRAP = "https://rdap.org/domain/"


def is_available(domain: str, timeout: float = 5.0) -> bool:
    """
    返回 True 表示"看起来可注册"。

    策略（DNS 是主信号、RDAP 是二次验证）：
    1) DNS 解析成功 → 已注册（False，100% 确定）
    2) DNS 失败 + RDAP 200 → 已注册（False）
    3) DNS 失败 + RDAP 404 → 可注册（True）
    4) DNS 失败 + RDAP 超时/失败 → 推定可用（True）

    第 4 条理由：DNS 失败已经是较强信号；RDAP 只是辅助确认。
    真实下单时注册商 API 会做最终鉴权，所以这里偏可用一侧。

    注：drop catch 场景下不能依赖 WHOIS 缓存，必须接注册商 check API。
    """
    domain = domain.lower().strip()

    # 1) DNS
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(domain)
        return False  # 解析成功 = 已注册
    except socket.gaierror:
        pass  # DNS 失败 → 大概率可用，继续 RDAP 二次确认
    except Exception as e:
        log.warn("DNS 查询异常", domain=domain, err=str(e))

    # 2) RDAP — 有结果才用，没结果就信 DNS
    try:
        r = requests.get(RDAP_BOOTSTRAP + domain, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return False
        if r.status_code == 404:
            return True
        # 其他状态码（429/5xx）也按可用处理
    except Exception as e:
        log.warn("RDAP 查询失败（信任 DNS 结果）", domain=domain, err=str(e))

    # DNS 失败 + RDAP 未给结论 → 推定可用
    return True


def check(domain: str) -> None:
    if not is_available(domain):
        raise NotAvailable(f"WHOIS 显示已注册：{domain}")
