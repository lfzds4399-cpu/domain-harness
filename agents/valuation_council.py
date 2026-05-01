"""AI Council: Claude + DeepSeek 双盲打商业潜力分

只对 valuation.py 给出 ≥ min_score_council 分的候选喂 AI（节省 token）。
两个 provider 都给一个 0-100 商业潜力分 + 一句话理由。

输出：{ council_score: 平均分, providers: {anthropic: ..., deepseek: ...}, consensus: 0-1 }
"""
from __future__ import annotations
import json
import os
import re
from typing import Optional

import requests

from core import config, log


PROMPT = """你是域名投资专家，给下列域名打 0-100 的商业潜力分，并用一句话说明。
评估维度：可记忆性、品牌潜力、行业相关性、SEO 价值、转售流动性。
严格按 JSON 返回：{"score": <int 0-100>, "reason": "<一句话>"}
不要任何额外文字。

域名：{domain}
长度：{length}
TLD：{tld}
"""


def _call_anthropic(prompt: str, model: str = "claude-opus-4-7") -> Optional[dict]:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            log.warn("anthropic 失败", status=r.status_code, body=r.text[:200])
            return None
        data = r.json()
        text = data["content"][0]["text"]
        return _extract_json(text)
    except Exception as e:
        log.warn("anthropic 异常", err=str(e))
        return None


def _call_deepseek(prompt: str, model: str = "deepseek-chat") -> Optional[dict]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return None
    try:
        r = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        if r.status_code != 200:
            log.warn("deepseek 失败", status=r.status_code, body=r.text[:200])
            return None
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return _extract_json(text)
    except Exception as e:
        log.warn("deepseek 异常", err=str(e))
        return None


def _extract_json(text: str) -> Optional[dict]:
    m = re.search(r"\{[^{}]*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        score = int(obj.get("score", 0))
        return {"score": max(0, min(100, score)), "reason": str(obj.get("reason", ""))[:200]}
    except Exception:
        return None


def evaluate(domain_record: dict) -> dict:
    """对单个域名跑 council。domain_record 要含 domain/length/tld"""
    cfg = config.load().get("council", {})
    if not cfg.get("enabled"):
        return {"council_score": None, "providers": {}, "consensus": None}

    prompt = PROMPT.format(
        domain=domain_record["domain"],
        length=domain_record.get("length", len(domain_record["domain"].split(".")[0])),
        tld=domain_record.get("tld", domain_record["domain"].split(".")[-1]),
    )

    providers = {}
    for p in cfg.get("providers", []):
        if not p.get("enabled"):
            continue
        if p["name"] == "anthropic":
            r = _call_anthropic(prompt, p.get("model", "claude-opus-4-7"))
            if r: providers["anthropic"] = r
        elif p["name"] == "deepseek":
            r = _call_deepseek(prompt, p.get("model", "deepseek-chat"))
            if r: providers["deepseek"] = r

    if not providers:
        return {"council_score": None, "providers": {}, "consensus": None}

    scores = [p["score"] for p in providers.values()]
    avg = sum(scores) / len(scores)
    consensus = 1 - (max(scores) - min(scores)) / 100 if len(scores) > 1 else 1.0

    return {
        "council_score": round(avg, 1),
        "providers": providers,
        "consensus": round(consensus, 2),
    }


def evaluate_batch(records: list[dict], threshold: int = 75) -> list[dict]:
    """批量评估，只对本地分 ≥ threshold 的喂 AI"""
    out = []
    for rec in records:
        if rec.get("score", 0) < threshold:
            out.append(rec)
            continue
        verdict = evaluate(rec)
        rec.update(verdict)
        out.append(rec)
        if verdict.get("council_score") is not None:
            log.info(
                "council",
                domain=rec["domain"],
                local=rec["score"],
                council=verdict["council_score"],
                consensus=verdict["consensus"],
            )
    return out
