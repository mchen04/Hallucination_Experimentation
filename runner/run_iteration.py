"""Run one iteration: load strategy, sample, infer, score, write report.

Outputs:
  results/iteration_NNNN/
    summary.json       # aggregate scores per benchmark
    failures.jsonl     # only the wrong items, with full trace + reason
    raw.jsonl          # every prediction (only if HALLUC_KEEP_RAW=1)
    cost.json          # total cost + per-benchmark breakdown
  results/best.json    # rolling best score per benchmark (monotone)
  experiments/log.jsonl  # append-only run-history line
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "runner"))

from inference import Runner  # noqa: E402
from scoring import score_item  # noqa: E402
from techniques import TECHNIQUES, Ctx  # noqa: E402

BENCHMARKS = ["truthfulqa", "halueval", "factualityprompt"]


def load_jsonl(path: Path):
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def sample_items(benchmark: str, n: int, seed: int) -> list[dict]:
    path = REPO / "benchmarks" / benchmark / "data.jsonl"
    items = list(load_jsonl(path))
    rng = random.Random(seed)
    if n >= len(items):
        return items
    return rng.sample(items, n)


async def run_one_item(item: dict, technique, runner: Runner, ctx: Ctx) -> dict:
    t0 = time.time()
    try:
        out = await technique(item, runner, ctx)
    except Exception as e:  # pylint: disable=broad-except
        out = {"parsed_answer": None, "raw_response": "", "trace": [{"step": "error", "text": repr(e)}]}
    scored = await score_item(item, out["parsed_answer"], runner)
    return {
        "id": item["id"],
        "benchmark": item["benchmark"],
        "parsed_answer": out["parsed_answer"],
        "raw_response": out["raw_response"],
        "trace": out["trace"],
        "correct": scored.correct,
        "score_detail": scored.detail,
        "expected": item.get("correct"),
        "prompt": item["prompt"][:600],
        "metadata": item.get("metadata", {}),
        "duration_s": round(time.time() - t0, 2),
    }


async def run_benchmark(benchmark: str, technique_name: str, items: list[dict],
                        ctx: Ctx, runner: Runner) -> dict:
    technique = TECHNIQUES.get(technique_name)
    if technique is None:
        raise SystemExit(f"unknown technique: {technique_name}")
    results = await asyncio.gather(*[
        run_one_item(it, technique, runner, ctx) for it in items
    ])
    correct = sum(1 for r in results if r["correct"])
    n = len(results)
    return {
        "benchmark": benchmark,
        "technique": technique_name,
        "n": n,
        "correct": correct,
        "accuracy": correct / n if n else 0.0,
        "hallucination_rate": 1 - (correct / n) if n else 1.0,
        "results": results,
    }


def update_best(by_bench: dict, best_path: Path) -> dict:
    prev = {}
    if best_path.exists():
        prev = json.loads(best_path.read_text())
    new = dict(prev)
    for b, d in by_bench.items():
        old = prev.get(b, {}).get("hallucination_rate", 1.0)
        if d["hallucination_rate"] < old:
            new[b] = {
                "hallucination_rate": d["hallucination_rate"],
                "accuracy": d["accuracy"],
                "technique": d["technique"],
                "iteration": d.get("iteration"),
                "n": d["n"],
            }
    best_path.write_text(json.dumps(new, indent=2))
    return new


async def main() -> None:
    strategy = json.loads((REPO / "prompts" / "strategy.json").read_text())
    iteration = strategy.get("iteration", 0) + 1
    strategy["iteration"] = iteration
    (REPO / "prompts" / "strategy.json").write_text(json.dumps(strategy, indent=2))

    is_full = iteration % strategy.get("full_eval_every", 10) == 0
    subset_size = strategy.get("subset_size", 100) if not is_full else 10_000_000

    system_prompt = (REPO / "prompts" / "system_prompt.md").read_text()
    few_shots = (REPO / "prompts" / "few_shots.md").read_text()
    ctx = Ctx(system_prompt=system_prompt, few_shots=few_shots)

    runner = Runner(concurrency=strategy.get("concurrency", 4))

    out_dir = REPO / "results" / f"iteration_{iteration:04d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[iter {iteration}] full_eval={is_full} subset={subset_size}")
    by_bench: dict = {}
    for b in BENCHMARKS:
        items = sample_items(b, subset_size, seed=iteration)
        technique_name = strategy.get(b, "direct")
        print(f"[iter {iteration}]   {b}: technique={technique_name} n={len(items)}")
        rep = await run_benchmark(b, technique_name, items, ctx, runner)
        rep["iteration"] = iteration
        by_bench[b] = rep
        # Per-benchmark progress
        print(f"[iter {iteration}]   {b}: accuracy={rep['accuracy']:.3f} "
              f"hallucination_rate={rep['hallucination_rate']:.3f}")

    summary = {
        "iteration": iteration,
        "is_full_eval": is_full,
        "by_benchmark": {b: {k: v for k, v in d.items() if k != "results"} for b, d in by_bench.items()},
        "totals": {
            "calls": runner.calls,
            "cost_usd": round(runner.cost, 4),
            "errors": runner.errors,
            "cache_hits": runner.cache_hits,
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # failures.jsonl — only wrong items, full detail
    with (out_dir / "failures.jsonl").open("w") as f:
        for b, d in by_bench.items():
            for r in d["results"]:
                if not r["correct"]:
                    f.write(json.dumps(r) + "\n")

    if os.environ.get("HALLUC_KEEP_RAW") == "1":
        with (out_dir / "raw.jsonl").open("w") as f:
            for b, d in by_bench.items():
                for r in d["results"]:
                    f.write(json.dumps(r) + "\n")

    (out_dir / "cost.json").write_text(json.dumps({
        "iteration": iteration,
        "total_cost_usd": round(runner.cost, 4),
        "calls": runner.calls,
        "errors": runner.errors,
        "cache_hits": runner.cache_hits,
    }, indent=2))

    new_best = update_best({b: {**d, "iteration": iteration} for b, d in by_bench.items()},
                           REPO / "results" / "best.json")

    # experiments/log.jsonl
    log_line = {
        "iteration": iteration,
        "ts": summary["timestamp"],
        "is_full_eval": is_full,
        "strategy": {b: strategy.get(b, "direct") for b in BENCHMARKS},
        "hallucination_rate": {b: round(d["hallucination_rate"], 4) for b, d in by_bench.items()},
        "accuracy": {b: round(d["accuracy"], 4) for b, d in by_bench.items()},
        "n": {b: d["n"] for b, d in by_bench.items()},
        "cost_usd": round(runner.cost, 4),
        "best_so_far": {b: round(new_best.get(b, {}).get("hallucination_rate", 1.0), 4) for b in BENCHMARKS},
    }
    with (REPO / "experiments" / "log.jsonl").open("a") as f:
        f.write(json.dumps(log_line) + "\n")

    print(f"[iter {iteration}] done. cost=${runner.cost:.4f} "
          f"calls={runner.calls} errors={runner.errors}")
    print(f"[iter {iteration}] hallucination rates: "
          + " ".join(f"{b}={by_bench[b]['hallucination_rate']:.3f}" for b in BENCHMARKS))


if __name__ == "__main__":
    asyncio.run(main())
