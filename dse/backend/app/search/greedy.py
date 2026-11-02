"""Greedy local search strategy with restarts.

Implements Section 10.3:
- Starts from valid low-cost legal binding
- Generates 1-change neighbours (rebind one task)
- Evaluates neighbours using common evaluator
- Selects best improving candidate under weighted normalized score
- Stops at local optimum or budget limit; restarts with seed
"""

import random
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.ir.models import CandidateDesign
from app.ir.lowering import LoweredProblem
from app.core.evaluator import derive_canonical_allocation, evaluate_candidate
from app.search.pareto import extract_objective_value


def _candidate_score(
    candidate: CandidateDesign,
    objectives: List[str],
    weights: Dict[str, float],
) -> float:
    """Computes a penalty score to minimize (infeasible designs heavily penalized)."""
    ev = candidate.evaluation
    if not ev:
        return float("inf")
    if not ev.feasible:
        # Feasible designs always rank ahead of infeasible ones
        return 1e6 + len(ev.violations) * 1e4

    score = 0.0
    for obj in objectives:
        val = extract_objective_value(ev, obj)
        w = weights.get(obj, 1.0)
        if val is not None:
            score += w * val
    return score


def run_greedy_search(
    lowered: LoweredProblem,
    budget: int = 200,
    seed: int = 42,
    objectives: Optional[List[str]] = None,
    weights: Optional[Dict[str, float]] = None,
    progress_callback: Optional[Callable[[int, int, CandidateDesign], None]] = None,
) -> List[CandidateDesign]:
    """Runs greedy local search with seeded restarts."""
    rng = random.Random(seed)
    if objectives is None or not objectives:
        objectives = ["latency", "allocation_cost"]
    if weights is None:
        weights = {obj: 1.0 / len(objectives) for obj in objectives}

    tasks = sorted(list(lowered.nodes_by_id.keys()))
    seen_signatures: Set[Tuple[Tuple[str, str], ...]] = set()
    evaluated_archive: List[CandidateDesign] = []

    def evaluate_and_record(candidate: CandidateDesign) -> float:
        sig = tuple(sorted(candidate.bindings.items()))
        if sig in seen_signatures:
            # Already evaluated
            for c in evaluated_archive:
                if tuple(sorted(c.bindings.items())) == sig:
                    candidate.evaluation = c.evaluation
                    return _candidate_score(c, objectives, weights)
        seen_signatures.add(sig)
        evaluate_candidate(lowered, candidate)
        evaluated_archive.append(candidate)
        if progress_callback:
            progress_callback(len(evaluated_archive), budget, candidate)
        return _candidate_score(candidate, objectives, weights)

    total_possible = 1
    for t in tasks:
        node = lowered.nodes_by_id[t]
        if not node.fixed_resource_id:
            total_possible *= len(lowered.mapping_options_by_node[t])

    effective_budget = min(budget, total_possible)
    eval_count = 0
    restart_num = 0
    consecutive_empty_restarts = 0

    while len(evaluated_archive) < effective_budget and consecutive_empty_restarts < 10:
        restart_num += 1
        prev_archive_size = len(evaluated_archive)
        # 1. Generate starting point for this restart
        start_bindings: Dict[str, str] = {}
        for t in tasks:
            node = lowered.nodes_by_id[t]
            if node.fixed_resource_id:
                start_bindings[t] = node.fixed_resource_id
            else:
                opts = sorted(list(lowered.mapping_options_by_node[t].keys()))
                if restart_num == 1:
                    # Initial run: pick lowest execution time option
                    opts.sort(key=lambda r: lowered.mapping_options_by_node[t][r].execution_time_ms)
                    start_bindings[t] = opts[0]
                else:
                    start_bindings[t] = rng.choice(opts)

        current = CandidateDesign(
            id=f"greedy_r{restart_num}_0000",
            bindings=start_bindings,
            allocated_resources=derive_canonical_allocation(lowered, start_bindings),
        )
        current_score = evaluate_and_record(current)

        # 2. Local search around current point
        step = 0
        while len(evaluated_archive) < budget:
            step += 1
            best_neighbor: Optional[CandidateDesign] = None
            best_neighbor_score = current_score

            # Generate all 1-change neighbors
            for t in tasks:
                node = lowered.nodes_by_id[t]
                if node.fixed_resource_id:
                    continue  # Cannot rebind fixed task

                all_opts = sorted(list(lowered.mapping_options_by_node[t].keys()))
                curr_res = current.bindings[t]

                for alt_res in all_opts:
                    if alt_res == curr_res:
                        continue
                    if len(evaluated_archive) >= budget:
                        break

                    neighbor_bindings = dict(current.bindings)
                    neighbor_bindings[t] = alt_res

                    cand = CandidateDesign(
                        id=f"greedy_r{restart_num}_{step:04d}",
                        bindings=neighbor_bindings,
                        allocated_resources=derive_canonical_allocation(lowered, neighbor_bindings),
                    )
                    n_score = evaluate_and_record(cand)
                    if n_score < best_neighbor_score - 1e-6:
                        best_neighbor_score = n_score
                        best_neighbor = cand

            if best_neighbor is not None and best_neighbor_score < current_score - 1e-6:
                # Move to improving neighbor
                current = best_neighbor
                current_score = best_neighbor_score
            else:
                # Local optimum reached for this restart
                break

        if len(evaluated_archive) == prev_archive_size:
            consecutive_empty_restarts += 1
        else:
            consecutive_empty_restarts = 0

    return evaluated_archive
