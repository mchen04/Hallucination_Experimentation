"""Thin wrapper around `claude -p` for Haiku calls.

Design:
- One subprocess per call (claude CLI), --output-format json, parsed for "result".
- Concurrency limited by a semaphore (default 4).
- All calls are content-addressed and cached on disk (.cache/) — re-running an
  iteration with the same strategy is free.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / ".cache"
CACHE.mkdir(exist_ok=True)

DEFAULT_MODEL = os.environ.get("HALLUC_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_CONCURRENCY = int(os.environ.get("HALLUC_CONCURRENCY", "4"))
CALL_TIMEOUT_S = int(os.environ.get("HALLUC_CALL_TIMEOUT", "120"))


@dataclass
class CallResult:
    text: str
    cost_usd: float
    duration_ms: int
    cached: bool
    is_error: bool
    raw: dict


def _cache_key(model: str, system: str, user: str, temperature: float | None) -> str:
    h = hashlib.sha256()
    h.update(model.encode())
    h.update(b"\x00")
    h.update(system.encode())
    h.update(b"\x00")
    h.update(user.encode())
    h.update(b"\x00")
    h.update(str(temperature).encode())
    return h.hexdigest()


def _cache_get(key: str) -> CallResult | None:
    p = CACHE / f"{key}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return CallResult(
        text=d["text"],
        cost_usd=d.get("cost_usd", 0.0),
        duration_ms=d.get("duration_ms", 0),
        cached=True,
        is_error=False,
        raw=d.get("raw", {}),
    )


def _cache_put(key: str, res: CallResult) -> None:
    p = CACHE / f"{key}.json"
    p.write_text(json.dumps({
        "text": res.text,
        "cost_usd": res.cost_usd,
        "duration_ms": res.duration_ms,
        "raw": res.raw,
    }))


async def call_haiku(
    user: str,
    system: str = "",
    *,
    model: str = DEFAULT_MODEL,
    temperature: float | None = None,
    use_cache: bool = True,
) -> CallResult:
    key = _cache_key(model, system, user, temperature)
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    cmd = [
        "claude", "-p",
        "--model", model,
        "--output-format", "json",
    ]
    if system:
        cmd += ["--system-prompt", system]
    cmd.append(user)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=CALL_TIMEOUT_S)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return CallResult(text="", cost_usd=0.0, duration_ms=CALL_TIMEOUT_S * 1000,
                          cached=False, is_error=True, raw={"error": "timeout"})

    try:
        d = json.loads(stdout.decode())
    except json.JSONDecodeError:
        return CallResult(text="", cost_usd=0.0, duration_ms=0, cached=False,
                          is_error=True, raw={"error": "bad-json", "stdout": stdout.decode()[:500],
                                              "stderr": stderr.decode()[:500]})

    is_error = bool(d.get("is_error"))
    text = d.get("result", "") if not is_error else ""
    res = CallResult(
        text=text,
        cost_usd=float(d.get("total_cost_usd", 0.0)),
        duration_ms=int(d.get("duration_ms", 0)),
        cached=False,
        is_error=is_error,
        raw={k: d.get(k) for k in ("session_id", "stop_reason", "usage")},
    )
    if not is_error:
        _cache_put(key, res)
    return res


class Runner:
    """Bounded-concurrency executor for Haiku calls."""

    def __init__(self, concurrency: int = DEFAULT_CONCURRENCY) -> None:
        self.sem = asyncio.Semaphore(concurrency)
        self.calls = 0
        self.cost = 0.0
        self.errors = 0
        self.cache_hits = 0

    async def call(self, user: str, system: str = "", **kw) -> CallResult:
        async with self.sem:
            res = await call_haiku(user, system, **kw)
        self.calls += 1
        self.cost += res.cost_usd
        if res.cached:
            self.cache_hits += 1
        if res.is_error:
            self.errors += 1
        return res


async def _smoke() -> None:
    r = Runner(concurrency=2)
    out = await asyncio.gather(*[
        r.call("What color is the sky? Reply with one word.", system="Be terse.")
        for _ in range(3)
    ])
    for o in out:
        print(f"text={o.text!r}  cost=${o.cost_usd:.4f}  dur={o.duration_ms}ms  cached={o.cached}")
    print(f"total: calls={r.calls} cost=${r.cost:.4f} cache_hits={r.cache_hits}")


if __name__ == "__main__":
    if not shutil.which("claude"):
        sys.exit("claude CLI not on PATH")
    asyncio.run(_smoke())
