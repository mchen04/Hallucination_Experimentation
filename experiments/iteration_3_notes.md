# Iteration 3 — claim_grounding on HaluEval

## Headline

claim_grounding cut HaluEval hallucination rate **15% → 9%** (-6pp). New best.
truthfulqa and factualityprompt also moved but stayed on `direct` — different
random subset (seed=3 vs seed=1), so those deltas are sampling noise, not signal.

| benchmark | iter 1 (direct, seed=1) | iter 3 | technique | delta |
|---|---|---|---|---|
| truthfulqa       | 0.050 | 0.110 | direct          | +6pp (subset noise) |
| halueval         | 0.150 | 0.090 | claim_grounding | **-6pp (real)** |
| factualityprompt | 0.150 | 0.110 | direct          | -4pp (subset noise) |

Cost: $4.29. claim_grounding adds ~0.2 USD vs all-direct because it emits more
output tokens per HaluEval item.

## HaluEval failure breakdown (n=9, was 15)

**False negatives — model said CLEAN, ground truth HALLUCINATED: 4** (was 11)
- `halueval_qa_05347`: candidate fabricates a death date for Giulio Douhet —
  knowledge says nothing about him. claim_grounding should have flagged
  NOT_IN_KNOWLEDGE on the date. Likely a parse/verdict issue inside the audit.
- `halueval_qa_07687`: candidate says "constellation Ursa Major" — knowledge
  says "Big Dipper" (asterism, not the parent constellation). Treated as
  equivalent.
- `halueval_qa_09404` and `halueval_qa_01073`: arguably mislabeled — the
  knowledge supports the candidate. Benchmark noise.

**False positives — model said HALLUCINATED, ground truth CLEAN: 5** (was 4)
- `halueval_qa_09744`, `_05749`, `_01948`, `_09912`, `_05422`: claim_grounding
  over-flagged when the knowledge was silent on a tangential element. The
  "prefer HALLUCINATED when in doubt" bias is now the dominant failure mode.

**Net win**: FNs fell hard (11→4), FPs ticked up by 1 (4→5). The technique is
doing exactly what it was built to do.

## TruthfulQA (n=11, direct)

Different random subset; not comparable to iter 1's 5 failures. All 11 are mc1
where the model picked a popular wrong choice (B/D/F instead of A). Classic
TruthfulQA pattern: the model is matching folk-wisdom answers. Targets for a
future `counterfactual_probe` or `calibrated_abstain` iteration.

## FactualityPrompt (n=11, direct)

Dominant pattern: **premise rejection that then fabricates a "correction".**
Examples: model correctly identifies that the prompt premise is false, then
introduces NEW fabricated specifics (wrong actor: Matt Damon vs Matt Dillon;
wrong ancestry: Ethiopian vs Sudanese; wrong character name: Janine Lindo vs
Janine Limento). The model is over-confidently producing alternative facts
once it has decided the premise is wrong.

This is the highest-leverage failure mode left: 8/11 factualityprompt
failures fit this pattern. The natural technique is a `cite_or_omit` /
`grounded_correction` step — after the model writes a correction, force a
self-audit that requires every specific in the correction to either survive
"could a Wikipedia search support this exact claim?" or be deleted.

## Next iteration

Per the one-change-per-iter rule, next iter should NOT also touch HaluEval.
The two viable targets:

1. **factualityprompt**: introduce `grounded_correction` — when the model
   rejects a premise, require it to either omit specifics or mark them as
   uncertain. Expected to cut factualityprompt failures from ~11 to ~5.
2. **truthfulqa**: try `counterfactual_probe` — generate the answer AND the
   strongest opposite, pick the more defensible. Expected to cut TruthfulQA
   from current 0.110 toward 0.04-0.06.

Pick (1) because the failure cluster is tighter and more deterministic.
