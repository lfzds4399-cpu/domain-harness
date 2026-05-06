"""配置加载 — manifest.yaml + 环境变量"""
from __future__ import annotations
import os
from pathlib import Path
from functools import lru_cache

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "manifest.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    _resolve_env(cfg)
    return cfg


def _resolve_env(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and v.startswith("$"):
                node[k] = os.environ.get(v[1:], "")
            else:
                _resolve_env(v)
    elif isinstance(node, list):
        for item in node:
            _resolve_env(item)


def is_dry_run() -> bool:
    return load().get("mode", "dry_run") == "dry_run"


def data_dir() -> Path:
    p = ROOT / "data"
    p.mkdir(exist_ok=True)
    return p


def logs_dir() -> Path:
    p = ROOT / "logs"
    p.mkdir(exist_ok=True)
    return p
