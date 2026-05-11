# Contributing to domain-harness

Thanks for your interest. This project is a working tool, not a toy — contributions that improve real-world reliability are welcome.

## Quick start

```bash
git clone https://github.com/<your-fork>/domain-harness.git
cd domain-harness
pip install -r requirements.txt
python tests/e2e_smoke.py        # must show 25/25 PASS
```

## Before opening a PR

1. **Run the smoke**: `python tests/e2e_smoke.py` must pass 25/25 in `DRY_RUN` mode. If your change touches a guard/validator, add a case here.
2. **Keep the harness honest**: every spend gate, blacklist, or budget rule must be exercised by a smoke case. No "trust me" code paths.
3. **Stay in `dry_run` for tests**: never commit code that calls a paid registrar API in tests.
4. **Document new manifest knobs**: anything user-facing in `manifest.yaml` must be explained in `README.md` and have a sane default.

## What's a great PR

- A new registrar adapter (Cloudflare flip, Namecheap, Hexonet ...)
- A sharper valuation feature (e.g. brandability score from a small LM)
- A new sales channel adapter (Sedo bulk listing, Afternic API)
- A failure mode the smoke didn't catch — with a regression case added

## What we won't merge

- Features that require always-on paid services to test
- Anything that disables a budget guard
- Code that prints API keys, account IDs, or balances to stdout

## Code style

- Python ≥ 3.9, type hints encouraged on public functions
- Standard library where possible — avoid pulling new heavy deps
- `manifest.yaml` is the single source of truth for thresholds; don't hard-code

## Reporting bugs

Open an issue with: Python version, OS, the manifest section involved, and the failing log excerpt. Don't paste live API keys.

## License

By contributing you agree your work is released under the MIT License.
