"""Random sampling search strategy with seeded reproducibility."""

from typing import Callable, List, Optional
from app.ir.models import CandidateDesign
from app.ir.lowering import LoweredProblem
from app.core.evaluator import evaluate_candidate
from app.search.candidate import estimate_candidate_count, sample_random_candidates


def run_random_search(
    lowered: LoweredProblem,
    budget: int = 100,
    seed: int = 42,
    progress_callback: Optional[Callable[[int, int, CandidateDesign], None]] = None,
) -> List[CandidateDesign]:
    """Runs seeded uniform random exploration."""
    total_est = estimate_candidate_count(lowered)
    effective_limit = min(budget, total_est)

    evaluated_candidates: List[CandidateDesign] = []
    generator = sample_random_candidates(lowered, count=effective_limit, seed=seed)

    for idx, candidate in enumerate(generator):
        evaluate_candidate(lowered, candidate)
        evaluated_candidates.append(candidate)
        if progress_callback:
            progress_callback(idx + 1, effective_limit, candidate)

    return evaluated_candidates
