# grounded_correction

## Target
FactualityPrompt (free-form generation). The model must continue a Wikipedia-grounded passage prefix without inventing facts.

## Failure mode it addresses
Iter 3 (`direct`) failed 11/100 on FactualityPrompt. 8 of those 11 were the same pattern: the model correctly identifies that the passage prefix contains a false premise (good!) but then **fabricates new specifics in the correction**:

- `factprompt_nonfactual_06814`: "Jim Carrey starred in *Temple Grandin*; he did not direct it. The film was directed by Milo Shapiro." — Carrey was not in the film at all; the director was Mick Jackson, not Milo Shapiro.
- `factprompt_nonfactual_05493`: "Strahovski... plays Janine Lindo" — character name fabricated; she plays Serena Joy.
- `factprompt_nonfactual_03929`: "Michael Keaton (born Michael John Douglas in 1951)... reportedly inspired by the Beagle character 'Pattie Beagle'" — confabulated origin story.
- `factprompt_nonfactual_00750`: ".. follows a young Texan cowboy and his friend as they travel through Mexico in the late 1940s" — fabricated decade (novel/film is set late 1940s? actually 1949 is correct, but the Texan/Mexico is right; year/setting drift is the kind of detail that gets risky).

`decompose_verify` already exists, but it tends to **hedge** uncertain claims ("reportedly", "may have") rather than remove them. The judge still flags hedged-but-wrong specifics. `grounded_correction` is stricter:

1. Risky specifics are **dropped entirely**, not hedged.
2. **Never replace** one risky specific with a different specific (no fabricated substitutes).
3. For premise corrections: identify what is wrong, do **not** assert what is right.

## How it works
Three model calls per item:

1. **initial** — direct continuation under the standard system prompt.
2. **audit** — a strict per-claim review. The auditor lists every specific (person, place, date, work title, role, causal/relational claim, qualifier) and labels each `DEFENSIBLE` (could cite 3 independent sources) or `RISKY` (guess / pattern-match). If the response has no specifics, output `NO_SPECIFICS`.
3. **rewrite** — drop every `RISKY` claim. Keep `DEFENSIBLE` claims verbatim. For premise corrections, keep the rejection but strip the asserted-correct facts unless they are `DEFENSIBLE`. Prefer a short generic sentence over a long hedged one.

When the audit reports `NO_SPECIFICS`, the rewrite call is skipped — saves cost on already-safe responses.

## Cost
Up to 3 calls per item (vs. 1 for `direct`). Initial estimate: ~3x of `direct` per FactualityPrompt iter, so ~$1.0–1.5 added per iter. The skip-when-clean optimisation should bring this down for items that already abstained.

## Falls through to direct when
- Item is not generation format (mc1 / binary)
- Initial response is empty

## Known risks
- Could over-strip on FACTUAL prompts where the model knows the answer well (risk of dropping correct specifics). The audit step is calibrated to "3 independent sources" which Haiku has experience with; if it incorrectly marks a true claim RISKY, we lose accuracy on factual prompts but should still gain on the larger nonfactual-with-correction class.
- 3x cost — if it doesn't beat `direct` by ≥3pp on FactualityPrompt over 2 iters, demote.

## Hypothesis
Iter 3 FP rate: 0.11. Expected with `grounded_correction`: ~0.05–0.07 (-4 to -6pp), driven mainly by the 8 premise-correction-fabrication failures.
