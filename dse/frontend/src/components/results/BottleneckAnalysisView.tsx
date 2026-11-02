import React from 'react'
import { useAppStore } from '../../store'

export const BottleneckAnalysisView: React.FC = () => {
  const { bottleneckReport, currentProject } = useAppStore()

  if (!bottleneckReport) {
    return (
      <div className="w-full h-full flex items-center justify-center p-8 bg-gray-900 border border-gray-800 rounded-lg text-gray-500">
        No bottleneck analysis available. Select an evaluated design.
      </div>
    )
  }

  const timeUnit = currentProject?.meta.time_unit || 'ms'

  return (
    <div className="w-full h-full p-4 flex flex-col space-y-6 bg-gray-900 border border-gray-800 rounded-lg overflow-y-auto">
      {/* Header */}
      <div>
        <h3 className="font-semibold text-lg text-gray-100 flex items-center gap-2">
          <span>Bottleneck Analysis · Design:</span>
          <span className="font-mono text-blue-400 font-bold">{bottleneckReport.design_id}</span>
        </h3>
        <p className="text-xs text-gray-400">
          Inspection of the critical path, resource occupancy bottlenecks, and evaluated what-if binding alternatives.
        </p>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 bg-gray-950 rounded border border-gray-800">
          <div className="text-[11px] text-gray-400">Total Latency</div>
          <div className="text-lg font-bold text-gray-100 font-mono mt-0.5">
            {bottleneckReport.total_latency_ms} {timeUnit}
          </div>
        </div>
        <div className="p-3 bg-gray-950 rounded border border-gray-800">
          <div className="text-[11px] text-gray-400">Compute Time</div>
          <div className="text-lg font-bold text-blue-400 font-mono mt-0.5">
            {bottleneckReport.compute_time_total} {timeUnit}
          </div>
        </div>
        <div className="p-3 bg-gray-950 rounded border border-gray-800">
          <div className="text-[11px] text-gray-400">Communication Time</div>
          <div className="text-lg font-bold text-amber-400 font-mono mt-0.5">
            {bottleneckReport.communication_time_total} {timeUnit}
          </div>
        </div>
        <div className="p-3 bg-gray-950 rounded border border-gray-800">
          <div className="text-[11px] text-gray-400">Serialization Waits</div>
          <div className="text-lg font-bold text-purple-400 font-mono mt-0.5">
            {bottleneckReport.serialization_wait_total} {timeUnit}
          </div>
        </div>
      </div>

      {/* Critical Path Sequence */}
      <div className="p-4 bg-gray-950 rounded border border-gray-800">
        <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-3">
          Critical Path Chain (Dominant Latency Path)
        </h4>
        <div className="flex flex-wrap items-center gap-2">
          {bottleneckReport.critical_path.map((item, idx) => (
            <React.Fragment key={item.id}>
              <div className="p-2 rounded bg-gray-900 border border-gray-700 text-xs">
                <div className="font-bold text-gray-200 flex items-center justify-between gap-3">
                  <span>{item.id}</span>
                  <span className="text-[10px] text-amber-400">{item.percentage_of_latency}%</span>
                </div>
                <div className="text-[10px] text-gray-400 mt-0.5">
                  {item.duration} {timeUnit} on {item.resource_id || 'local'}
                </div>
              </div>
              {idx < bottleneckReport.critical_path.length - 1 && (
                <span className="text-gray-600 font-bold">→</span>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Resource Utilization */}
      <div className="p-4 bg-gray-950 rounded border border-gray-800">
        <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-3">
          Resource Busy Times & Utilization
        </h4>
        <div className="space-y-3">
          {Object.entries(bottleneckReport.resource_utilization).map(([resId, util]) => {
            const busy = bottleneckReport.resource_busy_times[resId] || 0
            const pct = Math.round(util * 100)
            return (
              <div key={resId} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold text-gray-300">{resId}</span>
                  <span className="text-gray-400 font-mono">
                    {busy} {timeUnit} ({pct}%)
                  </span>
                </div>
                <div className="w-full h-2 bg-gray-800 rounded overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded"
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  ></div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* What-If Re-evaluations */}
      {bottleneckReport.what_if_suggestions.length > 0 && (
        <div className="p-4 bg-gray-950 rounded border border-gray-800">
          <h4 className="text-xs font-semibold text-gray-300 uppercase tracking-wider mb-3">
            What-If Exploration (Alternative Bindings for Critical Tasks)
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-900 text-gray-400 border-b border-gray-800">
                <tr>
                  <th className="p-2">Task</th>
                  <th className="p-2">Current</th>
                  <th className="p-2">Suggested</th>
                  <th className="p-2">Δ Latency</th>
                  <th className="p-2">Δ Cost</th>
                  <th className="p-2">Feasible?</th>
                  <th className="p-2">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-gray-300">
                {bottleneckReport.what_if_suggestions.map((w, idx) => (
                  <tr key={idx} className="hover:bg-gray-900/50">
                    <td className="p-2 font-bold text-gray-200">{w.task_id}</td>
                    <td className="p-2">{w.original_resource}</td>
                    <td className="p-2 text-blue-400 font-semibold">{w.suggested_resource}</td>
                    <td
                      className={`p-2 font-mono ${
                        w.delta_latency_ms < 0 ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {w.delta_latency_ms > 0 ? `+${w.delta_latency_ms}` : w.delta_latency_ms} {timeUnit}
                    </td>
                    <td className="p-2 font-mono">
                      {w.delta_cost > 0 ? `+${w.delta_cost}` : w.delta_cost}
                    </td>
                    <td className="p-2">
                      {w.feasible ? (
                        <span className="text-emerald-400 font-semibold">✓ Yes</span>
                      ) : (
                        <span className="text-red-400 font-semibold">✕ No</span>
                      )}
                    </td>
                    <td className="p-2 text-gray-400 text-[11px]">{w.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
