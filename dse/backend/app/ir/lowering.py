"""Lowering passes for the DSE framework.

Lowers validated ProjectIR into indexed and resolved LoweredProblem:
- Resolves execution times from cycles/clock frequencies
- Inserts explicit communication objects for each application graph edge
- Builds resource topologies and deterministically derives shortest-hop routes
"""

from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict, deque
from pydantic import BaseModel, Field

from app.ir.models import ComputeNode, DataEdge, ProjectIR, ResourceIR
from app.ir.types import ResourceKind
from app.ir.validator import validate_project, ValidationResult


class ResolvedMappingOption(BaseModel):
    """Mapping option with resolved execution time in ms (or ticks)."""
    node_id: str
    resource_id: str
    execution_time_ms: float
    active_power_mw: Optional[float] = None
    usage: Dict[str, float] = Field(default_factory=dict)


class LoweredCommunicationObject(BaseModel):
    """Lowered communication event corresponding to a data dependency edge."""
    id: str
    source_node_id: str
    destination_node_id: str
    data_kb: float
    edge: DataEdge


class LoweredProblem(BaseModel):
    """Fully resolved and indexed problem representation for scheduling and evaluation."""
    project: ProjectIR
    nodes_by_id: Dict[str, ComputeNode]
    resources_by_id: Dict[str, ResourceIR]
    buses_by_id: Dict[str, ResourceIR]
    comm_objects: List[LoweredCommunicationObject]
    comm_objects_by_id: Dict[str, LoweredCommunicationObject]
    comm_by_edge: Dict[Tuple[str, str], LoweredCommunicationObject]
    predecessors_by_node: Dict[str, List[str]]
    successors_by_node: Dict[str, List[str]]
    mapping_options_by_node: Dict[str, Dict[str, ResolvedMappingOption]]
    bus_connections: Dict[str, Set[str]]  # bus_id -> set of connected resource_ids
    resource_buses: Dict[str, Set[str]]   # resource_id -> set of connected bus_ids


def lower_problem(project: ProjectIR) -> LoweredProblem:
    """Lower a ProjectIR into an indexed LoweredProblem."""
    validation = validate_project(project)
    if not validation.is_valid:
        error_msgs = "; ".join([e.message for e in validation.errors])
        raise ValueError(f"Cannot lower invalid project: {error_msgs}")

    nodes_by_id = {node.id: node for node in project.problem.nodes}
    resources_by_id = {res.id: res for res in project.architecture.resources}
    buses_by_id = {res.id: res for res in project.architecture.resources if res.kind == ResourceKind.BUS}

    # Predecessors and successors
    predecessors_by_node: Dict[str, List[str]] = defaultdict(list)
    successors_by_node: Dict[str, List[str]] = defaultdict(list)
    for edge in project.problem.edges:
        predecessors_by_node[edge.destination_id].append(edge.source_id)
        successors_by_node[edge.source_id].append(edge.destination_id)

    # Lower communication objects (Pass 3)
    comm_objects: List[LoweredCommunicationObject] = []
    comm_objects_by_id: Dict[str, LoweredCommunicationObject] = {}
    comm_by_edge: Dict[Tuple[str, str], LoweredCommunicationObject] = {}

    for idx, edge in enumerate(project.problem.edges):
        cid = edge.comm_id if edge.comm_id else f"C_{edge.source_id}_{edge.destination_id}"
        comm_obj = LoweredCommunicationObject(
            id=cid,
            source_node_id=edge.source_id,
            destination_node_id=edge.destination_id,
            data_kb=edge.data_kb,
            edge=edge,
        )
        comm_objects.append(comm_obj)
        comm_objects_by_id[cid] = comm_obj
        comm_by_edge[(edge.source_id, edge.destination_id)] = comm_obj

    # Resolve mapping option execution times (Pass 4)
    # t_ms = cycles / (clock_mhz * 1000)
    mapping_options_by_node: Dict[str, Dict[str, ResolvedMappingOption]] = defaultdict(dict)
    for opt in project.mapping.options:
        res = resources_by_id[opt.resource_id]
        if opt.execution_time_ms is not None:
            exec_time = opt.execution_time_ms
        elif opt.execution_cycles is not None and res.clock_mhz:
            exec_time = opt.execution_cycles / (res.clock_mhz * 1000.0)
        else:
            raise ValueError(f"Unresolvable execution time for node {opt.node_id} on {opt.resource_id}")

        resolved_opt = ResolvedMappingOption(
            node_id=opt.node_id,
            resource_id=opt.resource_id,
            execution_time_ms=exec_time,
            active_power_mw=opt.active_power_mw,
            usage=opt.usage,
        )
        mapping_options_by_node[opt.node_id][opt.resource_id] = resolved_opt

    # Architecture graph bus connections (Pass 5)
    bus_connections: Dict[str, Set[str]] = defaultdict(set)
    resource_buses: Dict[str, Set[str]] = defaultdict(set)
    for bus_id, bus in buses_by_id.items():
        for endpoint in bus.connects:
            bus_connections[bus_id].add(endpoint)
            resource_buses[endpoint].add(bus_id)

    return LoweredProblem(
        project=project,
        nodes_by_id=nodes_by_id,
        resources_by_id=resources_by_id,
        buses_by_id=buses_by_id,
        comm_objects=comm_objects,
        comm_objects_by_id=comm_objects_by_id,
        comm_by_edge=comm_by_edge,
        predecessors_by_node=predecessors_by_node,
        successors_by_node=successors_by_node,
        mapping_options_by_node=mapping_options_by_node,
        bus_connections=bus_connections,
        resource_buses=resource_buses,
    )


def derive_deterministic_route(
    lowered: LoweredProblem,
    source_resource_id: str,
    target_resource_id: str,
    allocated_resource_ids: Optional[Set[str]] = None,
) -> Optional[List[str]]:
    """Derive deterministic shortest-hop route between two compute resources.

    Returns:
        - [] if source == target (local communication)
        - List of bus IDs [bus1, bus2, ...] in hop order
        - None if no valid route exists through allocated resources
    """
    if source_resource_id == target_resource_id:
        return []

    allocated = (
        allocated_resource_ids
        if allocated_resource_ids is not None
        else set(lowered.resources_by_id.keys())
    )

    if source_resource_id not in allocated or target_resource_id not in allocated:
        return None

    # BFS exploring resource -> bus -> resource transitions
    # Queue stores: (current_resource_id, list_of_bus_ids_taken)
    queue: deque = deque([(source_resource_id, [])])
    visited_resources: Set[str] = {source_resource_id}
    visited_buses: Set[str] = set()

    # Track best path to break ties deterministically by lexical order
    candidates: List[List[str]] = []
    min_hops: Optional[int] = None

    while queue:
        curr_res, path = queue.popleft()

        if min_hops is not None and len(path) > min_hops:
            break

        if curr_res == target_resource_id and len(path) > 0:
            if min_hops is None:
                min_hops = len(path)
            candidates.append(path)
            continue

        # Look at all connected buses that are allocated
        connected_buses = sorted(list(lowered.resource_buses.get(curr_res, set())))
        for bus_id in connected_buses:
            if bus_id not in allocated:
                continue
            if bus_id in path:
                continue  # Avoid loops

            # From this bus, look at all connected endpoints that are allocated
            endpoints = sorted(list(lowered.bus_connections.get(bus_id, set())))
            for next_res in endpoints:
                if next_res not in allocated:
                    continue
                if next_res not in visited_resources or next_res == target_resource_id:
                    visited_resources.add(next_res)
                    queue.append((next_res, path + [bus_id]))

    if not candidates:
        return None

    # Deterministic tie break: stable resource ID ordering
    candidates.sort()
    return candidates[0]


def calculate_hop_transfer_time(bus: ResourceIR, data_kb: float) -> float:
    """Calculate transfer time in ms for one bus hop.

    t_transfer = setup_latency_ms + (data_kb / bandwidth_mb_per_s)
    """
    if bus.bandwidth_mb_per_s and bus.bandwidth_mb_per_s > 0:
        return bus.setup_latency_ms + (data_kb / bus.bandwidth_mb_per_s)
    return bus.setup_latency_ms
