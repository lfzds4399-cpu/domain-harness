# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-05-01

Initial public release.

### Added
- Two-tier valuation: local heuristic gates + AI Council (Claude + DeepSeek) with per-provider score thresholds
- Hard budget walls: daily cap, monthly cap, per-domain cap, reserve floor
- Multi-registrar fallback: Porkbun, Cloudflare, Namecheap, GoDaddy by priority
- Trademark blacklist with `validators/trademark_check.py`
- 22-case end-to-end smoke (`tests/e2e_smoke.py`) covering every gate in `DRY_RUN`
- Sales adapter scaffolding for Dan, Afternic, Sedo
- AI-generated counter-offer reply for inbound buyer negotiations
- Offline backtest with Monte Carlo report (`simulate/`)
- CLI: `status`, `scan`, `appraise`, `buy`, `list-for-sale`, `portfolio`, `watchlist`, `simulate`, `auto-register`, `review`, `budget`

### Notes
- Defaults to `mode: dry_run`. Live mode requires explicit manifest flip plus registrar API keys.
- Tested on Python 3.10–3.12. Windows console output uses `sys.stdout.reconfigure(encoding="utf-8")` to avoid GBK errors.
