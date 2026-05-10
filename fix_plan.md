# fix_plan.md — Ralph's prioritized work queue

The loop edits this each iteration. Top of file = next work.

---

## Now (next iteration)

- [ ] Invent **`grounded_correction`** for FactualityPrompt. 8/11 iter-3 factualityprompt failures are "model rejects a false premise, then fabricates new specifics in the correction" (wrong actor, wrong ancestry, wrong character name). Technique: after the initial generation, run a self-audit pass that flags every specific in the correction and forces the model to either keep specifics it would defend in 3 sources or replace them with a generic phrasing. Expected: 0.11 → ~0.05 on factualityprompt.

## Soon (high-value next moves the loop might pick)

- [ ] Tune `claim_grounding` — the FN→FP swap (4 FNs left, 5 FPs) means the "prefer HALLUCINATED when in doubt" bias is now too aggressive. Try downgrading "any NOT_IN_KNOWLEDGE specific = hallucinated" to "any NOT_IN_KNOWLEDGE date/place/quantifier/named-entity = hallucinated". Should cut FPs while preserving the FN gains.
- [ ] Try `counterfactual_probe` on TruthfulQA — generate the answer AND its strongest opposite, pick the more defensible. Good for TruthfulQA mc1's "popular wrong answer" failures (all 11 iter-3 failures are this pattern).
- [ ] Try `calibrated_abstain` on TruthfulQA — second-place option after counterfactual_probe.
- [ ] Invent a `misconception_index.json` harvested from failures — pattern-match new questions against known traps before answering.

## Future / blocked

- [ ] Replace Haiku-as-judge in FactualityPrompt scoring with Wikipedia retrieval — current judge is itself hallucination-prone. Blocked until we have a Wikipedia API client.
- [ ] Add per-iteration confidence calibration metric (Brier score) so we can detect over/under-confidence.
- [ ] If a single technique dominates >3 iters, lock it and start optimizing the SECOND-priority benchmark.

## Done

- [x] **iter 1**: Established baseline (`direct` on all three). truthfulqa=0.05, halueval=0.15, factualityprompt=0.15. Cost $4.07.
- [x] **iter 1**: Fixed `JUDGE_SYS` scoring bug. Explicit refusals, calibrated hedging without specific fabrications, and correct premise rejections are now scored CLEAN. Specific fabricated facts still HALLUCINATED.
- [x] **iter 3**: Built `claim_grounding` for HaluEval. Per-element audit (FAITHFUL / ELEMENTS / GROUND / VERDICT) against the knowledge passage. HaluEval 0.15 → **0.09** (-6pp, new best). FNs 11→4; FPs 4→5. Cost $4.29. (Iteration 2 was aborted mid-work — see notes file iteration_3_notes.md for the dropped numbering.)
