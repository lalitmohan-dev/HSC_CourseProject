import React, { useState } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useAppStore } from '../../store'

export const ParetoChartView: React.FC = () => {
  const { allDesigns, runSummary, selectedDesignId, setSelectedDesignId } = useAppStore()
  const [xMetric, setXMetric] = useState<string>('latency_ms')
  const [yMetric, setYMetric] = useState<string>('allocation_cost')

  const paretoIds = new Set(runSummary?.pareto_front.map((c) => c.id) || [])
  const recId = runSummary?.recommended_design?.id

  const data = allDesigns
    .filter((d) => d.evaluation)
    .map((d) => {
      const ev = d.evaluation!
      return {
        id: d.id,
        x: (ev as any)[xMetric] ?? 0,
        y: (ev as any)[yMetric] ?? 0,
        isPareto: paretoIds.has(d.id),
        isRecommended: d.id === recId,
        isSelected: d.id === selectedDesignId,
        feasible: ev.feasible,
      }
    })

  return (
    <div className="w-full h-full p-4 flex flex-col bg-gray-900 border border-gray-800 rounded-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-100">Design Space & Pareto Frontier</h3>
          <p className="text-xs text-gray-400">Click any design point to inspect schedule & bottlenecks</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs text-gray-300">
            <span>X:</span>
            <select
              value={xMetric}
              onChange={(e) => setXMetric(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200"
            >
              <option value="latency_ms">Latency (ms / ticks)</option>
              <option value="allocation_cost">Allocation Cost</option>
              <option value="energy_mj">Energy (mJ)</option>
              <option value="avg_power_w">Avg Power (W)</option>
            </select>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-gray-300">
            <span>Y:</span>
            <select
              value={yMetric}
              onChange={(e) => setYMetric(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-200"
            >
              <option value="allocation_cost">Allocation Cost</option>
              <option value="latency_ms">Latency (ms / ticks)</option>
              <option value="energy_mj">Energy (mJ)</option>
              <option value="avg_power_w">Avg Power (W)</option>
            </select>
          </div>
        </div>
      </div>

      <div className="flex-1 w-full min-h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 30, bottom: 20, left: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              type="number"
              dataKey="x"
              name={xMetric}
              stroke="#64748b"
              fontSize={11}
              label={{ value: xMetric, position: 'bottom', fill: '#64748b', fontSize: 11, offset: 0 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name={yMetric}
              stroke="#64748b"
              fontSize={11}
              label={{ value: yMetric, angle: -90, position: 'left', fill: '#64748b', fontSize: 11 }}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (active && payload && payload.length) {
                  const pt = payload[0].payload
                  return (
                    <div className="bg-gray-950 p-2.5 rounded border border-gray-700 shadow-xl text-xs space-y-1">
                      <div className="font-bold text-blue-400">{pt.id}</div>
                      <div>
                        {xMetric}: <span className="font-mono text-gray-200">{pt.x}</span>
                      </div>
                      <div>
                        {yMetric}: <span className="font-mono text-gray-200">{pt.y}</span>
                      </div>
                      {pt.isRecommended && <div className="text-amber-400 font-semibold">★ Recommended Design</div>}
                      {pt.isPareto && !pt.isRecommended && (
                        <div className="text-emerald-400 font-semibold">● Pareto Optimal</div>
                      )}
                      {!pt.feasible && <div className="text-red-400">✕ Infeasible</div>}
                    </div>
                  )
                }
                return null
              }}
            />
            <Scatter
              data={data}
              onClick={(pt: any) => setSelectedDesignId(pt.id)}
              cursor="pointer"
            >
              {data.map((entry, index) => {
                let fill = '#475569' // dominated
                if (!entry.feasible) fill = '#ef4444' // infeasible
                else if (entry.isRecommended) fill = '#f59e0b' // star/recommended
                else if (entry.isPareto) fill = '#10b981' // pareto optimal

                const stroke = entry.isSelected ? '#ffffff' : 'none'
                const strokeWidth = entry.isSelected ? 2 : 0

                return (
                  <Cell
                    key={`cell-${index}`}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={strokeWidth}
                    r={entry.isRecommended ? 7 : entry.isPareto ? 6 : 4}
                  />
                )
              })}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-center gap-6 mt-2 pt-2 border-t border-gray-800 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-amber-500 inline-block"></span>
          <span>Recommended</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block"></span>
          <span>Pareto Optimal</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-slate-600 inline-block"></span>
          <span>Feasible</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span>
          <span>Infeasible</span>
        </div>
      </div>
    </div>
  )
}
