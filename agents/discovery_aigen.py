"""Discovery: AI 模式生成可注册短域名候选

不依赖外部 API：用 CVCV / 字典组合 / 单词截短 模式批量生成，
然后调用 whois_check 过滤已注册的，留下可注册短域名。

输出：候选 list[dict]，每条 {domain, source, pattern, raw_name}
"""
from __future__ import annotations
import random
from typing import Iterable

from core import config, log
from validators import whois_check


# 常见可发音辅音/元音
CONSONANTS = list("bcdfghjklmnpqrstvwxyz")
VOWELS = list("aeiou")

# 高价值前/后缀词典（短而泛用）
PREFIXES = [
    "ai", "neo", "pro", "max", "go", "be", "my", "we", "the", "get",
    "use", "try", "lab", "hub", "box", "kit", "pad", "log", "map", "net",
]
SUFFIXES = [
    "ly", "io", "fy", "hub", "lab", "kit", "pad", "box", "now", "app",
    "go", "x", "ai", "co", "up", "ware", "ify", "nest", "deck", "wave",
]
# 行业关键词
INDUSTRY = [
    "shop", "pay", "bank", "loan", "fund", "stock", "trade", "crypto",
    "health", "med", "fit", "yoga", "diet", "sleep",
    "edu", "learn", "study", "kid", "tutor",
    "work", "job", "team", "task", "flow", "doc", "form",
    "art", "music", "song", "video", "photo", "design",
    "food", "drink", "cook", "eat", "chef",
    "travel", "trip", "hotel", "flight", "tour",
    "home", "rent", "deal", "sale",
    "data", "cloud", "edge", "mesh", "node",
    "gen", "auto", "smart", "fast", "easy",
]


def cvcv(n: int = 4) -> str:
    """生成可发音 CVCV 模式（4-6 字符）"""
    pieces = []
    for _ in range(n // 2):
        pieces.append(random.choice(CONSONANTS) + random.choice(VOWELS))
    return "".join(pieces)


def cvcvc(n: int = 5) -> str:
    s = cvcv(n - 1)
    return s + random.choice(CONSONANTS)


def combo() -> str:
    """前缀 + 后缀 / 行业 + 后缀（强制 ≥5 字符，<5 几乎全注册了）"""
    for _ in range(10):
        a = random.choice(PREFIXES + INDUSTRY)
        b = random.choice(SUFFIXES + INDUSTRY)
        if a == b:
            b = random.choice(SUFFIXES)
        s = a + b
        if len(s) >= 5:
            return s
    return a + b  # 兜底


def brand_short() -> str:
    """3-5 字符随机辅音元音串（更激进、更多噪声）"""
    n = random.choice([4, 5])
    s = ""
    for i in range(n):
        s += random.choice(VOWELS) if i % 2 else random.choice(CONSONANTS)
    return s


GENERATORS = {
    "cvcv": lambda: cvcv(4),
    "cvcvcv": lambda: cvcv(6),
    "dictionary_combo": combo,
    "brand_short": brand_short,
}


# 模式权重 — 偏向有商业信号的 dictionary_combo
# cvcv/brand_short 几乎全是噪声，权重压到 0.05；dictionary_combo 占 0.85
PATTERN_WEIGHTS = {
    "dictionary_combo": 0.85,
    "cvcvcv": 0.05,
    "cvcv": 0.05,
    "brand_short": 0.05,
}


def _weighted_choice(patterns: list[str]) -> str:
    weights = [PATTERN_WEIGHTS.get(p, 0.05) for p in patterns]
    return random.choices(patterns, weights=weights, k=1)[0]


def generate(target: int, patterns: Iterable[str], tlds: list[str]) -> list[dict]:
    """生成 target 个候选。

    商业潜力优先：dictionary_combo 占 85%，纯随机模式仅留 15% 兜底。
    每个名字只出一个 TLD（成本控制 + 防 watchlist 污染）。
    """
    out = []
    seen = set()
    patterns = list(patterns)
    if not patterns:
        return out

    attempts = 0
    while len(out) < target and attempts < target * 20:
        attempts += 1
        pattern = _weighted_choice(patterns)
        gen = GENERATORS.get(pattern)
        if gen is None:
            continue
        name = gen()
        # 最短 5 字符（≤4 字符 .com 已几乎全注册，AI 拿不到）
        if not name or len(name) < 5 or name in seen:
            continue
        seen.add(name)
        for tld in tlds:
            domain = f"{name}.{tld}"
            out.append({
                "domain": domain,
                "raw_name": name,
                "pattern": pattern,
                "tld": tld,
                "source": "ai_generated",
            })
            break
    return out


def _prefilter_commercial(candidates: list[dict]) -> list[dict]:
    """送 WHOIS 前先本地过滤 — 没商业信号的直接丢，省 RDAP 调用"""
    from agents import valuation
    kept = []
    dropped = 0
    for c in candidates:
        s = valuation.score(c["domain"])
        if s.get("commercial_signal"):
            c["pre_score"] = s["score"]
            c["signal_reason"] = s["signal_reason"]
            kept.append(c)
        else:
            dropped += 1
    log.info(f"本地预筛：保留 {len(kept)}，过滤 {dropped} 条无商业信号噪声")
    return kept


def filter_available(candidates: list[dict], max_check: int = 100) -> list[dict]:
    """对候选做 WHOIS 可用性过滤；为节流，每次最多 check max_check 个"""
    available = []
    for i, c in enumerate(candidates[:max_check]):
        if whois_check.is_available(c["domain"]):
            available.append(c)
            log.ok("可注册",
                   domain=c["domain"],
                   pattern=c["pattern"],
                   pre_score=c.get("pre_score"))
        if (i + 1) % 20 == 0:
            log.info(f"WHOIS 进度 {i+1}/{min(max_check, len(candidates))}")
    return available


def run(daily_target: int | None = None) -> list[dict]:
    cfg = config.load()
    src = cfg["sources"]["ai_generated"]
    if not src.get("enabled"):
        return []

    target = daily_target or src.get("daily_target", 100)
    patterns = src.get("patterns", ["cvcv", "dictionary_combo"])
    tlds = sorted(
        cfg["tld"]["whitelist"],
        key=lambda t: -cfg["tld"]["priority"].get(t, 0),
    )

    # 多生成 5 倍量，本地预筛后再送 WHOIS（节省 RDAP 调用 + 提高命中率）
    overshoot = target * 5
    log.info(f"AI 生成 {overshoot} 个原始候选", patterns=patterns, tlds=tlds[:3])
    raw = generate(overshoot, patterns, tlds[:2])
    candidates = _prefilter_commercial(raw)
    candidates.sort(key=lambda x: -x.get("pre_score", 0))  # 高分先 WHOIS

    log.info(f"开始 WHOIS 过滤前 {min(target, len(candidates))} 条")
    available = filter_available(candidates, max_check=min(target, 100))
    log.ok(f"可注册候选 {len(available)} 条")
    return available


if __name__ == "__main__":
    rows = run(daily_target=20)
    for r in rows:
        print(r)
