# fix_plan.md — Ralph's prioritized work queue

The loop edits this each iteration. Top of file = next work.

---

## Now (next iteration)

- [ ] Build a `claim_grounding` technique targeted at HaluEval. Decompose the candidate answer into atomic claims and verify each against the provided knowledge passage (which is embedded in the prompt). HaluEval failures are 11/15 false negatives where the model fails to audit candidate claims against knowledge. Hypothesis: this gets HaluEval from 0.15 → ~0.08.
- [ ] Iter 2 will re-baseline scoring with the new judge — expect FactualityPrompt to drop a few percentage points just from the scoring fix.

## Soon (high-value next moves the loop might pick)

- [ ] Try `calibrated_abstain` on TruthfulQA (4/5 failures are missed cautious-option). Expected to reduce TruthfulQA hallucination rate from 0.05 toward 0.02.
- [ ] Try `decompose_verify` on FactualityPrompt. After the judge fix, residual ~10 failures are fabricated specifics — decompose_verify is the natural fit.
- [ ] Invent a `misconception_index.json` harvested from failures — pattern-match new questions against known traps before answering.
- [ ] Invent `counterfactual_probe` — generate the answer AND its strongest opposite, pick the more defensible one. Good for TruthfulQA mc1.

## Future / blocked

- [ ] Replace Haiku-as-judge in FactualityPrompt scoring with Wikipedia retrieval — current judge is itself hallucination-prone. Blocked until we have a Wikipedia API client.
- [ ] Add per-iteration confidence calibration metric (Brier score) so we can detect over/under-confidence.
- [ ] If a single technique dominates >3 iters, lock it and start optimizing the SECOND-priority benchmark.

## Done

- [x] **iter 1**: Established baseline (`direct` on all three). truthfulqa=0.05, halueval=0.15, factualityprompt=0.15. Cost $4.07.
- [x] **iter 1**: Fixed `JUDGE_SYS` scoring bug. Explicit refusals, calibrated hedging without specific fabrications, and correct premise rejections are now scored CLEAN. Specific fabricated facts still HALLUCINATED.
