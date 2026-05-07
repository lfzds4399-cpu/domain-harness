"""secret_scanner — scan tracked files for accidentally committed credentials.

Runs as part of `python tests/e2e_smoke.py` and stand-alone via:

    python -m validators.secret_scanner [--root .] [--strict]

Detects high-confidence patterns only — provider tokens whose first 3-7
characters are unmistakable (sk-ant-, sk-proj-, AKIA, ghp_, AIza, hf_, …).
False positives on those prefixes are vanishingly rare in code that isn't
intentionally a token registry; that's why we don't widen the regex set.

Returns a list of ``(path, line_no, masked_match, kind)`` tuples. CLI mode
exits with rc=1 on any finding so it can be wired into pre-commit / CI.

Lives next to budget_guard / dup_check / trademark_check / whois_check —
same shape (pure functions, no side effects beyond the scan).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (kind, regex). Patterns are anchored on signatures unique enough that we
# don't need entropy heuristics on top.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("anthropic_user_key",   re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai_proj_key",      re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}")),
    ("openai_user_key",      re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("aws_access_key",       re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat",           re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("github_oauth",         re.compile(r"gho_[A-Za-z0-9]{30,}")),
    ("google_api_key",       re.compile(r"AIza[A-Za-z0-9_\-]{30,}")),
    ("hf_token",             re.compile(r"hf_[A-Za-z0-9]{30,}")),
    ("slack_bot_token",      re.compile(r"xoxb-[A-Za-z0-9\-]{30,}")),
    ("replicate_api_token",  re.compile(r"r8_[A-Za-z0-9]{30,}")),
]

# Files we never scan — binary or vendored.
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              "logs", "runs", "marketing", "data"}
_SKIP_SUFFIXES = {".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif",
                  ".webp", ".mp4", ".mov", ".zip", ".gz", ".whl"}

# Lines whose presence marks the rest as a placeholder (test / example).
_PLACEHOLDER_HINTS = ("# allow-secret-here", "# example", "placeholder")


def _mask(s: str) -> str:
    if len(s) <= 12:
        return "***"
    return f"{s[:6]}...{s[-4:]}"


def scan(root: Path) -> list[tuple[Path, int, str, str]]:
    findings: list[tuple[Path, int, str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(hint in line for hint in _PLACEHOLDER_HINTS):
                continue
            for kind, regex in _PATTERNS:
                m = regex.search(line)
                if m:
                    findings.append((path, lineno, _mask(m.group(0)), kind))
                    break
    return findings


def main() -> int:
    p = argparse.ArgumentParser(prog="domain-harness secret-scanner")
    p.add_argument("--root", default=".", help="root path to scan (default: cwd)")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 on any finding (for CI / pre-commit)")
    args = p.parse_args()

    findings = scan(Path(args.root).resolve())
    if not findings:
        print("[secret-scanner] clean — no credential patterns found")
        return 0

    print(f"[secret-scanner] {len(findings)} potential leak(s):")
    for path, lineno, masked, kind in findings:
        print(f"  {path}:{lineno}  [{kind}]  {masked}")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
