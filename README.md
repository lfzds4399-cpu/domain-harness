# domain-harness

[![tests](https://github.com/lfzds4399-cpu/domain-harness/actions/workflows/test.yml/badge.svg)](https://github.com/lfzds4399-cpu/domain-harness/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Mode: dry_run by default](https://img.shields.io/badge/mode-dry__run%20by%20default-green.svg)](#configuration)

> 中文版 → [README.zh-CN.md](./README.zh-CN.md) · Docs → [getting-started](./docs/getting-started.md) · [FAQ](./docs/faq.md) · [troubleshooting](./docs/troubleshooting.md)

![domain-harness demo (animated illustration)](./docs/domain-harness-demo.gif)

**Automated domain investing pipeline.** Discover → value → register → list → settle —
with hard budget walls and an AI Council that has to agree before any money moves.

```
discover  ─►  value  ─►  acquire  ─►  list  ─►  negotiate  ─►  settle
   │           │           │           │           │
   AI gen +    local +     multi-     Dan /        AI reply
   expired     AI Council  registrar   Afternic    + counter
   feeds       (Claude     fallback   Sedo
               + DeepSeek)
```

## Why this is different

Most "domain finders" you'll see on GitHub stop at the first stage — they spit out a list of names. The real work is the rest:

- **Two-tier valuation** — local heuristic gates filter ~90% of noise; only the survivors get billed against the AI Council. Saves tokens, raises signal.
- **AI Council** — every shortlisted candidate is scored by **Claude + DeepSeek independently**. *Both* must clear a per-provider threshold before the harness will spend.
- **Hard budget walls** — daily cap, monthly cap, per-domain cap, reserve floor. The buyer literally cannot exceed them; if any one trips, the loop stops.
- **Multi-registrar fallback** — Porkbun → Cloudflare → Namecheap → GoDaddy by priority. If one rejects, the next tries.
- **Trademark blacklist** — built-in list + user blacklist; no `mygoogle.com` accidents.
- **22-case end-to-end smoke** — `tests/e2e_smoke.py` exercises every gate in DRY_RUN mode without touching a wallet. CI runs it on every push.

## Architecture

```mermaid
flowchart LR
    A[discovery_aigen<br/>discovery_expired] --> B[valuation<br/>local heuristic]
    B -->|score >= min| C[valuation_council<br/>Claude + DeepSeek]
    C -->|both pass| D[trademark_check<br/>budget_guard<br/>dup_check<br/>whois_check]
    D -->|all pass| E[acquisition<br/>multi-registrar fallback]
    E --> F[portfolio]
    F --> G[sales<br/>Dan / Afternic / Sedo]
    G --> H[negotiate<br/>AI counter-offer]
    H --> I[settle]
```

## Sample output

```
$ python cli.py status

mode:        dry_run
daily cap:   $50
monthly cap: $1000
holdings:    0 domains
spent:       $0 today, $0 this month
watchlist:   0
```

```
$ python tests/e2e_smoke.py

[1] 配置 import          ✓ 配置加载
[2] valuation 分数边界    ✓ pay.com 高分（字典词）
                         ✓ zuvow.com 受 hard cap 抑 40 分
                         ✓ go.ai 短品牌通过
                         ✓ 长域名+多字符 -25 分惩罚
[3] 商标黑名单           ✓ mygoogle.com 拦截
                         ✓ openai-clone.ai 拦截
                         ✓ paywall.com 通过（非商标）
[4] WHOIS 检查           ✓ 注册过的域名识别（google.com）
[5] 预算守卫硬刹车        ✓ 单域名超过返回拦截（$200 > $15）
                         ✓ 正常金额通过（$10）
[6] 重复购买检查          ✓ 空持仓时 dup_check 不抛异常
[7] DRY_RUN 注册          ✓ acquisition.buy DRY_RUN
                         ✓ 写入 portfolio.owned
                         ✓ 写入 budget_state（spent +10）
[8] 二次买入应被拦        ✓ 再次 buy 抛 DuplicateError
[9] 挂牌定价             ✓ list_for_sale DRY_RUN
                         ✓ 挂牌后 portfolio 有 listed_price_usd
[10] AI 议价（无 key 时降级）  ✓ negotiate_reply 返回 counter_offer
[11] 清理测试数据         ✓ 清掉测试域名

汇总：22 PASS / 0 FAIL/ERROR / 共 22
```

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/<your-username>/domain-harness.git
cd domain-harness
pip install -r requirements.txt
cp .env.example .env       # fill in only what you use
```

## Run

```bash
# Status snapshot (mode, budget, holdings, watchlist)
python cli.py status

# One scan pass (generate candidates → value → push to watchlist)
python cli.py scan --target 30

# Watchlist top N
python cli.py watchlist --top 10

# Single-domain appraisal (with optional AI Council)
python cli.py appraise example.com

# Offline backtest — Monte Carlo over a candidate pool
python cli.py simulate --pool 200 --top 20

# Manual buy with confirmation (DRY_RUN; flip mode in manifest.yaml)
python cli.py buy somedomain.com --price 9.13

# Run end-to-end smoke
python tests/e2e_smoke.py
```

The harness defaults to **`mode: dry_run`** in `manifest.yaml`. Flip to `live` only after you've seeded keys and reviewed the budget block.

## Configuration

`manifest.yaml` is the single source of truth:

| section | what it controls |
|---|---|
| `budget` | daily / monthly / per-domain caps and reserve floor |
| `tld` | whitelist + per-TLD priority weight + blacklist |
| `valuation` | score thresholds, length limits, commercial-signal hard gate |
| `registrars` | enable + per-registrar priority |
| `sources` | AI generation patterns + expired-domain feeds |

Secrets stay in `.env` — see [`.env.example`](./.env.example).

## Architecture (filesystem)

```
domain-harness/
├── manifest.yaml           # all knobs
├── cli.py                  # entrypoint
├── core/                   # config / store / log
├── validators/             # budget_guard / dup_check / whois_check / trademark_check
├── agents/                 # valuation / valuation_council / acquisition / sales
├── pipelines/              # daily_scan / auto_register / portfolio_review
├── simulate/               # backtest + Monte Carlo report
├── tests/                  # e2e_smoke (22 cases, DRY_RUN)
├── data/                   # runtime state (gitignored)
└── logs/                   # daily logs (gitignored)
```

## Disclaimer

Domain investing involves financial risk. This tool will spend real money once `mode: live` and registrar keys are set. Read `manifest.yaml` carefully, keep `dry_run` until you're sure, and start with a tiny daily cap. The author runs no guarantee.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). The bar is: every spend gate must be exercised by a smoke case.

## Sibling projects

Other small, single-author harnesses I publish under [@lfzds4399-cpu](https://github.com/lfzds4399-cpu) — same MIT, same opinionated taste:

| Repo | One line |
|---|---|
| [**ai-council**](https://github.com/lfzds4399-cpu/ai-council) | The multi-voter consensus framework that powers the valuation gate here — extracted, zero-dep, reusable |
| [**voice2ai**](https://github.com/lfzds4399-cpu/voice2ai) | Hands-free dictation for Windows — push-to-talk into VS Code / Cursor / WeChat / browsers, 4 STT providers |
| [**sitige-harness**](https://github.com/lfzds4399-cpu/sitige-harness) | Pipeline runtime — composable agents / validators / pipelines, async, observable. domain-harness uses the same three-layer pattern |

If domain-harness is useful, ⭐ the repo — it's the cheapest signal and it actually moves the needle.

## License

MIT — see [LICENSE](./LICENSE).
