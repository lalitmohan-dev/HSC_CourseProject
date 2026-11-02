import type {
  BottleneckReport,
  CandidateDesign,
  EvaluationResult,
  ProjectIR,
  ProjectMetadata,
  RunSummary,
  ValidationResult,
} from '../types'

const BASE_URL = '/api'

export async function fetchProjects(): Promise<ProjectMetadata[]> {
  const res = await fetch(`${BASE_URL}/projects`)
  if (!res.ok) throw new Error('Failed to fetch projects')
  return res.json()
}

export async function fetchProject(id: string): Promise<ProjectIR> {
  const res = await fetch(`${BASE_URL}/projects/${id}`)
  if (!res.ok) throw new Error(`Failed to fetch project ${id}`)
  return res.json()
}

export async function saveProject(id: string, project: ProjectIR): Promise<ProjectIR> {
  const res = await fetch(`${BASE_URL}/projects/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(project),
  })
  if (!res.ok) throw new Error(`Failed to save project ${id}`)
  return res.json()
}

export async function validateProject(id: string): Promise<ValidationResult> {
  const res = await fetch(`${BASE_URL}/projects/${id}/validate`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Failed to validate project ${id}`)
  return res.json()
}

export async function evaluateCandidateDesign(
  projectId: string,
  candidate: CandidateDesign
): Promise<EvaluationResult> {
  const res = await fetch(`${BASE_URL}/projects/${projectId}/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(candidate),
  })
  if (!res.ok) throw new Error('Evaluation failed')
  return res.json()
}

export async function startExploration(projectId: string): Promise<{ run_id: string; status: string }> {
  const res = await fetch(`${BASE_URL}/projects/${projectId}/explore`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to start exploration')
  return res.json()
}

export async function cancelExploration(runId: string): Promise<void> {
  await fetch(`${BASE_URL}/runs/${runId}/cancel`, { method: 'POST' })
}

export async function fetchRunSummary(runId: string): Promise<RunSummary> {
  const res = await fetch(`${BASE_URL}/runs/${runId}`)
  if (!res.ok) throw new Error(`Failed to fetch run summary ${runId}`)
  return res.json()
}

export async function fetchRunDesigns(
  runId: string,
  feasibleOnly = false
): Promise<{ total: number; items: CandidateDesign[] }> {
  const res = await fetch(`${BASE_URL}/runs/${runId}/designs?feasible_only=${feasibleOnly}&page_size=200`)
  if (!res.ok) throw new Error('Failed to fetch designs')
  return res.json()
}

export async function fetchBottlenecks(runId: string, designId?: string): Promise<BottleneckReport> {
  const url = designId
    ? `${BASE_URL}/runs/${runId}/bottlenecks?design_id=${designId}`
    : `${BASE_URL}/runs/${runId}/bottlenecks`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Failed to fetch bottleneck analysis')
  return res.json()
}

export async function compareDesigns(
  projectId: string,
  designIds: string[]
): Promise<{ designs: CandidateDesign[]; metrics_table: Array<Record<string, any>> }> {
  const res = await fetch(`${BASE_URL}/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, design_ids: designIds }),
  })
  if (!res.ok) throw new Error('Failed to compare designs')
  return res.json()
}
