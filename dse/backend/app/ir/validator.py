"""IR Validation module for the DSE framework.

Performs comprehensive validation of ProjectIR:
- Schema rules, uniqueness, and reference integrity
- Directed Acyclic Graph (DAG) cycle detection
- Resource kinds, bus topologies, and capacity groups
- Compute node implementation option coverage and timing specifications
- Communication route feasibility
"""

from typing import Dict, List, Set, Tuple
from collections import defaultdict, deque
from pydantic import BaseModel, Field

from app.ir.models import ProjectIR
from app.ir.types import ResourceKind, ValidationSeverity


class ValidationIssue(BaseModel):
    """A single validation finding (error or warning)."""
    severity: ValidationSeverity
    path: str
    message: str
    code: str


class ValidationResult(BaseModel):
    """Aggregate result of validating a ProjectIR."""
    is_valid: bool
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)

    def add_error(self, path: str, message: str, code: str) -> None:
        self.errors.append(ValidationIssue(severity=ValidationSeverity.ERROR, path=path, message=message, code=code))
        self.is_valid = False

    def add_warning(self, path: str, message: str, code: str) -> None:
        self.warnings.append(ValidationIssue(severity=ValidationSeverity.WARNING, path=path, message=message, code=code))


def validate_project(project: ProjectIR) -> ValidationResult:
    """Validate a complete ProjectIR against all architectural constraints."""
    result = ValidationResult(is_valid=True)

    # 1. Validate Problem Nodes
    node_ids: Set[str] = set()
    for idx, node in enumerate(project.problem.nodes):
        path = f"problem.nodes[{idx}]"
        if not node.id.strip():
            result.add_error(f"{path}.id", "Node id must not be empty", "EMPTY_ID")
        elif node.id in node_ids:
            result.add_error(f"{path}.id", f"Duplicate node id '{node.id}'", "DUPLICATE_ID")
        node_ids.add(node.id)

        if node.memory_kb < 0:
            result.add_error(f"{path}.memory_kb", f"Memory footprint must be non-negative, got {node.memory_kb}", "NEGATIVE_VALUE")
        if node.input_kb < 0:
            result.add_error(f"{path}.input_kb", f"Input size must be non-negative, got {node.input_kb}", "NEGATIVE_VALUE")
        if node.output_kb < 0:
            result.add_error(f"{path}.output_kb", f"Output size must be non-negative, got {node.output_kb}", "NEGATIVE_VALUE")

    # 2. Validate Architecture Resources
    resource_ids: Set[str] = set()
    resources_by_id: Dict[str, Any] = {}
    bus_ids: Set[str] = set()
    compute_resource_ids: Set[str] = set()

    for idx, res in enumerate(project.architecture.resources):
        path = f"architecture.resources[{idx}]"
        if not res.id.strip():
            result.add_error(f"{path}.id", "Resource id must not be empty", "EMPTY_ID")
        elif res.id in resource_ids:
            result.add_error(f"{path}.id", f"Duplicate resource id '{res.id}'", "DUPLICATE_ID")
        resource_ids.add(res.id)
        resources_by_id[res.id] = res

        if res.allocation_cost < 0:
            result.add_error(f"{path}.allocation_cost", f"Allocation cost must be non-negative, got {res.allocation_cost}", "NEGATIVE_VALUE")
        if res.max_parallel < 1:
            result.add_error(f"{path}.max_parallel", f"max_parallel must be >= 1, got {res.max_parallel}", "INVALID_VALUE")

        if res.kind == ResourceKind.BUS:
            bus_ids.add(res.id)
            if res.bandwidth_mb_per_s is not None and res.bandwidth_mb_per_s <= 0:
                result.add_error(f"{path}.bandwidth_mb_per_s", f"Bandwidth must be positive, got {res.bandwidth_mb_per_s}", "INVALID_VALUE")
            if res.setup_latency_ms < 0:
                result.add_error(f"{path}.setup_latency_ms", f"Setup latency must be non-negative, got {res.setup_latency_ms}", "NEGATIVE_VALUE")
            if len(res.connects) < 2:
                result.add_warning(f"{path}.connects", f"Bus '{res.id}' connects fewer than 2 endpoints", "DEGENERATE_BUS")
        else:
            compute_resource_ids.add(res.id)
            if res.clock_mhz is not None and res.clock_mhz <= 0:
                result.add_error(f"{path}.clock_mhz", f"Clock must be positive, got {res.clock_mhz}", "INVALID_VALUE")

    # Validate Bus Endpoints Exist
    for idx, res in enumerate(project.architecture.resources):
        if res.kind == ResourceKind.BUS:
            path = f"architecture.resources[{idx}].connects"
            for endpoint in res.connects:
                if endpoint not in resource_ids:
                    result.add_error(path, f"Bus '{res.id}' connects to unknown resource '{endpoint}'", "UNKNOWN_RESOURCE")

    # Validate Node Fixed Resource
    for idx, node in enumerate(project.problem.nodes):
        if node.fixed_resource_id:
            path = f"problem.nodes[{idx}].fixed_resource_id"
            if node.fixed_resource_id not in resource_ids:
                result.add_error(path, f"Fixed resource '{node.fixed_resource_id}' does not exist", "UNKNOWN_RESOURCE")
            elif node.fixed_resource_id in bus_ids:
                result.add_error(path, f"Compute node cannot be fixed to bus '{node.fixed_resource_id}'", "INVALID_RESOURCE_KIND")

    # 3. Validate Edges and Check for DAG Cycles
    edge_comm_ids: Set[str] = set()
    adjacency: Dict[str, List[str]] = defaultdict(list)
    in_degree: Dict[str, int] = {nid: 0 for nid in node_ids}

    for idx, edge in enumerate(project.problem.edges):
        path = f"problem.edges[{idx}]"
        src = edge.source_id
        dst = edge.destination_id

        if src not in node_ids:
            result.add_error(f"{path}.from", f"Edge source '{src}' does not exist in nodes", "UNKNOWN_NODE")
        if dst not in node_ids:
            result.add_error(f"{path}.to", f"Edge destination '{dst}' does not exist in nodes", "UNKNOWN_NODE")

        if src in node_ids and dst in node_ids:
            if src == dst:
                result.add_error(path, f"Self-loop detected on node '{src}'", "CYCLE_DETECTED")
            else:
                adjacency[src].append(dst)
                in_degree[dst] = in_degree.get(dst, 0) + 1

        if edge.data_kb < 0:
            result.add_error(f"{path}.data_kb", f"Data volume must be non-negative, got {edge.data_kb}", "NEGATIVE_VALUE")

        if edge.comm_id:
            if edge.comm_id in edge_comm_ids:
                result.add_error(f"{path}.comm_id", f"Duplicate comm_id '{edge.comm_id}'", "DUPLICATE_ID")
            edge_comm_ids.add(edge.comm_id)

    # Topological sorting / Cycle detection using Kahn's algorithm
    queue = deque([nid for nid in node_ids if in_degree[nid] == 0])
    visited_count = 0
    while queue:
        curr = queue.popleft()
        visited_count += 1
        for neighbor in adjacency[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < len(node_ids):
        # Find which nodes participate in cycle
        unvisited = [nid for nid, deg in in_degree.items() if deg > 0]
        result.add_error(
            "problem.edges",
            f"Cycle detected in application problem graph involving nodes: {', '.join(sorted(unvisited))}",
            "CYCLE_DETECTED"
        )

    # 4. Validate Capacity Groups
    group_ids: Set[str] = set()
    for idx, grp in enumerate(project.architecture.capacity_groups):
        path = f"architecture.capacity_groups[{idx}]"
        if not grp.id.strip():
            result.add_error(f"{path}.id", "Capacity group id must not be empty", "EMPTY_ID")
        elif grp.id in group_ids:
            result.add_error(f"{path}.id", f"Duplicate capacity group id '{grp.id}'", "DUPLICATE_ID")
        group_ids.add(grp.id)

        for rid in grp.resource_ids:
            if rid not in resource_ids:
                result.add_error(f"{path}.resource_ids", f"Group references unknown resource '{rid}'", "UNKNOWN_RESOURCE")

        for key, limit in grp.limits.items():
            if limit < 0:
                result.add_error(f"{path}.limits[{key}]", f"Capacity limit must be non-negative, got {limit}", "NEGATIVE_VALUE")

    # 5. Validate Mapping Options
    options_by_node: Dict[str, List[str]] = defaultdict(list)
    seen_pairs: Set[Tuple[str, str]] = set()

    for idx, opt in enumerate(project.mapping.options):
        path = f"mapping.options[{idx}]"
        pair = (opt.node_id, opt.resource_id)

        if opt.node_id not in node_ids:
            result.add_error(f"{path}.node_id", f"Mapping option references unknown node '{opt.node_id}'", "UNKNOWN_NODE")
        if opt.resource_id not in resource_ids:
            result.add_error(f"{path}.resource_id", f"Mapping option references unknown resource '{opt.resource_id}'", "UNKNOWN_RESOURCE")
        elif opt.resource_id in bus_ids:
            result.add_error(f"{path}.resource_id", f"Compute node cannot be mapped to bus '{opt.resource_id}'", "INVALID_RESOURCE_KIND")

        if pair in seen_pairs:
            result.add_error(path, f"Duplicate mapping option for node '{opt.node_id}' on resource '{opt.resource_id}'", "DUPLICATE_MAPPING")
        seen_pairs.add(pair)
        options_by_node[opt.node_id].append(opt.resource_id)

        # Check execution timing resolution
        res = resources_by_id.get(opt.resource_id)
        has_time = opt.execution_time_ms is not None
        has_cycles = opt.execution_cycles is not None

        if not has_time and not has_cycles:
            result.add_error(path, f"Mapping option for '{opt.node_id}' on '{opt.resource_id}' must specify execution_time_ms or execution_cycles", "MISSING_TIMING")
        elif has_time and opt.execution_time_ms < 0:
            result.add_error(f"{path}.execution_time_ms", f"Execution time must be non-negative, got {opt.execution_time_ms}", "NEGATIVE_VALUE")
        elif has_cycles:
            if opt.execution_cycles < 0:
                result.add_error(f"{path}.execution_cycles", f"Cycles must be non-negative, got {opt.execution_cycles}", "NEGATIVE_VALUE")
            if res and not res.clock_mhz:
                result.add_error(path, f"Mapping option specifies execution_cycles but resource '{opt.resource_id}' has no clock_mhz", "MISSING_CLOCK")

    # 6. Verify Option Coverage
    for node in project.problem.nodes:
        opts = options_by_node.get(node.id, [])
        if not opts:
            result.add_error("mapping.options", f"Compute node '{node.id}' has no legal mapping options", "NO_MAPPING_OPTIONS")
        elif node.fixed_resource_id and node.fixed_resource_id not in opts:
            result.add_error(
                "mapping.options",
                f"Node '{node.id}' is fixed to '{node.fixed_resource_id}', but has no mapping option for it",
                "FIXED_RESOURCE_UNMAPPED"
            )

    return result
