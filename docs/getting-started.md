# Getting started

This guide walks you from a fresh clone to your first scan, in roughly 5 minutes. The whole tour runs in `dry_run` mode — no wallet, no registrar keys required.

## 1. Install

Requires Python 3.10+.

```bash
git clone https://github.com/lfzds4399-cpu/domain-harness.git
cd domain-harness
pip install -r requirements.txt
```

Optional but recommended:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. First sanity check

```bash
python cli.py status
```

Expected output:

```
mode:        dry_run
daily 余额:  $50
monthly 余额:$1000
持仓:        0 个域名
```

If you see this, the harness is wired up correctly.

## 3. Run the smoke suite

```bash
python tests/e2e_smoke.py
```

22 cases must pass. They exercise every spend gate (valuation, trademark blacklist, budget guard, dup check, WHOIS) without touching a wallet. If even one fails, **stop** — you have a broken install, not a flaky test.

## 4. First scan (still no money)

```bash
python cli.py scan --target 30
python cli.py watchlist --top 10
```

`scan` generates 30 candidate domains, runs them through local valuation gates, and pushes survivors to the watchlist. `watchlist --top 10` prints the highest-scoring 10 so you can eyeball them.

`scan` does **not** call the AI Council and does **not** spend money. Costs you nothing.

## 5. Single-domain appraisal (this *can* call the AI Council)

```bash
python cli.py appraise example.com
```

If you've put `ANTHROPIC_API_KEY` and/or `DEEPSEEK_API_KEY` in `.env`, this will request a council vote. Each provider call is metered — the harness will show you the spend before it happens. If neither key is set, only the local heuristic runs (free).

## 6. Backtest before going live

```bash
python cli.py simulate --pool 200 --top 20
```

Generates a 200-domain pool offline, scores them, and prints what the harness *would* have bought against your current `manifest.yaml` budget. Run this until you're satisfied with the gate behavior.

## 7. Going live (only when you're ready)

1. Read `manifest.yaml` end-to-end. Every knob matters.
2. Lower `daily_cap_usd` to something you can afford to lose entirely (try $20 first).
3. Add only the registrar key for your priority registrar in `.env`.
4. Flip `mode: dry_run` → `mode: live` in `manifest.yaml`.
5. Run `python cli.py status` and confirm the mode changed.
6. Run **one** manual buy with `python cli.py buy <domain> --price <usd>` to confirm the live registrar path works end-to-end.

After that, the daily pipeline (`pipelines/daily_scan.py` + `pipelines/auto_register.py`) is yours to schedule.

## What to read next

- [FAQ](./faq.md) — common questions about cost, safety, and design tradeoffs.
- [Troubleshooting](./troubleshooting.md) — what to do when something breaks.
- [`manifest.yaml`](../manifest.yaml) — every configurable knob.
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — how to add a registrar / valuation factor / smoke case.
