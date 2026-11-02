"""Common candidate evaluator for the DSE framework.

Implements Section 6 of the specification:
- Single source of truth for design-space evaluation
- Pure Python: no FastAPI or UI dependencies
- Dynamic canonical allocation derivation
- Latency and sequential/pipelined throughput calculation
- Optional power and energy evaluation with strict null-preservation (Decision D8, §6.6)
- Abstract time unit handling (Decision D7, §5.4)
- Area, memory footprint, and bus bandwidth calculation
- Multi-dimensional capacity and user constraint checking
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set
from pydantic import BaseModel

from app.ir.models import (
    CandidateDesign,
    ConstraintViolation,
    EvaluationResult,
    Schedule,
)
from app.ir.lowering import LoweredProblem, derive_deterministic_route
from app.ir.types import ResourceKind
from app.core.scheduler import schedule_candidate, SchedulingError


def derive_canonical_allocation(
    lowered: LoweredProblem,
    bindings: Dict[str, str],
) -> List[str]:
    """Derives canonical minimal allocation set α for a given binding dictionary.

    α = mandatory resources ∪ bound compute resources ∪ route buses.
    """
    allocated: Set[str] = set()

    # 1. Mandatory resources
    for res_id, res in lowered.resources_by_id.items():
        if res.mandatory:
            allocated.add(res_id)

    # 2. Bound compute resources
    for node_id, res_id in bindings.items():
        allocated.add(res_id)

    # 3. Buses on deterministic routes between bound resources
    for edge in lowered.project.problem.edges:
        u_res = bindings.get(edge.source_id)
        v_res = bindings.get(edge.destination_id)
        if u_res and v_res and u_res != v_res:
            route = derive_deterministic_route(lowered, u_res, v_res, set(lowered.resources_by_id.keys()))
            if route:
                for bus_id in route:
                    allocated.add(bus_id)

    return sorted(list(allocated))


def evaluate_candidate(
    lowered: LoweredProblem,
    candidate: CandidateDesign,
) -> EvaluationResult:
    """Evaluates a candidate design according to the canonical resource and cost model."""
    # Canonicalize allocation if not provided
    if not candidate.allocated_resources:
        candidate.allocated_resources = derive_canonical_allocation(lowered, candidate.bindings)

    allocated_set = set(candidate.allocated_resources)
    violations: List[ConstraintViolation] = []

    # 1. Generate Schedule
    schedule: Optional[Schedule] = None
    try:
        schedule = schedule_candidate(lowered, candidate)
    except SchedulingError as e:
        violations.append(
            ConstraintViolation(
                metric="feasibility",
                limit=0.0,
                actual=1.0,
                unit="",
                severity="error",
            )
        )
        return EvaluationResult(
            design_id=candidate.id,
            feasible=False,
            violations=violations,
            latency_ms=float("inf"),
            allocation_cost=sum(
                lowered.resources_by_id[r].allocation_cost
                for r in candidate.allocated_resources
                if r in lowered.resources_by_id
            ),
        )

    # 2. Latency & Throughput
    latency = schedule.latency
    time_unit = lowered.project.meta.time_unit
    is_ms_time = (time_unit == "ms")

    throughput_fps: Optional[float] = None
    steady_state_ii_ms: Optional[float] = None

    if is_ms_time and latency > 0:
        if lowered.project.settings.pipelined:
            # Steady-state Initiation Interval II = max busy time across scheduled resources
            busy_times = [
                sum(s.duration for s in schedule.objects if s.resource_id == r)
                for r in candidate.allocated_resources
            ]
            steady_state_ii_ms = max(busy_times, default=latency)
            throughput_fps = (1000.0 / steady_state_ii_ms) if steady_state_ii_ms > 0 else None
        else:
            throughput_fps = 1000.0 / latency

    # 3. Allocation Cost & Area
    allocation_cost = sum(
        lowered.resources_by_id[r].allocation_cost
        for r in candidate.allocated_resources
        if r in lowered.resources_by_id
    )

    area_usage: Dict[str, float] = defaultdict(float)
    for r in candidate.allocated_resources:
        res = lowered.resources_by_id[r]
        for metric, val in res.area.items():
            area_usage[metric] += val

    for node_id, res_id in candidate.bindings.items():
        opt = lowered.mapping_options_by_node.get(node_id, {}).get(res_id)
        if opt and opt.usage:
            for metric, val in opt.usage.items():
                area_usage[metric] += val

    # 4. Energy & Average Power (Decision D7 & D8)
    total_energy_mj: Optional[float] = None
    avg_power_w: Optional[float] = None

    if is_ms_time and latency > 0:
        power_computable = True
        e_tasks = 0.0
        for node_id, res_id in candidate.bindings.items():
            opt = lowered.mapping_options_by_node.get(node_id, {}).get(res_id)
            if opt is None or opt.active_power_mw is None:
                power_computable = False
                break
            e_tasks += (opt.active_power_mw * opt.execution_time_ms) / 1000.0

        e_buses = 0.0
        if power_computable:
            for bus_id in candidate.allocated_resources:
                bus_res = lowered.resources_by_id[bus_id]
                if bus_res.kind == ResourceKind.BUS:
                    if bus_res.power_mw is None:
                        power_computable = False
                        break
                    busy_time = sum(
                        s.duration for s in schedule.objects if s.resource_id == bus_id
                    )
                    e_buses += (bus_res.power_mw * busy_time) / 1000.0

        e_static = 0.0
        if power_computable:
            for r in candidate.allocated_resources:
                res = lowered.resources_by_id[r]
                if res.static_power_mw is None:
                    power_computable = False
                    break
                e_static += (res.static_power_mw * latency) / 1000.0

        if power_computable:
            total_energy_mj = e_tasks + e_buses + e_static
            avg_power_w = total_energy_mj / latency

    # 5. Memory Footprint
    declared_memory_kb = (
        sum(node.memory_kb for node in lowered.project.problem.nodes)
        + sum(edge.data_kb for edge in lowered.project.problem.edges)
    )

    # 6. Bus Bandwidth Usage
    bus_data_kb: Dict[str, float] = defaultdict(float)
    for edge in lowered.project.problem.edges:
        u_res = candidate.bindings.get(edge.source_id)
        v_res = candidate.bindings.get(edge.destination_id)
        if u_res and v_res and u_res != v_res:
            cid = lowered.comm_by_edge[(edge.source_id, edge.destination_id)].id
            route = candidate.routes.get(cid) or derive_deterministic_route(lowered, u_res, v_res, allocated_set)
            if route:
                for bus_id in route:
                    bus_data_kb[bus_id] += edge.data_kb

    bus_bandwidth_usage: Dict[str, float] = {}
    if throughput_fps is not None:
        for bus_id, kb in bus_data_kb.items():
            bw_mb_s = (kb / 1000.0) * throughput_fps
            bus_bandwidth_usage[bus_id] = bw_mb_s

    # 7. Check Constraints & Capacity Limits
    constraints = lowered.project.constraints
    actual_power_mw = (avg_power_w * 1000.0) if avg_power_w is not None else None

    checks = [
        ("latency", constraints.max_latency_ms, latency, time_unit, False),
        ("throughput", constraints.min_throughput_fps, throughput_fps, "fps", True),
        ("energy", constraints.max_total_energy_mj, total_energy_mj, "mJ", False),
        ("avg_power", constraints.max_avg_power_mw, actual_power_mw, "mW", False),
        ("allocation_cost", constraints.max_allocation_cost, allocation_cost, "cost", False),
        ("memory", constraints.max_memory_kb, declared_memory_kb, "KB", False),
    ]

    for metric, limit, actual, unit, is_min in checks:
        if limit is not None:
            if actual is None or (actual < limit if is_min else actual > limit):
                violations.append(
                    ConstraintViolation(
                        metric=metric,
                        limit=limit,
                        actual=(0.0 if is_min else float("inf")) if actual is None else actual,
                        unit=unit,
                    )
                )

    # Check capacity limits per resource
    for res_id in candidate.allocated_resources:
        res = lowered.resources_by_id[res_id]
        if res.capacity:
            for cap_name, cap_limit in res.capacity.items():
                usage_val = area_usage.get(cap_name, 0.0)
                if usage_val > cap_limit:
                    violations.append(
                        ConstraintViolation(
                            metric=f"capacity_{res_id}_{cap_name}",
                            limit=cap_limit,
                            actual=usage_val,
                            unit=cap_name,
                        )
                    )

    # Check capacity groups
    for group in lowered.project.architecture.capacity_groups:
        group_usage: Dict[str, float] = defaultdict(float)
        for member_res_id in group.resource_ids:
            if member_res_id in allocated_set:
                for node_id, res_id in candidate.bindings.items():
                    if res_id == member_res_id:
                        opt = lowered.mapping_options_by_node.get(node_id, {}).get(res_id)
                        if opt:
                            for dim, val in opt.usage.items():
                                group_usage[dim] += val
        for dim, limit in group.limits.items():
            actual_dim = group_usage[dim]
            if actual_dim > limit:
                violations.append(
                    ConstraintViolation(
                        metric=f"capacity_group_{group.id}_{dim}",
                        limit=limit,
                        actual=actual_dim,
                        unit=dim,
                    )
                )

    result = EvaluationResult(
        design_id=candidate.id,
        feasible=(len(violations) == 0),
        violations=violations,
        latency_ms=latency,
        throughput_fps=throughput_fps,
        steady_state_ii_ms=steady_state_ii_ms,
        energy_mj=total_energy_mj,
        avg_power_w=avg_power_w,
        allocation_cost=allocation_cost,
        area_usage=dict(area_usage),
        memory_kb=declared_memory_kb,
        bus_bandwidth_usage=bus_bandwidth_usage,
        schedule=schedule,
    )

    candidate.evaluation = result
    return result
