"""domain-harness CLI

子命令：
  status                   预算/持仓/watchlist 总览
  scan [--target N]        跑一次 daily_scan
  appraise <domain>        单域名估值（本地+council 可选）
  buy <domain> [--price]   手动注册下单（带二次确认 except --yes）
  list-for-sale <domain>   挂牌
  portfolio                列出所有持仓
  watchlist [--top N]      列出 watchlist 前 N
  selected                 显示上次仿真标记的选中域名
  review                   跑 portfolio_review
  auto-register [--dry]    跑 auto_register pipeline
  budget                   显示预算余额
  simulate [--pool/--top]  离线回测仿真（选中+蒙卡 ROI）
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core import config, store, log
from validators import budget_guard, dup_check, whois_check
from agents import valuation, valuation_council, acquisition, sales
from pipelines import daily_scan, auto_register, portfolio_review
from simulate import backtest, report


def cmd_status(args):
    cfg = config.load()
    b = budget_guard.remaining()
    p = store.portfolio()
    owned = p.get("owned", [])
    listed = [x for x in owned if "listed_price_usd" in x]
    watch = p.get("watchlist", [])

    print("\n=== domain-harness status ===")
    print(f"mode:        {cfg.get('mode')}")
    print(f"daily 余额:  ${b['daily_remaining']}")
    print(f"monthly 余额:${b['monthly_remaining']}")
    print(f"持仓:        {len(owned)} 个域名")
    print(f"已挂牌:      {len(listed)}")
    print(f"watchlist:   {len(watch)}")

    if owned:
        print("\n— 持仓 (前 10) —")
        for r in owned[:10]:
            tag = f"挂牌 ${r.get('listed_price_usd')}" if "listed_price_usd" in r else "未挂牌"
            print(f"  {r['domain']:<30} score={r.get('score')} {tag}")

    if watch:
        top = sorted(watch, key=lambda x: -(x.get("score") or 0))[:5]
        print("\n— watchlist Top 5 —")
        for w in top:
            print(f"  {w['score']:>3} | {w['domain']:<30} | {w.get('source')}")


def cmd_scan(args):
    s = daily_scan.run(daily_target=args.target)
    print(f"\nscan: 发现 {s['total_candidates']} → 入选 {s['added_to_watchlist']} → 用时 {s['duration_sec']:.1f}s")
    print("\nTop 10:")
    for t in s["top10"]:
        c = t.get("council_score")
        suffix = f" council={c}" if c else ""
        print(f"  {t['score']:>3} | {t['domain']:<30}{suffix}")


def cmd_appraise(args):
    domain = args.domain
    s = valuation.score(domain)
    print(json.dumps(s, indent=2, ensure_ascii=False))
    if args.council:
        v = valuation_council.evaluate(s)
        print("\n--- AI Council ---")
        print(json.dumps(v, indent=2, ensure_ascii=False))


def cmd_buy(args):
    domain = args.domain.lower()
    s = valuation.score(domain)
    print(f"score: {s['score']}  breakdown: {s['breakdown']}")

    try:
        whois_check.check(domain)
    except whois_check.NotAvailable as e:
        log.err(str(e))
        return

    try:
        dup_check.check(domain)
    except dup_check.DuplicateError as e:
        log.err(str(e))
        return

    price = args.price or config.load()["budget"]["per_domain_register"]
    if not args.yes:
        ans = input(f"确认以 max ${price} 注册 {domain}? (yes/no): ").strip().lower()
        if ans != "yes":
            print("取消")
            return
    try:
        rec = acquisition.buy(domain, max_price=price, score_meta=s)
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    except Exception as e:
        log.err(f"注册失败：{e}")


def cmd_list_for_sale(args):
    try:
        r = sales.list_for_sale(args.domain, price=args.price)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
    except Exception as e:
        log.err(str(e))


def cmd_portfolio(args):
    p = store.portfolio()
    for r in p.get("owned", []):
        print(json.dumps(r, ensure_ascii=False))


def cmd_watchlist(args):
    p = store.portfolio()
    watch = sorted(p.get("watchlist", []), key=lambda x: -(x.get("score") or 0))
    for w in watch[:args.top]:
        c = w.get("council_score")
        suffix = f" council={c}" if c else ""
        print(f"  {w.get('score'):>3} | {w['domain']:<30}{suffix} | {w.get('source')}")


def cmd_review(args):
    s = portfolio_review.run()
    print(json.dumps(s, indent=2, ensure_ascii=False, default=str))


def cmd_auto_register(args):
    s = auto_register.run(dry_only=args.dry)
    print(f"bought={len(s['bought'])} skipped={s['skipped']} errors={len(s['errors'])}")
    for r in s["bought"]:
        print(f"  ✓ {r['domain']} via {r['registrar']} ${r['cost_usd']}")
    for e in s["errors"]:
        print(f"  ✗ {e['domain']}: {e['err']}")


def cmd_budget(args):
    print(json.dumps(budget_guard.remaining(), indent=2))


def cmd_selected(args):
    """显示上一次仿真标记的选中域名"""
    p = Path(__file__).resolve().parent / "data" / "selected.json"
    if not p.exists():
        print("还没跑过 simulate --save。先 `python cli.py simulate --save` 标记。")
        return
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    print(f"\n标记于 {data['ts']}  共 {data['count']} 个")
    print(f"  {'#':<3} {'domain':<28} {'score':>5} {'估价$':>7} {'年成交':>7} {'年化期望$':>10} signal")
    for i, item in enumerate(data["items"], 1):
        flag = "✓" if item["is_profitable"] else " "
        print(f"  {i:<3} {item['domain']:<28} {item['score']:>5} "
              f"{item['expected_price_usd']:>7.0f} {item['sale_prob_yearly']*100:>6.1f}% "
              f"{item['expected_annual_usd']:>10.2f} {flag} {item.get('signal_reason','')}")


def cmd_simulate(args):
    """跑回测仿真 — 离线评估当前策略的预期 ROI"""
    log.info("启动仿真",
             pool=args.pool, top_n=args.top, min_score=args.min_score,
             years=args.years, runs=args.runs)
    r = backtest.run(
        pool_size=args.pool,
        top_n=args.top,
        min_score=args.min_score,
        years=args.years,
        runs=args.runs,
    )
    print(report.render(r))
    if args.save:
        path = backtest.save_selected(r["selected"])
        print(f"\n选中名单已保存到 {path}")
        out_path = path.parent / f"backtest_{r['ts'][:10]}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            # 选中里 market 字段含 numpy-ish 数据，序列化前清理
            json.dump({k: v for k, v in r.items() if k != "selected"} | {
                "selected": [{**{kk: vv for kk, vv in s.items() if kk != "breakdown"}} for s in r["selected"]]
            }, f, ensure_ascii=False, indent=2, default=str)
        print(f"完整报告已保存到 {out_path}")


def build_parser():
    p = argparse.ArgumentParser(prog="domain-harness")
    p.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="quiet console (file logs unaffected) — for CC sessions / cron",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status").set_defaults(fn=cmd_status)

    s = sub.add_parser("scan")
    s.add_argument("--target", type=int, default=None, help="AI 生成候选数")
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("appraise")
    s.add_argument("domain")
    s.add_argument("--council", action="store_true")
    s.set_defaults(fn=cmd_appraise)

    s = sub.add_parser("buy")
    s.add_argument("domain")
    s.add_argument("--price", type=float, default=None)
    s.add_argument("--yes", action="store_true", help="跳过确认")
    s.set_defaults(fn=cmd_buy)

    s = sub.add_parser("list-for-sale")
    s.add_argument("domain")
    s.add_argument("--price", type=float, default=None)
    s.set_defaults(fn=cmd_list_for_sale)

    sub.add_parser("portfolio").set_defaults(fn=cmd_portfolio)

    s = sub.add_parser("watchlist")
    s.add_argument("--top", type=int, default=20)
    s.set_defaults(fn=cmd_watchlist)

    sub.add_parser("review").set_defaults(fn=cmd_review)

    s = sub.add_parser("auto-register")
    s.add_argument("--dry", action="store_true", help="仅打印决策不下单")
    s.set_defaults(fn=cmd_auto_register)

    sub.add_parser("budget").set_defaults(fn=cmd_budget)
    sub.add_parser("selected", help="显示上次仿真标记的选中域名").set_defaults(fn=cmd_selected)

    s = sub.add_parser("simulate", help="离线回测仿真 — 评估策略预期 ROI")
    s.add_argument("--pool", type=int, default=1000, help="生成候选池规模")
    s.add_argument("--top", type=int, default=30, help="选中前 N 名")
    s.add_argument("--min-score", type=int, default=80, help="最低分门槛")
    s.add_argument("--years", type=int, default=3, help="持有期（年）")
    s.add_argument("--runs", type=int, default=1000, help="蒙卡次数")
    s.add_argument("--save", action="store_true", help="保存 selected.json + backtest_xxx.json")
    s.set_defaults(fn=cmd_simulate)

    return p


def main():
    args = build_parser().parse_args()
    if getattr(args, "quiet", False):
        log.set_quiet(True)
    args.fn(args)


if __name__ == "__main__":
    main()
