"""Download HaluEval QA subset from the canonical RUCAIBox repo.

Outputs benchmarks/halueval/data.jsonl in the normalized schema. Each item
becomes TWO normalized items (one for the right answer, one for the hallucinated)
so the model is asked to classify each candidate independently as
hallucinated yes/no — this is the harder, more diagnostic eval.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data.jsonl"

URL = "https://raw.githubusercontent.com/RUCAIBox/HaluEval/main/data/qa_data.json"


def main() -> None:
    req = urllib.request.Request(URL, headers={"User-Agent": "ralph-loop/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = resp.read().decode("utf-8")

    n = 0
    with OUT.open("w") as f:
        for i, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            row = json.loads(line)
            question = row["question"]
            knowledge = row.get("knowledge", "")
            base_prompt = (
                f"Knowledge: {knowledge}\n"
                f"Question: {question}\n"
                f"Answer: "
            )
            for which, ans, label in (
                ("right", row["right_answer"], "no"),
                ("hallucinated", row["hallucinated_answer"], "yes"),
            ):
                full_prompt = (
                    base_prompt + ans
                    + "\n\nIs the answer above hallucinated (i.e. unsupported by the knowledge or factually wrong)? "
                    "Reply with exactly one word: yes or no."
                )
                item = {
                    "id": f"halueval_qa_{i:05d}_{which}",
                    "benchmark": "halueval",
                    "format": "binary",
                    "prompt": full_prompt,
                    "correct": label,
                    "metadata": {
                        "task": "qa",
                        "knowledge": knowledge,
                        "question": question,
                        "candidate_answer": ans,
                    },
                }
                f.write(json.dumps(item) + "\n")
                n += 1

    print(f"wrote {n} items to {OUT}")


if __name__ == "__main__":
    main()
