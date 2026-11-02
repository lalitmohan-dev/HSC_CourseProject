"""Simple CPU/FPGA preset adapter.

Implements Section 9:
- Lowers legacy binary SW/HW tasks into the generalized architecture model
- Mandatory CPU processor resource
- Shared bus connecting CPU and all dedicated accelerator modules
- For each task with hardware option: dedicated accelerator module ACC_<task_id>
- Shared capacity group 'FPGA_Fabric' enforcing LUT, DSP, and BRAM limits
- No second evaluator: uses the single canonical IR and evaluator
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.ir.models import (
    ArchitectureGraph,
    CapacityGroup,
    ComputeNode,
    ConstraintsIR,
    DataEdge,
    MappingIR,
    MappingOption,
    ProblemGraph,
    ProjectIR,
    ProjectMetadata,
    ResourceIR,
    SearchSettings,
)
from app.ir.types import ResourceKind, SearchStrategy


class SimpleTaskConfig(BaseModel):
    id: str
    name: str
    sw_cycles: int
    hw_cycles: Optional[int] = None
    power_sw_mw: Optional[float] = None
    power_hw_mw: Optional[float] = None
    hw_luts: float = 0.0
    hw_dsps: float = 0.0
    hw_bram: float = 0.0
    memory_kb: float = 0.0
    input_kb: float = 0.0
    output_kb: float = 0.0


class SimplePlatformConfig(BaseModel):
    cpu_mhz: float = 1000.0
    fpga_mhz: float = 250.0
    bus_bandwidth_mb_per_s: float = 8.0
    bus_latency_us: float = 250.0  # 0.25 ms
    bus_power_mw: float = 100.0
    cpu_static_power_mw: float = 500.0
    fpga_static_power_mw: float = 200.0
    bus_static_power_mw: float = 50.0
    fpga_luts: float = 5000.0
    fpga_dsps: float = 20.0
    fpga_bram: float = 10.0


def lower_simple_preset(
    project_id: str,
    project_name: str,
    tasks: List[SimpleTaskConfig],
    edges: List[DataEdge],
    platform: SimplePlatformConfig,
) -> ProjectIR:
    """Lowers a simple CPU/FPGA description into the generalized ProjectIR."""
    nodes: List[ComputeNode] = []
    resources: List[ResourceIR] = []
    mapping_options: List[MappingOption] = []
    acc_ids: List[str] = []

    # 1. Mandatory CPU resource
    cpu = ResourceIR(
        id="CPU",
        name="Host CPU",
        kind=ResourceKind.PROCESSOR,
        mandatory=True,
        allocation_cost=10.0,
        static_power_mw=platform.cpu_static_power_mw,
        clock_mhz=platform.cpu_mhz,
        max_parallel=1,
    )
    resources.append(cpu)

    # 2. Process tasks and generate dedicated accelerators
    for t in tasks:
        nodes.append(
            ComputeNode(
                id=t.id,
                name=t.name,
                memory_kb=t.memory_kb,
                input_kb=t.input_kb,
                output_kb=t.output_kb,
            )
        )

        # Software mapping option on CPU
        mapping_options.append(
            MappingOption(
                node_id=t.id,
                resource_id="CPU",
                execution_cycles=t.sw_cycles,
                active_power_mw=t.power_sw_mw,
            )
        )

        # Hardware option if hw_cycles specified
        if t.hw_cycles is not None:
            acc_id = f"ACC_{t.id}"
            acc_ids.append(acc_id)
            acc = ResourceIR(
                id=acc_id,
                name=f"Accelerator for {t.id}",
                kind=ResourceKind.HW_MODULE,
                mandatory=False,
                allocation_cost=5.0,
                static_power_mw=0.0,  # Included in fabric
                clock_mhz=platform.fpga_mhz,
                max_parallel=1,
                area={
                    "luts": t.hw_luts,
                    "dsps": t.hw_dsps,
                    "bram": t.hw_bram,
                },
            )
            resources.append(acc)

            mapping_options.append(
                MappingOption(
                    node_id=t.id,
                    resource_id=acc_id,
                    execution_cycles=t.hw_cycles,
                    active_power_mw=t.power_hw_mw,
                    usage={
                        "luts": t.hw_luts,
                        "dsps": t.hw_dsps,
                        "bram": t.hw_bram,
                    },
                )
            )

    # 3. Shared Bus connecting CPU and all generated accelerators
    bus = ResourceIR(
        id="SharedBus",
        name="System Interconnect Bus",
        kind=ResourceKind.BUS,
        mandatory=True,
        allocation_cost=0.0,
        static_power_mw=platform.bus_static_power_mw,
        power_mw=platform.bus_power_mw,
        connects=["CPU"] + acc_ids,
        bandwidth_mb_per_s=platform.bus_bandwidth_mb_per_s,
        setup_latency_ms=platform.bus_latency_us / 1000.0,  # us -> ms
    )
    resources.append(bus)

    # 4. Capacity group for FPGA Fabric
    capacity_groups = [
        CapacityGroup(
            id="FPGA_Fabric",
            name="FPGA Fabric Resource Pool",
            resource_ids=acc_ids,
            limits={
                "luts": platform.fpga_luts,
                "dsps": platform.fpga_dsps,
                "bram": platform.fpga_bram,
            },
        )
    ]

    return ProjectIR(
        schema_version=2,
        meta=ProjectMetadata(
            id=project_id,
            name=project_name,
            description="Lowered from Simple CPU/FPGA preset",
            time_unit="ms",
        ),
        problem=ProblemGraph(nodes=nodes, edges=edges),
        architecture=ArchitectureGraph(resources=resources, capacity_groups=capacity_groups),
        mapping=MappingIR(options=mapping_options),
        constraints=ConstraintsIR(),
        settings=SearchSettings(strategy=SearchStrategy.EXHAUSTIVE),
    )
