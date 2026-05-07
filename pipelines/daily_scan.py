"""每日扫描 pipeline

流程：
1) 多源 Discovery（AI 生成 + Expired 抓榜）
2) 本地多维打分
3) 高分候选喂 AI Council 复评
4) 入库 watchlist（high score 但未注册）+ scan_history
5) 不下单（auto_register pipeline 才下单）
"""
from __future__ import annotations
from datetime import datetime

from core import config, store, log
from agents import discovery_aigen, discovery_expired, valuation, valuation_council
from validators import dup_check, trademark_check


def run(daily_target: int | None = None) -> dict:
    cfg = config.load()
    started = datetime.utcnow()
    log.info("===== daily_scan 开始 =====", mode=cfg.get("mode"))

    # 1) Discovery
    aigen = discovery_aigen.run(daily_target=daily_target)
    expired = discovery_expired.run(limit=200)
    all_candidates = aigen + expired
    log.info(f"Discovery total {len(all_candidates)}", aigen=len(aigen), expired=len(expired))

    # 去重 + 过滤已持有/黑名单/商标冲突
    seen = set()
    filtered = []
    tm_blocked = 0
    for c in all_candidates:
        d = c["domain"].lower()
        if d in seen:
            continue
        seen.add(d)
        try:
            dup_check.check(d)
            trademark_check.check(d)
            filtered.append(c)
        except trademark_check.TrademarkConflict as e:
            tm_blocked += 1
            log.warn("商标拦截", err=str(e))
        except Exception:
            continue
    log.info(f"过滤后 {len(filtered)} 条", trademark_blocked=tm_blocked)

    # 2) 本地估值
    scored = valuation.score_many(filtered)
    scored.sort(key=lambda x: -x["score"])

    # 3) AI Council 复评（仅高分）
    threshold = cfg["scoring"].get("min_score_council", 75)
    scored = valuation_council.evaluate_batch(scored, threshold=threshold)

    # 4) 入 watchlist — 必须满足：分数门槛 AND commercial_signal
    min_watch = cfg["scoring"].get("min_score_watchlist", 70)
    require_signal = cfg["scoring"].get("require_commercial_signal", True)
    watch_added = 0
    rejected_no_signal = 0
    for s in scored:
        if require_signal and not s.get("commercial_signal", False):
            rejected_no_signal += 1
            continue
        if s["score"] >= min_watch:
            store.add_watchlist({
                "domain": s["domain"],
                "score": s["score"],
                "council_score": s.get("council_score"),
                "consensus": s.get("consensus"),
                "providers": s.get("providers"),
                "commercial_signal": s.get("commercial_signal"),
                "signal_reason": s.get("signal_reason"),
                "source": s.get("source"),
                "found_at": started.isoformat(),
                "reason": s.get("breakdown"),
            })
            watch_added += 1

    # 5) 落 scan history
    store.append_scan_log([{
        "ts": started.isoformat(),
        **s,
    } for s in scored])

    summary = {
        "ts": started.isoformat(),
        "total_candidates": len(all_candidates),
        "after_filter": len(filtered),
        "scored": len(scored),
        "rejected_no_commercial_signal": rejected_no_signal,
        "added_to_watchlist": watch_added,
        "top10": scored[:10],
        "duration_sec": (datetime.utcnow() - started).total_seconds(),
    }
    log.ok("===== daily_scan 完成 =====",
           total=summary["total_candidates"],
           watch=summary["added_to_watchlist"],
           rejected_noise=rejected_no_signal,
           dur=f"{summary['duration_sec']:.1f}s")
    return summary


if __name__ == "__main__":
    import json
    s = run(daily_target=20)
    print(json.dumps({k: v for k, v in s.items() if k != "top10"}, indent=2))
    print("\nTop 10:")
    for t in s["top10"]:
        print(f"  {t['score']:>3} | {t['domain']:<30} | {t.get('source')}")
