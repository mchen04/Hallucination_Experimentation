"""Hallucination-mitigation techniques.

Each technique is an async function that takes a normalized benchmark item +
a Runner and returns a dict:

    {
      "parsed_answer": <int|str>,   # mc1: choice index; binary: "yes"/"no"; generation: text
      "raw_response":  <str>,       # final model output
      "trace":         [{"step": "...", "text": "..."}, ...],  # full reasoning chain
    }

The loop is encouraged to MUTATE this file: add new techniques, retire old
ones, or compose them. Every technique must be registered in TECHNIQUES
at the bottom of the file.

Design principles for new techniques (read this before adding):
  1. Make the technique do ONE thing the others don't. Don't combine — compose
     instead via "ensemble_*" wrappers.
  2. Cost matters. A technique that calls Haiku 5x must beat the 1x baseline
     by ≥5pp on its target benchmark or it's not worth keeping.
  3. Handle all three formats (mc1 / binary / generation), or declare what
     it doesn't support and fall through to direct.
  4. Log every model call into trace[] so the failure analyzer can see it.
"""
from __future__ import annotations

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from inference import Runner


@dataclass
class Ctx:
    system_prompt: str
    few_shots: str = ""
    extra: dict = field(default_factory=dict)


# ---------------- shared helpers ----------------

def _format_mc_prompt(item: dict, instr: str = "") -> str:
    lines = [item["prompt"], "", "Choices:"]
    for i, c in enumerate(item["choices"]):
        lines.append(f"  ({chr(65 + i)}) {c}")
    if instr:
        lines += ["", instr]
    else:
        lines += [
            "",
            "Reply with EXACTLY the single capital letter of the best choice (A, B, C, ...). "
            "No explanation, no punctuation, no extra text."
        ]
    return "\n".join(lines)


def _parse_mc_answer(text: str, n_choices: int) -> int | None:
    if not text:
        return None
    # First grab any single A-Z letter that maps to a valid choice.
    for m in re.finditer(r"\b([A-Z])\b", text.strip()):
        idx = ord(m.group(1)) - 65
        if 0 <= idx < n_choices:
            return idx
    # Fallback: digit
    for m in re.finditer(r"\b(\d+)\b", text):
        idx = int(m.group(1)) - 1  # 1-indexed
        if 0 <= idx < n_choices:
            return idx
    return None


def _parse_binary(text: str) -> str | None:
    if not text:
        return None
    t = text.strip().lower()
    # Take first yes/no token
    m = re.search(r"\b(yes|no)\b", t)
    if m:
        return m.group(1)
    return None


# ---------------- TECHNIQUE 1: direct ----------------

async def direct(item: dict, runner: Runner, ctx: Ctx) -> dict:
    """Single-shot baseline. No tricks."""
    fmt = item["format"]
    sys_prompt = ctx.system_prompt
    if ctx.few_shots:
        sys_prompt = sys_prompt + "\n\n" + ctx.few_shots

    if fmt == "mc1":
        prompt = _format_mc_prompt(item)
        res = await runner.call(prompt, system=sys_prompt)
        parsed = _parse_mc_answer(res.text, len(item["choices"]))
    elif fmt == "binary":
        res = await runner.call(item["prompt"], system=sys_prompt)
        parsed = _parse_binary(res.text)
    else:  # generation
        res = await runner.call(item["prompt"], system=sys_prompt)
        parsed = res.text
    return {
        "parsed_answer": parsed,
        "raw_response": res.text,
        "trace": [{"step": "direct", "text": res.text}],
    }


# ---------------- TECHNIQUE 2: premise_check ----------------
# Inspiration: TruthfulQA failures often stem from accepting a false premise
# embedded in the question (e.g. "Why does lightning never strike twice?").
# Force premise extraction + verification BEFORE answering.

PREMISE_SYS = """You analyze questions for hidden false premises.
A "premise" is something the question takes for granted (e.g. "When did X happen?" presumes X happened).
Your job: list the premises, then judge each as True / False / Uncertain, citing your reasoning briefly.
Output format:
  P1: <premise>  -> True|False|Uncertain  (one-line reason)
  P2: ...
  VERDICT: SAFE_TO_ANSWER  |  REJECT_PREMISE  |  ANSWER_WITH_CAVEAT
"""

async def premise_check(item: dict, runner: Runner, ctx: Ctx) -> dict:
    fmt = item["format"]
    if fmt == "generation":
        return await direct(item, runner, ctx)

    q_text = item["prompt"] if fmt == "binary" else item["prompt"]
    premise_res = await runner.call(
        f"Question:\n{q_text}\n\nAnalyze the premises.",
        system=PREMISE_SYS,
    )

    # Pass premise analysis as context to a final answer
    sys_prompt = ctx.system_prompt + "\n\nA premise audit was performed:\n" + premise_res.text
    if fmt == "mc1":
        prompt = _format_mc_prompt(
            item,
            instr=(
                "Using the premise audit above, choose the best answer. If a premise is FALSE, "
                "prefer a choice that rejects the premise or says 'I have no comment'. "
                "Reply with EXACTLY one capital letter."
            ),
        )
        res = await runner.call(prompt, system=sys_prompt)
        parsed = _parse_mc_answer(res.text, len(item["choices"]))
    else:  # binary
        res = await runner.call(item["prompt"], system=sys_prompt)
        parsed = _parse_binary(res.text)

    return {
        "parsed_answer": parsed,
        "raw_response": res.text,
        "trace": [
            {"step": "premise_audit", "text": premise_res.text},
            {"step": "final", "text": res.text},
        ],
    }


# ---------------- TECHNIQUE 3: self_consistency_3 ----------------
# Sample 3 times at temperature>0 (Haiku is sampled even at default; we just
# replay 3x and vote). For generation, picks the most "central" sample by
# self-judged factuality.

async def self_consistency_3(item: dict, runner: Runner, ctx: Ctx) -> dict:
    fmt = item["format"]
    sys_prompt = ctx.system_prompt
    if ctx.few_shots:
        sys_prompt = sys_prompt + "\n\n" + ctx.few_shots

    if fmt == "mc1":
        prompt = _format_mc_prompt(item)
    elif fmt == "binary":
        prompt = item["prompt"]
    else:
        prompt = item["prompt"]

    # Three "different" samples by perturbing the user prompt very slightly
    # (cache key changes -> three independent calls).
    perturbations = [
        prompt,
        "Take a careful breath, then:\n\n" + prompt,
        "Think step by step internally, then give only the final answer:\n\n" + prompt,
    ]
    samples = await asyncio.gather(*[
        runner.call(p, system=sys_prompt) for p in perturbations
    ])

    if fmt == "mc1":
        parses = [_parse_mc_answer(s.text, len(item["choices"])) for s in samples]
        votes = Counter([p for p in parses if p is not None])
        parsed = votes.most_common(1)[0][0] if votes else None
    elif fmt == "binary":
        parses = [_parse_binary(s.text) for s in samples]
        votes = Counter([p for p in parses if p is not None])
        parsed = votes.most_common(1)[0][0] if votes else None
    else:
        # For generation: pick the shortest non-empty answer (less surface area for hallucination).
        texts = [s.text for s in samples if s.text]
        parsed = min(texts, key=len) if texts else ""

    return {
        "parsed_answer": parsed,
        "raw_response": samples[0].text,
        "trace": [{"step": f"sample_{i}", "text": s.text} for i, s in enumerate(samples)],
    }


# ---------------- TECHNIQUE 4: adversarial_critique ----------------
# Generate, then ask a separate critic call to attack the answer, then revise.
# Helps when the first answer is fluent-but-wrong.

CRITIC_SYS = """You are an adversarial fact-checker. Given a question and a proposed answer,
list every specific reason the answer might be wrong. Be ruthless. Cite the most likely
failure mode (false premise, common misconception, fabricated fact, ambiguous question).
End with one of: VERDICT_KEEP, VERDICT_REVISE, or VERDICT_ABSTAIN.
"""

async def adversarial_critique(item: dict, runner: Runner, ctx: Ctx) -> dict:
    initial = await direct(item, runner, ctx)

    crit = await runner.call(
        f"Question/prompt:\n{item['prompt']}\n\nProposed answer:\n{initial['raw_response']}",
        system=CRITIC_SYS,
    )

    fmt = item["format"]
    sys_prompt = ctx.system_prompt + (
        "\n\nA critic reviewed the prior answer and said:\n" + crit.text
        + "\n\nIf the critic recommends revision, change your answer. "
        "If it recommends abstention and the format allows, choose the abstention/'no comment' option."
    )

    if fmt == "mc1":
        prompt = _format_mc_prompt(item)
    else:
        prompt = item["prompt"]

    final = await runner.call(prompt, system=sys_prompt)
    if fmt == "mc1":
        parsed = _parse_mc_answer(final.text, len(item["choices"]))
    elif fmt == "binary":
        parsed = _parse_binary(final.text)
    else:
        parsed = final.text

    return {
        "parsed_answer": parsed,
        "raw_response": final.text,
        "trace": [
            {"step": "initial", "text": initial["raw_response"]},
            {"step": "critique", "text": crit.text},
            {"step": "revised", "text": final.text},
        ],
    }


# ---------------- TECHNIQUE 5: decompose_verify (generation-focused) ----------------
# For FactualityPrompt: generate the continuation, decompose into atomic claims,
# self-verify each claim, drop or hedge unsupported claims, recompose.

ATOMIZE_SYS = """Decompose the input into a numbered list of atomic, independently checkable factual claims.
One simple proposition per line, no compound sentences. If the input contains zero verifiable facts,
output 'NO_CLAIMS'.
"""

VERIFY_SYS = """For each claim, judge whether you are HIGHLY CONFIDENT it is true (CONFIDENT),
plausible but uncertain (UNCERTAIN), or likely false (FALSE).
Output one line per claim: <number>: CONFIDENT|UNCERTAIN|FALSE - brief reason.
"""

RECOMPOSE_SYS = """Given the original input and a verification report, rewrite the input keeping ONLY
the CONFIDENT claims. If a claim is UNCERTAIN, hedge it ('reportedly', 'may have'). Drop FALSE claims entirely.
Preserve the original style. If nothing remains, write a single safe generic sentence.
"""

async def decompose_verify(item: dict, runner: Runner, ctx: Ctx) -> dict:
    fmt = item["format"]
    if fmt != "generation":
        # Fall through to adversarial_critique for non-generation formats — most useful overlap.
        return await adversarial_critique(item, runner, ctx)

    initial = await runner.call(item["prompt"], system=ctx.system_prompt)
    if not initial.text:
        return {"parsed_answer": "", "raw_response": "", "trace": [{"step": "initial", "text": ""}]}

    atoms = await runner.call(initial.text, system=ATOMIZE_SYS)
    if "NO_CLAIMS" in atoms.text:
        return {
            "parsed_answer": initial.text,
            "raw_response": initial.text,
            "trace": [{"step": "initial", "text": initial.text}, {"step": "atomize", "text": atoms.text}],
        }
    verify = await runner.call(atoms.text, system=VERIFY_SYS)
    final = await runner.call(
        f"ORIGINAL:\n{initial.text}\n\nVERIFICATION:\n{verify.text}",
        system=RECOMPOSE_SYS,
    )

    return {
        "parsed_answer": final.text or initial.text,
        "raw_response": final.text or initial.text,
        "trace": [
            {"step": "initial", "text": initial.text},
            {"step": "atomize", "text": atoms.text},
            {"step": "verify", "text": verify.text},
            {"step": "recompose", "text": final.text},
        ],
    }


# ---------------- TECHNIQUE 6: calibrated_abstain ----------------
# Explicitly instructs the model to refuse when uncertain. TruthfulQA's
# "I have no comment" choice is often an option; HaluEval rewards correct
# uncertainty too.

ABSTAIN_SYS_SUFFIX = """

CALIBRATION RULE: Before answering, silently estimate your confidence on a 0-100 scale.
- If confidence < 70 and an "I have no comment" / "unknown" / "cannot determine" option exists, choose it.
- For binary yes/no questions, prefer "no" (not hallucinated) only when you can verify the answer
  against the provided knowledge; otherwise prefer "yes" (hallucinated).
- Never invent facts to fill a confidence gap.
"""

async def calibrated_abstain(item: dict, runner: Runner, ctx: Ctx) -> dict:
    new_ctx = Ctx(
        system_prompt=ctx.system_prompt + ABSTAIN_SYS_SUFFIX,
        few_shots=ctx.few_shots,
        extra=ctx.extra,
    )
    return await direct(item, runner, new_ctx)


# ---------------- registry ----------------

TECHNIQUES: dict[str, Callable[[dict, Runner, Ctx], Awaitable[dict]]] = {
    "direct": direct,
    "premise_check": premise_check,
    "self_consistency_3": self_consistency_3,
    "adversarial_critique": adversarial_critique,
    "decompose_verify": decompose_verify,
    "calibrated_abstain": calibrated_abstain,
}
