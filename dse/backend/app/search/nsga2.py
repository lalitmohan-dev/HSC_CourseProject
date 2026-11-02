"""NSGA-II multi-objective evolutionary search strategy.

Implements Section 10.4:
- Constraint-dominated sorting (feasible designs rank ahead of infeasible)
- Non-dominated sorting and crowding distance
- Genome representation: categorical task-to-resource binding
- Preserves fixed/pinned task bindings during initialization, crossover, and mutation
- Evaluates candidates using common candidate evaluator
"""

import math
import random
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.ir.models import CandidateDesign
from app.ir.lowering import LoweredProblem
from app.core.evaluator import derive_canonical_allocation, evaluate_candidate
from app.search.pareto import dominates, extract_objective_value


def run_nsga2_search(
    lowered: LoweredProblem,
    population_size: int = 40,
    generations: int = 25,
    seed: int = 42,
    objectives: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int, CandidateDesign], None]] = None,
) -> List[CandidateDesign]:
    """Runs NSGA-II multi-objective genetic optimization."""
    rng = random.Random(seed)
    if objectives is None or not objectives:
        objectives = ["latency", "allocation_cost"]

    tasks = sorted(list(lowered.nodes_by_id.keys()))
    seen_signatures: Set[Tuple[Tuple[str, str], ...]] = set()
    evaluated_archive: List[CandidateDesign] = []
    total_eval_budget = population_size * generations

    def evaluate_individual(cand: CandidateDesign) -> CandidateDesign:
        sig = tuple(sorted(cand.bindings.items()))
        if sig in seen_signatures:
            for existing in evaluated_archive:
                if tuple(sorted(existing.bindings.items())) == sig:
                    cand.evaluation = existing.evaluation
                    return cand
        seen_signatures.add(sig)
        evaluate_candidate(lowered, cand)
        evaluated_archive.append(cand)
        if progress_callback:
            progress_callback(len(evaluated_archive), total_eval_budget, cand)
        return cand

    def make_random_individual(idx: int) -> CandidateDesign:
        bindings: Dict[str, str] = {}
        for t in tasks:
            node = lowered.nodes_by_id[t]
            if node.fixed_resource_id:
                bindings[t] = node.fixed_resource_id
            else:
                legal = sorted(list(lowered.mapping_options_by_node[t].keys()))
                bindings[t] = rng.choice(legal)
        return CandidateDesign(
            id=f"nsga2_init_{idx:04d}",
            bindings=bindings,
            allocated_resources=derive_canonical_allocation(lowered, bindings),
        )

    # 1. Initialize Population
    population: List[CandidateDesign] = []
    for i in range(population_size):
        ind = make_random_individual(i + 1)
        evaluate_individual(ind)
        population.append(ind)

    # 2. Evolutionary Loop
    for gen in range(1, generations):
        if len(evaluated_archive) >= total_eval_budget:
            break

        # Fast non-dominated sorting and crowding distance assignment on current population
        fronts = _fast_non_dominated_sort(population, objectives)
        for front in fronts:
            _assign_crowding_distance(front, objectives)

        # Tournament selection and offspring creation
        offspring: List[CandidateDesign] = []
        while len(offspring) < population_size:
            p1 = _tournament_select(population, rng)
            p2 = _tournament_select(population, rng)

            # Crossover
            child_bindings: Dict[str, str] = {}
            for t in tasks:
                node = lowered.nodes_by_id[t]
                if node.fixed_resource_id:
                    child_bindings[t] = node.fixed_resource_id
                else:
                    child_bindings[t] = p1.bindings[t] if rng.random() < 0.5 else p2.bindings[t]

            # Mutation
            for t in tasks:
                node = lowered.nodes_by_id[t]
                if not node.fixed_resource_id and rng.random() < 0.2:
                    legal = sorted(list(lowered.mapping_options_by_node[t].keys()))
                    if len(legal) > 1:
                        child_bindings[t] = rng.choice(legal)

            child = CandidateDesign(
                id=f"nsga2_g{gen}_{len(offspring) + 1:04d}",
                bindings=child_bindings,
                allocated_resources=derive_canonical_allocation(lowered, child_bindings),
            )
            evaluate_individual(child)
            offspring.append(child)

        # Combine parent + offspring (2N) and select top N
        combined = population + offspring
        combined_fronts = _fast_non_dominated_sort(combined, objectives)

        new_population: List[CandidateDesign] = []
        for front in combined_fronts:
            _assign_crowding_distance(front, objectives)
            if len(new_population) + len(front) <= population_size:
                new_population.extend(front)
            else:
                # Sort remaining front by crowding distance descending
                front.sort(key=lambda ind: getattr(ind, "_crowding_dist", 0.0), reverse=True)
                needed = population_size - len(new_population)
                new_population.extend(front[:needed])
                break

        population = new_population

    return evaluated_archive


def _fast_non_dominated_sort(
    population: List[CandidateDesign],
    objectives: List[str],
) -> List[List[CandidateDesign]]:
    """Partitions population into non-dominated Pareto fronts."""
    fronts: List[List[CandidateDesign]] = [[]]
    domination_count: Dict[str, int] = {}
    dominated_solutions: Dict[str, List[CandidateDesign]] = {}

    for p in population:
        p_id = p.id
        domination_count[p_id] = 0
        dominated_solutions[p_id] = []

        for q in population:
            if p.id == q.id:
                continue
            if dominates(p.evaluation, q.evaluation, objectives):
                dominated_solutions[p_id].append(q)
            elif dominates(q.evaluation, p.evaluation, objectives):
                domination_count[p_id] += 1

        if domination_count[p_id] == 0:
            setattr(p, "_rank", 0)
            fronts[0].append(p)

    current_front_idx = 0
    while fronts[current_front_idx]:
        next_front: List[CandidateDesign] = []
        for p in fronts[current_front_idx]:
            for q in dominated_solutions[p.id]:
                domination_count[q.id] -= 1
                if domination_count[q.id] == 0:
                    setattr(q, "_rank", current_front_idx + 1)
                    next_front.append(q)
        current_front_idx += 1
        fronts.append(next_front)

    return [f for f in fronts if f]


def _assign_crowding_distance(front: List[CandidateDesign], objectives: List[str]) -> None:
    """Calculates and assigns crowding distance to maintain diversity in each front."""
    l = len(front)
    if l == 0:
        return
    for ind in front:
        setattr(ind, "_crowding_dist", 0.0)

    if l <= 2:
        for ind in front:
            setattr(ind, "_crowding_dist", float("inf"))
        return

    for obj in objectives:
        front.sort(key=lambda ind: extract_objective_value(ind.evaluation, obj) or 0.0)
        setattr(front[0], "_crowding_dist", float("inf"))
        setattr(front[-1], "_crowding_dist", float("inf"))

        min_val = extract_objective_value(front[0].evaluation, obj) or 0.0
        max_val = extract_objective_value(front[-1].evaluation, obj) or 0.0
        spread = max_val - min_val

        if spread > 1e-9:
            for i in range(1, l - 1):
                prev_val = extract_objective_value(front[i - 1].evaluation, obj) or 0.0
                next_val = extract_objective_value(front[i + 1].evaluation, obj) or 0.0
                current_dist = getattr(front[i], "_crowding_dist", 0.0)
                setattr(front[i], "_crowding_dist", current_dist + (next_val - prev_val) / spread)


def _tournament_select(population: List[CandidateDesign], rng: random.Random) -> CandidateDesign:
    """Binary tournament selection favoring lower rank and higher crowding distance."""
    a, b = rng.sample(population, 2)
    rank_a = getattr(a, "_rank", 9999)
    rank_b = getattr(b, "_rank", 9999)

    if rank_a < rank_b:
        return a
    elif rank_b < rank_a:
        return b
    else:
        dist_a = getattr(a, "_crowding_dist", 0.0)
        dist_b = getattr(b, "_crowding_dist", 0.0)
        return a if dist_a >= dist_b else b
