"""Unit tests for Canonical IR models."""

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
    EvaluationResult,
)
from app.ir.types import ResourceKind, TimeUnit, SearchStrategy


def test_compute_node_instantiation():
    node = ComputeNode(
        id="T1",
        name="Filter",
        input_kb=4.0,
        output_kb=4.0,
        memory_kb=8.0,
    )
    assert node.id == "T1"
    assert node.name == "Filter"
    assert node.op_type == "compute"
    assert node.input_kb == 4.0
    assert node.fixed_resource_id is None


def test_data_edge_aliases():
    # Test using 'from' and 'to' aliases
    edge = DataEdge(**{"from": "T1", "to": "T2", "data_kb": 16.0, "comm_id": "C_T1_T2"})
    assert edge.source_id == "T1"
    assert edge.destination_id == "T2"
    assert edge.data_kb == 16.0
    assert edge.comm_id == "C_T1_T2"

    # Test using field names directly
    edge2 = DataEdge(source_id="T1", destination_id="T2", data_kb=8.0)
    assert edge2.source_id == "T1"
    assert edge2.destination_id == "T2"


def test_resource_instantiation():
    cpu = ResourceIR(
        id="CPU",
        name="Host CPU",
        kind=ResourceKind.PROCESSOR,
        allocation_cost=10.0,
        clock_mhz=1000.0,
        max_parallel=1,
    )
    assert cpu.id == "CPU"
    assert cpu.kind == ResourceKind.PROCESSOR
    assert cpu.mandatory is True

    bus = ResourceIR(
        id="SB",
        name="Shared Bus",
        kind=ResourceKind.BUS,
        bandwidth_mb_per_s=8.0,
        setup_latency_ms=0.25,
        connects=["CPU", "ACC1"],
    )
    assert bus.id == "SB"
    assert bus.bandwidth_mb_per_s == 8.0
    assert len(bus.connects) == 2


def test_project_ir_roundtrip_dict():
    project = ProjectIR(
        meta={"name": "Test Project", "time_unit": "ms"},
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="T1", name="Task 1"),
                ComputeNode(id="T2", name="Task 2"),
            ],
            edges=[
                DataEdge(source_id="T1", destination_id="T2", data_kb=4.0),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="CPU", name="CPU", kind=ResourceKind.PROCESSOR),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=1.5),
                MappingOption(node_id="T2", resource_id="CPU", execution_time_ms=2.0),
            ]
        ),
    )
    d = project.model_dump()
    assert d["schema_version"] == 2
    assert d["meta"]["name"] == "Test Project"
    assert len(d["problem"]["nodes"]) == 2
    assert len(d["mapping"]["options"]) == 2

    reloaded = ProjectIR.model_validate(d)
    assert reloaded.meta.name == "Test Project"
    assert reloaded.problem.nodes[0].id == "T1"
