"""Canonical Intermediate Representation (IR) models for the DSE framework.

Shared data contracts across all modules: IR, Core, Hardware, Search, Persistence, and Reporting.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.ir.types import ResourceKind, TimeUnit, SearchStrategy, PriorityPolicy


class ComputeNode(BaseModel):
    """Compute / operation task node in the application problem graph."""
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    op_type: str = "compute"
    input_kb: float = 0.0
    output_kb: float = 0.0
    memory_kb: float = 0.0
    fixed_resource_id: Optional[str] = None
    notes: Optional[str] = None


class DataEdge(BaseModel):
    """Directed data dependency between compute nodes."""
    model_config = ConfigDict(populate_by_name=True)

    source_id: str = Field(..., alias="from")
    destination_id: str = Field(..., alias="to")
    data_kb: float = 0.0
    comm_id: Optional[str] = None


class ProblemGraph(BaseModel):
    """The application DAG: compute tasks and data dependencies."""
    nodes: List[ComputeNode] = Field(default_factory=list)
    edges: List[DataEdge] = Field(default_factory=list)


class ResourceIR(BaseModel):
    """Architecture platform resource: processor, hardware accelerator, or bus."""
    id: str
    name: str
    kind: ResourceKind = ResourceKind.PROCESSOR
    mandatory: bool = True
    allocation_cost: float = 0.0
    static_power_mw: Optional[float] = None
    clock_mhz: Optional[float] = None
    max_parallel: int = 1
    capacity: Dict[str, float] = Field(default_factory=dict)
    area: Dict[str, float] = Field(default_factory=dict)

    # Bus specific properties
    connects: List[str] = Field(default_factory=list)
    bandwidth_mb_per_s: Optional[float] = None
    setup_latency_ms: float = 0.0
    power_mw: Optional[float] = None


class CapacityGroup(BaseModel):
    """Shared resource pool / group (e.g. FPGA fabric holding multiple HW modules)."""
    id: str
    name: str
    resource_ids: List[str] = Field(default_factory=list)
    limits: Dict[str, float] = Field(default_factory=dict)


class ArchitectureGraph(BaseModel):
    """Platform architecture graph: resources and shared capacity groups."""
    resources: List[ResourceIR] = Field(default_factory=list)
    capacity_groups: List[CapacityGroup] = Field(default_factory=list)


class MappingOption(BaseModel):
    """A legal implementation option for a compute node on a specific resource."""
    node_id: str
    resource_id: str
    execution_time_ms: Optional[float] = None
    execution_cycles: Optional[float] = None
    active_power_mw: Optional[float] = None
    usage: Dict[str, float] = Field(default_factory=dict)


class MappingIR(BaseModel):
    """Legal compute-node/resource implementation alternatives and costs."""
    options: List[MappingOption] = Field(default_factory=list)


class ConstraintsIR(BaseModel):
    """Hard constraints for design-space exploration."""
    max_latency_ms: Optional[float] = None
    min_throughput_fps: Optional[float] = None
    max_total_energy_mj: Optional[float] = None
    max_avg_power_mw: Optional[float] = None
    max_allocation_cost: Optional[float] = None
    max_area: Dict[str, float] = Field(default_factory=dict)
    max_memory_kb: Optional[float] = None


class ObjectivesIR(BaseModel):
    """Optimization objectives and weights."""
    primary: str = "latency"
    names: List[str] = Field(default_factory=lambda: ["latency", "allocation_cost"])
    weights: Dict[str, float] = Field(default_factory=dict)


class SearchSettings(BaseModel):
    """Settings controlling exploration and scheduling algorithms."""
    strategy: SearchStrategy = SearchStrategy.EXHAUSTIVE
    priority_policy: PriorityPolicy = PriorityPolicy.DEFAULT
    explicit_priorities: List[str] = Field(default_factory=list)
    pipelined: bool = False
    budget_evaluations: Optional[int] = 1000
    seed: Optional[int] = 42
    population_size: Optional[int] = 50
    generations: Optional[int] = 50


class ProjectMetadata(BaseModel):
    """Metadata describing a DSE project."""
    id: Optional[str] = None
    name: str = "New Project"
    description: str = ""
    time_unit: str = "ms"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    display: Dict[str, Any] = Field(default_factory=dict)


class ScheduledObject(BaseModel):
    """A single scheduled execution or transfer interval on a resource."""
    id: str
    name: str
    resource_id: str
    start_time: float
    duration: float
    finish_time: float
    is_communication: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class Schedule(BaseModel):
    """Derived deterministic schedule."""
    objects: List[ScheduledObject] = Field(default_factory=list)
    latency: float = 0.0
    resource_utilization: Dict[str, float] = Field(default_factory=dict)
    critical_path: List[str] = Field(default_factory=list)


class ConstraintViolation(BaseModel):
    """Specific metric violation of a hard constraint."""
    metric: str
    limit: float
    actual: float
    unit: str
    severity: str = "error"


class EvaluationResult(BaseModel):
    """Evaluated metrics and constraint feasibility for a candidate design."""
    design_id: str
    feasible: bool = True
    violations: List[ConstraintViolation] = Field(default_factory=list)
    latency_ms: float = 0.0
    throughput_fps: Optional[float] = None
    steady_state_ii_ms: Optional[float] = None
    energy_mj: Optional[float] = None
    avg_power_w: Optional[float] = None
    allocation_cost: float = 0.0
    area_usage: Dict[str, float] = Field(default_factory=dict)
    memory_kb: float = 0.0
    bus_bandwidth_usage: Dict[str, float] = Field(default_factory=dict)
    schedule: Optional[Schedule] = None


class CandidateDesign(BaseModel):
    """A design proposal: allocation, task binding, derived routes, and priority."""
    id: str
    bindings: Dict[str, str] = Field(default_factory=dict)  # node_id -> resource_id
    allocated_resources: List[str] = Field(default_factory=list)
    routes: Dict[str, List[str]] = Field(default_factory=dict)  # comm_id -> list of bus_ids
    priority_order: List[str] = Field(default_factory=list)
    evaluation: Optional[EvaluationResult] = None


class ProjectIR(BaseModel):
    """Top-level canonical intermediate representation for a DSE project."""
    schema_version: int = 2
    meta: ProjectMetadata = Field(default_factory=ProjectMetadata)
    problem: ProblemGraph = Field(default_factory=ProblemGraph)
    architecture: ArchitectureGraph = Field(default_factory=ArchitectureGraph)
    mapping: MappingIR = Field(default_factory=MappingIR)
    constraints: ConstraintsIR = Field(default_factory=ConstraintsIR)
    objectives: ObjectivesIR = Field(default_factory=ObjectivesIR)
    settings: SearchSettings = Field(default_factory=SearchSettings)
    designs: List[CandidateDesign] = Field(default_factory=list)
