"""市场估值 + 成交概率模型

数据来源：域名投资行业经验值（NameBio 历史成交、Sedo 年度报告、GoDaddy Auctions）。
不是精准数字，是数量级估算 — 用于策略空间分析和"是否值得买"决策。

estimate(domain_record) → {
    expected_price_usd:  期望成交价（中位数）
    sale_prob_yearly:    年化成交概率
    expected_annual_revenue: P × V（年化期望收入）
    hold_years_to_break_even: 收回 $10 注册成本所需期望年数
}
"""
from __future__ import annotations
from agents import valuation


# 长度 → .com 基础价中位数（USD）
# 数据来源：NameBio 历史成交中位数（2022-2024），偏保守。
# 注：这是"AI 组合词"价位，不是"纯单词"。纯单词 .com 价位高 5-10 倍，但 AI 拿不到。
LENGTH_BASE_COM = {
    4: 800,    # 4 字符组合（非单词）
    5: 200,
    6: 120,
    7: 80,
    8: 60,
    9: 40,
    10: 30,
    11: 20,
    12: 15,
}

# TLD 相对 .com 的折扣（NameBio 历史数据）
TLD_FACTOR = {
    "com": 1.00,
    "ai": 0.55,
    "io": 0.30,
    "co": 0.18,
    "app": 0.12,
    "dev": 0.10,
    "xyz": 0.04,
}

# 字典词/行业词加成（叠加后封顶 ×3）
# AI 生成的"组合词"不是真字典词，加成应远低于真单词
DICT_MULTIPLIER = 1.5
KEYWORD_MULTIPLIER = 1.3
DOUBLE_HIT_MULTIPLIER = 2.0  # 字典+行业双命中

# 年化成交概率基础值（按长度）
# Sedo / Afternic 行业平均：投资型域名 2-5% 年成交率
BASE_SALE_PROB = {
    4: 0.08,
    5: 0.05,
    6: 0.04,
    7: 0.03,
    8: 0.025,
    9: 0.02,
    10: 0.015,
    11: 0.01,
    12: 0.008,
}

# 销售平台佣金（实际到手要扣）
PLATFORM_FEE = 0.15


def estimate(record: dict) -> dict:
    """record 至少要有 domain。可选：score / commercial_signal / breakdown"""
    domain = record["domain"]
    name, _, tld = domain.lower().rpartition(".")
    n = len(name)

    # 1) 基础价
    base = LENGTH_BASE_COM.get(min(max(n, 4), 12), 50)

    tld_factor = TLD_FACTOR.get(tld, 0.05)
    price = base * tld_factor

    # 2) 字典/行业词加成 — 区分"真单词命中"和"子串命中"
    s = record.get("breakdown") or valuation.score(domain)["breakdown"]
    dict_score = s.get("dictionary", 0)
    keyword_score = s.get("keyword", 0)
    has_real_dict = dict_score >= 15  # 完全等于字典词（pay.com 这种）
    has_substr_dict = 0 < dict_score < 15  # 子串包含字典词
    has_keyword = keyword_score > 0

    if has_real_dict:
        price *= 5.0  # 真字典词 .com 行业溢价巨大
    elif has_substr_dict and has_keyword:
        price *= DOUBLE_HIT_MULTIPLIER
    elif has_substr_dict:
        price *= DICT_MULTIPLIER
    elif has_keyword:
        price *= KEYWORD_MULTIPLIER
    else:
        # 纯随机字母（ultra_short_brand 但无字典/关键词命中）— 市场价低
        price *= 0.25

    # 3) 惩罚
    if s.get("penalty", 0) < 0:
        price *= 0.4

    # 4) 年化成交概率
    base_prob = BASE_SALE_PROB.get(min(max(n, 4), 12), 0.005)
    prob = base_prob * tld_factor
    if has_real_dict:
        prob *= 2.0
    elif has_substr_dict and has_keyword:
        prob *= 1.5
    elif has_substr_dict:
        prob *= 1.3
    elif has_keyword:
        prob *= 1.1
    else:
        prob *= 0.5  # 无意义随机字母极少有人买
    prob = min(prob, 0.20)

    # 5) 可获得性折扣 — AI 生成的 "好域名" 大多已被注册
    #    短的更难拿（市场已经被职业 domainer 扫了几十年）
    obtainability = {
        4: 0.005, 5: 0.05, 6: 0.15, 7: 0.30, 8: 0.50,
        9: 0.65, 10: 0.75, 11: 0.85, 12: 0.90,
    }.get(n, 0.5)

    # 6) 扣平台佣金
    net_price = price * (1 - PLATFORM_FEE)
    expected_annual = prob * net_price
    cost = 10

    return {
        "domain": domain,
        "expected_price_usd": round(price, 2),
        "expected_net_price_usd": round(net_price, 2),
        "sale_prob_yearly": round(prob, 4),
        "obtainability": round(obtainability, 3),  # 可获得性概率
        "expected_annual_revenue_usd": round(expected_annual, 2),
        "annual_roi_pct": round((expected_annual - cost) / cost * 100, 1) if cost else None,
        "break_even_years": round(cost / expected_annual, 2) if expected_annual > 0 else None,
        "is_profitable": expected_annual > cost,
    }
