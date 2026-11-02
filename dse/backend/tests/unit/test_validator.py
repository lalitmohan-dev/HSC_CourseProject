"""Unit tests for IR Validator."""

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
from app.ir.types import ResourceKind, ValidationSeverity
from app.ir.validator import validate_project


def make_valid_project() -> ProjectIR:
    return ProjectIR(
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
                ResourceIR(id="ACC1", name="ACC1", kind=ResourceKind.HW_MODULE),
                ResourceIR(
                    id="SB",
                    name="Bus",
                    kind=ResourceKind.BUS,
                    connects=["CPU", "ACC1"],
                    bandwidth_mb_per_s=10.0,
                ),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T1", resource_id="CPU", execution_time_ms=2.0),
                MappingOption(node_id="T2", resource_id="ACC1", execution_time_ms=1.0),
            ]
        ),
    )


def test_valid_project_passes():
    project = make_valid_project()
    result = validate_project(project)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_duplicate_node_id():
    project = make_valid_project()
    project.problem.nodes.append(ComputeNode(id="T1", name="Duplicate T1"))
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "DUPLICATE_ID" and "T1" in e.message for e in result.errors)


def test_unknown_node_in_edge():
    project = make_valid_project()
    project.problem.edges.append(DataEdge(source_id="T1", destination_id="NON_EXISTENT", data_kb=2.0))
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "UNKNOWN_NODE" for e in result.errors)


def test_dag_cycle_detection():
    project = make_valid_project()
    # Add T2 -> T1 edge, creating cycle T1 -> T2 -> T1
    project.problem.edges.append(DataEdge(source_id="T2", destination_id="T1", data_kb=1.0))
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "CYCLE_DETECTED" for e in result.errors)


def test_self_loop_detection():
    project = make_valid_project()
    project.problem.edges.append(DataEdge(source_id="T1", destination_id="T1", data_kb=1.0))
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "CYCLE_DETECTED" and "Self-loop" in e.message for e in result.errors)


def test_bus_unknown_endpoint():
    project = make_valid_project()
    project.architecture.resources.append(
        ResourceIR(id="BUS2", name="Bus2", kind=ResourceKind.BUS, connects=["CPU", "UNKNOWN_RES"])
    )
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "UNKNOWN_RESOURCE" for e in result.errors)


def test_mapping_node_to_bus_rejected():
    project = make_valid_project()
    project.mapping.options.append(
        MappingOption(node_id="T1", resource_id="SB", execution_time_ms=1.0)
    )
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "INVALID_RESOURCE_KIND" for e in result.errors)


def test_missing_execution_time_and_cycles():
    project = make_valid_project()
    project.mapping.options.append(
        MappingOption(node_id="T1", resource_id="ACC1")  # No time, no cycles
    )
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "MISSING_TIMING" for e in result.errors)


def test_cycles_without_clock_rejected():
    project = make_valid_project()
    # ACC1 has no clock_mhz
    project.mapping.options.append(
        MappingOption(node_id="T1", resource_id="ACC1", execution_cycles=1000)
    )
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "MISSING_CLOCK" for e in result.errors)


def test_unmapped_node_detected():
    project = make_valid_project()
    project.problem.nodes.append(ComputeNode(id="T3", name="Task 3"))
    # No mapping option added for T3
    result = validate_project(project)
    assert result.is_valid is False
    assert any(e.code == "NO_MAPPING_OPTIONS" and "T3" in e.message for e in result.errors)


def test_multiple_errors_returned_together():
    project = make_valid_project()
    project.problem.nodes.append(ComputeNode(id="T1", name="Dup"))  # DUPLICATE_ID
    project.problem.edges.append(DataEdge(source_id="T1", destination_id="FAKE", data_kb=-5.0))  # UNKNOWN_NODE, NEGATIVE_VALUE
    result = validate_project(project)
    assert result.is_valid is False
    assert len(result.errors) >= 3
