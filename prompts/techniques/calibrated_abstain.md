# calibrated_abstain

**Calls per item:** 1
**Best for:** TruthfulQA (which has "I have no comment" choices), HaluEval (binary)
**Inspiration:** Kadavath et al. 2022 "Language Models (Mostly) Know What They Know"; selective prediction.
**Hypothesis:** Calibrated refusal beats wrong-with-confidence on truthfulness metrics that don't penalize abstention.

## How it works
Augments the system prompt with an explicit calibration rule: self-estimate confidence, abstain below threshold, prefer "hallucinated=yes" on HaluEval when knowledge insufficient.

## When to retire
If abstention rate climbs above 60% it's degenerate. If unchanged from direct, no signal — retire.
