# Troubleshooting

Triage roughly in this order: install → config → runtime.

## `python cli.py status` errors with `ModuleNotFoundError`

You skipped the `pip install`. Re-run:

```bash
pip install -r requirements.txt
```

If you're on a venv and it's still missing, you're not in the venv. Activate it (`.venv\Scripts\activate` on Windows, `source .venv/bin/activate` on macOS/Linux) and reinstall.

## Smoke suite fails on `[4] WHOIS 检查`

Almost always a network issue. WHOIS over RDAP needs port 443 reachable to `rdap.org`. Corporate firewalls, VPNs, and PRC-side networks without a proxy will block it.

Workaround: set `whois.enabled: false` in `manifest.yaml` to skip the WHOIS gate during testing. **Re-enable before going live** — without it, the harness can attempt to register a domain someone else already owns.

## Smoke suite fails on `[7] DRY_RUN 注册` with `ImportError: cannot import name X`

You upgraded Python to 3.13+ and one dependency hasn't been wheeled yet. Either:

1. Drop to Python 3.12 (the CI matrix tops out at 3.12 for this reason), or
2. Open an issue with the failing import + your Python version.

## `cli.py scan` returns zero candidates

Two common causes:

1. Your TLD whitelist in `manifest.yaml` doesn't include any TLD the discovery sources generate for. Default sources generate `.com`/`.ai`/`.io`; if you whitelist only `.dev`, you'll get zero.
2. Your `valuation.score_min` threshold is too high. Drop it to `40` and re-run; you should see at least a handful of candidates.

## `cli.py appraise <domain>` returns `degraded`

Means at least one AI provider couldn't be reached. Check, in order:

1. Is `ANTHROPIC_API_KEY` (or `DEEPSEEK_API_KEY`) set in `.env`? Run `python -c "import os; print(bool(os.getenv('ANTHROPIC_API_KEY')))"` to confirm Python sees it.
2. Is the key valid? Hit the provider's own test endpoint with `curl` to confirm.
3. Are you out of credit? Both providers fail with HTTP 402 or 429 well before they fail with a clean error message. Check the dashboard.

If only one provider is missing, the council degrades to a single-vote check and logs `consensus: degraded`. The harness will *not* spend on a degraded decision.

## Council always returns `consensus: split`

The two providers genuinely disagree, or one of them is being more conservative than usual. Look at the per-provider scores in `logs/<date>.log`:

- If both are below the threshold but on opposite sides, the threshold is too tight; consider lowering `valuation.council_min`.
- If one provider is consistently scoring much lower than the other, you may have a stale model snapshot. Update the model name in `agents/valuation_council.py` to the current generation.

## Buy fails with `BudgetExceeded`

Working as designed. Check `python cli.py status` for current spend vs caps. If you actually want to spend more, raise the cap in `manifest.yaml` — the validator will not let you bypass it.

## Buy fails with `DuplicateError`

Working as designed. The domain is already in `data/portfolio.json`. If it shouldn't be (e.g., you tested in dry_run and want to clear state), delete the entry from `data/portfolio.json` directly. The portfolio is a flat JSON file on purpose.

## Buy fails with `TrademarkConflict`

Working as designed. The domain matches an entry in the built-in trademark blacklist or your user blacklist (`manifest.tld.user_blacklist`). Either pick a different domain or — if you're certain it's a false positive — open an issue with the conflict and we'll triage the blacklist.

## Live registrar returns 4xx but DRY_RUN works

Almost always a key/auth issue, not a code issue. The DRY_RUN path doesn't touch the registrar API, so it can't catch bad keys. Hit the registrar's API with `curl` first, with the exact key from `.env`, before suspecting the harness.

## Logs are growing without bound

`logs/` is a flat append-only directory of per-day files. Rotate with whatever you already use (logrotate, scheduled task, etc.). The harness intentionally does not auto-delete logs because they are the audit trail for spend.

## I think I found a real bug

Open an issue with: the command you ran, the full output, your Python version (`python --version`), and your `manifest.yaml` with secrets redacted. The smoke suite log (`python tests/e2e_smoke.py 2>&1`) is also useful even if it passes — it tells us what your environment looks like.
