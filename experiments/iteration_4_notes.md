# Iteration 4 — diagnosis

## Headline numbers (subset=100, seed=4)
- truthfulqa: **0.05** (direct) — matches iter-1 best
- halueval: **0.20** (claim_grounding) — REGRESSION from iter-3's 0.09
- factualityprompt: **0.07** (direct) — NEW BEST, beats iter-3's 0.11

best.json updates: factualityprompt 0.11 → 0.07.

## Cluster analysis

### TruthfulQA (5 fails)
Standard "famous misconception" pattern, no actionable change here.

### HaluEval (20 fails — 11 FP, 9 FN)
**FPs (clean → flagged hallucinated, 11 total)** — dominant pattern is
**over-decomposition of short-name answers**:
- `halueval_qa_03867_right`: candidate = "MGM Resorts International"; grounder
  internally rephrased as "MGM owns the resort that REFLECTS Mandalay's former
  name (Circus Circus)", flagged NOT_IN_KNOWLEDGE.
- `halueval_qa_03636_right`: candidate = "Mika Juhani Kaurismäki"; grounder
  rephrased as "Mika has been nominated for fewer Academy Awards than Field" —
  candidate said no such thing.
- `halueval_qa_00420_right`: candidate = "Barton Mine"; grounder added
  hypothetical "natural disaster" element.
- `halueval_qa_01328_right`: candidate = "1934"; grounder reasoned correctly
  that 1934 is mother-in-law's year, but the HaluEval label says clean —
  possibly a label-vs-judge mismatch.

3 of 5 sampled FPs are the same over-decomposition pattern.

**FNs (hallucinated → called clean, 9 total)** — two subpatterns:
- Loose paraphrase matching: `halueval_qa_05107_hallucinated` accepts "advocating
  religious beliefs" as supported by "branding student with Christian cross
  and teaching creationism".
- Question-context blindness: `halueval_qa_04077_hallucinated` accepts that
  "Lomax played Josh" is supported (true in Safe Haven) without noticing the
  question was about "Playing for Keeps" where he played Lewis.

### FactualityPrompt (7 fails, down from 11)
Same premise-correction-fabrication pattern persists (e.g. `factprompt_factual_03247`,
others) but at lower rate. fix_plan-recommended `grounded_correction` technique
remains a good next move when this benchmark needs attention again.

## Highest-leverage move
Tune **claim_grounding's GROUND_SYS** to:
1. Read the candidate LITERALLY — never internally rephrase a short-name answer
   into a hypothetical relational/comparative claim.
2. For 1-5 word "name" candidates, the ELEMENTS list must be exactly one entry:
   "the answer is <X>", which is SUPPORTED if the knowledge mentions X in a
   plausibly-answering context.
3. Split the "when in doubt" tiebreak: prefer CLEAN for short-name candidates
   (FP failure mode), prefer HALLUCINATED for longer prose candidates (FN mode).

Expected: should recover ~3-4 FPs (~3pp improvement) without losing FN coverage.

## Parallel addition (passive)
Added `grounded_correction` technique (3-call pipeline: generate → audit
specifics → rewrite dropping RISKY claims) per fix_plan's prior recommendation.
Not activated this iter — FactualityPrompt improved organically. Available for
future iterations.

## Cost
$4.29 (no improvement over iter 3's $4.29 — no extra calls added).
