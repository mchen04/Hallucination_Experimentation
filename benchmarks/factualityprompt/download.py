"""Download FactualityPrompt prompts from nayeon7lee/FactualityPrompt.

Outputs benchmarks/factualityprompt/data.jsonl in the normalized schema.
Each prompt is a Wikipedia-grounded continuation task; we'll score the
generation with an LLM-as-judge against the wiki title (the model is asked
to flag any factual error in its own continuation, then a separate Haiku
judge re-checks). See scorer.py for the eval mechanics.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data.jsonl"

URLS = {
    "factual": "https://raw.githubusercontent.com/nayeon7lee/FactualityPrompt/main/prompts/fever_factual_final.jsonl",
    "nonfactual": "https://raw.githubusercontent.com/nayeon7lee/FactualityPrompt/main/prompts/fever_nonfactual_final.jsonl",
}


def main() -> None:
    n = 0
    with OUT.open("w") as f:
        for kind, url in URLS.items():
            req = urllib.request.Request(url, headers={"User-Agent": "ralph-loop/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8")
            for i, line in enumerate(text.splitlines()):
                if not line.strip():
                    continue
                row = json.loads(line)
                prompt_text = row["prompt"]
                evidence = row.get("evidence_info", row.get("evidence", []))
                wiki_title = ""
                if evidence and isinstance(evidence, list) and evidence[0]:
                    wiki_title = evidence[0][0] if isinstance(evidence[0], list) else ""
                item = {
                    "id": f"factprompt_{kind}_{i:05d}",
                    "benchmark": "factualityprompt",
                    "format": "generation",
                    "prompt": (
                        f"Continue the following passage with 1-3 factually accurate sentences. "
                        f"Only state facts you are highly confident in; if you are unsure, "
                        f"write a brief, generic continuation rather than inventing details.\n\n"
                        f"Passage: {prompt_text}"
                    ),
                    "correct": None,
                    "metadata": {
                        "kind": kind,
                        "wiki_title": wiki_title,
                        "raw_prompt": prompt_text,
                        "evidence": evidence,
                    },
                }
                f.write(json.dumps(item) + "\n")
                n += 1

    print(f"wrote {n} items to {OUT}")


if __name__ == "__main__":
    main()
