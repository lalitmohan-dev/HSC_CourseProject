// Canonical Frontend Types matching the DSE Backend IR

export type ResourceKind = 'processor' | 'hw_module' | 'bus'

export type SearchStrategy = 'exhaustive' | 'random' | 'greedy' | 'nsga2'

export interface ProjectMetadata {
  id?: string
  name: string
  description?: string
  time_unit?: string
  created_at?: string
  updated_at?: string
  display?: Record<string, any>
}

export interface ComputeNode {
  id: string
  name: string
  op_type?: string
  input_kb?: number
  output_kb?: number
  memory_kb?: number
  fixed_resource_id?: string | null
  notes?: string | null
}

export interface DataEdge {
  from: string
  to: string
  data_kb?: number
  comm_id?: string | null
}

export interface ProblemGraph {
  nodes: ComputeNode[]
  edges: DataEdge[]
}

export interface ResourceIR {
  id: string
  name: string
  kind: ResourceKind
  mandatory?: boolean
  allocation_cost?: number
  static_power_mw?: number | null
  clock_mhz?: number | null
  max_parallel?: number
  capacity?: Record<string, number>
  area?: Record<string, number>
  connects?: string[]
  bandwidth_mb_per_s?: number | null
  setup_latency_ms?: number
  power_mw?: number | null
}

export interface CapacityGroup {
  id: string
  name: string
  resource_ids: string[]
  limits: Record<string, number>
}

export interface ArchitectureGraph {
  resources: ResourceIR[]
  capacity_groups?: CapacityGroup[]
}

export interface MappingOption {
  node_id: string
  resource_id: string
  execution_time_ms?: number | null
  execution_cycles?: number | null
  active_power_mw?: number | null
  usage?: Record<string, number>
}

export interface MappingIR {
  options: MappingOption[]
}

export interface ConstraintsIR {
  max_latency_ms?: number | null
  min_throughput_fps?: number | null
  max_total_energy_mj?: number | null
  max_avg_power_mw?: number | null
  max_allocation_cost?: number | null
  max_area?: Record<string, number>
  max_memory_kb?: number | null
}

export interface ObjectivesIR {
  primary?: string
  names?: string[]
  weights?: Record<string, number>
}

export interface SearchSettings {
  strategy: SearchStrategy
  priority_policy?: string
  explicit_priorities?: string[]
  pipelined?: boolean
  budget_evaluations?: number
  seed?: number
  population_size?: number
  generations?: number
}

export interface ScheduledObject {
  id: string
  name: string
  resource_id: string
  start_time: number
  duration: number
  finish_time: number
  is_communication: boolean
  details?: Record<string, any>
}

export interface Schedule {
  objects: ScheduledObject[]
  latency: number
  resource_utilization: Record<string, number>
  critical_path: string[]
}

export interface ConstraintViolation {
  metric: string
  limit: number
  actual: number
  unit: string
  severity: string
}

export interface EvaluationResult {
  design_id: string
  feasible: boolean
  violations: ConstraintViolation[]
  latency_ms: number
  throughput_fps?: number | null
  steady_state_ii_ms?: number | null
  energy_mj?: number | null
  avg_power_w?: number | null
  allocation_cost: number
  area_usage: Record<string, number>
  memory_kb: number
  bus_bandwidth_usage: Record<string, number>
  schedule?: Schedule | null
}

export interface CandidateDesign {
  id: string
  bindings: Record<string, string>
  allocated_resources: string[]
  routes?: Record<string, string[]>
  priority_order?: string[]
  evaluation?: EvaluationResult | null
}

export interface ProjectIR {
  schema_version: number
  meta: ProjectMetadata
  problem: ProblemGraph
  architecture: ArchitectureGraph
  mapping: MappingIR
  constraints: ConstraintsIR
  objectives: ObjectivesIR
  settings: SearchSettings
  designs?: CandidateDesign[]
}

export interface ValidationIssue {
  severity: 'error' | 'warning'
  path: string
  message: string
  code: string
}

export interface ValidationResult {
  is_valid: boolean
  errors: ValidationIssue[]
  warnings: ValidationIssue[]
}

export interface CriticalPathItem {
  id: string
  name: string
  resource_id: string | null
  duration: number
  percentage_of_latency: number
  is_communication: boolean
}

export interface WhatIfAlternative {
  task_id: string
  original_resource: string
  suggested_resource: string
  delta_latency_ms: number
  delta_cost: number
  delta_energy_mj?: number | null
  feasible: boolean
  rationale: string
}

export interface BottleneckReport {
  design_id: string
  total_latency_ms: number
  compute_time_total: number
  communication_time_total: number
  serialization_wait_total: number
  critical_path: CriticalPathItem[]
  resource_utilization: Record<string, number>
  resource_busy_times: Record<string, number>
  bus_bandwidths: Record<string, number>
  what_if_suggestions: WhatIfAlternative[]
}

export interface RecommendationDetails {
  recommended_design_id: string
  objectives_used: string[]
  weights: Record<string, number>
  normalized_scores: Record<string, number>
  rationale: string
  tradeoffs: string[]
}

export interface RunSummary {
  run_id: string
  project_id: string
  status: 'running' | 'completed' | 'cancelled' | 'error'
  elapsed_seconds: number
  evaluated_count: number
  pareto_count: number
  recommended_design?: CandidateDesign | null
  recommendation_details?: RecommendationDetails | null
  pareto_front: CandidateDesign[]
  logs: Array<{ timestamp: string; level: string; message: string }>
}
