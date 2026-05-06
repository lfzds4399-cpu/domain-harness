# FAQ

### Will this spend my money the moment I run it?

No. `manifest.yaml` ships with `mode: dry_run`. Every `acquisition.buy()` call short-circuits and writes a `DRY_RUN` log line instead of hitting a registrar. The 22-case smoke suite exists to prove this in CI on every push.

You have to explicitly flip to `mode: live` **and** add a registrar key. If either is missing, no money moves.

### Why two valuation tiers (local heuristic + AI Council)?

Cost. A local heuristic is free; an LLM call is not. Running every generated candidate through Claude+DeepSeek would cost more than the domains. So the local heuristic filters ~90% of noise first, and only survivors get billed against the council.

The council's job is to catch *commercial signal* the heuristic can't — brandability, market fit, language nuance — not to score raw shape (length, character mix), which the heuristic already does well.

### Why "both providers must agree" instead of an average?

Adversarial robustness. If a single LLM hallucinates value into garbage, the harness shouldn't spend on it. Requiring two independent providers to clear a per-provider threshold catches single-model bias, prompt-injection in scraped name lists, and provider outages. The cost is some false negatives, which is the right tradeoff when the downstream action is "spend real money."

### What happens if the council is split?

Skipped. Logged as `consensus: split`. The candidate sits on the watchlist, and you can re-appraise later (LLM judgment isn't stable across days). The harness will not buy a split decision.

### Can I add my own valuation factor?

Yes. `agents/valuation.py` is a pure function — input dict, output score. Add a factor, add a smoke case in `tests/e2e_smoke.py` that exercises it, open a PR. The PR bar is: every spend-affecting gate has at least one smoke case.

### Can I add my own registrar?

Yes. `agents/acquisition.py` has a `register()` dispatch keyed on `manifest.registrars`. Add a `registrars/<your_registrar>.py` with `register(domain, price) -> dict` and `available(domain) -> bool`, append to `manifest.yaml`, smoke-test in DRY_RUN, open a PR.

### Why is the watchlist different from the holdings?

- **Watchlist** = candidates that passed valuation but haven't been bought. Re-scored on every scan.
- **Holdings** = domains the harness has actually registered (or, in dry_run, *would have* registered). Persisted in `data/portfolio.json`.

`auto_register.py` is the only thing that promotes watchlist → holdings, and it requires the council to clear, the budget to be available, and the trademark/dup/whois validators to all pass.

### The CI badge says tests are passing — but how do I run them locally?

```bash
python tests/e2e_smoke.py
```

That's it. No pytest, no fixtures, no dependencies beyond `requirements.txt`. The 22 cases run end-to-end in DRY_RUN against the real validators and a stubbed registrar layer. Takes ~10 seconds.

### Does this work outside `.com`?

Yes. `manifest.yaml` has a TLD whitelist with per-TLD priority weights. Default ships with `.com`, `.ai`, `.io`. Add what you want — but understand that registrar coverage and the AI Council's brandability priors both bias toward `.com`.

### Can I use this without any AI provider?

Yes. With no `ANTHROPIC_API_KEY` and no `DEEPSEEK_API_KEY`, the harness falls back to local heuristic only. The council step is skipped (logged as `degraded`), and the spend gate becomes a hard threshold on the local score. Less safe (one signal instead of three), but it works.

### What's the legal disclaimer again?

Domain investing involves financial risk. This tool will spend real money once `mode: live`. The author warrants nothing. Start with a $20 daily cap and read every line of `manifest.yaml` first. See `LICENSE`.
