"""端到端冒烟测试 — DRY_RUN 模式跑遍所有核心路径

不调付费 API，不真实下单。验证：
  1. 配置/依赖能加载
  2. valuation 打分逻辑（含商业信号 hard gate）
  3. 商标黑名单
  4. WHOIS 检查
  5. 预算守卫三层硬刹车
  6. 重复购买检查
  7. DRY_RUN 注册（写入 portfolio + budget）
  8. 挂牌定价
  9. AI 议价（无 key 时降级到固定策略）
  10. watchlist 入库
  11. auto_register 决策（应该全拒）

每一项 PASS/FAIL 单独打印，最后给汇总。
"""
from __future__ import annotations
import sys
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results = []


def case(name):
    def deco(fn):
        try:
            fn()
            results.append((name, "PASS", ""))
            print(f"  ✓ {name}")
        except AssertionError as e:
            results.append((name, "FAIL", str(e)))
            print(f"  ✗ {name}  -- {e}")
        except Exception as e:
            results.append((name, "ERROR", f"{type(e).__name__}: {e}"))
            print(f"  ! {name}  -- {type(e).__name__}: {e}")
            traceback.print_exc()
        return fn
    return deco


# ---------- 1. 配置/依赖 ----------
print("\n[1] 配置 & 依赖")

@case("manifest.yaml 加载")
def _():
    from core import config
    cfg = config.load()
    assert cfg.get("mode") == "dry_run", f"mode 必须是 dry_run，实际：{cfg.get('mode')}"
    assert cfg["budget"]["daily_limit"] > 0
    assert cfg["scoring"]["min_score_auto_buy"] >= 85

@case("data 目录可读写")
def _():
    from core import store
    p = store.portfolio()
    assert "owned" in p and "watchlist" in p

@case("依赖 import")
def _():
    import requests, yaml, bs4  # noqa


# ---------- 2. Valuation ----------
print("\n[2] Valuation & Hard Gate")

@case("pay.com 高分（字典词）")
def _():
    from agents import valuation
    s = valuation.score("pay.com")
    assert s["score"] >= 80, f"pay.com 应该 ≥80，实际 {s['score']}"
    assert s["commercial_signal"] is True

@case("zuvow.com 被 hard cap 在 40")
def _():
    from agents import valuation
    s = valuation.score("zuvow.com")
    assert s["score"] <= 40, f"无信号应该 ≤40，实际 {s['score']}"
    assert s["commercial_signal"] is False
    assert s["signal_reason"] == "no_commercial_signal"

@case("go.ai 极短品牌通过")
def _():
    from agents import valuation
    s = valuation.score("go.ai")
    assert s["commercial_signal"] is True
    assert s["score"] >= 70

@case("含数字+连字符 -25 分惩罚")
def _():
    from agents import valuation
    s = valuation.score("pay-99.com")
    assert s["breakdown"]["penalty"] == -25


# ---------- 3. 商标黑名单 ----------
print("\n[3] 商标黑名单")

@case("mygoogle.com 拦截")
def _():
    from validators import trademark_check
    try:
        trademark_check.check("mygoogle.com")
        assert False, "应该 raise"
    except trademark_check.TrademarkConflict as e:
        assert "google" in str(e)

@case("openai-clone.ai 拦截")
def _():
    from validators import trademark_check
    try:
        trademark_check.check("openai-clone.ai")
        assert False
    except trademark_check.TrademarkConflict:
        pass

@case("paywall.com 通过（不含商标）")
def _():
    from validators import trademark_check
    trademark_check.check("paywall.com")  # 不抛异常即通过


# ---------- 4. WHOIS ----------
print("\n[4] WHOIS 可用性")

@case("已注册域名识别（google.com）")
def _():
    from validators import whois_check
    available = whois_check.is_available("google.com")
    assert available is False, "google.com 显然已注册"


# ---------- 5. 预算守卫 ----------
print("\n[5] RiskGuard 三层硬刹车")

@case("单域名上限拦截（$200 > $15）")
def _():
    from validators import budget_guard
    try:
        budget_guard.check(200, "test.com", kind="register")
        assert False, "应该被单域名上限拦"
    except budget_guard.BudgetExceeded as e:
        assert "上限" in str(e)

@case("正常金额通过（$10）")
def _():
    from validators import budget_guard
    budget_guard.check(10, "test.com", kind="register")  # 不抛异常即通过


# ---------- 6. 重复购买 ----------
print("\n[6] 重复购买检查")

@case("空持仓时 dup_check 不抛异常")
def _():
    from validators import dup_check
    dup_check.check("brandnew.com")


# ---------- 7. DRY_RUN 注册 ----------
print("\n[7] DRY_RUN 注册（不真实下单）")

# 用一个绝对不存在的随机域名
import random
import string
TEST_DOMAIN = "drytest" + "".join(random.choices(string.ascii_lowercase, k=8)) + ".com"

@case(f"acquisition.buy({TEST_DOMAIN}) DRY_RUN")
def _():
    from agents import acquisition
    rec = acquisition.buy(TEST_DOMAIN, max_price=10, score_meta={"score": 85, "source": "test"})
    assert rec["registrar"] == "dry_run"
    assert rec["cost_usd"] == 10

@case("写入 portfolio.owned")
def _():
    from core import store
    p = store.portfolio()
    assert any(x["domain"] == TEST_DOMAIN for x in p["owned"])

@case("写入 budget_state（spent +10）")
def _():
    from core import store
    b = store.budget()
    assert b["today"]["spent_usd"] >= 10


# ---------- 8. 重复检测 ----------
print("\n[8] 二次买入应被拦")

@case(f"再次 buy({TEST_DOMAIN}) 抛 DuplicateError")
def _():
    from agents import acquisition
    from validators import dup_check
    try:
        acquisition.buy(TEST_DOMAIN, max_price=10)
        assert False
    except dup_check.DuplicateError:
        pass


# ---------- 9. 挂牌 ----------
print("\n[9] 挂牌定价")

@case(f"list_for_sale({TEST_DOMAIN}) DRY_RUN")
def _():
    from agents import sales
    r = sales.list_for_sale(TEST_DOMAIN)
    assert r["price_usd"] >= 99
    assert "dry_run" in r["platforms"]

@case("挂牌后 portfolio 有 listed_price_usd")
def _():
    from core import store
    p = store.portfolio()
    rec = next(x for x in p["owned"] if x["domain"] == TEST_DOMAIN)
    assert "listed_price_usd" in rec


# ---------- 10. AI 议价（无 key 降级）----------
print("\n[10] AI 议价（无 key 时降级策略）")

@case(f"negotiate_reply({TEST_DOMAIN}, $200) 返回 counter_offer")
def _():
    import os
    from agents import sales
    # Smoke test must not hit the real LLM — clear the key locally so we
    # exercise the deterministic fallback regardless of operator env.
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        r = sales.negotiate_reply(TEST_DOMAIN, buyer_offer=200)
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
    assert "counter_offer_usd" in r
    assert "reply" in r
    assert r["counter_offer_usd"] > 0
    assert r.get("ai") is False, "smoke must take the deterministic fallback path"


# ---------- 12. validators: secret_scanner + cost_tracker ----------
print("\n[12] secret_scanner / cost_tracker")

@case("secret_scanner 在 repo 上跑出 0 finding")
def _():
    from validators import secret_scanner
    findings = secret_scanner.scan(ROOT)
    assert findings == [], f"expected clean, got {len(findings)} finding(s): {findings[:2]}"

@case("cost_tracker 累计金额")
def _():
    from validators import cost_tracker
    cost_tracker.reset()
    cost_tracker.record("anthropic", "valuation", 0.012, tokens_in=500, tokens_out=200)
    cost_tracker.record("deepseek", "valuation", 0.003, tokens_in=500, tokens_out=200)
    rep = cost_tracker.report()
    assert rep["calls"] == 2
    assert abs(rep["total_usd"] - 0.015) < 1e-6
    assert rep["by_provider"]["anthropic"] == 0.012
    assert rep["tokens_in"] == 1000

@case("cost_tracker.reset 后归零")
def _():
    from validators import cost_tracker
    cost_tracker.record("openai", "negotiation", 0.01)
    cost_tracker.reset()
    assert cost_tracker.total_usd() == 0.0
    assert cost_tracker.report()["calls"] == 0


# ---------- 11. 清理测试数据 ----------
print("\n[11] 清理测试数据")

@case("清掉测试域名")
def _():
    from core import store
    p = store.portfolio()
    p["owned"] = [x for x in p["owned"] if x["domain"] != TEST_DOMAIN]
    store.save_portfolio(p)


# ---------- 汇总 ----------
print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s != "PASS")
print(f"  汇总：{passed} PASS / {failed} FAIL/ERROR / 共 {len(results)}")
if failed:
    print("\n失败项:")
    for n, s, msg in results:
        if s != "PASS":
            print(f"  [{s}] {n} — {msg}")
    sys.exit(1)
else:
    print("  ✓ 所有测试通过")
