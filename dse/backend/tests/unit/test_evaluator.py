"""Unit tests for Candidate Evaluator and Hardware Estimation Model."""

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
    CandidateDesign,
    ConstraintsIR,
    SearchSettings,
)
from app.ir.types import ResourceKind
from app.ir.lowering import lower_problem
from app.core.evaluator import evaluate_candidate, derive_canonical_allocation


def make_eval_project() -> ProjectIR:
    """Project with complete timing, power, capacity, and cost properties."""
    return ProjectIR(
        meta={"name": "Walkthrough Eval", "time_unit": "ms"},
        settings=SearchSettings(pipelined=False),
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="T1", name="Task 1", memory_kb=10.0),
                ComputeNode(id="T2", name="Task 2", memory_kb=20.0),
                ComputeNode(id="T3", name="Task 3", memory_kb=10.0),
            ],
            edges=[
                DataEdge(source_id="T1", destination_id="T2", data_kb=4.0, comm_id="C1"),
                DataEdge(source_id="T2", destination_id="T3", data_kb=4.0, comm_id="C2"),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(
                    id="CPU",
                    name="Host CPU",
                    kind=ResourceKind.PROCESSOR,
                    mandatory=True,
                    allocation_cost=10.0,
                    static_power_mw=500.0,
                    capacity={"memory_kb": 128.0},
                ),
                ResourceIR(
                    id="ACC1",
                    name="Accelerator 1",
                    kind=ResourceKind.HW_MODULE,
                    mandatory=False,
                    allocation_cost=25.0,
                    static_power_mw=200.0,
                    capacity={"logic": 500.0},
                    area={"logic": 50.0},
                ),
                ResourceIR(
                    id="SB",
                    name="Shared Bus",
                    kind=ResourceKind.BUS,
                    mandatory=True,
                    allocation_cost=0.0,
                    static_power_mw=50.0,
                    power_mw=100.0,
                    connects=["CPU", "ACC1"],
                    bandwidth_mb_per_s=8.0,
                    setup_latency_ms=0.25,
                ),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=3.0, active_power_mw=1200.0),
                MappingOption(node_id="T2", resource_id="CPU", execution_time_ms=4.0, active_power_mw=1500.0),
                MappingOption(
                    node_id="T2",
                    resource_id="ACC1",
                    execution_time_ms=1.0,
                    active_power_mw=300.0,
                    usage={"logic": 100.0},
                ),
                MappingOption(node_id="T3", resource_id="CPU", execution_time_ms=3.0, active_power_mw=1200.0),
            ]
        ),
    )


def test_all_software_evaluation():
    project = make_eval_project()
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="all_sw",
        bindings={"T1": "CPU", "T2": "CPU", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)

    assert res.feasible is True
    # All SW latency: 3.0 + 4.0 + 3.0 = 10.0 ms
    assert res.latency_ms == 10.0
    # Sequential throughput: 1000 / 10 = 100 fps
    assert pytest.approx(res.throughput_fps) == 100.0
    # Allocation cost: CPU is 10.0, SB is 0.0, ACC1 is unused so dropped = 10.0
    assert res.allocation_cost == 10.0
    assert "ACC1" not in candidate.allocated_resources


def test_accelerator_mapping_evaluation():
    project = make_eval_project()
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="acc_sw",
        bindings={"T1": "CPU", "T2": "ACC1", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)

    assert res.feasible is True
    # Timing:
    # T1 on CPU [0, 3.0]
    # C1 on SB [3.0, 3.75] (4/8 + 0.25 = 0.75 ms)
    # T2 on ACC1 [3.75, 4.75] (1.0 ms)
    # C2 on SB [4.75, 5.5] (0.75 ms)
    # T3 on CPU [5.5, 8.5] (3.0 ms)
    assert pytest.approx(res.latency_ms) == 8.5
    assert pytest.approx(res.throughput_fps) == 1000.0 / 8.5
    # Allocation cost: CPU (10.0) + ACC1 (25.0) + SB (0.0) = 35.0
    assert res.allocation_cost == 35.0
    # Logic area usage: base 50 + usage 100 = 150
    assert res.area_usage.get("logic") == 150.0

    # Energy check:
    # E_tasks = (1200*3 + 300*1 + 1200*3) / 1000 = (3600 + 300 + 3600) / 1000 = 7.5 mJ
    # E_buses = (100 * (0.75 + 0.75)) / 1000 = 150 / 1000 = 0.15 mJ
    # E_static = (500 + 200 + 50) * 8.5 / 1000 = 750 * 8.5 / 1000 = 6.375 mJ
    # E_total = 7.5 + 0.15 + 6.375 = 14.025 mJ
    assert pytest.approx(res.energy_mj) == 14.025
    # P_avg = 14.025 / 8.5 = 1.65 W
    assert pytest.approx(res.avg_power_w) == 1.65


def test_pipelined_throughput():
    project = make_eval_project()
    project.settings.pipelined = True
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="pipelined_design",
        bindings={"T1": "CPU", "T2": "ACC1", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)

    # Busy times:
    # CPU: T1 (3.0) + T3 (3.0) = 6.0 ms
    # ACC1: T2 (1.0) = 1.0 ms
    # SB: C1 (0.75) + C2 (0.75) = 1.5 ms
    # Max busy time = II = 6.0 ms
    assert pytest.approx(res.steady_state_ii_ms) == 6.0
    # Throughput = 1000 / 6.0 = 166.67 fps
    assert pytest.approx(res.throughput_fps) == 1000.0 / 6.0


def test_null_power_handling():
    project = make_eval_project()
    # Erase static power of CPU to test Decision D8
    project.architecture.resources[0].static_power_mw = None
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="test_null_power",
        bindings={"T1": "CPU", "T2": "CPU", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)
    # When power input is unknown, energy and avg_power must be None (NOT 0.0)
    assert res.energy_mj is None
    assert res.avg_power_w is None


def test_abstract_time_unit_handling():
    project = make_eval_project()
    project.meta.time_unit = "ticks"  # Not "ms"
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="test_ticks",
        bindings={"T1": "CPU", "T2": "CPU", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)
    # Abstract time unit: throughput and energy are unavailable
    assert res.throughput_fps is None
    assert res.energy_mj is None


def test_hard_constraint_violation():
    project = make_eval_project()
    # Impose max latency constraint of 5.0 ms (All-SW is 10.0 ms)
    project.constraints.max_latency_ms = 5.0
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="violating_design",
        bindings={"T1": "CPU", "T2": "CPU", "T3": "CPU"},
    )
    res = evaluate_candidate(lowered, candidate)
    assert res.feasible is False
    assert len(res.violations) == 1
    assert res.violations[0].metric == "latency"
    assert res.violations[0].limit == 5.0
    assert res.violations[0].actual == 10.0
