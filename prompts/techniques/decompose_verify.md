# decompose_verify

**Calls per item:** 4 (initial + atomize + verify + recompose)
**Best for:** FactualityPrompt (generation)
**Inspiration:** FActScore (Min et al. 2023); FaithfulCoT.
**Hypothesis:** Hallucination is concentrated in atomic factual claims; verifying claims one-at-a-time and dropping unsupported ones beats free-form generation.

## How it works
1. Generate initial continuation.
2. Decompose into numbered atomic claims.
3. Self-verify each claim (CONFIDENT / UNCERTAIN / FALSE).
4. Recompose, dropping FALSE and hedging UNCERTAIN.

## When to retire
If FactualityPrompt hallucination rate doesn't improve by ≥3pp vs `direct` within 5 iterations.
