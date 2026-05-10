# claim_grounding

## Target
HaluEval QA (binary). The candidate answer is graded against the provided
knowledge passage — there is a closed-world ground truth in the prompt itself.

## Failure mode it addresses
Iter 1 (`direct`) failed 15/100 on HaluEval. 11 of those were false negatives:
the candidate answer slipped in an unsupported specific (added date, place,
cause, temporal/causal relation, qualifier like "totally" or "annual") and the
model treated the candidate as roughly right.

Examples from iter 1 failures:
- `halueval_qa_05200`: candidate said the county "shares its name with the
  Potawatomi tribe" — knowledge actually says "**takes its name from** the
  Potawatomi tribe" (different relationship). Direct said `no`.
- `halueval_qa_04655`: candidate said the festival was promoting "the Fyre
  music **book**" — knowledge says "Fyre music booking **app**". Direct said `no`.
- `halueval_qa_01537`: candidate said the supply chain "is **totally owned** by
  the company" — knowledge only says "is owned by that company". The qualifier
  "totally" is not supported. Direct said `no`.

These are all single-word or short qualifier discrepancies that get washed out
by a holistic "does the answer roughly match" read.

## How it works
One model call per item with a structured 4-step procedure baked into the
system prompt:

1. **FAITHFUL** — derive the answer that strictly follows from the knowledge.
2. **ELEMENTS** — atomize the candidate into every distinct factual element
   (entities, dates, qualifiers, comparatives, causal claims).
3. **GROUND** — for each element, mark SUPPORTED / CONTRADICTED / NOT_IN_KNOWLEDGE.
4. **VERDICT** — HALLUCINATED if any element is CONTRADICTED or NOT_IN_KNOWLEDGE
   (with the "specific factual element" caveat to avoid flagging tautological
   restatements of the question); CLEAN only if every element is SUPPORTED.

The yes/no answer is then parsed deterministically from the VERDICT line.

## Cost
~1 model call per item (same as `direct`), but with ~3-4x output tokens because
of the structured per-element breakdown. Estimated cost: ~2x of `direct` per
HaluEval iter, still well under $1.

## Falls through to direct when
- Item is not binary format (mc1 / generation)
- Metadata is missing `knowledge` or `candidate_answer`

## Known risks
- May over-flag (false positive) on candidates that are correct but where the
  knowledge is silent on a corroborating detail. Iter 1 already had 4/15 FPs;
  this technique could increase that count. We accept the trade because FNs
  were the dominant failure (11/15).
- If the model's verdict line is malformed, falls back to a yes/no direct call —
  costs slightly more, no degradation.

## Iter 4 → tuning
Iter 4 reproduced HaluEval at 0.20 (vs 0.09 in iter 3) — high variance.
11 of 20 failures were FPs; 3-4 of those were the same over-decomposition
pattern: short-name candidate (e.g. "MGM Resorts International",
"Mika Juhani Kaurismäki", "Barton Mine") got internally rephrased into a
hypothetical comparative or relational claim that the candidate never
actually made, then flagged NOT_IN_KNOWLEDGE.

Iter-4 GROUND_SYS update:
- Added a CRITICAL INTERPRETATION RULE telling the checker to read the
  candidate LITERALLY and never invent inferred relational claims.
- For SHORT-NAME answers (1-5 words, no verb/predicate), the ELEMENTS list
  must contain exactly ONE entry: "the answer to the question is <X>".
- That single element is SUPPORTED whenever the knowledge mentions <X> in a
  plausible answering context, and CONTRADICTED only if the knowledge clearly
  indicates a different answer.
- "When in doubt" tiebreak is now SPLIT: prefer CLEAN for short-name answers,
  prefer HALLUCINATED for longer prose candidates (the original FN failure mode).

Hypothesis: this should recover ~3-4 FPs without re-introducing FNs on the
longer candidates. If iter 5 doesn't show ≥3pp improvement, demote to direct.
