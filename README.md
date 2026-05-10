# Hallucination_Experimentation

An autonomous research loop that pushes Claude Haiku 4.5 toward 0% hallucination rate on TruthfulQA, HaluEval, and FactualityPrompt by iteratively inventing and combining new mitigation techniques.

## What this is

A "Ralph loop" — `while true; do claude -p "$(cat PROMPT.md)"; done` — that, on every iteration:

1. Loads the current "strategy" (a pipeline composed of techniques from `prompts/techniques/`).
2. Runs a 100-sample subset of each of the 3 benchmarks (full benchmark every 10th iteration).
3. Scores results, isolates failures.
4. Either refines the active strategy, **invents a new technique**, or retires one that isn't earning its keep.
5. Commits + pushes to GitHub with a structured run report.

## The 0% claim

0% hallucination is asymptotic — every published technique falls short. This loop treats existing methods (self-consistency, FActScore, constitutional self-critique, abstention calibration) as **seed material** and is explicitly tasked with proposing novel combinations and new techniques per iteration. Progress is measured by the monotonic best-score-so-far curve in `results/best.json`, not by whether 0% is ever reached.

## Layout

```
benchmarks/         # Per-benchmark data + scorers
runner/             # Inference (claude -p subprocess), scoring, analysis
prompts/
  ├── strategy.json # Active pipeline of techniques
  ├── techniques/   # Library of techniques the loop has tried
  ├── system_prompt.md
  └── few_shots.md
results/            # Per-iteration outputs + best.json
experiments/        # Append-only log of what was tried and why
PROMPT.md           # Re-fed to Claude Code each iteration
AGENT.md            # How to run anything in this repo
fix_plan.md         # Ralph's prioritized to-do list
ralph_loop.sh       # The `while true` driver
```

## Run it

```bash
./ralph_loop.sh                     # forever
./ralph_loop.sh --iters 5           # bounded
./ralph_loop.sh --once              # one iteration, for debugging
```
