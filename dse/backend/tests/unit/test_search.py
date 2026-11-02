"""Unit tests for Search Strategies (Exhaustive, Random, Greedy, NSGA-II)."""

import pytest
from app.ir.models import (
    ComputeNode,
    DataEdge,
    ProblemGraph,
    ResourceIR,
    ArchitectureGraph,
    MappingOption,
    MappingIR,
    ProjectIR,
    SearchSettings,
)
from app.ir.types import ResourceKind, SearchStrategy
from app.ir.lowering import lower_problem
from app.search.candidate import estimate_candidate_count, generate_all_candidates
from app.search.runner import execute_search


def make_dse_search_project() -> ProjectIR:
    """Project with 3 tasks where T1 has 2 options, T2 has 2 options, T3 has 1 option = 4 candidates."""
    return ProjectIR(
        meta={"name": "Search Space Test", "time_unit": "ms"},
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="T1", name="Task 1"),
                ComputeNode(id="T2", name="Task 2"),
                ComputeNode(id="T3", name="Task 3", fixed_resource_id="CPU"),
            ],
            edges=[
                DataEdge(source_id="T1", destination_id="T2", data_kb=4.0),
                DataEdge(source_id="T2", destination_id="T3", data_kb=4.0),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="CPU", name="CPU", kind=ResourceKind.PROCESSOR, mandatory=True, allocation_cost=10.0),
                ResourceIR(id="ACC1", name="ACC 1", kind=ResourceKind.HW_MODULE, mandatory=False, allocation_cost=20.0),
                ResourceIR(id="SB", name="Bus", kind=ResourceKind.BUS, connects=["CPU", "ACC1"], bandwidth_mb_per_s=10.0),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=3.0),
                MappingOption(node_id="T1", resource_id="ACC1", execution_time_ms=1.5),
                MappingOption(node_id="T2", resource_id="CPU", execution_time_ms=4.0),
                MappingOption(node_id="T2", resource_id="ACC1", execution_time_ms=1.0),
                MappingOption(node_id="T3", resource_id="CPU", execution_time_ms=3.0),
            ]
        ),
    )


def test_candidate_count_and_generation():
    project = make_dse_search_project()
    lowered = lower_problem(project)

    # T1 has 2 options (CPU, ACC1), T2 has 2 options (CPU, ACC1), T3 is fixed to CPU (1 option)
    # Total candidates = 2 * 2 * 1 = 4
    count = estimate_candidate_count(lowered)
    assert count == 4

    cands = list(generate_all_candidates(lowered))
    assert len(cands) == 4
    for c in cands:
        # T3 must always be pinned to CPU
        assert c.bindings["T3"] == "CPU"


def test_exhaustive_search_execution():
    project = make_dse_search_project()
    project.settings.strategy = SearchStrategy.EXHAUSTIVE
    lowered = lower_problem(project)

    evaluated, pareto, best, details = execute_search(lowered)
    assert len(evaluated) == 4
    assert len(pareto) >= 1
    assert best is not None
    assert best.evaluation.feasible is True


def test_random_search_seeded_reproducibility():
    project = make_dse_search_project()
    project.settings.strategy = SearchStrategy.RANDOM
    project.settings.budget_evaluations = 4
    project.settings.seed = 123
    lowered = lower_problem(project)

    eval1, _, best1, _ = execute_search(lowered)
    eval2, _, best2, _ = execute_search(lowered)

    assert [c.bindings for c in eval1] == [c.bindings for c in eval2]
    assert best1.id == best2.id


def test_greedy_search_execution():
    project = make_dse_search_project()
    project.settings.strategy = SearchStrategy.GREEDY
    project.settings.budget_evaluations = 10
    lowered = lower_problem(project)

    evaluated, pareto, best, details = execute_search(lowered)
    assert len(evaluated) >= 1
    assert best is not None
    assert best.evaluation.feasible is True


def test_nsga2_search_execution():
    project = make_dse_search_project()
    project.settings.strategy = SearchStrategy.NSGA2
    project.settings.population_size = 4
    project.settings.budget_evaluations = 8
    project.settings.seed = 42
    lowered = lower_problem(project)

    evaluated, pareto, best, details = execute_search(lowered)
    assert len(evaluated) >= 2
    assert len(pareto) >= 1
    assert best is not None
