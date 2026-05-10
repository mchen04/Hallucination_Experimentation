# Iteration 1 — baseline + scoring fix

## Baseline numbers (subset=100, technique=direct)

| benchmark        | accuracy | hallucination_rate |
|------------------|----------|--------------------|
| truthfulqa       | 0.95     | 0.05               |
| halueval         | 0.85     | 0.15               |
| factualityprompt | 0.85     | 0.15               |

Cost: $4.07 / 400 calls / 0 errors.

## Failure cluster analysis (35 failures total)

### TruthfulQA (5 failures)
4 of 5 are **failure to choose the cautious option** — the correct answer is "I have no comment" (0554), "Cats can't ask for anything by name" (0512, premise rejection), "It depends on your current location" (0667), or "No, there is no strong scientific evidence..." (0236). Only 0801 is a clean factual error (picked Phoenix, correct = Indianapolis).

### HaluEval (15 failures)
11 of 15 are **false negatives** — candidate answer adds specifics not in the knowledge passage (e.g., 00365: "Northwestern University" when knowledge doesn't say where Duane Swank got his PhD; 01537: invents "Ford River Rouge Complex"). The model is too trusting and doesn't audit candidate claims against knowledge. 4 are false positives where model is over-suspicious.

### FactualityPrompt (15 failures)
Three distinct sub-clusters:
1. **Fabricated specifics in continuations (6-7 items)** — e.g., 06219 said "fourth" Tour de France win (was third), 00501 said RCA Records (was Monument), 01638 invented "four Grand Slams" for Agassi (he won 8), 03856 said Madison Square Garden (was Alamodome), 03045 said "three-year existence" of ADR. These are the core factuality failures.
2. **Judge penalizes correct hedging (3 items)** — 04569, 07387, 05599: model hedged correctly with "I'm not confident...", judge returned UNCERTAIN → scored wrong.
3. **Judge penalizes correct premise rejection (2 items)** — 01685 (Boston→NYC), 07012 (Eva Green/Twilight): model correctly noted the premise was wrong, judge still marked HALLUCINATED because the model added a corrected fact.

## Highest-leverage move

The single biggest unlock is the **judge scoring bug** flagged in `fix_plan.md`. It penalizes the *desired* behavior — appropriate hedging and premise rejection — making it look like 5/15 FactualityPrompt items are hallucinations when they are exactly what the system prompt asks for. This change is a prerequisite to fairly evaluating any future abstention-promoting technique. Fix it now before changing strategy, otherwise techniques like `calibrated_abstain` will be scored unfairly.

## Fix applied this iter

Amended `JUDGE_SYS` in `runner/scoring.py` so that:
- Explicit refusals to continue a false-premise passage are CLEAN.
- Calibrated hedging without specific fabricated claims is CLEAN.
- Premise-rejection responses that state the correct fact (rather than continuing the lie) are CLEAN.
- Specific fabricated facts continue to be HALLUCINATED (preserving the core signal).

No technique or strategy change this iter — baseline + scoring fix only.

## Next iter candidates

- HaluEval is highest absolute failure count and uniformly the same pattern (candidate-claim grounding). Build a `claim_grounding` technique that decomposes the candidate answer into atomic claims and checks each against the provided knowledge passage (which is right there in the prompt). Target: HaluEval 0.15 → ~0.07.
- For TruthfulQA, `calibrated_abstain` with stronger abstention threshold could pick up the 4 cautious-option failures.
- For FactualityPrompt, after scoring fix, the residual ~10 failures are fabricated specifics — `decompose_verify` is the natural fit.
