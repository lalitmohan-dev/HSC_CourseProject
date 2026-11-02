import React, { useState } from 'react'
import { useAppStore } from '../../store'
import type { SearchStrategy } from '../../types'

type NumericConstraintKey =
  | 'max_latency_ms'
  | 'min_throughput_fps'
  | 'max_allocation_cost'
  | 'max_memory_kb'
  | 'max_total_energy_mj'
  | 'max_avg_power_mw'

export const ConstraintsSettingsView: React.FC = () => {
  const { currentProject, updateCurrentProject, saveCurrentProject } = useAppStore()

  if (!currentProject) return null

  const [settings, setSettings] = useState(currentProject.settings)
  const [constraints, setConstraints] = useState(currentProject.constraints)
  const [savedSuccess, setSavedSuccess] = useState(false)

  const constraintFields: { key: NumericConstraintKey; label: string }[] = [
    { key: 'max_latency_ms', label: `Max Latency (${currentProject.meta.time_unit || 'ms'})` },
    { key: 'min_throughput_fps', label: 'Min Throughput (fps)' },
    { key: 'max_allocation_cost', label: 'Max Allocation Cost' },
    { key: 'max_memory_kb', label: 'Max Memory (KB)' },
    { key: 'max_total_energy_mj', label: 'Max Energy (mJ)' },
    { key: 'max_avg_power_mw', label: 'Max Avg Power (mW)' },
  ]

  const handleSave = async () => {
    const updated = {
      ...currentProject,
      settings,
      constraints,
    }
    updateCurrentProject(updated)
    await saveCurrentProject()
    setSavedSuccess(true)
    setTimeout(() => setSavedSuccess(false), 2500)
  }

  return (
    <div className="w-full h-full p-4 flex flex-col space-y-6 bg-gray-900 border border-gray-800 rounded-lg overflow-y-auto">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-lg text-gray-100">Constraints & Exploration Settings</h3>
          <p className="text-xs text-gray-400">Configure hard constraints and search algorithm parameters</p>
        </div>
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 font-semibold text-xs text-white rounded transition flex items-center gap-2 shadow"
        >
          {savedSuccess ? '✓ Saved!' : 'Save Settings'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Search Algorithm Settings */}
        <div className="p-4 bg-gray-950 rounded border border-gray-800 space-y-4">
          <h4 className="text-sm font-semibold text-blue-400 border-b border-gray-800 pb-2">
            Search Strategy Configuration
          </h4>

          <div className="space-y-1">
            <label className="text-xs text-gray-300 font-medium">Exploration Strategy</label>
            <select
              value={settings.strategy}
              onChange={(e) => setSettings({ ...settings, strategy: e.target.value as SearchStrategy })}
              className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
            >
              <option value="exhaustive">Exhaustive Search (Guaranteed Global Pareto Front)</option>
              <option value="random">Random Sampling (Fast Broad Exploration)</option>
              <option value="greedy">Greedy Local Search with Restarts</option>
              <option value="nsga2">NSGA-II Multi-Objective Genetic Algorithm</option>
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-gray-300 font-medium">Evaluation Budget</label>
              <input
                type="number"
                value={settings.budget_evaluations ?? 1000}
                onChange={(e) => setSettings({ ...settings, budget_evaluations: parseInt(e.target.value) || 100 })}
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-gray-300 font-medium">Random Seed</label>
              <input
                type="number"
                value={settings.seed ?? 42}
                onChange={(e) => setSettings({ ...settings, seed: parseInt(e.target.value) || 0 })}
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-xs text-gray-300 font-medium">Population Size (NSGA-II)</label>
              <input
                type="number"
                value={settings.population_size ?? 50}
                onChange={(e) => setSettings({ ...settings, population_size: parseInt(e.target.value) || 20 })}
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-gray-300 font-medium">Generations (NSGA-II)</label>
              <input
                type="number"
                value={settings.generations ?? 50}
                onChange={(e) => setSettings({ ...settings, generations: parseInt(e.target.value) || 10 })}
                className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
              />
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-center gap-2 text-xs text-gray-200 cursor-pointer">
              <input
                type="checkbox"
                checked={settings.pipelined ?? false}
                onChange={(e) => setSettings({ ...settings, pipelined: e.target.checked })}
                className="rounded bg-gray-900 border-gray-700 text-blue-600"
              />
              <span className="font-semibold">Enable Steady-State Pipelining Evaluation (II Model)</span>
            </label>
            <p className="text-[11px] text-gray-500 mt-1 pl-6">
              When enabled, throughput is estimated via steady-state initiation interval II = max(busy_time_r).
            </p>
          </div>
        </div>

        {/* Hard Constraints */}
        <div className="p-4 bg-gray-950 rounded border border-gray-800 space-y-4">
          <h4 className="text-sm font-semibold text-purple-400 border-b border-gray-800 pb-2">
            Hard Feasibility Constraints
          </h4>

          <div className="grid grid-cols-2 gap-3">
            {constraintFields.map(({ key, label }) => (
              <div key={key} className="space-y-1">
                <label className="text-xs text-gray-300 font-medium">{label}</label>
                <input
                  type="number"
                  placeholder="No limit"
                  value={constraints[key] ?? ''}
                  onChange={(e) =>
                    setConstraints({
                      ...constraints,
                      [key]: e.target.value ? parseFloat(e.target.value) : null,
                    })
                  }
                  className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-xs text-gray-200"
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
