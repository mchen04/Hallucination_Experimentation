# self_consistency_3

**Calls per item:** 3
**Best for:** TruthfulQA, HaluEval (formats with discrete answers)
**Inspiration:** Wang et al. 2022 "Self-Consistency Improves Chain of Thought".
**Hypothesis:** Variance across sampled answers correlates with uncertainty; majority vote filters out one-off bad samples.

## How it works
Three slightly perturbed user-message variants → three calls → vote on parsed answer. For generation, picks the shortest sample (smallest hallucination surface area).

## When to retire
If vote unanimity is >90% AND the marginal lift over `direct` is <1pp — costs 3x for nothing.
