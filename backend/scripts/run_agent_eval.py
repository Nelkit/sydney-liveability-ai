"""Offline LLM-judge evaluator for the chat agent's retrieval grounding.

Reads a fixed prompt set from ``data/eval/prompts.yaml``, runs each prompt
through ``crews.query_crew.run_query``, asks an LLM judge whether every
named-suburb factual claim in the answer is supported by at least one
``evidence_trace`` entry, and writes per-prompt verdicts to
``data/eval/results.csv``.

Single source of truth for the report's retrieval-grounding numbers.
The script is decoupled from the chat hot-path: judging happens out-of-band
so chat latency and cost are unaffected.

Owner: Kai (Ying-Kai Liao)
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

# Make `from crews.query_crew import run_query` importable when this script
# is invoked from the repo root with `python backend/scripts/run_agent_eval.py`.
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import yaml  # noqa: E402  (after sys.path mutation)

from config import get_agent_llm, settings  # noqa: E402
from crews.query_crew import run_query  # noqa: E402


REPO_ROOT = _BACKEND.parent
DEFAULT_PROMPTS_PATH = REPO_ROOT / "data" / "eval" / "prompts.yaml"
DEFAULT_OUTPUT_PATH = REPO_ROOT / "data" / "eval" / "results.csv"

REQUIRED_PROMPT_FIELDS = ("id", "prompt", "expect_grounded", "notes")

CSV_COLUMNS = [
    "id",
    "prompt",
    "answer",
    "retrieval_grounded",
    "expect_grounded",
    "reason",
    "trace_length",
    "n_no_data",
    "judge_model",
    "agent_latency_ms",
]

JUDGE_PROMPT_TEMPLATE = """You are evaluating whether a Sydney-liveability assistant's answer is
grounded in retrieved evidence.

Definition of "grounded": every factual claim that names a Sydney suburb in
the answer is supported by at least one evidence-trace entry. An honest
"I don't have data on <suburb>'s <dimension>" statement counts as grounded
because no fabricated claim was made. A polite refusal that names no
suburbs is also grounded by default (there are no claims to check).

Reply with ONLY a single line of valid JSON, no prose, no code fences:
{{"retrieval_grounded": <true|false>, "reason": "<short explanation>"}}

User prompt: {prompt}

Agent answer: {answer}

Flattened evidence trace ({trace_length} entries):
{trace_block}
"""


def _load_prompts(path: Path) -> list[dict[str, Any]]:
    """Load and validate the prompt set, aborting on the first malformed record."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit(f"Prompts file at {path} must be a YAML list, got {type(raw).__name__}")
    prompts: list[dict[str, Any]] = []
    for idx, record in enumerate(raw, start=1):
        if not isinstance(record, dict):
            raise SystemExit(f"Prompt record #{idx} is not a mapping (got {type(record).__name__})")
        for field in REQUIRED_PROMPT_FIELDS:
            if field not in record:
                raise SystemExit(
                    f"Prompt record #{idx} (id={record.get('id', '?')}) is missing required field '{field}'"
                )
        prompts.append(record)
    return prompts


def _run_agent(prompt: str) -> dict[str, Any]:
    """Run one prompt through the live agent and return the run_query payload.

    The dict carries ``answer``, ``sources``, ``quality``, plus the augmented
    ``outputs`` and ``router`` keys ``run_query`` exposes for offline use, plus
    a measured ``agent_latency_ms``.
    """
    started = time.perf_counter()
    response = run_query(prompt)
    latency_ms = (time.perf_counter() - started) * 1000.0
    response = dict(response)
    response["agent_latency_ms"] = round(latency_ms, 2)
    return response


def _flatten_trace(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ``outputs["sentiment"][*]["evidence_trace"]`` into one list.

    Tags each entry with its suburb so the judge can see which suburb a tool
    call belonged to.
    """
    outputs = response.get("outputs")
    flat: list[dict[str, Any]] = []
    if not isinstance(outputs, dict):
        return flat
    sentiment = outputs.get("sentiment")
    if not isinstance(sentiment, dict):
        return flat
    for suburb, result in sentiment.items():
        if not isinstance(result, dict):
            continue
        for entry in result.get("evidence_trace") or []:
            if isinstance(entry, dict):
                tagged = dict(entry)
                tagged.setdefault("suburb", suburb)
                flat.append(tagged)
    return flat


def _format_trace_for_judge(trace: list[dict[str, Any]]) -> str:
    if not trace:
        return "(no evidence-trace entries this turn)"
    lines: list[str] = []
    for entry in trace:
        args = json.dumps(entry.get("arguments") or {}, default=str)
        preview = str(entry.get("result_preview") or "").replace("\n", " ")[:200]
        lines.append(
            f"- step {entry.get('step')} [{entry.get('suburb', '?')}] "
            f"{entry.get('tool')}({args}) -> n={entry.get('result_count')} | {preview}"
        )
    return "\n".join(lines)


def _judge(prompt: str, answer: str, trace: list[dict[str, Any]], judge_llm) -> dict[str, Any]:
    """Single uniform judge prompt; parse JSON; record parse failure as ungrounded."""
    judge_input = JUDGE_PROMPT_TEMPLATE.format(
        prompt=prompt,
        answer=answer or "(empty)",
        trace_length=len(trace),
        trace_block=_format_trace_for_judge(trace),
    )
    try:
        raw_response = judge_llm.call(judge_input)
    except Exception as exc:  # network / provider failure
        return {"retrieval_grounded": False, "reason": f"judge call failed: {exc!s}[:120]"}

    text = (str(raw_response) if raw_response is not None else "").strip()
    # Strip code fences if the model wrapped them anyway.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    # Pull the first {...} block out, defensively.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"retrieval_grounded": False, "reason": "judge returned invalid JSON"}
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"retrieval_grounded": False, "reason": "judge returned invalid JSON"}
    grounded = parsed.get("retrieval_grounded")
    reason = parsed.get("reason") or ""
    if not isinstance(grounded, bool):
        return {"retrieval_grounded": False, "reason": "judge returned invalid JSON"}
    return {"retrieval_grounded": grounded, "reason": str(reason)[:500]}


def _resolve_judge_model(cli_value: str | None) -> str:
    """Pick the judge model: CLI flag > LLM_AGENT_MODELS_JSON['evaluator'] > LLM_MODEL."""
    if cli_value and cli_value.strip():
        return cli_value.strip()
    raw = (settings.llm_agent_models_json or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                evaluator = parsed.get("evaluator")
                if isinstance(evaluator, str) and evaluator.strip():
                    return evaluator.strip()
        except json.JSONDecodeError:
            pass
    return settings.llm_model


def _build_judge_llm(judge_model: str):
    """Construct the judge LLM under the resolved model name."""
    return get_agent_llm("evaluator", model=judge_model)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS_PATH,
                        help="Path to the prompts YAML file.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH,
                        help="Path to write the results CSV (overwrites existing).")
    parser.add_argument("--judge-model", type=str, default=None,
                        help="Override the judge model name (e.g. claude-opus-4-7).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only the first N prompts (for smoke runs).")
    args = parser.parse_args(argv)

    prompts = _load_prompts(args.prompts)
    if args.limit is not None:
        prompts = prompts[: args.limit]

    judge_model = _resolve_judge_model(args.judge_model)
    judge_llm = _build_judge_llm(judge_model)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    grounded_count = 0
    ungrounded_count = 0
    agreement_count = 0

    for record in prompts:
        prompt_id = str(record["id"])
        prompt_text = str(record["prompt"])
        expect_grounded = bool(record["expect_grounded"])

        try:
            response = _run_agent(prompt_text)
        except Exception as exc:
            reason = f"agent failure: {str(exc)[:200]}"
            print(f"[{prompt_id}] agent ERROR: {str(exc)[:120]}")
            rows.append({
                "id": prompt_id,
                "prompt": prompt_text,
                "answer": "",
                "retrieval_grounded": False,
                "expect_grounded": expect_grounded,
                "reason": reason,
                "trace_length": 0,
                "n_no_data": 0,
                "judge_model": judge_model,
                "agent_latency_ms": 0.0,
            })
            ungrounded_count += 1
            continue

        trace = _flatten_trace(response)
        answer = str(response.get("answer") or "")
        verdict = _judge(prompt_text, answer, trace, judge_llm)

        quality = response.get("quality") or {}
        summary = quality.get("evidence_trace_summary") or {}
        trace_length = int(summary.get("length") or len(trace))
        n_no_data = int(summary.get("no_data_count") or 0)

        rows.append({
            "id": prompt_id,
            "prompt": prompt_text,
            "answer": answer,
            "retrieval_grounded": verdict["retrieval_grounded"],
            "expect_grounded": expect_grounded,
            "reason": verdict["reason"],
            "trace_length": trace_length,
            "n_no_data": n_no_data,
            "judge_model": judge_model,
            "agent_latency_ms": response.get("agent_latency_ms", 0.0),
        })

        if verdict["retrieval_grounded"]:
            grounded_count += 1
        else:
            ungrounded_count += 1
        if verdict["retrieval_grounded"] == expect_grounded:
            agreement_count += 1

        verdict_label = "grounded" if verdict["retrieval_grounded"] else "ungrounded"
        print(f"[{prompt_id}] {verdict_label} — {verdict['reason'][:100]}")

    with args.output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    total = len(rows)
    print(
        f"\n{total} prompts: {grounded_count} grounded, "
        f"{ungrounded_count} ungrounded, {agreement_count} agreement-with-prior"
    )
    print(f"Wrote results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
