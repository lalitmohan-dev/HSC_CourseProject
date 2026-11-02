"""Canonical Golden Test for the System-Level Synthesis Scheduler.

Directly validates Section 7 of the specification:
- Replicates the slide synthesis problem (V1..V4, V5..V7, RISC, SB, HWM1, optional HWM2, PTP)
- Allocation: RISC, SB, HWM1 (HWM2 and PTP unallocated)
- Binding: V1, V2, V3 -> RISC, V4 -> HWM1, V5 -> local RISC, V6, V7 -> SB
- Exact assertions:
  - Exact start/finish timestamps matching the slide
  - V5 duration is 0 and consumes no bus slot
  - V6 and V7 occupy SB at non-overlapping intervals
  - Total latency = exactly 32 abstract ticks
"""

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
)
from app.ir.types import ResourceKind, TimeUnit
from app.ir.lowering import lower_problem
from app.core.scheduler import schedule_candidate


def make_golden_project() -> ProjectIR:
    """Builds the canonical golden slide test project as specified in Section 7."""
    return ProjectIR(
        meta={"name": "Golden Slide Synthesis", "time_unit": "ticks"},
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="V1", name="Task V1"),
                ComputeNode(id="V2", name="Task V2"),
                ComputeNode(id="V3", name="Task V3"),
                ComputeNode(id="V4", name="Task V4"),
            ],
            edges=[
                # V1 -> V5 -> V3
                DataEdge(source_id="V1", destination_id="V3", data_kb=1.0, comm_id="V5"),
                # V2 -> V6 -> V4
                DataEdge(source_id="V2", destination_id="V4", data_kb=1.0, comm_id="V6"),
                # V3 -> V7 -> V4
                DataEdge(source_id="V3", destination_id="V4", data_kb=1.0, comm_id="V7"),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="RISC", name="RISC Processor", kind=ResourceKind.PROCESSOR, mandatory=True),
                ResourceIR(id="HWM1", name="Hardware Module 1", kind=ResourceKind.HW_MODULE, mandatory=True),
                ResourceIR(id="HWM2", name="Hardware Module 2", kind=ResourceKind.HW_MODULE, mandatory=False),
                ResourceIR(
                    id="SB",
                    name="Shared Bus",
                    kind=ResourceKind.BUS,
                    mandatory=True,
                    connects=["RISC", "HWM1"],
                    setup_latency_ms=1.0,  # 1 tick duration
                    bandwidth_mb_per_s=None,
                ),
                ResourceIR(
                    id="PTP",
                    name="Point-to-Point Bus",
                    kind=ResourceKind.BUS,
                    mandatory=False,
                    connects=["HWM1", "HWM2"],
                    setup_latency_ms=1.0,
                ),
            ]
        ),
        mapping=MappingIR(
            options=[
                # V1: 1 tick on RISC
                MappingOption(node_id="V1", resource_id="RISC", execution_time_ms=1.0),
                # V2: 20 ticks on RISC
                MappingOption(node_id="V2", resource_id="RISC", execution_time_ms=20.0),
                # V3: 8 ticks on RISC
                MappingOption(node_id="V3", resource_id="RISC", execution_time_ms=8.0),
                # V4: 2 ticks on HWM1
                MappingOption(node_id="V4", resource_id="HWM1", execution_time_ms=2.0),
            ]
        ),
    )


def test_canonical_golden_schedule():
    """Verify the exact schedule and timing table from Section 7.2 of the specification."""
    project = make_golden_project()
    lowered = lower_problem(project)

    candidate = CandidateDesign(
        id="golden_design",
        bindings={
            "V1": "RISC",
            "V2": "RISC",
            "V3": "RISC",
            "V4": "HWM1",
        },
        allocated_resources=["RISC", "SB", "HWM1"],
        priority_order=["V1", "V2", "V3", "V5", "V6", "V7", "V4"],
    )

    schedule = schedule_candidate(lowered, candidate)

    # 1. Total latency must be exactly 32 abstract units
    assert schedule.latency == 32.0

    # 2. Check each scheduled object against Section 7.2 table
    sched_by_id = {s.id: s for s in schedule.objects}

    # V1 on RISC: start 0, duration 1, finish 1
    v1 = sched_by_id["V1"]
    assert v1.resource_id == "RISC"
    assert v1.start_time == 0.0
    assert v1.duration == 1.0
    assert v1.finish_time == 1.0

    # V5: local RISC event: start 1, duration 0, finish 1
    v5 = sched_by_id["V5"]
    assert v5.start_time == 1.0
    assert v5.duration == 0.0
    assert v5.finish_time == 1.0
    assert v5.is_communication is True

    # V2 on RISC: start 1, duration 20, finish 21
    v2 = sched_by_id["V2"]
    assert v2.resource_id == "RISC"
    assert v2.start_time == 1.0
    assert v2.duration == 20.0
    assert v2.finish_time == 21.0

    # V3 on RISC: start 21, duration 8, finish 29
    v3 = sched_by_id["V3"]
    assert v3.resource_id == "RISC"
    assert v3.start_time == 21.0
    assert v3.duration == 8.0
    assert v3.finish_time == 29.0

    # V6 on SB: start 21, duration 1, finish 22
    v6 = sched_by_id["V6"]
    assert v6.resource_id == "SB"
    assert v6.start_time == 21.0
    assert v6.duration == 1.0
    assert v6.finish_time == 22.0

    # V7 on SB: start 29, duration 1, finish 30
    v7 = sched_by_id["V7"]
    assert v7.resource_id == "SB"
    assert v7.start_time == 29.0
    assert v7.duration == 1.0
    assert v7.finish_time == 30.0

    # V4 on HWM1: start 30, duration 2, finish 32
    v4 = sched_by_id["V4"]
    assert v4.resource_id == "HWM1"
    assert v4.start_time == 30.0
    assert v4.duration == 2.0
    assert v4.finish_time == 32.0

    # 3. DMA concurrency verification: at time 21, V6 is active on SB while V3 is active on RISC
    assert v6.start_time == v3.start_time == 21.0
    assert v6.resource_id == "SB" and v3.resource_id == "RISC"

    # 4. Bus serialization verification: V6 and V7 do not overlap on SB
    assert v6.finish_time <= v7.start_time

    # 5. Bottleneck verification: RISC busy time = 1 + 20 + 8 = 29
    risc_util = schedule.resource_utilization["RISC"]
    assert pytest.approx(risc_util) == 29.0 / 32.0


def test_bus_serialization_contention():
    """Verify that when two transfers compete for the same bus simultaneously, they serialize."""
    project = ProjectIR(
        problem=ProblemGraph(
            nodes=[
                ComputeNode(id="T_SRC1", name="Source 1"),
                ComputeNode(id="T_SRC2", name="Source 2"),
                ComputeNode(id="T_DST1", name="Dest 1"),
                ComputeNode(id="T_DST2", name="Dest 2"),
            ],
            edges=[
                DataEdge(source_id="T_SRC1", destination_id="T_DST1", data_kb=1.0, comm_id="C1"),
                DataEdge(source_id="T_SRC2", destination_id="T_DST2", data_kb=1.0, comm_id="C2"),
            ],
        ),
        architecture=ArchitectureGraph(
            resources=[
                ResourceIR(id="CPU1", name="CPU 1", kind=ResourceKind.PROCESSOR),
                ResourceIR(id="CPU2", name="CPU 2", kind=ResourceKind.PROCESSOR),
                ResourceIR(id="ACC1", name="ACC 1", kind=ResourceKind.HW_MODULE),
                ResourceIR(id="ACC2", name="ACC 2", kind=ResourceKind.HW_MODULE),
                ResourceIR(id="SB", name="Shared Bus", kind=ResourceKind.BUS, connects=["CPU1", "CPU2", "ACC1", "ACC2"], setup_latency_ms=2.0),
            ]
        ),
        mapping=MappingIR(
            options=[
                MappingOption(node_id="T_SRC1", resource_id="CPU1", execution_time_ms=1.0),
                MappingOption(node_id="T_SRC2", resource_id="CPU2", execution_time_ms=1.0),
                MappingOption(node_id="T_DST1", resource_id="ACC1", execution_time_ms=1.0),
                MappingOption(node_id="T_DST2", resource_id="ACC2", execution_time_ms=1.0),
            ]
        ),
    )
    lowered = lower_problem(project)
    candidate = CandidateDesign(
        id="contention_design",
        bindings={
            "T_SRC1": "CPU1",
            "T_SRC2": "CPU2",
            "T_DST1": "ACC1",
            "T_DST2": "ACC2",
        },
        allocated_resources=["CPU1", "CPU2", "ACC1", "ACC2", "SB"],
        priority_order=["T_SRC1", "T_SRC2", "C1", "C2", "T_DST1", "T_DST2"],
    )
    schedule = schedule_candidate(lowered, candidate)
    sched_by_id = {s.id: s for s in schedule.objects}

    c1 = sched_by_id["C1"]
    c2 = sched_by_id["C2"]

    # Both sources finish at t=1.0. But SB only has max_parallel=1.
    # Therefore, C1 and C2 must serialize on SB: one from 1 to 3, the other from 3 to 5.
    assert c1.start_time == 1.0
    assert c1.finish_time == 3.0
    assert c2.start_time == 3.0
    assert c2.finish_time == 5.0
