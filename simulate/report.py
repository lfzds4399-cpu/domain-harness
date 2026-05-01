"""把 backtest.run() 结果格式化成人类可读报告"""
from __future__ import annotations


def render(r: dict) -> str:
    lines = []
    lines.append("\n" + "=" * 72)
    lines.append("  domain-harness 仿真回测报告")
    lines.append("=" * 72)
    lines.append(f"  生成时间    {r['ts']}")
    lines.append(f"  参数        top_n={r['params']['top_n']}  min_score={r['params']['min_score']}  "
                 f"持有期={r['params']['years']}年  蒙卡次数={r['params']['runs']}")
    lines.append(f"  候选池      {r['pool_size']} 条（已过商业信号过滤+商标黑名单）")
    lines.append(f"  选中标记    {r['selected_count']} 条")
    lines.append(f"  耗时        {r['duration_sec']:.2f}s")

    # ===== 选中名单（前 20 条）=====
    lines.append("\n--- A. 选中标记的域名（按 score 倒序前 20）---")
    lines.append(f"  {'#':<3} {'score':>5} {'domain':<30} {'估价$':>8} {'年成交率':>8} {'可得%':>6} {'年化期望$':>10}  signal")
    for i, s in enumerate(r["selected"][:20], 1):
        m = s["market"]
        lines.append(
            f"  {i:<3} {s['score']:>5} {s['domain']:<30} "
            f"{m['expected_price_usd']:>8.0f} {m['sale_prob_yearly']*100:>7.1f}% "
            f"{m.get('obtainability', 0)*100:>5.1f}% "
            f"{m['expected_annual_revenue_usd']:>10.2f}  {s.get('signal_reason','')}"
        )

    # ===== 整体仿真 =====
    sim = r["simulation"]
    lines.append("\n--- B. 整体仿真（蒙特卡洛 + 可获得性折扣）---")
    lines.append(f"  目标选中   {sim['selected_targeted']} 个")
    lines.append(f"  实际拿到   {sim['actual_buys_avg']} 个（可得率 {sim['obtain_rate_pct']}%）")
    lines.append(f"  总投入     ${sim['total_cost_avg']}（含注册+续费）")
    lines.append(f"  期望收入   ${sim['revenue_avg']}  （中位数 ${sim['revenue_median']}，"
                 f"P10 ${sim['revenue_p10']}，P90 ${sim['revenue_p90']}）")
    lines.append(f"  期望成交   {sim['sales_avg']} 个 / {sim['actual_buys_avg']} 拿到的（成交率 {sim['sales_pct_avg']}%）")
    profit = sim["net_profit_avg"]
    sign = "+" if profit >= 0 else ""
    lines.append(f"  净利润     {sign}${profit}   ROI {sim['roi_pct']}%")

    # ===== 策略对比 =====
    lines.append("\n--- C. 不同 min_score 门槛下的对比 ---")
    lines.append(f"  {'门槛':>5} {'选中':>5} {'均分':>5} {'年/域$':>8} {'总投入$':>8} {'期望收$':>9} "
                 f"{'净利$':>8} {'ROI%':>6} {'成交%':>7}")
    for row in r["strategy_grid"]:
        if row.get("skipped"):
            lines.append(f"  {row['min_score']:>5} {'-':>5}    （无候选）")
            continue
        lines.append(
            f"  {row['min_score']:>5} {row['n']:>5} {row['avg_score']:>5} "
            f"{row['avg_expected_annual_per_domain']:>8.1f} {row['total_cost']:>8.0f} "
            f"{row['revenue_avg']:>9.0f} {row['net_profit_avg']:>+8.0f} "
            f"{row['roi_pct']:>+6.1f} {row['sales_pct']:>6.1f}"
        )

    # ===== 最优策略 =====
    opt = r["optimal"]["best"]
    if opt:
        lines.append("\n--- D. 推荐最优参数（按净利润最大）---")
        lines.append(f"  min_score={opt['min_score']}  top_n={opt['top_n']}  实际选中 {opt['actual_n']} 个")
        lines.append(f"  总投入 ${opt['total_cost']:.0f}  期望收入 ${opt['revenue_avg']:.0f}  "
                     f"净利 ${opt['net_profit_avg']:+.0f}  ROI {opt['roi_pct']:+.1f}%")

    lines.append("\n--- E. 风险与免责 ---")
    lines.append("  • 估价用行业经验中位数，实际成交价高度长尾（多数卖不出，极少数 10x+）")
    lines.append("  • 蒙卡假设事件独立 — 真实市场存在批量市场冷却 / 行业突发热度")
    lines.append("  • 不含 Sedo/Dan 平台佣金（实际 -10~15%）和挂牌广告费")
    lines.append("  • 续费成本按 $10/年计算 — .ai/.io 续费更贵需上调")

    lines.append("=" * 72 + "\n")
    return "\n".join(lines)
