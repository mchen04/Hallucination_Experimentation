# premise_check

**Calls per item:** 2
**Best for:** TruthfulQA (mc1), HaluEval (binary)
**Inspiration:** Lin et al. 2022 (TruthfulQA paper) — most failures are misconception-shaped.
**Hypothesis:** Many wrong answers stem from the model implicitly accepting a false premise embedded in the question. Audit premises first.

## How it works
1. Call Haiku with a "premise auditor" system prompt — list premises, judge T/F/Uncertain, give a verdict.
2. Pass that audit as additional context into the answer call.

## When to retire
If after 3 iterations on TruthfulQA it shows ≥2pp lower accuracy than `direct`. Drop it.
