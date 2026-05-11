# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-05-07

Lifts the repo onto the harness-engineering pattern (logging quiet mode, unified pipeline manifest, ship-with-every-harness validators) without breaking any existing surface.

### Added
- **`-q` / `--quiet` flag + `DOMAIN_HARNESS_QUIET` env var** — suppresses INFO/OK/DRY console output for CC sessions and cron, while the JSONL file log keeps the complete record. Implementation in `core/log.py`.
- **`core/manifest.py`** — top-level pipeline-stage manifest. Each pipeline (`daily_scan`, `auto_register`, `portfolio_review`) records a one-line summary (counts, errors, status) on completion. Persists at `data/manifest.json`. Surfaced via `python cli.py status` and a new `python cli.py manifest` subcommand.
- **`validators/secret_scanner.py`** — repo-tree scan for high-confidence credential patterns (sk-ant-, AKIA, ghp_, AIza, hf_, slack/replicate tokens). CLI: `python -m validators.secret_scanner --root . --strict` for pre-commit / CI. Honours inline `# allow-secret-here` placeholder hints.
- **`validators/cost_tracker.py`** — process-local API spend ledger. Pipelines call `record(provider, op, usd)` at every external call; `report()` returns a per-provider / per-operation summary suitable for embedding in a manifest entry. Uses `RLock` so `report()` can compose `by_provider()` / `by_operation()` without deadlocking.
- **3 new `e2e_smoke.py` cases** covering the new validators (clean scan + accumulation + reset round-trip). Total: 25/25 PASS, was 22/22.

### Changed
- e2e_smoke.py clears `ANTHROPIC_API_KEY` around the `negotiate_reply` case so the deterministic fallback path runs regardless of operator env.

### Deferred to v0.4.0
- [#5](https://github.com/lfzds4399-cpu/domain-harness/issues/5) — migrate to `src/` layout
- [#6](https://github.com/lfzds4399-cpu/domain-harness/issues/6) — replace argparse with typer

## [0.2.0] — 2026-05-07

### Fixed
- **Fresh-install crash** — `core/store.portfolio()` and `budget()` now seed schema defaults (`owned`, `watchlist`, `blacklist`, `lifetime`), so a clean checkout no longer `KeyError`s on the first scan or buy.
- **Trademark blacklist now ships in the repo** — `data/trademark_blacklist.txt` was previously gitignored, which silently disabled the trademark validator on every fresh clone. The seed list is now committed.
- **`data/` is auto-created** on first write (`config.data_dir()` mirrors `logs_dir()`), so `cli.py scan` / `buy` work without `mkdir data` first.

### Changed
- CI now runs on both `master` and `main` push/PR (repo default branch is `master`).
- Added a `ruff` lint job to CI (`F`, `E9` rules; `F401`/`F811` ignored). Fixed 4 pre-existing lint warnings.

### Added
- `docs/getting-started.md` — 7-step tour from clone to first scan, all in `dry_run`.
- `docs/faq.md` — common questions about cost, safety, and design tradeoffs.
- `docs/troubleshooting.md` — triage tree for install / config / runtime failures.
- README header now links the docs.
- 3 pinned `help wanted` issues for first-time contributors:
  - [#1 Add Namecheap registrar adapter](https://github.com/lfzds4399-cpu/domain-harness/issues/1)
  - [#2 Add a second expired-domain feed source](https://github.com/lfzds4399-cpu/domain-harness/issues/2)
  - [#3 Add edit-distance brand similarity factor to valuation](https://github.com/lfzds4399-cpu/domain-harness/issues/3)

### Notes
- The 22-case smoke suite still passes on a fresh checkout (no `data/` dir, no env vars). This is now actually true on CI, not just on machines with accumulated state.
- 0.1.0's CHANGELOG mentioned Namecheap and GoDaddy as supported registrars; that was aspirational. Only Porkbun and Cloudflare are wired up today — adding Namecheap is help-wanted #1.

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
