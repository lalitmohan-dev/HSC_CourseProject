"""Unified search runner orchestrating all DSE exploration strategies.

Integrates:
- Exhaustive Search
- Random Sampling
- Greedy Local Search
- NSGA-II Genetic Optimization
- Pareto Front Extraction & Recommendation
"""

from typing import Callable, Dict, List, Optional, Tuple

from app.ir.models import CandidateDesign, SearchSettings
from app.ir.lowering import LoweredProblem
from app.ir.types import SearchStrategy
from app.search.candidate import estimate_candidate_count
from app.search.exhaustive import run_exhaustive_search
from app.search.random_search import run_random_search
from app.search.greedy import run_greedy_search
from app.search.nsga2 import run_nsga2_search
from app.search.pareto import (
    RecommendationDetails,
    extract_pareto_front,
    recommend_design,
)


def execute_search(
    lowered: LoweredProblem,
    settings: Optional[SearchSettings] = None,
    progress_callback: Optional[Callable[[int, int, CandidateDesign], None]] = None,
) -> Tuple[List[CandidateDesign], List[CandidateDesign], Optional[CandidateDesign], Optional[RecommendationDetails]]:
    """Executes the chosen search strategy and returns evaluated candidates, Pareto front, and recommendation.

    Returns:
        (all_evaluated, pareto_front, recommended_candidate, recommendation_details)
    """
    if settings is None:
        settings = lowered.project.settings

    strategy = settings.strategy
    budget = settings.budget_evaluations or 1000
    seed = settings.seed if settings.seed is not None else 42
    objectives = lowered.project.objectives.names or ["latency", "allocation_cost"]
    weights = lowered.project.objectives.weights

    all_evaluated: List[CandidateDesign] = []

    if strategy == SearchStrategy.EXHAUSTIVE:
        all_evaluated = run_exhaustive_search(
            lowered=lowered,
            budget=budget,
            progress_callback=progress_callback,
        )
    elif strategy == SearchStrategy.RANDOM:
        all_evaluated = run_random_search(
            lowered=lowered,
            budget=budget,
            seed=seed,
            progress_callback=progress_callback,
        )
    elif strategy == SearchStrategy.GREEDY:
        all_evaluated = run_greedy_search(
            lowered=lowered,
            budget=budget,
            seed=seed,
            objectives=objectives,
            weights=weights,
            progress_callback=progress_callback,
        )
    elif strategy == SearchStrategy.NSGA2:
        pop_size = settings.population_size or 40
        generations = max(1, budget // pop_size)
        all_evaluated = run_nsga2_search(
            lowered=lowered,
            population_size=pop_size,
            generations=generations,
            seed=seed,
            objectives=objectives,
            progress_callback=progress_callback,
        )
    else:
        # Fallback to random
        all_evaluated = run_random_search(
            lowered=lowered,
            budget=budget,
            seed=seed,
            progress_callback=progress_callback,
        )

    # Compute Pareto Front
    pareto_front = extract_pareto_front(all_evaluated, objectives=objectives)

    # Compute Recommendation
    best_cand, rec_details = recommend_design(
        pareto_front,
        objectives=objectives,
        weights=weights,
    )

    return all_evaluated, pareto_front, best_cand, rec_details
