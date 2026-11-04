"""Regression tests for the final-checklist verification pass."""

import json
from pathlib import Path

from app.core.evaluator import evaluate_candidate
from app.ir.lowering import lower_problem
from app.ir.models import CandidateDesign, ProjectIR
from app.search.runner import execute_search

DATA = Path(__file__).resolve().parents[3] / "data" / "projects"


def _load(name: str) -> ProjectIR:
    return ProjectIR.model_validate(json.loads((DATA / f"{name}.json").read_text()))


def test_walkthrough_accelerated_latency_is_8_5_ms():
    """Resolves the 6.5 vs 8.5 ms discrepancy: 3 + 0.75 + 1 + 0.75 + 3 = 8.5."""
    lowered = lower_problem(_load("synthetic-walkthrough"))
    res = evaluate_candidate(
        lowered, CandidateDesign(id="acc", bindings={"T1": "CPU", "T2": "ACC1", "T3": "CPU"})
    )
    assert abs(res.latency_ms - 8.5) < 1e-9


def test_impossible_latency_marks_all_infeasible_and_flags_recommendation():
    proj = _load("synthetic-walkthrough")
    proj.constraints.max_latency_ms = 0.1
    all_c, front, rec, details = execute_search(lower_problem(proj))
    assert all_c and not any(c.evaluation.feasible for c in all_c)
    assert rec is not None and not rec.evaluation.feasible
    assert "no feasible design" in details.rationale


def test_simple_preset_area_counted_once():
    """Accelerator area must not be double counted (resource.area + option.usage)."""
    from app.ir.models import DataEdge
    from app.ir.presets import SimplePlatformConfig, SimpleTaskConfig, lower_simple_preset

    tasks = [
        SimpleTaskConfig(id="A", name="A", sw_cycles=3_000_000, hw_cycles=1_000_000, hw_luts=200, hw_dsps=1),
        SimpleTaskConfig(id="B", name="B", sw_cycles=5_000_000, hw_cycles=800_000, hw_luts=800, hw_dsps=4),
    ]
    proj = lower_simple_preset("t", "t", tasks, [DataEdge(source_id="A", destination_id="B", data_kb=4.0)], SimplePlatformConfig())
    res = evaluate_candidate(
        lower_problem(proj), CandidateDesign(id="x", bindings={"A": "ACC_A", "B": "ACC_B"})
    )
    assert res.area_usage["luts"] == 1000.0  # 200 + 800
    assert res.area_usage["dsps"] == 5.0     # 1 + 4
