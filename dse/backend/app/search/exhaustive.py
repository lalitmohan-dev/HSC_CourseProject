"""Exhaustive search strategy.

Evaluates every legal design configuration up to a budget/ceiling.
"""

from typing import Callable, List, Optional
from app.ir.models import CandidateDesign
from app.ir.lowering import LoweredProblem
from app.core.evaluator import evaluate_candidate
from app.search.candidate import estimate_candidate_count, generate_all_candidates

EXHAUSTIVE_CEILING = 1_048_576  # 2^20 ceiling per Section 10.2


def run_exhaustive_search(
    lowered: LoweredProblem,
    budget: Optional[int] = 1000,
    progress_callback: Optional[Callable[[int, int, CandidateDesign], None]] = None,
) -> List[CandidateDesign]:
    """Runs exhaustive search over legal design space."""
    total_est = estimate_candidate_count(lowered)
    effective_limit = min(budget or total_est, total_est)

    evaluated_candidates: List[CandidateDesign] = []
    generator = generate_all_candidates(lowered, max_budget=effective_limit)

    for idx, candidate in enumerate(generator):
        evaluate_candidate(lowered, candidate)
        evaluated_candidates.append(candidate)
        if progress_callback:
            progress_callback(idx + 1, effective_limit, candidate)

    return evaluated_candidates
