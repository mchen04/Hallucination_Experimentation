"""Download TruthfulQA MC1 from the canonical HF parquet mirror.

Outputs benchmarks/truthfulqa/data.jsonl in the normalized schema.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data.jsonl"

# HuggingFace public parquet for truthful_qa multiple_choice config (validation split).
# Pinned by commit so the download is reproducible.
PARQUET_URL = (
    "https://huggingface.co/datasets/truthfulqa/truthful_qa/resolve/main/"
    "multiple_choice/validation-00000-of-00001.parquet"
)


def main() -> None:
    try:
        import pyarrow.parquet as pq  # type: ignore
    except ImportError:
        sys.stderr.write(
            "Need pyarrow. Run via:  uv run --with pyarrow python download.py\n"
        )
        sys.exit(1)

    req = urllib.request.Request(PARQUET_URL, headers={"User-Agent": "ralph-loop/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        buf = io.BytesIO(resp.read())
    table = pq.read_table(buf).to_pylist()

    n = 0
    with OUT.open("w") as f:
        for i, row in enumerate(table):
            mc1 = row["mc1_targets"]
            choices = list(mc1["choices"])
            labels = list(mc1["labels"])
            try:
                correct_idx = labels.index(1)
            except ValueError:
                continue
            item = {
                "id": f"truthfulqa_{i:04d}",
                "benchmark": "truthfulqa",
                "format": "mc1",
                "prompt": row["question"],
                "choices": choices,
                "correct": correct_idx,
                "metadata": {
                    "category": row.get("category", ""),
                },
            }
            f.write(json.dumps(item) + "\n")
            n += 1

    print(f"wrote {n} items to {OUT}")


if __name__ == "__main__":
    main()
