import { useEffect, useState } from 'react'

interface HealthStatus {
  status: string
  version: string
}

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex items-center justify-center">
      <div className="text-center space-y-6">
        <h1 className="text-4xl font-bold text-blue-400">
          DSE Framework
        </h1>
        <p className="text-lg text-gray-400">
          Hardware–Software Co-design / Design Space Exploration
        </p>
        <div className="mt-8 p-4 rounded-lg bg-gray-900 border border-gray-800">
          {error ? (
            <p className="text-red-400">Backend not connected: {error}</p>
          ) : health ? (
            <div className="space-y-1">
              <p className="text-green-400">✓ Backend connected</p>
              <p className="text-gray-500 text-sm">Status: {health.status} · Version: {health.version}</p>
            </div>
          ) : (
            <p className="text-gray-500">Connecting to backend...</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
