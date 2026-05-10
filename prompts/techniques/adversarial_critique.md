# adversarial_critique

**Calls per item:** 3 (initial + critic + revised)
**Best for:** all formats
**Inspiration:** Constitutional AI self-critique (Bai et al. 2022); LLM-as-judge debate.
**Hypothesis:** A fresh "adversarial" call attacking the initial answer surfaces hidden failure modes the first answer missed.

## How it works
1. Generate initial answer with `direct`.
2. Separate call with adversarial-fact-checker system prompt: critique the answer, output VERDICT_KEEP / VERDICT_REVISE / VERDICT_ABSTAIN.
3. Final answer call sees the critique as additional context.

## When to retire
If the critic verdict is KEEP for >80% of items, the revision step is wasted. Either tune the critic to be harsher or retire.
