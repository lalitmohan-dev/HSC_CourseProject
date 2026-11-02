"""Bottleneck and what-if analysis for candidate designs.

Implements Section 14:
- Critical path inspection (ordered compute and communication objects, duration, % latency)
- Resource busy times and utilization
- Communication time vs compute time breakdown
- Serialization wait delays
- What-if alternative exploration for critical path tasks using the common candidate evaluator
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.ir.models import CandidateDesign, ScheduledObject
from app.ir.lowering import LoweredProblem
from app.core.evaluator import evaluate_candidate, derive_canonical_allocation


class CriticalPathItem(BaseModel):
    id: str
    name: str
    resource_id: Optional[str]
    duration: float
    percentage_of_latency: float
    is_communication: bool


class WhatIfAlternative(BaseModel):
    task_id: str
    original_resource: str
    suggested_resource: str
    delta_latency_ms: float
    delta_cost: float
    delta_energy_mj: Optional[float]
    feasible: bool
    rationale: str


class BottleneckReport(BaseModel):
    design_id: str
    total_latency_ms: float
    compute_time_total: float
    communication_time_total: float
    serialization_wait_total: float
    critical_path: List[CriticalPathItem] = Field(default_factory=list)
    resource_utilization: Dict[str, float] = Field(default_factory=dict)
    resource_busy_times: Dict[str, float] = Field(default_factory=dict)
    bus_bandwidths: Dict[str, float] = Field(default_factory=dict)
    what_if_suggestions: List[WhatIfAlternative] = Field(default_factory=list)


def analyze_bottlenecks(
    lowered: LoweredProblem,
    candidate: CandidateDesign,
) -> BottleneckReport:
    """Computes comprehensive bottleneck statistics and what-if suggestions for a candidate."""
    if not candidate.evaluation or not candidate.evaluation.schedule:
        evaluate_candidate(lowered, candidate)

    ev = candidate.evaluation
    sched = ev.schedule
    total_lat = sched.latency if sched else 0.0

    # 1. Critical Path breakdown
    cp_items: List[CriticalPathItem] = []
    if sched:
        sched_by_id = {s.id: s for s in sched.objects}
        for cid in sched.critical_path:
            s_obj = sched_by_id.get(cid)
            if s_obj:
                pct = (s_obj.duration / total_lat * 100.0) if total_lat > 0 else 0.0
                cp_items.append(
                    CriticalPathItem(
                        id=s_obj.id,
                        name=s_obj.name,
                        resource_id=s_obj.resource_id,
                        duration=s_obj.duration,
                        percentage_of_latency=round(pct, 1),
                        is_communication=s_obj.is_communication,
                    )
                )

    # 2. Timing Breakdown
    compute_total = sum(s.duration for s in sched.objects if not s.is_communication) if sched else 0.0
    comm_total = sum(s.duration for s in sched.objects if s.is_communication) if sched else 0.0

    # Serialization wait: difference between total latency and pure critical path duration
    cp_duration_sum = sum(item.duration for item in cp_items)
    serialization_wait = max(0.0, total_lat - cp_duration_sum)

    # 3. Resource busy times & utilization
    busy_times: Dict[str, float] = {}
    if sched:
        for s in sched.objects:
            if s.resource_id and s.resource_id != "local":
                busy_times[s.resource_id] = busy_times.get(s.resource_id, 0.0) + s.duration

    # 4. What-If Alternatives for tasks on the critical path
    what_ifs: List[WhatIfAlternative] = []
    if sched and total_lat > 0:
        cp_task_ids = [
            item.id for item in cp_items
            if not item.is_communication and item.id in lowered.nodes_by_id
        ]
        for tid in cp_task_ids:
            node = lowered.nodes_by_id[tid]
            if node.fixed_resource_id:
                continue

            curr_res = candidate.bindings.get(tid)
            legal_options = sorted(list(lowered.mapping_options_by_node[tid].keys()))

            for alt_res in legal_options:
                if alt_res == curr_res:
                    continue

                alt_bindings = dict(candidate.bindings)
                alt_bindings[tid] = alt_res
                alt_cand = CandidateDesign(
                    id=f"whatif_{tid}_{alt_res}",
                    bindings=alt_bindings,
                    allocated_resources=derive_canonical_allocation(lowered, alt_bindings),
                )
                alt_eval = evaluate_candidate(lowered, alt_cand)

                d_lat = alt_eval.latency_ms - total_lat
                d_cost = alt_eval.allocation_cost - ev.allocation_cost
                d_energy = (
                    (alt_eval.energy_mj - ev.energy_mj)
                    if (alt_eval.energy_mj is not None and ev.energy_mj is not None)
                    else None
                )

                if d_lat < -1e-6:
                    rationale = f"Rebinding {tid} to {alt_res} accelerates execution by {-d_lat:.2f} ms (ticks)."
                else:
                    rationale = f"Rebinding {tid} to {alt_res} changes latency by {d_lat:+.2f} ms (ticks)."

                what_ifs.append(
                    WhatIfAlternative(
                        task_id=tid,
                        original_resource=curr_res or "",
                        suggested_resource=alt_res,
                        delta_latency_ms=round(d_lat, 3),
                        delta_cost=round(d_cost, 2),
                        delta_energy_mj=round(d_energy, 3) if d_energy is not None else None,
                        feasible=alt_eval.feasible,
                        rationale=rationale,
                    )
                )

    return BottleneckReport(
        design_id=candidate.id,
        total_latency_ms=total_lat,
        compute_time_total=round(compute_total, 3),
        communication_time_total=round(comm_total, 3),
        serialization_wait_total=round(serialization_wait, 3),
        critical_path=cp_items,
        resource_utilization=sched.resource_utilization if sched else {},
        resource_busy_times=busy_times,
        bus_bandwidths=ev.bus_bandwidth_usage,
        what_if_suggestions=what_ifs,
    )
