# Security Policy

## Reporting a vulnerability

If you find a security issue — particularly anything that could expose API keys, bypass budget guards, or trigger unintended spend — **do not open a public issue**.

Email the maintainer privately at the address listed on the GitHub profile, with:
- The vulnerable code path
- A minimal reproduction
- Whether you've already disclosed it elsewhere

I'll acknowledge within 7 days and aim to ship a fix within 30 days.

## What counts

- Anything that lets a value bypass `validators/budget_guard.py`
- Anything that prints / logs / persists raw API keys outside of `.env`
- Any way to make the harness register a domain in `dry_run` mode
- Path traversal or arbitrary file write through manifest config

## What doesn't

- Domain valuation disagreement — open a normal issue, that's a model question
- Slow responses from an external registrar — that's their problem
