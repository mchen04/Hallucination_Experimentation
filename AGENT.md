# AGENT.md — how to run anything in this repo

## Prerequisites (one-time)

- `claude` CLI logged in (Pro/Max subscription used for Haiku calls)
- Python 3.11+
- `uv` available (used for TruthfulQA download which needs pyarrow)

## Run a single iteration manually

```bash
python3 runner/run_iteration.py
```

Reads `prompts/strategy.json`, runs the active technique per benchmark on a 100-sample subset (default), writes `results/iteration_<N>/`.

Environment knobs:
- `HALLUC_CONCURRENCY=8`     — parallel claude -p calls (default 4; higher = faster but more rate-limit risk)
- `HALLUC_CALL_TIMEOUT=120`  — per-call timeout seconds
- `HALLUC_MODEL=claude-haiku-4-5-20251001`  — override target model
- `HALLUC_KEEP_RAW=1`        — also write `raw.jsonl` with every prediction (large)

## Run the forever loop

```bash
./ralph_loop.sh                 # forever
./ralph_loop.sh --iters 5       # bounded
./ralph_loop.sh --once          # one iteration (for debugging the orchestrator)
```

Each iteration spawns a fresh `claude -p` session that re-reads `PROMPT.md`.

## Re-download benchmark data

```bash
uv run --with pyarrow python benchmarks/truthfulqa/download.py
python3 benchmarks/halueval/download.py
python3 benchmarks/factualityprompt/download.py
```

Each writes `benchmarks/<name>/data.jsonl` in the normalized schema (see `benchmarks/schema.md`).

## Test the inference layer in isolation

```bash
python3 runner/inference.py     # smoke-tests one Haiku call + cache hit
```

## Debug a single failure

To re-run a single failed item with a different technique without touching state:

```bash
python3 -c "
import asyncio, json
from runner.inference import Runner
from runner.techniques import TECHNIQUES, Ctx
item = json.loads(open('results/iteration_0001/failures.jsonl').readline())
ctx = Ctx(system_prompt=open('prompts/system_prompt.md').read())
async def go():
    r = Runner(concurrency=1)
    out = await TECHNIQUES['adversarial_critique'](item, r, ctx)
    print(json.dumps(out, indent=2))
asyncio.run(go())
"
```

## Inspect score trajectory

```bash
cat experiments/log.jsonl | tail -20
cat results/best.json
```

## Cost guardrail

`runner/inference.py` caches every call by content hash to `.cache/`, so re-running the same iteration costs $0. New iterations vary the seed (= iteration number), so they're fresh samples.

Typical cost (subset=100, 3 benchmarks, `direct` technique on all): **~$0.20-0.30 per iteration**.
Higher-tech techniques (decompose_verify is 4x): **~$1-2 per iteration**.

## Known limitations

- FactualityPrompt scoring uses Haiku-as-judge — it has its own hallucination problem. We accept this for relative-progress signal. Future work: add Wikipedia retrieval to the judge.
- HaluEval scoring is binary classification of model responses — not the same as preventing the model from PRODUCING hallucinations in open-ended generation.
- Both subsetting and judge variance mean small score deltas are noise. Trust trends over 3+ iterations.
