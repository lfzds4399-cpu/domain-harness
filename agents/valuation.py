"""Valuation: 多维度域名估值

打分维度（满分 100）：
- 长度：≤4=40, 5=30, 6=22, 7-8=12, 9-10=4, 11-12=0, >12=-20
- TLD 优先级（manifest 配置，最高权重 25）
- 字典词命中：英文常见词 +15
- 可发音性：CVCV/有元音分布 +10
- 数字/连字符：含数字 -10，含连字符 -15
- 含黑名单字符（如保留拼音/敏感词）-30
- 关键词命中（行业热词）+5/词 上限 +15

返回 score 0-100，附带 breakdown 便于审计。
"""
from __future__ import annotations
from typing import Iterable

from core import config


# 简易字典（可逐步扩充）
COMMON_WORDS = set("""
go run fly jump leap rise wave lake river ocean sky cloud sun moon star
ai bot data cloud edge mesh node ledger token chain coin
shop pay bank loan fund stock trade crypto invest money
health med fit yoga diet sleep dream calm rest
edu learn study tutor teach kid class school
work job team task flow doc form deck note
art music song video photo design draw paint
food drink cook eat chef diner kitchen taste
travel trip hotel flight tour map road path
home rent deal sale buy gift store room
gen auto smart fast easy quick swift bright
hub lab kit pad box deck nest wave bridge
""".lower().split())

INDUSTRY_KEYWORDS = COMMON_WORDS  # 简化处理，复用同一词典

VOWELS = set("aeiou")


def _length_score(name: str) -> int:
    n = len(name)
    if n <= 4: return 40
    if n == 5: return 30
    if n == 6: return 22
    if n <= 8: return 12
    if n <= 10: return 4
    if n <= 12: return 0
    return -20


def _tld_score(tld: str, priority_map: dict) -> int:
    p = priority_map.get(tld, 0)
    return min(25, p // 4)  # 100 优先级 → 25 分


def _dictionary_hit(name: str) -> int:
    if name in COMMON_WORDS:
        return 15
    # 包含一个常见词作为子串（前缀/后缀）
    for w in COMMON_WORDS:
        if len(w) >= 4 and (name.startswith(w) or name.endswith(w)):
            return 8
    return 0


def _pronounceable(name: str) -> int:
    if not name:
        return 0
    vowels = sum(1 for c in name if c in VOWELS)
    ratio = vowels / len(name)
    if 0.25 <= ratio <= 0.6:
        return 10
    if 0.15 <= ratio <= 0.7:
        return 5
    return 0


def _penalties(name: str) -> int:
    p = 0
    if any(c.isdigit() for c in name):
        p -= 10
    if "-" in name:
        p -= 15
    if "xn--" in name:
        p -= 30  # punycode
    return p


def _keyword_hit(name: str) -> int:
    hits = 0
    for kw in INDUSTRY_KEYWORDS:
        if len(kw) >= 4 and kw in name:
            hits += 1
            if hits >= 3:
                break
    return hits * 5


def _commercial_signal(name: str, dictionary_score: int, keyword_score: int) -> tuple[bool, str]:
    """硬门槛：必须有商业信号才算"潜力域名"。

    达成任一即可：
      A) 字典词命中（dictionary_score > 0）
      B) 行业关键词命中（keyword_score > 0）
      C) 极短品牌候选（≤4 字符且无数字/连字符）

    都不满足 → 不是有潜力的，无论本地分多高都拒绝自动买。
    """
    if dictionary_score > 0:
        return True, "dictionary"
    if keyword_score > 0:
        return True, "keyword"
    if len(name) <= 4 and name.isalpha():
        return True, "ultra_short_brand"
    return False, "no_commercial_signal"


def score(domain: str) -> dict:
    cfg = config.load()
    name, _, tld = domain.lower().rpartition(".")

    dict_s = _dictionary_hit(name)
    kw_s = _keyword_hit(name)
    has_signal, signal_reason = _commercial_signal(name, dict_s, kw_s)

    breakdown = {
        "length": _length_score(name),
        "tld": _tld_score(tld, cfg["tld"]["priority"]),
        "dictionary": dict_s,
        "pronounceable": _pronounceable(name) if has_signal else 0,  # 无商业信号时连可发音分都不给
        "keyword": kw_s,
        "penalty": _penalties(name),
    }
    total = sum(breakdown.values())
    # 无商业信号 hard cap 在 40 分（连 watchlist 门槛 60 都过不了）
    if not has_signal:
        total = min(total, 40)
    total = max(0, min(100, total))
    return {
        "domain": domain,
        "score": total,
        "breakdown": breakdown,
        "commercial_signal": has_signal,
        "signal_reason": signal_reason,
        "tld": tld,
        "name": name,
        "length": len(name),
    }


def score_many(domains: Iterable[str | dict]) -> list[dict]:
    out = []
    for d in domains:
        domain = d if isinstance(d, str) else d["domain"]
        result = score(domain)
        if isinstance(d, dict):
            result.update({k: v for k, v in d.items() if k not in result})
        out.append(result)
    return out


if __name__ == "__main__":
    for d in ["pay.com", "go.ai", "myshop.io", "quantumledger.xyz", "x9z-bot.info"]:
        print(score(d))
