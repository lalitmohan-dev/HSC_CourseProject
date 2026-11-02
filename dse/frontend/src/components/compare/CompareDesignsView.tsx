import React from 'react'
import { useAppStore } from '../../store'

export const CompareDesignsView: React.FC = () => {
  const { allDesigns, runSummary, setActiveView } = useAppStore()

  // Select top 2-3 pareto designs as default for comparison if none selected
  const designsToCompare = runSummary?.pareto_front.slice(0, 3) || allDesigns.slice(0, 3)

  if (designsToCompare.length < 2) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center p-8 bg-gray-900 border border-gray-800 rounded-lg text-gray-500 space-y-3">
        <p>At least 2 designs are required for comparison.</p>
        <button
          onClick={() => setActiveView('results')}
          className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded font-medium"
        >
          Select Designs from Results Table
        </button>
      </div>
    )
  }

  const recId = runSummary?.recommended_design?.id

  return (
    <div className="w-full h-full p-4 flex flex-col bg-gray-900 border border-gray-800 rounded-lg space-y-6 overflow-y-auto">
      <div>
        <h3 className="font-semibold text-lg text-gray-100">Design Comparison</h3>
        <p className="text-xs text-gray-400">Side-by-side metric and architecture allocation trade-offs</p>
      </div>

      {/* Comparison Cards / Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-950 text-gray-400 border-b border-gray-800">
            <tr>
              <th className="p-3 w-44">Metric / Property</th>
              {designsToCompare.map((d) => (
                <th key={d.id} className="p-3">
                  <div className="flex items-center gap-1.5 font-bold text-gray-200">
                    <span>{d.id}</span>
                    {d.id === recId && (
                      <span className="text-[10px] bg-amber-900/60 text-amber-200 border border-amber-700 px-1.5 py-0.5 rounded font-normal">
                        Recommended
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800 text-gray-300">
            <tr>
              <td className="p-3 font-semibold text-gray-400">Feasibility</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3">
                  {d.evaluation?.feasible ? (
                    <span className="text-emerald-400 font-semibold">✓ Feasible</span>
                  ) : (
                    <span className="text-red-400 font-semibold">✕ Infeasible ({d.evaluation?.violations.length})</span>
                  )}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Latency (ms / ticks)</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 font-mono font-bold text-blue-400">
                  {d.evaluation?.latency_ms ?? '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Allocation Cost</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 font-mono font-bold text-gray-200">
                  {d.evaluation?.allocation_cost ?? '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Energy (mJ)</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 font-mono">
                  {d.evaluation?.energy_mj !== null && d.evaluation?.energy_mj !== undefined
                    ? d.evaluation.energy_mj.toFixed(2)
                    : '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Average Power (W)</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 font-mono">
                  {d.evaluation?.avg_power_w !== null && d.evaluation?.avg_power_w !== undefined
                    ? d.evaluation.avg_power_w.toFixed(2)
                    : '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Throughput (fps)</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 font-mono">
                  {d.evaluation?.throughput_fps !== null && d.evaluation?.throughput_fps !== undefined
                    ? d.evaluation.throughput_fps.toFixed(1)
                    : '—'}
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Allocated Resources</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3">
                  <div className="flex flex-wrap gap-1">
                    {d.allocated_resources.map((r) => (
                      <span key={r} className="bg-gray-800 text-gray-200 text-[10px] px-1.5 py-0.5 rounded">
                        {r}
                      </span>
                    ))}
                  </div>
                </td>
              ))}
            </tr>
            <tr>
              <td className="p-3 font-semibold text-gray-400">Task Bindings</td>
              {designsToCompare.map((d) => (
                <td key={d.id} className="p-3 space-y-1">
                  {Object.entries(d.bindings).map(([task, res]) => (
                    <div key={task} className="flex justify-between text-[11px] font-mono">
                      <span className="text-gray-400">{task}:</span>
                      <span className="text-gray-200 font-semibold">{res}</span>
                    </div>
                  ))}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
