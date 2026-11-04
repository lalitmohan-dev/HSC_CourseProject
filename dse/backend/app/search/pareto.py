"""Pareto optimality, non-dominated sorting, and transparent design recommendation.

Implements Section 10.5 and 10.6 of the specification:
- Non-dominated sorting over user-selected minimization objectives
- Deduplication of identical candidates
- Transparent recommendation using min-max normalized weighted sum
- Deterministic tie-breaking (latency, allocation_cost, stable design ID)
- Detailed justification generation comparing the recommendation to Pareto alternatives
"""

from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from app.ir.models import CandidateDesign, EvaluationResult


class RecommendationDetails(BaseModel):
    """Detailed justification for why a particular design was recommended."""
    recommended_design_id: str
    objectives_used: List[str]
    weights: Dict[str, float]
    normalized_scores: Dict[str, float]  # design_id -> score
    rationale: str
    tradeoffs: List[str] = Field(default_factory=list)


def extract_objective_value(eval_res: EvaluationResult, obj_name: str) -> Optional[float]:
    """Extract numeric value for a given objective name (always formulated as minimization)."""
    if obj_name in ("latency", "latency_ms"):
        return eval_res.latency_ms
    elif obj_name in ("allocation_cost", "cost"):
        return eval_res.allocation_cost
    elif obj_name in ("energy", "energy_mj"):
        return eval_res.energy_mj
    elif obj_name in ("power", "avg_power_w", "avg_power"):
        return eval_res.avg_power_w
    elif obj_name in ("area", "logic_area"):
        return eval_res.area_usage.get("logic", 0.0)
    elif obj_name == "throughput":
        # Throughput is maximized; negate it for minimization comparisons
        return -eval_res.throughput_fps if eval_res.throughput_fps is not None else None
    return getattr(eval_res, obj_name, None)


def dominates(
    eval_a: EvaluationResult,
    eval_b: EvaluationResult,
    objectives: List[str],
) -> bool:
    """Returns True if candidate A dominates candidate B on all specified objectives.

    A dominates B if A is no worse than B on every objective and strictly better on at least one.
    """
    if not eval_a.feasible and eval_b.feasible:
        return False
    if eval_a.feasible and not eval_b.feasible:
        return True
    if not eval_a.feasible and not eval_b.feasible:
        # Fewer constraint violations dominates
        return len(eval_a.violations) < len(eval_b.violations)

    strictly_better = False
    for obj in objectives:
        val_a = extract_objective_value(eval_a, obj)
        val_b = extract_objective_value(eval_b, obj)

        if val_a is None or val_b is None:
            continue

        if val_a > val_b + 1e-9:  # A is worse (since we minimize)
            return False
        if val_a < val_b - 1e-9:  # A is strictly better
            strictly_better = True

    return strictly_better


def extract_pareto_front(
    candidates: List[CandidateDesign],
    objectives: Optional[List[str]] = None,
) -> List[CandidateDesign]:
    """Computes the first non-dominated front (Pareto optimal set) of feasible designs."""
    if objectives is None or not objectives:
        objectives = ["latency", "allocation_cost"]

    # Filter to feasible designs with valid evaluations
    evaluated = [c for c in candidates if c.evaluation is not None]
    feasible_candidates = [c for c in evaluated if c.evaluation.feasible]

    if not feasible_candidates:
        # If no feasible candidate exists, return least-violating candidates
        if not evaluated:
            return []
        min_violations = min(len(c.evaluation.violations) for c in evaluated)
        least_violating = [c for c in evaluated if len(c.evaluation.violations) == min_violations]
        return least_violating

    pareto_front: List[CandidateDesign] = []

    for i, cand_a in enumerate(feasible_candidates):
        is_dominated = False
        eval_a = cand_a.evaluation

        for j, cand_b in enumerate(feasible_candidates):
            if i == j:
                continue
            eval_b = cand_b.evaluation
            if dominates(eval_b, eval_a, objectives):
                is_dominated = True
                break

        if not is_dominated:
            # Check for duplicates before adding
            signature = (tuple(sorted(cand_a.bindings.items())), tuple(sorted(cand_a.allocated_resources)))
            if not any(
                (tuple(sorted(p.bindings.items())), tuple(sorted(p.allocated_resources))) == signature
                for p in pareto_front
            ):
                pareto_front.append(cand_a)

    return pareto_front


def recommend_design(
    pareto_candidates: List[CandidateDesign],
    objectives: Optional[List[str]] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Tuple[Optional[CandidateDesign], Optional[RecommendationDetails]]:
    """Recommends one design from the Pareto set using min-max normalized weighted sum.

    Tie-break order: lower latency, lower allocation cost, stable design ID.
    """
    if not pareto_candidates:
        return None, None

    if objectives is None or not objectives:
        objectives = ["latency", "allocation_cost"]

    if weights is None:
        weights = {obj: 1.0 / len(objectives) for obj in objectives}
    else:
        # Normalize weights to sum to 1.0
        total_w = sum(weights.get(obj, 1.0) for obj in objectives)
        weights = {obj: weights.get(obj, 1.0) / (total_w if total_w > 0 else 1.0) for obj in objectives}

    # Extract min and max values for each objective across the Pareto front
    min_vals: Dict[str, float] = {}
    max_vals: Dict[str, float] = {}

    for obj in objectives:
        vals = [
            extract_objective_value(c.evaluation, obj)
            for c in pareto_candidates
            if extract_objective_value(c.evaluation, obj) is not None
        ]
        if vals:
            min_vals[obj] = min(vals)
            max_vals[obj] = max(vals)
        else:
            min_vals[obj] = 0.0
            max_vals[obj] = 1.0

    scores: Dict[str, float] = {}
    for c in pareto_candidates:
        total_score = 0.0
        for obj in objectives:
            val = extract_objective_value(c.evaluation, obj)
            w = weights.get(obj, 1.0)
            if val is not None:
                spread = max_vals[obj] - min_vals[obj]
                norm_val = (val - min_vals[obj]) / spread if spread > 1e-9 else 0.0
                total_score += w * norm_val
        scores[c.id] = total_score

    # Sort by score ascending, then latency, then allocation cost, then ID
    def sort_key(c: CandidateDesign) -> Tuple[float, float, float, str]:
        ev = c.evaluation
        lat = ev.latency_ms if ev else float("inf")
        cost = ev.allocation_cost if ev else float("inf")
        return (scores.get(c.id, float("inf")), lat, cost, c.id)

    sorted_pareto = sorted(pareto_candidates, key=sort_key)
    best = sorted_pareto[0]

    # Build justification rationale
    best_ev = best.evaluation
    rationale_parts = [
        f"Design '{best.id}' achieves the optimal weighted balance score of {scores[best.id]:.3f} "
        f"across objectives {', '.join(objectives)}."
    ]
    if best_ev:
        rationale_parts.append(
            f"Latency: {best_ev.latency_ms:.2f} (project time unit), Allocation Cost: {best_ev.allocation_cost:.1f}."
        )
        if not best_ev.feasible:
            rationale_parts.insert(
                0,
                "WARNING: no feasible design exists under the current constraints; "
                "this is the least-violating fallback, not a feasible recommendation.",
            )

    tradeoffs = []
    for other in sorted_pareto[1:4]:
        o_ev = other.evaluation
        if o_ev and best_ev:
            diffs = []
            if o_ev.latency_ms < best_ev.latency_ms:
                diffs.append(f"{best_ev.latency_ms - o_ev.latency_ms:.2f} ms faster")
            if o_ev.allocation_cost < best_ev.allocation_cost:
                diffs.append(f"{best_ev.allocation_cost - o_ev.allocation_cost:.1f} cheaper")
            if diffs:
                tradeoffs.append(f"Alternative '{other.id}' is {', '.join(diffs)} but higher in weighted penalty.")

    details = RecommendationDetails(
        recommended_design_id=best.id,
        objectives_used=objectives,
        weights=weights,
        normalized_scores=scores,
        rationale=" ".join(rationale_parts),
        tradeoffs=tradeoffs,
    )

    return best, details
