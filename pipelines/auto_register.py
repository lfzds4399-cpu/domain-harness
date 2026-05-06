"""自动注册 pipeline

策略：扫 watchlist，对满足以下条件的候选自动下单：
- 本地 score >= scoring.min_score_auto_buy
- council_score >= 75 且 consensus >= council.min_consensus
- 通过所有 validators

任何一条不满足都跳过。失败的不重试本轮。
DRY_RUN 时全部走 acquisition.buy 的 dry_run 分支。
"""
from __future__ import annotations
from datetime import datetime

from core import config, store, log
from agents import acquisition
from validators import budget_guard


def run(dry_only: bool = False) -> dict:
    cfg = config.load()
    started = datetime.utcnow()
    log.info("===== auto_register 开始 =====", mode=cfg.get("mode"))

    p = store.portfolio()
    watchlist = p.get("watchlist", [])
    if not watchlist:
        log.info("watchlist 为空，跳过")
        return {"bought": [], "skipped": 0, "errors": []}

    min_auto = cfg["scoring"].get("min_score_auto_buy", 88)
    require_signal = cfg["scoring"].get("require_commercial_signal", True)
    council_min = cfg["scoring"].get("council_min_per_provider", 70)
    council_cfg = cfg.get("council", {})
    min_consensus = council_cfg.get("min_consensus", 0.7)
    require_both = council_cfg.get("require_both_providers", True)
    per_cap = cfg["budget"].get("per_domain_register", 15)

    bought = []
    errors = []
    skipped = 0
    skip_reasons = {}

    def _skip(reason: str, domain: str):
        nonlocal skipped
        skipped += 1
        skip_reasons.setdefault(reason, []).append(domain)

    # 优先级：score 倒序
    candidates = sorted(watchlist, key=lambda x: -(x.get("score") or 0))

    for c in candidates:
        domain = c["domain"]
        score = c.get("score") or 0
        consensus = c.get("consensus")
        providers = c.get("providers") or {}

        # Gate 0: 商业信号 hard gate
        if require_signal and not c.get("commercial_signal", False):
            _skip("no_commercial_signal", domain)
            continue

        # Gate 1: 本地分门槛
        if score < min_auto:
            _skip(f"score<{min_auto}", domain)
            continue

        # Gate 2: AI Council 必须存在
        if not providers:
            _skip("no_council_verdict", domain)
            continue

        # Gate 3: 必须双 provider（防单家 AI 偏见）
        if require_both and len(providers) < 2:
            _skip("council_single_provider", domain)
            continue

        # Gate 4: 每个 provider 都要 ≥ council_min
        if any(p.get("score", 0) < council_min for p in providers.values()):
            _skip(f"provider<{council_min}", domain)
            continue

        # Gate 5: 共识度
        if consensus is not None and consensus < min_consensus:
            _skip(f"consensus<{min_consensus}", domain)
            continue

        # 预算先 dry-check（不修改状态）
        try:
            budget_guard.check(per_cap, domain, kind="register")
        except budget_guard.BudgetExceeded as e:
            log.warn("预算停止本轮", err=str(e))
            break

        if dry_only:
            log.dry("--dry-only 跳过实际下单", domain=domain, score=score)
            continue

        try:
            rec = acquisition.buy(domain, max_price=per_cap, score_meta=c)
            bought.append(rec)
            # 从 watchlist 移除
            p["watchlist"] = [x for x in p["watchlist"] if x["domain"] != domain]
            store.save_portfolio(p)
        except Exception as e:
            errors.append({"domain": domain, "err": str(e)})
            log.warn("注册失败", domain=domain, err=str(e))

    summary = {
        "ts": started.isoformat(),
        "bought": bought,
        "skipped": skipped,
        "skip_reasons": {k: len(v) for k, v in skip_reasons.items()},
        "skip_detail": skip_reasons,
        "errors": errors,
        "duration_sec": (datetime.utcnow() - started).total_seconds(),
    }
    log.ok("===== auto_register 完成 =====",
           bought=len(bought), skipped=skipped, errors=len(errors),
           reasons=summary["skip_reasons"])
    return summary


if __name__ == "__main__":
    import json
    s = run()
    print(json.dumps(s, indent=2, default=str))
