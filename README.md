# domain-harness

Personal pipeline for finding, scoring, and (optionally) buying expiring domains.
Default mode is dry-run. Live mode only runs after `manifest.yaml` is flipped and
registrar credentials are in `.env`.

[![tests](https://github.com/lfzds4399-cpu/domain-harness/actions/workflows/test.yml/badge.svg)](https://github.com/lfzds4399-cpu/domain-harness/actions/workflows/test.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Mode: dry_run by default](https://img.shields.io/badge/mode-dry__run%20by%20default-green.svg)](#configuration)

[Chinese README](./README.zh-CN.md) | [getting-started](./docs/getting-started.md) | [FAQ](./docs/faq.md) | [troubleshooting](./docs/troubleshooting.md)

## What it does

Candidate domains come in from expired-domain feeds and a few generators. Each
candidate runs through length, TLD, blacklist, and trademark checks, then a
local scorer assigns a value estimate. If a council provider is configured the
top candidates can get an optional model-review pass. Before any registrar call
the pipeline runs budget guard (daily / monthly / per-domain caps plus a
reserve floor) and a duplicate-holdings check. Failed checks stop the call.
Nothing is written upstream unless `manifest.yaml` says `mode: live`.

Acquired domains then move to listing, simple inbound-negotiation tracking, and
settlement. The settlement side is currently the least exercised path.

## Install

Python 3.10 or newer.

```bash
git clone https://github.com/lfzds4399-cpu/domain-harness.git
cd domain-harness
pip install -r requirements.txt
cp .env.example .env
```

Fill only the provider keys and registrar credentials you actually use.

## Run

```bash
python cli.py status
python cli.py scan --target 30
python cli.py watchlist --top 10
python cli.py appraise example.com
python cli.py simulate --pool 200 --top 20
python cli.py buy somedomain.com --price 9.13
python tests/e2e_smoke.py
```

`buy` is gated by `mode` in `manifest.yaml`. While `mode: dry_run` it logs and
exits without calling the registrar.

## Configuration

`manifest.yaml` is the main configuration file.

| Section | Purpose |
|---|---|
| `budget` | Daily, monthly, per-domain caps, and reserve floor. |
| `tld` | TLD whitelist, priority weights, and blacklist. |
| `valuation` | Score thresholds, length limits, and commercial-signal gates. |
| `registrars` | Enabled registrars and priority order. |
| `sources` | Candidate generation and expired-domain feeds. |

Secrets stay in `.env`; see [`.env.example`](./.env.example).

## Project layout

```text
domain-harness/
  manifest.yaml           main configuration
  cli.py                  status / scan / appraise / buy / simulate / manifest
  core/                   config, store, logging, manifest helpers
  validators/             budget, duplicate, whois, trademark, secret, cost checks
  agents/                 discovery, valuation, acquisition, sales adapters
  pipelines/              daily scan, auto register, portfolio review
  simulate/               backtest and Monte Carlo report
  tests/                  dry-run smoke tests
  data/                   runtime state, gitignored
  logs/                   runtime logs, gitignored
```

## Money warning

Domain investing loses money for most people who try it. Renewal fees compound,
liquidity on the resale side is poor, and time-to-sale on a single name is
routinely measured in years, not months. Treat any spend through this tool as
discretionary money you are prepared to lose in full.

This repository is a personal pipeline, not financial advice. Defaults are
conservative on purpose:

- `mode: dry_run` blocks every registrar write until manually changed.
- Budget guard enforces a daily cap, a monthly cap, a per-domain cap, and a
  reserve floor. If any cap would be breached the buy is rejected, not
  partially executed.
- Trademark blacklist and duplicate-holdings check run before the registrar
  call, not after.

Before flipping to live mode: re-read `manifest.yaml` end to end, confirm the
budget numbers against the actual bank balance you are willing to commit,
and run `tests/e2e_smoke.py` to confirm the guards still reject a too-large
buy. The smoke test is the last line of defence on the spend gates; if it
fails, do not run live.

## Development

The test suite is a single script, not pytest-collected:

```bash
python tests/e2e_smoke.py
```

## License

MIT. See [LICENSE](./LICENSE).
