"""Candidate generator for Design Space Exploration.

Implements lazy candidate generation per Section 10.2:
- Calculates exact Cartesian product size of legal options
- Lazily yields candidates without materializing full search space in memory
- Respects fixed/pinned resource constraints
- Produces deterministic, stable candidate IDs
"""

import itertools
import random
from typing import Dict, Iterator, List, Optional, Set, Tuple

from app.ir.models import CandidateDesign
from app.ir.lowering import LoweredProblem
from app.core.evaluator import derive_canonical_allocation


def estimate_candidate_count(lowered: LoweredProblem) -> int:
    """Calculates the exact total number of legal task-to-resource binding combinations."""
    total = 1
    for node_id, node in lowered.nodes_by_id.items():
        if node.fixed_resource_id:
            num_options = 1 if node.fixed_resource_id in lowered.mapping_options_by_node[node_id] else 0
        else:
            num_options = len(lowered.mapping_options_by_node[node_id])
        total *= num_options
    return total


def generate_all_candidates(
    lowered: LoweredProblem,
    max_budget: Optional[int] = None,
) -> Iterator[CandidateDesign]:
    """Lazily generates candidate designs across all legal task binding combinations."""
    tasks = sorted(list(lowered.nodes_by_id.keys()))
    options_per_task: List[List[Tuple[str, str]]] = []

    for task_id in tasks:
        node = lowered.nodes_by_id[task_id]
        if node.fixed_resource_id:
            # Fixed resource constraint
            res_id = node.fixed_resource_id
            if res_id in lowered.mapping_options_by_node[task_id]:
                options_per_task.append([(task_id, res_id)])
            else:
                return  # Infeasible: fixed task has no mapping option
        else:
            legal_res = sorted(list(lowered.mapping_options_by_node[task_id].keys()))
            options_per_task.append([(task_id, r) for r in legal_res])

    generated = 0
    for combo in itertools.product(*options_per_task):
        bindings = dict(combo)
        allocated = derive_canonical_allocation(lowered, bindings)
        cid = f"design_{generated + 1:04d}"
        yield CandidateDesign(
            id=cid,
            bindings=bindings,
            allocated_resources=allocated,
        )
        generated += 1
        if max_budget is not None and generated >= max_budget:
            break


def sample_random_candidates(
    lowered: LoweredProblem,
    count: int,
    seed: Optional[int] = 42,
) -> Iterator[CandidateDesign]:
    """Uniformly samples legal candidate designs with seeded reproducibility."""
    rng = random.Random(seed)
    tasks = sorted(list(lowered.nodes_by_id.keys()))
    seen_signatures: Set[Tuple[Tuple[str, str], ...]] = set()

    attempts = 0
    max_attempts = count * 20
    generated = 0

    while generated < count and attempts < max_attempts:
        attempts += 1
        bindings: Dict[str, str] = {}
        valid = True

        for task_id in tasks:
            node = lowered.nodes_by_id[task_id]
            if node.fixed_resource_id:
                res_id = node.fixed_resource_id
                if res_id in lowered.mapping_options_by_node[task_id]:
                    bindings[task_id] = res_id
                else:
                    valid = False
                    break
            else:
                legal_res = sorted(list(lowered.mapping_options_by_node[task_id].keys()))
                if not legal_res:
                    valid = False
                    break
                bindings[task_id] = rng.choice(legal_res)

        if not valid:
            continue

        sig = tuple(sorted(bindings.items()))
        if sig in seen_signatures:
            continue

        seen_signatures.add(sig)
        allocated = derive_canonical_allocation(lowered, bindings)
        cid = f"rand_{generated + 1:04d}"
        yield CandidateDesign(
            id=cid,
            bindings=bindings,
            allocated_resources=allocated,
        )
        generated += 1
