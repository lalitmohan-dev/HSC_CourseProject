"""Deterministic precedence-constrained list scheduler for the DSE framework.

Implements Section 6.3 and Section 7 of the specification:
- Expands application compute tasks and lowered communication objects into a unified scheduling DAG
- Models buses as serial schedulable resources (respecting max_parallel capacity)
- Supports DMA-style non-blocking transfers (bus transfers do not block compute resources)
- Handles zero-duration local communication events without bus reservation
- Deterministic conflict resolution via explicit priority ranking, bottom-level path length, and ID tie-breaking
- Computes critical path and per-resource utilization
- Independently validates precedence and non-overlapping resource occupancy
"""

import heapq
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from app.ir.models import CandidateDesign, Schedule, ScheduledObject
from app.ir.lowering import LoweredProblem, calculate_hop_transfer_time, derive_deterministic_route
from app.ir.types import PriorityPolicy


class SchedulingError(Exception):
    """Raised when scheduling cannot complete due to cycles, missing routes, or infeasibility."""
    pass


class SchedulableObject(BaseModel):
    """An object (compute task or communication transfer) in the expanded scheduling DAG."""
    id: str
    name: str
    resource_id: Optional[str] = None  # None for local communication events
    duration: float = 0.0
    is_communication: bool = False
    is_local: bool = False
    predecessors: List[str] = Field(default_factory=list)
    successors: List[str] = Field(default_factory=list)
    details: Dict[str, Any] = Field(default_factory=dict)


def expand_scheduling_dag(
    lowered: LoweredProblem,
    candidate: CandidateDesign,
) -> Tuple[Dict[str, SchedulableObject], Dict[str, List[str]]]:
    """Expands application tasks and communication edges into a unified scheduling DAG.

    Returns:
        objects_by_id: dict of all compute and communication objects
        derived_routes: dict of communication_id -> list of bus_ids
    """
    allocated_set = set(candidate.allocated_resources) if candidate.allocated_resources else set(lowered.resources_by_id.keys())
    objects: Dict[str, SchedulableObject] = {}
    derived_routes: Dict[str, List[str]] = {}

    # 1. Create compute task objects
    for node_id, node in lowered.nodes_by_id.items():
        if node_id not in candidate.bindings:
            raise SchedulingError(f"Task '{node_id}' is not bound to any resource")

        bound_resource = candidate.bindings[node_id]
        if bound_resource not in allocated_set:
            raise SchedulingError(f"Task '{node_id}' bound to unallocated resource '{bound_resource}'")

        if bound_resource not in lowered.mapping_options_by_node[node_id]:
            raise SchedulingError(f"No mapping option for task '{node_id}' on resource '{bound_resource}'")

        resolved_opt = lowered.mapping_options_by_node[node_id][bound_resource]
        objects[node_id] = SchedulableObject(
            id=node_id,
            name=node.name,
            resource_id=bound_resource,
            duration=resolved_opt.execution_time_ms,
            is_communication=False,
            is_local=False,
            predecessors=[],
            successors=[],
            details={"op_type": node.op_type, "input_kb": node.input_kb, "output_kb": node.output_kb},
        )

    # 2. Create communication objects for each dependency edge u -> v
    for edge in lowered.project.problem.edges:
        u = edge.source_id
        v = edge.destination_id
        res_u = candidate.bindings[u]
        res_v = candidate.bindings[v]

        comm_obj_meta = lowered.comm_by_edge[(u, v)]
        cid = comm_obj_meta.id

        if res_u == res_v:
            # Local communication: duration 0, no bus reserved
            comm_obj = SchedulableObject(
                id=cid,
                name=f"Local Comm {u}->{v}",
                resource_id=None,
                duration=0.0,
                is_communication=True,
                is_local=True,
                predecessors=[u],
                successors=[v],
                details={"source": u, "destination": v, "data_kb": edge.data_kb, "local_resource": res_u},
            )
            objects[cid] = comm_obj
            objects[u].successors.append(cid)
            objects[v].predecessors.append(cid)
            derived_routes[cid] = []
        else:
            # Multi-resource communication: determine route over allocated buses
            explicit_route = candidate.routes.get(cid)
            if explicit_route is not None:
                route = explicit_route
            else:
                route = derive_deterministic_route(lowered, res_u, res_v, allocated_set)

            if route is None:
                raise SchedulingError(f"No communication route between '{res_u}' and '{res_v}' for dependency {u}->{v}")

            derived_routes[cid] = route

            if len(route) == 1:
                # Single-hop transfer
                bus_id = route[0]
                bus_res = lowered.buses_by_id[bus_id]
                duration = calculate_hop_transfer_time(bus_res, edge.data_kb)

                comm_obj = SchedulableObject(
                    id=cid,
                    name=f"Transfer {u}->{v} on {bus_id}",
                    resource_id=bus_id,
                    duration=duration,
                    is_communication=True,
                    is_local=False,
                    predecessors=[u],
                    successors=[v],
                    details={"source": u, "destination": v, "data_kb": edge.data_kb, "route": route},
                )
                objects[cid] = comm_obj
                objects[u].successors.append(cid)
                objects[v].predecessors.append(cid)
            else:
                # Multi-hop transfer: u -> hop_1 -> hop_2 -> ... -> v
                prev_id = u
                for hop_idx, bus_id in enumerate(route):
                    hop_id = f"{cid}_hop{hop_idx + 1}"
                    bus_res = lowered.buses_by_id[bus_id]
                    duration = calculate_hop_transfer_time(bus_res, edge.data_kb)

                    is_last_hop = (hop_idx == len(route) - 1)
                    succ_id = v if is_last_hop else f"{cid}_hop{hop_idx + 2}"

                    hop_obj = SchedulableObject(
                        id=hop_id,
                        name=f"Transfer {u}->{v} [{bus_id}]",
                        resource_id=bus_id,
                        duration=duration,
                        is_communication=True,
                        is_local=False,
                        predecessors=[prev_id],
                        successors=[succ_id],
                        details={"source": u, "destination": v, "data_kb": edge.data_kb, "hop": hop_idx + 1, "bus": bus_id},
                    )
                    objects[hop_id] = hop_obj
                    objects[prev_id].successors.append(hop_id)
                    prev_id = hop_id

                objects[v].predecessors.append(prev_id)

    return objects, derived_routes


def compute_bottom_level_priorities(objects: Dict[str, SchedulableObject]) -> Dict[str, float]:
    """Compute bottom-level (longest remaining path duration to any sink) for all objects."""
    # Topological sort in reverse
    in_degree = {oid: len(obj.successors) for oid, obj in objects.items()}
    queue = deque([oid for oid, deg in in_degree.items() if deg == 0])

    b_level: Dict[str, float] = {oid: objects[oid].duration for oid in queue}

    while queue:
        curr_id = queue.popleft()
        curr_duration = objects[curr_id].duration

        for pred_id in objects[curr_id].predecessors:
            pred_succ_max = max([b_level.get(s, 0.0) for s in objects[pred_id].successors], default=0.0)
            b_level[pred_id] = objects[pred_id].duration + pred_succ_max

            in_degree[pred_id] -= 1
            if in_degree[pred_id] == 0:
                queue.append(pred_id)

    return b_level


def schedule_candidate(
    lowered: LoweredProblem,
    candidate: CandidateDesign,
) -> Schedule:
    """Executes deterministic precedence-constrained list scheduling for a candidate design.

    Returns:
        A validated Schedule object containing start/finish timestamps, latency, utilization, and critical path.
    """
    objects, derived_routes = expand_scheduling_dag(lowered, candidate)
    candidate.routes = derived_routes

    # Compute object priority ranking
    explicit_priorities = candidate.priority_order or lowered.project.settings.explicit_priorities
    priority_rank: Dict[str, int] = {}

    if explicit_priorities:
        for rank, oid in enumerate(explicit_priorities):
            priority_rank[oid] = rank
    else:
        # Bottom-level priority order (higher path length = higher priority = lower rank index)
        b_levels = compute_bottom_level_priorities(objects)
        sorted_objs = sorted(objects.keys(), key=lambda oid: (-b_levels.get(oid, 0.0), oid))
        for rank, oid in enumerate(sorted_objs):
            priority_rank[oid] = rank

    # Precedence tracking
    in_degree: Dict[str, int] = {oid: len(obj.predecessors) for oid, obj in objects.items()}
    ready_objects: Set[str] = {oid for oid, deg in in_degree.items() if deg == 0}

    # Resource occupancy tracking
    # resource_id -> list of (start, finish, object_id)
    resource_timelines: Dict[str, List[Tuple[float, float, str]]] = defaultdict(list)
    resource_capacities: Dict[str, int] = {
        res_id: res.max_parallel for res_id, res in lowered.resources_by_id.items()
    }
    resource_active_count: Dict[str, int] = defaultdict(int)

    scheduled_results: Dict[str, ScheduledObject] = {}

    # Event-driven list scheduling queue
    # Heap stores: (timestamp, event_type, object_id)
    # event_type: 0 for finish
    events: List[Tuple[float, int, str]] = []
    current_time: float = 0.0

    while len(scheduled_results) < len(objects):
        # 1. Process all events completing at or before current_time
        while events and events[0][0] <= current_time:
            event_time, _, obj_id = heapq.heappop(events)
            obj = objects[obj_id]

            if obj.resource_id:
                resource_active_count[obj.resource_id] = max(0, resource_active_count[obj.resource_id] - 1)

            # Release successors
            for succ_id in obj.successors:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    ready_objects.add(succ_id)

        # 2. Process zero-duration ready objects (e.g. local communication events)
        zero_duration_ready = [oid for oid in ready_objects if objects[oid].duration == 0.0]
        # Sort by priority
        zero_duration_ready.sort(key=lambda oid: (priority_rank.get(oid, 999999), oid))

        while zero_duration_ready:
            z_id = zero_duration_ready.pop(0)
            ready_objects.remove(z_id)
            z_obj = objects[z_id]

            # Record schedule for zero-duration object
            scheduled_results[z_id] = ScheduledObject(
                id=z_id,
                name=z_obj.name,
                resource_id=z_obj.resource_id or "local",
                start_time=current_time,
                duration=0.0,
                finish_time=current_time,
                is_communication=z_obj.is_communication,
                details=z_obj.details,
            )

            # Release successors immediately at current_time
            for succ_id in z_obj.successors:
                in_degree[succ_id] -= 1
                if in_degree[succ_id] == 0:
                    ready_objects.add(succ_id)
                    if objects[succ_id].duration == 0.0:
                        zero_duration_ready.append(succ_id)
                        zero_duration_ready.sort(key=lambda oid: (priority_rank.get(oid, 999999), oid))

        # 3. Schedule ready objects onto available resources
        # Group ready objects by resource
        ready_by_resource: Dict[str, List[str]] = defaultdict(list)
        for oid in ready_objects:
            res_id = objects[oid].resource_id
            if res_id:
                ready_by_resource[res_id].append(oid)

        assigned_any = False
        for res_id, candidate_oids in ready_by_resource.items():
            max_cap = resource_capacities.get(res_id, 1)
            active_cap = resource_active_count[res_id]
            avail_slots = max(0, max_cap - active_cap)

            if avail_slots > 0:
                # Sort candidate ready objects by priority rank, then ID
                candidate_oids.sort(key=lambda oid: (priority_rank.get(oid, 999999), oid))
                to_schedule = candidate_oids[:avail_slots]

                for oid in to_schedule:
                    obj = objects[oid]
                    start_t = current_time
                    finish_t = start_t + obj.duration

                    scheduled_results[oid] = ScheduledObject(
                        id=oid,
                        name=obj.name,
                        resource_id=res_id,
                        start_time=start_t,
                        duration=obj.duration,
                        finish_time=finish_t,
                        is_communication=obj.is_communication,
                        details=obj.details,
                    )

                    ready_objects.remove(oid)
                    resource_active_count[res_id] += 1
                    resource_timelines[res_id].append((start_t, finish_t, oid))
                    heapq.heappush(events, (finish_t, 0, oid))
                    assigned_any = True

        # 4. Advance time
        if events:
            # Advance to earliest upcoming event
            current_time = events[0][0]
        elif len(scheduled_results) < len(objects):
            # Deadlock: ready objects exist but cannot be assigned or no progress can be made
            unscheduled = [oid for oid in objects if oid not in scheduled_results]
            raise SchedulingError(f"Scheduling deadlock: unscheduled objects remain {unscheduled}")

    # Calculate total latency and critical path
    scheduled_list = list(scheduled_results.values())
    total_latency = max((s.finish_time for s in scheduled_list), default=0.0)

    # Compute resource utilization
    utilization: Dict[str, float] = {}
    for res_id in candidate.allocated_resources or lowered.resources_by_id.keys():
        busy_time = sum(s.duration for s in scheduled_list if s.resource_id == res_id)
        utilization[res_id] = (busy_time / total_latency) if total_latency > 0 else 0.0

    # Derive critical path by tracing backward from final object(s)
    critical_path: List[str] = []
    if scheduled_list:
        max_finish = max(s.finish_time for s in scheduled_list)
        end_objects = [s.id for s in scheduled_list if s.finish_time == max_finish]
        curr = end_objects[0]
        critical_path.append(curr)

        while True:
            curr_obj = objects[curr]
            curr_sched = scheduled_results[curr]
            # Look for predecessor that finished exactly at curr_sched.start_time
            pred_match = None
            for p in curr_obj.predecessors:
                if scheduled_results[p].finish_time == curr_sched.start_time:
                    pred_match = p
                    break

            if not pred_match and curr_obj.resource_id:
                # Check for preceding object on the same resource
                same_res = [
                    s for s in scheduled_list
                    if s.resource_id == curr_obj.resource_id and s.finish_time == curr_sched.start_time
                ]
                if same_res:
                    pred_match = same_res[0].id

            if pred_match and pred_match not in critical_path:
                critical_path.append(pred_match)
                curr = pred_match
            else:
                break

        critical_path.reverse()

    # 5. Independent validation of schedule correctness
    _validate_derived_schedule(objects, scheduled_results, resource_capacities)

    return Schedule(
        objects=scheduled_list,
        latency=total_latency,
        resource_utilization=utilization,
        critical_path=critical_path,
    )


def _validate_derived_schedule(
    objects: Dict[str, SchedulableObject],
    schedule: Dict[str, ScheduledObject],
    resource_capacities: Dict[str, int],
) -> None:
    """Independently verifies that precedence relations and resource capacity limits hold."""
    # Precedence check: for every u -> v, finish(u) <= start(v)
    for obj_id, obj in objects.items():
        v_sched = schedule[obj_id]
        for pred_id in obj.predecessors:
            u_sched = schedule[pred_id]
            if u_sched.finish_time > v_sched.start_time + 1e-9:
                raise SchedulingError(
                    f"Precedence violation: {pred_id} finished at {u_sched.finish_time} "
                    f"after {obj_id} started at {v_sched.start_time}"
                )

    # Resource capacity check: no overlapping intervals exceeding max_parallel
    by_res: Dict[str, List[Tuple[float, float, str]]] = defaultdict(list)
    for s in schedule.values():
        if s.resource_id and s.resource_id != "local":
            by_res[s.resource_id].append((s.start_time, s.finish_time, s.id))

    for res_id, intervals in by_res.items():
        max_parallel = resource_capacities.get(res_id, 1)
        # Check all event points
        points: List[Tuple[float, int]] = []
        for start, finish, _ in intervals:
            if finish > start:
                points.append((start, 1))
                points.append((finish, -1))
        # Sort points: finishes (-1) before starts (+1) on same timestamp
        points.sort(key=lambda p: (p[0], p[1]))

        current_occupancy = 0
        for t, delta in points:
            current_occupancy += delta
            if current_occupancy > max_parallel:
                raise SchedulingError(
                    f"Resource capacity exceeded on '{res_id}': {current_occupancy} > {max_parallel} at time {t}"
                )
