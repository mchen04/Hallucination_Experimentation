# Technique library

Each `.md` file here documents a technique implemented in `runner/techniques.py`. The Ralph loop reads these to:
- Pick which technique to assign to each benchmark in `strategy.json`.
- Decide which techniques to mutate / retire / combine.
- Invent new techniques (add a new `.md` + register a function).

When adding a new technique:
1. Implement it in `runner/techniques.py` and register in `TECHNIQUES`.
2. Create `prompts/techniques/<name>.md` with the template below.
3. Optionally update `prompts/strategy.json` to try it.

## Template

```
# <name>

**Calls per item:** <n>
**Best for:** <formats / benchmarks>
**Inspiration:** <source paper / prior technique / novel>
**Hypothesis:** <why this might reduce hallucination>

## How it works
<2-4 sentences>

## When to retire
<concrete metric — e.g. "if accuracy on TruthfulQA after 3 iters is < direct baseline, retire">
```
