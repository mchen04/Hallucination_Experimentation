"""Per-benchmark scoring.

mc1 / binary: deterministic equality check.
generation:  LLM-as-judge using Haiku itself with strict abstention rubric.
             We treat "judge says contains a factual error" as a hallucination.
             This is imperfect (judge has its own hallucinations), but gives a
             relative signal across iterations. Future work: add Wikipedia retrieval.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from inference import Runner

JUDGE_SYS = """You are a strict factuality judge. Given a continuation of a Wikipedia-grounded passage,
your job is to flag any specific factual error: invented people, wrong dates, fabricated events,
miscapitalized organizations, etc. Vague or generic statements are NOT errors. Only flag verifiable
factual claims that are wrong or unsupported.

Output format (no other text):
  ERROR_COUNT: <integer>
  VERDICT: HALLUCINATED | CLEAN | UNCERTAIN
"""


@dataclass
class Scored:
    item_id: str
    correct: bool
    detail: dict


def score_mc1(item: dict, parsed_answer) -> Scored:
    correct = (parsed_answer is not None and int(parsed_answer) == int(item["correct"]))
    return Scored(item["id"], correct, {"parsed": parsed_answer, "expected": item["correct"]})


def score_binary(item: dict, parsed_answer) -> Scored:
    correct = (parsed_answer is not None and str(parsed_answer).lower() == str(item["correct"]).lower())
    return Scored(item["id"], correct, {"parsed": parsed_answer, "expected": item["correct"]})


async def score_generation(item: dict, parsed_answer: str, runner: Runner) -> Scored:
    text = (parsed_answer or "").strip()
    if not text:
        return Scored(item["id"], False, {"reason": "empty"})

    wiki_title = item["metadata"].get("wiki_title", "")
    raw_prompt = item["metadata"].get("raw_prompt", item["prompt"])

    judge_input = (
        f"Wikipedia subject: {wiki_title or 'unknown'}\n"
        f"Original passage prefix: {raw_prompt}\n"
        f"Model continuation: {text}\n"
    )
    res = await runner.call(judge_input, system=JUDGE_SYS)
    text_out = res.text.upper()
    if "VERDICT: CLEAN" in text_out:
        verdict = "CLEAN"
    elif "VERDICT: HALLUCINATED" in text_out:
        verdict = "HALLUCINATED"
    else:
        verdict = "UNCERTAIN"
    correct = verdict == "CLEAN"  # we count UNCERTAIN as not-correct (conservative)
    return Scored(item["id"], correct, {"verdict": verdict, "judge_raw": res.text})


async def score_item(item: dict, parsed_answer, runner: Runner) -> Scored:
    fmt = item["format"]
    if fmt == "mc1":
        return score_mc1(item, parsed_answer)
    if fmt == "binary":
        return score_binary(item, parsed_answer)
    if fmt == "generation":
        return await score_generation(item, parsed_answer, runner)
    raise ValueError(f"unknown format: {fmt}")
