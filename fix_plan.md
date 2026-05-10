# fix_plan.md — Ralph's prioritized work queue

The loop edits this each iteration. Top of file = next work.

---

## Now (next iteration)

- [ ] Run iter 1 with `direct` on all three benchmarks to establish baseline.
- [ ] After baseline, analyze failures from `results/iteration_0001/failures.jsonl`. Look for the most common failure mode across all three benchmarks.

## Known scoring issue discovered in smoke test

The FactualityPrompt judge counts a calibrated refusal (e.g. "I cannot provide an accurate continuation without more context") as HALLUCINATED. That penalizes the desired behavior. The judge prompt in `runner/scoring.py` (constant `JUDGE_SYS`) should be amended so that explicit refusals or "I don't have enough information" responses are scored CLEAN, not HALLUCINATED. Fix this in iter 1 if it recurs.

## Soon (high-value next moves the loop might pick)

- [ ] Try `premise_check` on TruthfulQA. Expected to help on misconception-shaped questions.
- [ ] Try `calibrated_abstain` on TruthfulQA. Expected to help when "I have no comment" choices exist.
- [ ] Try `decompose_verify` on FactualityPrompt — designed for generation.
- [ ] Invent a `counterfactual_probe` technique (see PROMPT.md for sketch).
- [ ] Build a `misconception_index.json` harvested from failures — pattern-match new questions against known traps.

## Future / blocked

- [ ] Replace Haiku-as-judge in FactualityPrompt scoring with Wikipedia retrieval — current judge is itself hallucination-prone. Blocked until we have a Wikipedia API client.
- [ ] Add per-iteration confidence calibration metric (Brier score) so we can detect over/under-confidence.
- [ ] If a single technique dominates >3 iters, lock it and start optimizing the SECOND-priority benchmark.

## Done

(empty — first iteration)
