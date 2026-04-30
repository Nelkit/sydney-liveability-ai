"""Tests for backend/scripts/run_agent_eval.py — offline evaluator script.

Mocks ``crews.query_crew.run_query`` and the judge LLM so the test stays
pure-Python and asserts the CSV schema, summary line, and prompt-set
validation.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "scripts"))


@pytest.fixture
def prompts_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "prompts.yaml"
    p.write_text(
        "- id: spatial-grounded-001\n"
        "  prompt: How is transport in Newtown?\n"
        "  expect_grounded: true\n"
        "  notes: stub\n"
        "- id: out-of-scope-001\n"
        "  prompt: What's 2+2?\n"
        "  expect_grounded: true\n"
        "  notes: stub\n",
        encoding="utf-8",
    )
    return p


def _stub_run_query(prompt: str):
    if "Newtown" in prompt:
        return {
            "answer": "Newtown has decent transport.",
            "sources": [],
            "suburb_scores": [],
            "map_state": None,
            "outputs": {
                "sentiment": {
                    "Newtown": {
                        "evidence_trace": [
                            {
                                "step": 1,
                                "tool": "get_suburb_aspect",
                                "arguments": {"suburb": "Newtown", "dimension": "transport"},
                                "reasoning": "lookup",
                                "result_count": 1,
                                "result_preview": "score=0.62",
                                "elapsed_ms": 1.0,
                            }
                        ]
                    }
                }
            },
            "router": {"categories": ["sentiment"], "suburbs_mentioned": ["Newtown"]},
            "quality": {
                "evidence_trace_summary": {
                    "length": 1,
                    "by_tool": {"get_suburb_aspect": 1},
                    "last_action": {
                        "step": 1, "tool": "get_suburb_aspect",
                        "suburb": "Newtown", "dimension": "transport", "result_count": 1,
                    },
                    "no_data_count": 0,
                }
            },
        }
    # out_of_scope
    return {
        "answer": "I only answer Sydney liveability questions.",
        "sources": [],
        "suburb_scores": [],
        "map_state": None,
        "outputs": {},
        "router": {"categories": ["out_of_scope"], "suburbs_mentioned": []},
        "quality": {
            "evidence_trace_summary": {
                "length": 0, "by_tool": {}, "last_action": None, "n_no_data": 0,
            }
        },
    }


class _StubJudgeLLM:
    def call(self, prompt: str) -> str:
        return '{"retrieval_grounded": true, "reason": "stubbed grounded verdict"}'


def _import_main(monkeypatch):
    pytest.importorskip("yaml")
    pytest.importorskip("crewai")
    import run_agent_eval

    monkeypatch.setattr(run_agent_eval, "run_query", _stub_run_query)
    monkeypatch.setattr(run_agent_eval, "_build_judge_llm", lambda model: _StubJudgeLLM())
    return run_agent_eval


def test_eval_writes_well_formed_csv(monkeypatch, tmp_path, prompts_yaml, capsys) -> None:
    run_agent_eval = _import_main(monkeypatch)
    output = tmp_path / "results.csv"
    rc = run_agent_eval.main([
        "--prompts", str(prompts_yaml),
        "--output", str(output),
        "--judge-model", "stub-model",
    ])
    assert rc == 0
    assert output.exists()
    rows = list(csv.DictReader(output.open(encoding="utf-8")))
    assert len(rows) == 2
    expected_cols = set(run_agent_eval.CSV_COLUMNS)
    for row in rows:
        assert set(row.keys()) == expected_cols
        assert row["judge_model"] == "stub-model"
        assert row["retrieval_grounded"] in {"True", "False"}
    captured = capsys.readouterr().out
    assert "agreement-with-prior" in captured


def test_load_prompts_rejects_missing_field(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "- id: only-id\n  prompt: missing other fields\n",
        encoding="utf-8",
    )
    pytest.importorskip("yaml")
    pytest.importorskip("crewai")
    import run_agent_eval

    with pytest.raises(SystemExit) as excinfo:
        run_agent_eval._load_prompts(bad)
    assert "record #1" in str(excinfo.value)
