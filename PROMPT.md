# Ralph loop iteration — push Haiku toward 0% hallucination

You are one iteration of a forever-loop optimizing Claude Haiku's hallucination rate across **TruthfulQA**, **HaluEval**, and **FactualityPrompt**. Every iteration is a fresh Claude Code session reading these same files. The files are the memory; you are not.

**0% is asymptotic.** Existing published techniques (self-consistency, FActScore, constitutional self-critique, abstention calibration) all fall short. Treat them as seed material. **Your distinguishing job is to invent NEW techniques or novel compositions, not just tweak the system prompt.**

---

## Step 1 — Orient

Read in this order:
1. `AGENT.md` — how to run anything in this repo.
2. `fix_plan.md` — the prioritized work queue.
3. `prompts/strategy.json` — what techniques are currently active.
4. `experiments/log.jsonl` (last ~20 lines) — score trajectory so far.
5. `results/best.json` — best hallucination rate observed per benchmark.

If `experiments/log.jsonl` doesn't exist yet, this is iteration 1 — proceed.

## Step 2 — Run the eval

```bash
python3 runner/run_iteration.py
```

This runs the currently-active strategy on the configured subset (100 items per benchmark by default, full benchmark every 10th iteration). It writes:
- `results/iteration_<N>/summary.json`
- `results/iteration_<N>/failures.jsonl`  ← read this carefully
- `results/iteration_<N>/cost.json`
- Appends one line to `experiments/log.jsonl`
- Updates `results/best.json` (monotone best per benchmark)

If the eval fails or exits with errors, **fix the runner first** before changing strategy. Don't paper over bugs by tweaking prompts.

## Step 3 — Analyze failures

Read `results/iteration_<N>/failures.jsonl` (typically 20-50 items). For each failed benchmark:

1. Cluster the failures by failure mode. Useful categories:
   - **False premise** — the question presumes something untrue, model went along
   - **Famous misconception** — model gave the "popular wrong answer"
   - **Fabricated specifics** — invented date/name/number
   - **Premise rejected too aggressively** — model abstained on a question it should have answered
   - **Parse failure** — model gave a valid answer but the regex didn't capture it
   - **Judge disagreement** (FactualityPrompt only) — judge may have miscalled it

2. Identify the SINGLE highest-leverage pattern — the one fixing 5+ failures.

3. Write your diagnosis to `experiments/iteration_<N>_notes.md` (4-10 sentences). Be specific — quote IDs.

## Step 4 — Improve

Choose ONE of these per iteration (don't try multiple in one iter; you'll never know what helped):

**a) Mutate an existing technique.** Edit the function in `runner/techniques.py`. Update its `.md` doc.

**b) Tweak the system prompt or few-shots.** Edit `prompts/system_prompt.md` or `prompts/few_shots.md`. Cap few-shots at 20 examples.

**c) Invent a new technique.** Add a function to `runner/techniques.py`, register in `TECHNIQUES`, create `prompts/techniques/<name>.md`. **This is the highest-value option.** Look at failure patterns and ask: "what novel pipeline of model calls would have caught these?" Examples of techniques *not yet implemented* you could invent:

   - **counterfactual_probe** — generate the answer AND its strongest opposite, pick the more defensible one.
   - **question_typing** — first classify (factual / opinion / ambiguous / trap), route to a sub-prompt.
   - **token_shadow** — for binary/mc1, also ask "what would have to be true for the OTHER answer to be correct?" and use the difficulty of the rebuttal as a confidence signal.
   - **misconception_index** — maintain a JSON file of recurring trap patterns harvested from failures; match new questions against patterns before answering.
   - **multi_persona_ensemble** — 3 calls with different personas (skeptic / encyclopedist / contrarian), aggregate.
   - **inverse_check** — after answering, ask "is there any sentence in my answer I couldn't defend in 3 sources?" if yes, remove it.
   - **structured_decoding** — force the model to output a JSON with confidence per claim, then post-filter.
   - **two_pass_doubt** — first pass states an answer; second pass is told the first pass was wrong and asked to find why; final pass reconciles.

   These are *seeds*. Invent your own. The point is to materially change the inference pipeline, not the wording.

**d) Promote/demote a technique in `prompts/strategy.json`.** If a technique has had ≥3 iterations of data and underperforms `direct`, demote it. If a new technique is winning, promote it.

After your change, update `fix_plan.md`: mark what you did, add any new follow-ups you noticed.

## Step 5 — Commit and push

Stage **only** files relevant to this iteration. Specifically:
- `prompts/**` (if changed)
- `runner/**` (if changed)
- `results/iteration_<N>/summary.json` and `failures.jsonl` (skip `raw.jsonl` if it exists)
- `results/best.json`
- `experiments/log.jsonl` and `experiments/iteration_<N>_notes.md`
- `fix_plan.md`

Commit message format (machine-parseable, one commit per iteration):

```
iter <N>: <one-line headline of what changed>

Hallucination rates (this iter, subset=<n>):
- truthfulqa:        <prev>% -> <new>%  (technique: <name>)
- halueval:          <prev>% -> <new>%  (technique: <name>)
- factualityprompt:  <prev>% -> <new>%  (technique: <name>)

Best so far:
- truthfulqa:        <best>%   (iter <k>)
- halueval:          <best>%   (iter <k>)
- factualityprompt:  <best>%   (iter <k>)

What changed: <2-4 sentences — what file, why, hypothesis>
Cost this iter: $<x.xx>
```

Then `git push origin main`. If push fails (e.g. network), don't retry forever — record in `fix_plan.md` and exit normally so the next iteration retries.

## Step 6 — Iteration hygiene

- **Never** mark anything `# TODO` or leave a stub. Full implementations.
- **Never** edit `experiments/log.jsonl` retroactively — it's append-only history.
- **Never** delete `results/iteration_*` directories — they're the audit trail.
- If `results/best.json` shows a regression caused by your change, your next iteration's first task is to revert that change.
- If `experiments/log.jsonl` shows the loop has been thrashing (changing technique every iter without improvement) for >5 iters, your next change should be **conservative** — re-baseline by setting all benchmarks back to `direct` for one clean read.

Done. Exit normally. The bash loop will start the next iteration.
