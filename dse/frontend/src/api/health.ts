export interface HealthStatus {
  status: string
  version: string
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch('/api/health')
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`)
  return res.json()
}
