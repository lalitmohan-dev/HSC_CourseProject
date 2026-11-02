import React, { useState } from 'react'
import { useAppStore } from '../../store'

export const DesignsTableView: React.FC = () => {
  const { allDesigns, runSummary, selectedDesignId, setSelectedDesignId, setActiveView } = useAppStore()
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const [filterFeasibleOnly, setFilterFeasibleOnly] = useState<boolean>(false)

  const paretoIds = new Set(runSummary?.pareto_front.map((c) => c.id) || [])
  const recId = runSummary?.recommended_design?.id

  let filtered = allDesigns.filter((d) => {
    if (filterFeasibleOnly) return d.evaluation?.feasible
    return true
  })

  const toggleCompare = (id: string) => {
    if (selectedForCompare.includes(id)) {
      setSelectedForCompare(selectedForCompare.filter((x) => x !== id))
    } else {
      if (selectedForCompare.length < 4) {
        setSelectedForCompare([...selectedForCompare, id])
      }
    }
  }

  const exportCSV = () => {
    const headers = ['ID', 'Feasible', 'Pareto', 'Latency', 'Cost', 'Energy', 'Power', 'Bindings']
    const rows = filtered.map((d) => {
      const ev = d.evaluation
      return [
        d.id,
        ev?.feasible ? 'YES' : 'NO',
        paretoIds.has(d.id) ? 'YES' : 'NO',
        ev?.latency_ms ?? '',
        ev?.allocation_cost ?? '',
        ev?.energy_mj ?? '',
        ev?.avg_power_w ?? '',
        JSON.stringify(d.bindings).replace(/"/g, '""'),
      ].join(',')
    })
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows].join('\n')
    const encodedUri = encodeURI(csvContent)
    const link = document.createElement('a')
    link.setAttribute('href', encodedUri)
    link.setAttribute('download', `dse_designs_${runSummary?.run_id || 'run'}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div className="w-full h-full p-4 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Table Header Controls */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-100">All Evaluated Designs ({filtered.length})</h3>
          <p className="text-xs text-gray-400">Sort, filter, select candidates, or compare 2–4 designs</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-gray-300 cursor-pointer">
            <input
              type="checkbox"
              checked={filterFeasibleOnly}
              onChange={(e) => setFilterFeasibleOnly(e.target.checked)}
              className="rounded bg-gray-800 border-gray-700"
            />
            <span>Feasible Only</span>
          </label>
          <button
            onClick={exportCSV}
            className="px-2.5 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 rounded transition"
          >
            Export CSV
          </button>
          {selectedForCompare.length >= 2 && (
            <button
              onClick={() => setActiveView('compare')}
              className="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 font-semibold text-white rounded transition shadow"
            >
              Compare ({selectedForCompare.length})
            </button>
          )}
        </div>
      </div>

      {/* Table Container */}
      <div className="flex-1 overflow-auto border border-gray-800 rounded">
        <table className="w-full text-left text-xs">
          <thead className="bg-gray-950 text-gray-400 sticky top-0 border-b border-gray-800">
            <tr>
              <th className="p-2.5 w-8"></th>
              <th className="p-2.5">Design ID</th>
              <th className="p-2.5">Status</th>
              <th className="p-2.5">Latency</th>
              <th className="p-2.5">Alloc Cost</th>
              <th className="p-2.5">Energy (mJ)</th>
              <th className="p-2.5">Avg Power (W)</th>
              <th className="p-2.5">Task Bindings</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800 text-gray-300">
            {filtered.map((d) => {
              const ev = d.evaluation
              const isSelected = d.id === selectedDesignId
              const isPareto = paretoIds.has(d.id)
              const isRec = d.id === recId
              const checkedForCmp = selectedForCompare.includes(d.id)

              return (
                <tr
                  key={d.id}
                  onClick={() => setSelectedDesignId(d.id)}
                  className={`cursor-pointer transition ${
                    isSelected ? 'bg-blue-900/30' : 'hover:bg-gray-800/40'
                  }`}
                >
                  <td className="p-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={checkedForCmp}
                      onChange={() => toggleCompare(d.id)}
                      className="rounded bg-gray-800 border-gray-700"
                    />
                  </td>
                  <td className="p-2.5 font-bold flex items-center gap-1.5">
                    <span className="text-gray-100 font-mono">{d.id}</span>
                    {isRec && <span className="text-amber-400 text-xs" title="Recommended">★</span>}
                    {isPareto && !isRec && <span className="text-emerald-400 text-xs" title="Pareto Optimal">●</span>}
                  </td>
                  <td className="p-2.5">
                    {ev?.feasible ? (
                      <span className="text-emerald-400 font-semibold">Feasible</span>
                    ) : (
                      <span className="text-red-400">Infeasible ({ev?.violations.length})</span>
                    )}
                  </td>
                  <td className="p-2.5 font-mono text-gray-200">{ev?.latency_ms}</td>
                  <td className="p-2.5 font-mono text-gray-200">{ev?.allocation_cost}</td>
                  <td className="p-2.5 font-mono text-gray-400">
                    {ev?.energy_mj !== null && ev?.energy_mj !== undefined ? ev.energy_mj.toFixed(2) : '—'}
                  </td>
                  <td className="p-2.5 font-mono text-gray-400">
                    {ev?.avg_power_w !== null && ev?.avg_power_w !== undefined ? ev.avg_power_w.toFixed(2) : '—'}
                  </td>
                  <td className="p-2.5 text-gray-400 truncate max-w-xs font-mono text-[11px]">
                    {Object.entries(d.bindings)
                      .map(([t, r]) => `${t}→${r}`)
                      .join(', ')}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
