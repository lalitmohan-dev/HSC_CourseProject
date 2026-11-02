"""Unit tests for Pareto dominance, front extraction, and design recommendation."""

import pytest
from app.ir.models import CandidateDesign, EvaluationResult
from app.search.pareto import (
    dominates,
    extract_pareto_front,
    recommend_design,
)


def make_eval(design_id: str, latency: float, cost: float, feasible: bool = True) -> CandidateDesign:
    res = EvaluationResult(
        design_id=design_id,
        feasible=feasible,
        latency_ms=latency,
        allocation_cost=cost,
    )
    return CandidateDesign(
        id=design_id,
        bindings={"T1": design_id},
        evaluation=res,
    )


def test_pareto_dominance():
    # A is strictly better than B in both objectives
    a = make_eval("A", latency=5.0, cost=10.0)
    b = make_eval("B", latency=8.0, cost=15.0)
    assert dominates(a.evaluation, b.evaluation, ["latency", "allocation_cost"]) is True
    assert dominates(b.evaluation, a.evaluation, ["latency", "allocation_cost"]) is False

    # Tradeoff: C is faster but more expensive than D
    c = make_eval("C", latency=3.0, cost=20.0)
    d = make_eval("D", latency=6.0, cost=10.0)
    assert dominates(c.evaluation, d.evaluation, ["latency", "allocation_cost"]) is False
    assert dominates(d.evaluation, c.evaluation, ["latency", "allocation_cost"]) is False


def test_pareto_front_extraction():
    cands = [
        make_eval("A", latency=10.0, cost=10.0),  # Pareto
        make_eval("B", latency=5.0, cost=25.0),   # Pareto
        make_eval("C", latency=12.0, cost=15.0),  # Dominated by A
        make_eval("D", latency=8.0, cost=30.0),   # Dominated by B
        make_eval("E", latency=2.0, cost=50.0),   # Pareto
    ]
    front = extract_pareto_front(cands, ["latency", "allocation_cost"])
    front_ids = {c.id for c in front}
    assert front_ids == {"A", "B", "E"}


def test_recommendation_weighting():
    fast = make_eval("Fast", latency=2.0, cost=100.0)
    cheap = make_eval("Cheap", latency=20.0, cost=5.0)
    pareto = [fast, cheap]

    # Prioritize latency: weights {"latency": 0.9, "allocation_cost": 0.1}
    best_fast, details_fast = recommend_design(pareto, ["latency", "allocation_cost"], {"latency": 0.9, "allocation_cost": 0.1})
    assert best_fast.id == "Fast"
    assert "optimal weighted balance score" in details_fast.rationale

    # Prioritize cost: weights {"latency": 0.1, "allocation_cost": 0.9}
    best_cheap, details_cheap = recommend_design(pareto, ["latency", "allocation_cost"], {"latency": 0.1, "allocation_cost": 0.9})
    assert best_cheap.id == "Cheap"
