# Normalized benchmark item schema

Every loader yields items in this shape so the runner is benchmark-agnostic:

```json
{
  "id": "truthfulqa_0001",
  "benchmark": "truthfulqa" | "halueval" | "factualityprompt",
  "format": "mc1" | "binary" | "generation",
  "prompt": "<question or instruction shown to the model>",
  "choices": ["A...", "B...", "..."],   // present iff format == "mc1"
  "correct": 0,                          // mc1: index into choices; binary: "yes"/"no"; generation: null
  "metadata": {
    // benchmark-specific extras the scorer needs
    // factualityprompt: {"wiki_title": "...", "wiki_excerpt": "..."}
    // halueval: {"task": "qa"|"dialogue"|"summarization", "right_answer": "..."}
    // truthfulqa: {"category": "Misconceptions", "all_correct": [0,2]}
  }
}
```

The runner produces a parallel result item:

```json
{
  "id": "...",
  "raw_response": "<model output>",
  "parsed_answer": 0 | "yes" | "<text>",
  "correct": true|false,
  "score_detail": {...},   // scorer-specific
  "technique_used": "premise_check_v2"
}
```
