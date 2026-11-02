"""Unit tests for the Simple CPU/FPGA preset adapter."""

import pytest
from app.ir.models import DataEdge
from app.ir.presets import (
    SimplePlatformConfig,
    SimpleTaskConfig,
    lower_simple_preset,
)
from app.ir.validator import validate_project
from app.ir.lowering import lower_problem
from app.core.evaluator import evaluate_candidate
from app.search.runner import execute_search


def test_simple_cpu_fpga_preset_lowering():
    tasks = [
        SimpleTaskConfig(
            id="T1",
            name="Filter",
            sw_cycles=1_000_000,
            hw_cycles=250_000,
            hw_luts=100.0,
            hw_dsps=2.0,
            memory_kb=4.0,
        ),
        SimpleTaskConfig(
            id="T2",
            name="Compress",
            sw_cycles=2_000_000,
            hw_cycles=None,  # Software only
            memory_kb=8.0,
        ),
    ]
    edges = [DataEdge(source_id="T1", destination_id="T2", data_kb=4.0)]
    platform = SimplePlatformConfig(
        cpu_mhz=1000.0,
        fpga_mhz=250.0,
        bus_bandwidth_mb_per_s=8.0,
        bus_latency_us=250.0,
    )

    project = lower_simple_preset("test_preset", "Preset Test", tasks, edges, platform)

    # 1. Check generated resources
    res_ids = {r.id for r in project.architecture.resources}
    assert "CPU" in res_ids
    assert "ACC_T1" in res_ids  # Dedicated accelerator for T1
    assert "ACC_T2" not in res_ids  # T2 is SW only
    assert "SharedBus" in res_ids

    # 2. Check FPGA fabric capacity group
    assert len(project.architecture.capacity_groups) == 1
    fabric = project.architecture.capacity_groups[0]
    assert fabric.id == "FPGA_Fabric"
    assert "ACC_T1" in fabric.resource_ids
    assert fabric.limits["luts"] == 5000.0

    # 3. Check mapping options
    opts = project.mapping.options
    assert len(opts) == 3  # T1 on CPU, T1 on ACC_T1, T2 on CPU

    # 4. Must pass common IR validation
    validation = validate_project(project)
    assert validation.is_valid is True

    # 5. Successfully lowers and runs DSE
    lowered = lower_problem(project)
    evaluated, pareto, best, details = execute_search(lowered)
    assert len(evaluated) == 2  # T1 on CPU or ACC_T1 (T2 is always CPU)
    assert len(pareto) >= 1
    assert best is not None
    assert best.evaluation.feasible is True
