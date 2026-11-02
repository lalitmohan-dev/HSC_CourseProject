"""Unit tests for IR lowering passes and routing."""

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
)
from app.ir.types import ResourceKind
from app.ir.lowering import (
    lower_problem,
    derive_deterministic_route,
    calculate_hop_transfer_time,
)


def make_walkthrough_project() -> ProjectIR:
    """Creates synthetic walkthrough style project: T1 -> T2 -> T3 with CPU and ACC1 on Shared Bus."""
    return ProjectIR(
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="T1", name="Task 1", input_kb=4.0, output_kb=4.0),
                ComputeNode(id="T2", name="Task 2", input_kb=4.0, output_kb=4.0),
                ComputeNode(id="T3", name="Task 3", input_kb=4.0, output_kb=4.0),
            ],
            edges=[
                DataEdge(source_id="T1", destination_id="T2", data_kb=4.0, comm_id="C1"),
                DataEdge(source_id="T2", destination_id="T3", data_kb=4.0),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="CPU", name="Host CPU", kind=ResourceKind.PROCESSOR, clock_mhz=1000.0),
                ResourceIR(id="ACC1", name="Accelerator 1", kind=ResourceKind.HW_MODULE, clock_mhz=500.0),
                ResourceIR(
                    id="SB",
                    name="Shared Bus",
                    kind=ResourceKind.BUS,
                    connects=["CPU", "ACC1"],
                    bandwidth_mb_per_s=8.0,
                    setup_latency_ms=0.25,
                ),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=3.0),
                MappingOption(node_id="T2", resource_id="CPU", execution_time_ms=4.0),
                # T2 on ACC1 defined via cycles: 500,000 cycles at 500 MHz = 1.0 ms
                MappingOption(node_id="T2", resource_id="ACC1", execution_cycles=500_000),
                MappingOption(node_id="T3", resource_id="CPU", execution_time_ms=3.0),
            ]
        ),
    )


def test_lower_problem_communication_objects():
    project = make_walkthrough_project()
    lowered = lower_problem(project)

    assert len(lowered.comm_objects) == 2
    # Preserves explicit comm_id
    assert lowered.comm_objects[0].id == "C1"
    assert lowered.comm_objects[0].source_node_id == "T1"
    assert lowered.comm_objects[0].destination_node_id == "T2"

    # Generates deterministic comm_id when omitted
    assert lowered.comm_objects[1].id == "C_T2_T3"
    assert lowered.comm_objects[1].source_node_id == "T2"
    assert lowered.comm_objects[1].destination_node_id == "T3"


def test_lower_problem_cycles_conversion():
    project = make_walkthrough_project()
    lowered = lower_problem(project)

    # T2 on CPU: direct 4.0 ms
    t2_cpu = lowered.mapping_options_by_node["T2"]["CPU"]
    assert t2_cpu.execution_time_ms == 4.0

    # T2 on ACC1: 500,000 cycles / (500 MHz * 1000) = 1.0 ms
    t2_acc1 = lowered.mapping_options_by_node["T2"]["ACC1"]
    assert pytest.approx(t2_acc1.execution_time_ms) == 1.0


def test_deterministic_route_local():
    project = make_walkthrough_project()
    lowered = lower_problem(project)

    # Same resource -> local route, empty list
    route = derive_deterministic_route(lowered, "CPU", "CPU")
    assert route == []


def test_deterministic_route_single_bus():
    project = make_walkthrough_project()
    lowered = lower_problem(project)

    # CPU to ACC1 via SB
    route = derive_deterministic_route(lowered, "CPU", "ACC1")
    assert route == ["SB"]

    # Reverse direction
    route_rev = derive_deterministic_route(lowered, "ACC1", "CPU")
    assert route_rev == ["SB"]


def test_deterministic_route_unallocated_bus():
    project = make_walkthrough_project()
    lowered = lower_problem(project)

    # If SB is NOT in allocated resources, no route should exist
    route = derive_deterministic_route(lowered, "CPU", "ACC1", allocated_resource_ids={"CPU", "ACC1"})
    assert route is None


def test_multi_hop_route():
    # Setup CPU -> Bus1 -> Bridge -> Bus2 -> ACC1
    project = ProjectIR(
        problem=ProblemGraph(nodes=[ComputeNode(id="T1", name="T1")]),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="CPU", name="CPU", kind=ResourceKind.PROCESSOR),
                ResourceIR(id="Bridge", name="Bridge", kind=ResourceKind.HW_MODULE),
                ResourceIR(id="ACC1", name="ACC1", kind=ResourceKind.HW_MODULE),
                ResourceIR(id="B1", name="Bus 1", kind=ResourceKind.BUS, connects=["CPU", "Bridge"]),
                ResourceIR(id="B2", name="Bus 2", kind=ResourceKind.BUS, connects=["Bridge", "ACC1"]),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=1.0),
            ]
        ),
    )
    lowered = lower_problem(project)
    route = derive_deterministic_route(lowered, "CPU", "ACC1")
    assert route == ["B1", "B2"]


def test_calculate_hop_transfer_time():
    bus = ResourceIR(
        id="SB",
        name="Shared Bus",
        kind=ResourceKind.BUS,
        bandwidth_mb_per_s=8.0,
        setup_latency_ms=0.25,
    )
    # 4 KB / 8 MB/s = 0.5 ms + 0.25 ms setup = 0.75 ms
    t = calculate_hop_transfer_time(bus, 4.0)
    assert pytest.approx(t) == 0.75
