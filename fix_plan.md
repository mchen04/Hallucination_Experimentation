# fix_plan.md — Ralph's prioritized work queue

The loop edits this each iteration. Top of file = next work.

---

## Now (next iteration)

- [ ] **Read iter 5 result on tuned `claim_grounding` first.** Iter 4 hit 0.20 on HaluEval (regression vs iter-3's 0.09); iter 4 tuned the GROUND_SYS to handle short-name answers literally. If iter 5 still ≥ 0.18, demote `claim_grounding` back to `direct` for HaluEval (high-variance, no clear win over baseline 0.15).
- [ ] If iter 5 cleans up HaluEval, try activating **`grounded_correction`** for FactualityPrompt (already implemented in `runner/techniques.py`, doc in `prompts/techniques/grounded_correction.md`). FP is at 0.07 best — grounded_correction's hypothesis is to recover further by removing RISKY specifics introduced during premise corrections. Cost: ~3x of `direct` per FP iter (~$1 added).

## Soon (high-value next moves the loop might pick)

- [ ] Try `counterfactual_probe` on TruthfulQA — generate the answer AND its strongest opposite, pick the more defensible. Good for TruthfulQA mc1's "popular wrong answer" failures.
- [ ] Try `calibrated_abstain` on TruthfulQA — second-place option after counterfactual_probe.
- [ ] Invent a `misconception_index.json` harvested from failures — pattern-match new questions against known traps before answering.
- [ ] HaluEval FN failure mode (paraphrase laxity + question-context blindness) is not addressed by the iter-4 tune. If FNs dominate iter-5 failures, consider a follow-up "answers-the-question?" check step in claim_grounding.

## Future / blocked

- [ ] Replace Haiku-as-judge in FactualityPrompt scoring with Wikipedia retrieval — current judge is itself hallucination-prone. Blocked until we have a Wikipedia API client.
- [ ] Add per-iteration confidence calibration metric (Brier score) so we can detect over/under-confidence.
- [ ] If a single technique dominates >3 iters, lock it and start optimizing the SECOND-priority benchmark.

## Done

- [x] **iter 1**: Established baseline (`direct` on all three). truthfulqa=0.05, halueval=0.15, factualityprompt=0.15. Cost $4.07.
- [x] **iter 1**: Fixed `JUDGE_SYS` scoring bug. Explicit refusals, calibrated hedging without specific fabrications, and correct premise rejections are now scored CLEAN. Specific fabricated facts still HALLUCINATED.
- [x] **iter 3**: Built `claim_grounding` for HaluEval. Per-element audit (FAITHFUL / ELEMENTS / GROUND / VERDICT) against the knowledge passage. HaluEval 0.15 → **0.09** (-6pp, new best). FNs 11→4; FPs 4→5. Cost $4.29. (Iteration 2 was aborted mid-work — see notes file iteration_3_notes.md for the dropped numbering.)
- [x] **iter 4**: Tuned `claim_grounding` GROUND_SYS to read short-name candidates LITERALLY (no hypothetical relational claims). Iter 4 had hit 0.20 on HaluEval; 11 FPs were dominated by over-decomposition of 1-5 word answers. Also added `grounded_correction` technique to registry (passive — not activated this iter; available for FactualityPrompt). FactualityPrompt improved organically to **0.07** (new best, direct). Cost $4.29.
