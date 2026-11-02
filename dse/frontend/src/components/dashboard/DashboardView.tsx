import React from 'react'
import { useAppStore } from '../../store'
import { ApplicationGraphView } from '../graph/ApplicationGraphView'
import { ExplorationLogView } from './ExplorationLogView'

export const DashboardView: React.FC = () => {
  const { currentProject, selectedTaskId, runSummary, setActiveView } = useAppStore()

  if (!currentProject) {
    return (
      <div className="w-full h-full flex items-center justify-center p-8 bg-gray-900 border border-gray-800 rounded-lg text-gray-500">
        Loading project...
      </div>
    )
  }

  const selectedNode = currentProject.problem.nodes.find((n) => n.id === selectedTaskId)
  const taskOptions = currentProject.mapping.options.filter((o) => o.node_id === selectedTaskId)
  const recDesign = runSummary?.recommended_design
  const recEval = recDesign?.evaluation

  return (
    <div className="w-full h-full flex flex-col space-y-4">
      {/* 5-Panel Responsive Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1">
        {/* Panel 1: Input Configuration Summary */}
        <div className="lg:col-span-3 bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
          <div>
            <h3 className="font-semibold text-gray-100 text-sm mb-1">1. Project Configuration</h3>
            <p className="text-xs text-gray-400 mb-3">{currentProject.meta.description || 'System-level synthesis'}</p>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Time Unit:</span>
                <span className="font-mono text-gray-200">{currentProject.meta.time_unit}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Compute Tasks:</span>
                <span className="font-mono text-gray-200">{currentProject.problem.nodes.length}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Dependencies:</span>
                <span className="font-mono text-gray-200">{currentProject.problem.edges.length}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-800">
                <span className="text-gray-400">Resources:</span>
                <span className="font-mono text-gray-200">{currentProject.architecture.resources.length}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-gray-400">Active Strategy:</span>
                <span className="font-mono text-blue-400 font-semibold">{currentProject.settings.strategy}</span>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-gray-800 flex gap-2">
            <button
              onClick={() => setActiveView('application')}
              className="flex-1 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-center transition"
            >
              Edit Model
            </button>
            <button
              onClick={() => setActiveView('constraints')}
              className="flex-1 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-center transition"
            >
              Settings
            </button>
          </div>
        </div>

        {/* Panel 2: Task Graph Canvas */}
        <div className="lg:col-span-6 bg-gray-900 border border-gray-800 rounded-lg p-2 flex flex-col">
          <div className="flex items-center justify-between px-2 pt-1 pb-2">
            <h3 className="font-semibold text-gray-100 text-sm">2. Task Precedence Graph</h3>
            <button
              onClick={() => setActiveView('application')}
              className="text-xs text-blue-400 hover:underline"
            >
              Full Screen
            </button>
          </div>
          <div className="flex-1 min-h-[300px]">
            <ApplicationGraphView />
          </div>
        </div>

        {/* Panel 3: Selected Task Details */}
        <div className="lg:col-span-3 bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
          <div>
            <h3 className="font-semibold text-gray-100 text-sm mb-1">3. Task Inspector</h3>
            {selectedNode ? (
              <div className="space-y-3 mt-2 text-xs">
                <div className="p-2 bg-gray-950 rounded border border-gray-800">
                  <div className="font-bold text-blue-400">{selectedNode.id}</div>
                  <div className="text-gray-200 text-xs font-medium">{selectedNode.name}</div>
                  <div className="text-gray-500 text-[11px] mt-1">
                    Input: {selectedNode.input_kb} KB · Output: {selectedNode.output_kb} KB · Mem: {selectedNode.memory_kb} KB
                  </div>
                </div>

                <div>
                  <div className="font-semibold text-gray-400 text-[11px] uppercase mb-1">Implementation Options</div>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {taskOptions.map((opt, idx) => (
                      <div key={idx} className="p-1.5 bg-gray-950 rounded border border-gray-800 flex justify-between items-center text-[11px]">
                        <span className="font-semibold text-gray-300">{opt.resource_id}</span>
                        <span className="font-mono text-gray-400">
                          {opt.execution_time_ms !== null && opt.execution_time_ms !== undefined
                            ? `${opt.execution_time_ms} ms`
                            : `${opt.execution_cycles} cyc`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-500 mt-4">Select a task in the graph to view properties.</p>
            )}
          </div>
        </div>

        {/* Panel 4: Exploration Results Summary */}
        <div className="lg:col-span-6 bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-100 text-sm">4. Exploration Results & Recommendation</h3>
              <button onClick={() => setActiveView('results')} className="text-xs text-blue-400 hover:underline">
                View All Results →
              </button>
            </div>

            {recDesign && recEval ? (
              <div className="space-y-3">
                <div className="p-3 bg-amber-950/30 border border-amber-800/60 rounded">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-400 text-xs">★ Recommended: {recDesign.id}</span>
                    <span className="text-[10px] text-emerald-400 font-semibold">✓ Feasible</span>
                  </div>
                  <p className="text-xs text-gray-300 mt-1">
                    {runSummary?.recommendation_details?.rationale}
                  </p>
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="p-2 bg-gray-950 rounded border border-gray-800">
                    <div className="text-[10px] text-gray-500">Latency</div>
                    <div className="font-mono font-bold text-sm text-blue-400">
                      {recEval.latency_ms} {currentProject.meta.time_unit}
                    </div>
                  </div>
                  <div className="p-2 bg-gray-950 rounded border border-gray-800">
                    <div className="text-[10px] text-gray-500">Allocation Cost</div>
                    <div className="font-mono font-bold text-sm text-gray-200">
                      {recEval.allocation_cost}
                    </div>
                  </div>
                  <div className="p-2 bg-gray-950 rounded border border-gray-800">
                    <div className="text-[10px] text-gray-500">Pareto Set</div>
                    <div className="font-mono font-bold text-sm text-emerald-400">
                      {runSummary?.pareto_count} designs
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-6 text-center text-gray-500 text-xs italic">
                No run executed yet. Click "Run DSE" in the top bar to explore design space.
              </div>
            )}
          </div>

          <div className="pt-2 flex gap-2">
            <button
              onClick={() => setActiveView('schedule')}
              className="flex-1 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-center transition"
            >
              Gantt Schedule
            </button>
            <button
              onClick={() => setActiveView('bottlenecks')}
              className="flex-1 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 rounded text-center transition"
            >
              Bottlenecks
            </button>
          </div>
        </div>

        {/* Panel 5: Exploration Log */}
        <div className="lg:col-span-6 bg-gray-900 border border-gray-800 rounded-lg p-2 min-h-[220px]">
          <ExplorationLogView />
        </div>
      </div>
    </div>
  )
}
