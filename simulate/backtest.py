"""回测仿真器 — 跑一次告诉你"按现有策略实际能赚多少"

流程：
  1) 大批量生成 + 评分（不调 WHOIS，离线纯打分）
  2) 商业信号过滤
  3) 按 score 降序，选 top N 标记 "selected"（这是劳林要看的"被选中的域名"）
  4) 用 market_model 给每个 selected 算期望价 + 年化成交率 + 年化期望收入
  5) 模拟 N 年持有期，蒙特卡洛 1000 次跑成交
  6) 输出报告：选了哪些 / 总投入 / 期望年收入 / 持有 1/2/3 年净利润 / ROI

报告分两块：
  A. Selected 名单（带打分 + 期望价 + 期望收入）
  B. 策略对比：不同 score 门槛下的 ROI 表
"""
from __future__ import annotations
import json
import random
import statistics
from datetime import datetime
from pathlib import Path

from core import config
from agents import discovery_aigen, valuation
from validators import trademark_check
from . import market_model


def generate_pool(target: int = 500) -> list[dict]:
    """离线生成大批候选 — 不调 WHOIS（仿真不需要真可注册）"""
    cfg = config.load()
    tlds = ["com", "ai", "io"]
    raw = discovery_aigen.generate(target, ["dictionary_combo", "cvcvcv", "cvcv", "brand_short"], tlds)
    out = []
    for r in raw:
        if trademark_check.find_conflict(r["domain"]):
            continue
        s = valuation.score(r["domain"])
        if not s.get("commercial_signal"):
            continue
        r.update(s)
        out.append(r)
    return out


def select_top(pool: list[dict], n: int = 30, min_score: int = 70) -> list[dict]:
    """按 score 降序取 top n（且 ≥ min_score）"""
    qualified = [x for x in pool if x["score"] >= min_score]
    qualified.sort(key=lambda x: -x["score"])
    return qualified[:n]


def attach_market(selected: list[dict]) -> list[dict]:
    """给 selected 加上 market_model 估算"""
    for s in selected:
        s["market"] = market_model.estimate(s)
    return selected


def monte_carlo(selected: list[dict], years: int = 3, runs: int = 1000, register_cost: float = 10.0) -> dict:
    """蒙特卡洛模拟 N 年持有，每个域名每年按 sale_prob_yearly 抛硬币

    持有过程中每年要续费 (cost = register_cost)。
    成交后停止持有（不再续费）。
    """
    n = len(selected)

    revenues_per_run = []
    sales_per_run = []
    holding_costs_per_run = []
    actual_buys_per_run = []

    for _ in range(runs):
        # Step 1: 可获得性 — 先抛硬币看真能注册到几个
        actual_owned = []
        for item in selected:
            o = item["market"].get("obtainability", 0.5)
            if random.random() < o:
                actual_owned.append(item)
        actual_buys_per_run.append(len(actual_owned))

        revenue = 0.0
        sales = 0
        holding_cost = 0
        # 每个 actual_owned 一个 status
        statuses = ["holding"] * len(actual_owned)

        for year in range(1, years + 1):
            # 续费（仅尚未售出的）
            for i, st in enumerate(statuses):
                if st == "holding" and year > 1:
                    holding_cost += register_cost

            for i, item in enumerate(actual_owned):
                if statuses[i] != "holding":
                    continue
                p = item["market"]["sale_prob_yearly"]
                if random.random() < p:
                    base_net = item["market"].get(
                        "expected_net_price_usd",
                        item["market"]["expected_price_usd"] * 0.85,
                    )
                    actual = base_net * random.uniform(0.6, 1.4)
                    revenue += actual
                    statuses[i] = "sold"
                    sales += 1

        revenues_per_run.append(revenue)
        sales_per_run.append(sales)
        holding_costs_per_run.append(holding_cost + len(actual_owned) * register_cost)

    # 总投入按平均"实际买到的数量"
    total_cost_buy = statistics.mean(actual_buys_per_run) * register_cost

    revenues_per_run.sort()
    avg_actual_buys = statistics.mean(actual_buys_per_run)
    avg_holding_cost = statistics.mean(holding_costs_per_run)
    avg_revenue = statistics.mean(revenues_per_run)
    total_cost = avg_holding_cost  # 已含买入+续费
    return {
        "years_simulated": years,
        "runs": runs,
        "selected_targeted": n,
        "actual_buys_avg": round(avg_actual_buys, 2),
        "obtain_rate_pct": round(avg_actual_buys / n * 100, 1) if n else 0,
        "register_cost_total": round(total_cost_buy, 2),
        "holding_cost_avg": round(avg_holding_cost, 2),
        "total_cost_avg": round(total_cost, 2),
        "revenue_avg": round(avg_revenue, 2),
        "revenue_median": round(statistics.median(revenues_per_run), 2),
        "revenue_p10": round(revenues_per_run[int(runs * 0.1)], 2),
        "revenue_p90": round(revenues_per_run[int(runs * 0.9)], 2),
        "net_profit_avg": round(avg_revenue - total_cost, 2),
        "sales_avg": round(statistics.mean(sales_per_run), 2),
        "sales_pct_avg": round(statistics.mean(sales_per_run) / avg_actual_buys * 100, 1) if avg_actual_buys else 0,
        "roi_pct": round((avg_revenue - total_cost) / total_cost * 100, 1) if total_cost > 0 else 0,
    }


def strategy_grid(pool: list[dict], thresholds: list[int] = (70, 75, 80, 85, 88, 90), top_n: int = 30, years: int = 3) -> list[dict]:
    """策略对比：不同 min_score 门槛下选 top_n，跑蒙卡，给 ROI 表"""
    rows = []
    for th in thresholds:
        sel = select_top(pool, n=top_n, min_score=th)
        if not sel:
            rows.append({"min_score": th, "n": 0, "skipped": True})
            continue
        attach_market(sel)
        sim = monte_carlo(sel, years=years, runs=300)
        avg_ann = statistics.mean(s["market"]["expected_annual_revenue_usd"] for s in sel)
        rows.append({
            "min_score": th,
            "n": len(sel),
            "avg_score": round(statistics.mean(s["score"] for s in sel), 1),
            "avg_expected_annual_per_domain": round(avg_ann, 2),
            "total_cost": sim["total_cost_avg"],
            "revenue_avg": sim["revenue_avg"],
            "net_profit_avg": sim["net_profit_avg"],
            "roi_pct": sim["roi_pct"],
            "sales_pct": sim["sales_pct_avg"],
        })
    return rows


def find_optimal(pool: list[dict], top_n_options=(10, 20, 30, 50), threshold_options=(70, 80, 88), years: int = 3) -> dict:
    """搜最优 (min_score × top_n) 组合 — 按"绝对净利润"排"""
    best = None
    grid = []
    for th in threshold_options:
        for n in top_n_options:
            sel = select_top(pool, n=n, min_score=th)
            if not sel:
                continue
            attach_market(sel)
            sim = monte_carlo(sel, years=years, runs=300)
            row = {
                "min_score": th,
                "top_n": n,
                "actual_n": len(sel),
                "total_cost": sim["total_cost_avg"],
                "revenue_avg": sim["revenue_avg"],
                "net_profit_avg": sim["net_profit_avg"],
                "roi_pct": sim["roi_pct"],
            }
            grid.append(row)
            if best is None or row["net_profit_avg"] > best["net_profit_avg"]:
                best = row
    return {"best": best, "grid": grid}


def run(pool_size: int = 1000, top_n: int = 30, min_score: int = 80, years: int = 3, runs: int = 1000) -> dict:
    """完整一轮仿真"""
    started = datetime.utcnow()
    pool = generate_pool(target=pool_size)
    selected = select_top(pool, n=top_n, min_score=min_score)
    attach_market(selected)
    sim = monte_carlo(selected, years=years, runs=runs)
    grid = strategy_grid(pool, thresholds=[70, 80, 85, 88, 90], top_n=top_n, years=years)
    optimal = find_optimal(pool, years=years)

    return {
        "ts": started.isoformat(),
        "pool_size": len(pool),
        "selected_count": len(selected),
        "params": {"top_n": top_n, "min_score": min_score, "years": years, "runs": runs},
        "selected": selected,
        "simulation": sim,
        "strategy_grid": grid,
        "optimal": optimal,
        "duration_sec": (datetime.utcnow() - started).total_seconds(),
    }


def save_selected(selected: list[dict], path: str | Path = None) -> Path:
    """把选中的域名标记到 data/selected.json"""
    p = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "selected.json"
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "count": len(selected),
        "items": [
            {
                "domain": s["domain"],
                "score": s["score"],
                "signal_reason": s.get("signal_reason"),
                "expected_price_usd": s["market"]["expected_price_usd"],
                "sale_prob_yearly": s["market"]["sale_prob_yearly"],
                "expected_annual_usd": s["market"]["expected_annual_revenue_usd"],
                "is_profitable": s["market"]["is_profitable"],
            }
            for s in selected
        ],
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return p
