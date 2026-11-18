"""Tests for the parallel specialist execution helpers in crews/query_crew.py."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def crew():
    pytest.importorskip("crewai")
    from crews import query_crew

    return query_crew


def _slow_runner(name: str, delay: float, calls: list):
    def run(input_data):
        calls.append((name, input_data["suburb"], threading.get_ident()))
        time.sleep(delay)
        return {"suburb": input_data["suburb"], "agent": name}

    return run


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def test_plan_runs_each_category_for_each_suburb(crew):
    tasks = crew._plan_specialist_tasks(["crime", "sentiment"], ["Newtown", "Glebe"])
    assert tasks == [
        ("crime", "Newtown"),
        ("crime", "Glebe"),
        ("sentiment", "Newtown"),
        ("sentiment", "Glebe"),
    ]


def test_plan_comparator_adds_missing_specialists_for_first_two_suburbs(crew):
    tasks = crew._plan_specialist_tasks(["comparator", "crime"], ["A", "B", "C"])
    assert ("crime", "C") in tasks
    assert ("sentiment", "A") in tasks and ("sentiment", "B") in tasks
    assert ("gis", "A") in tasks and ("gis", "B") in tasks
    assert ("sentiment", "C") not in tasks and ("gis", "C") not in tasks


def test_plan_skips_specialists_already_run(crew):
    tasks = crew._plan_specialist_tasks(["gis", "crime"], ["A"], skip={"gis"})
    assert tasks == [("crime", "A")]


def test_plan_without_suburbs_is_empty(crew):
    assert crew._plan_specialist_tasks(["crime"], []) == []


# ---------------------------------------------------------------------------
# Blocking parallel execution
# ---------------------------------------------------------------------------


def test_run_parallel_overlaps_tasks_and_groups_outputs(crew):
    calls: list = []
    runners = {"crime": _slow_runner("crime", 0.3, calls), "sentiment": _slow_runner("sentiment", 0.3, calls)}
    tasks = [("crime", "A"), ("crime", "B"), ("sentiment", "A"), ("sentiment", "B")]

    started = time.perf_counter()
    outputs, timings = crew._run_specialists_parallel(tasks, "q", runners=runners)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.9  # sequential would take ~1.2s
    assert outputs["crime"]["A"] == {"suburb": "A", "agent": "crime"}
    assert outputs["sentiment"]["B"] == {"suburb": "B", "agent": "sentiment"}
    assert list(outputs["crime"].keys()) == ["A", "B"]  # planned order kept
    assert set(timings) == {"crime", "sentiment"}


def test_run_parallel_turns_exceptions_into_error_payloads(crew):
    def boom(_):
        raise RuntimeError("db down")

    outputs, _ = crew._run_specialists_parallel([("crime", "A")], "q", runners={"crime": boom})
    assert outputs["crime"]["A"]["status"] == "error"
    assert "db down" in outputs["crime"]["A"]["reason"]


def test_run_parallel_passes_question_to_runner(crew):
    seen = {}

    def run(input_data):
        seen.update(input_data)
        return {}

    crew._run_specialists_parallel([("sentiment", "A")], "is it quiet?", runners={"sentiment": run})
    assert seen == {"suburb": "A", "question": "is it quiet?"}


# ---------------------------------------------------------------------------
# Streaming parallel execution
# ---------------------------------------------------------------------------


def test_stream_parallel_yields_heartbeats_then_result(crew):
    calls: list = []
    runners = {"gis": _slow_runner("gis", 0.35, calls)}
    events = list(
        crew._stream_specialists_parallel(
            [("gis", "A"), ("gis", "B")], "q", runners=runners, heartbeat_interval=0.1
        )
    )

    kinds = [kind for kind, _ in events]
    assert kinds[-1] == "result"
    assert "step" in kinds
    outputs, timings = events[-1][1]
    assert set(outputs["gis"]) == {"A", "B"}
    assert "gis" in timings


def test_stream_parallel_enforces_timeout_without_blocking(crew):
    def hang(_):
        time.sleep(2.0)
        return {"never": True}

    started = time.perf_counter()
    events = list(
        crew._stream_specialists_parallel(
            [("crime", "A")], "q", runners={"crime": hang}, timeouts={"crime": 0.3}
        )
    )
    elapsed = time.perf_counter() - started

    outputs, _ = events[-1][1]
    assert outputs["crime"]["A"]["status"] == "error"
    assert "timed out" in outputs["crime"]["A"]["reason"]
    assert elapsed < 1.5  # must not wait for the hung worker to finish
