import React from 'react'
import { useAppStore } from '../../store'
import { Play, Square, Save, CheckCircle2, AlertCircle } from 'lucide-react'

export const TopBar: React.FC = () => {
  const {
    projects,
    currentProjectId,
    selectProject,
    saveCurrentProject,
    isExploring,
    startDSE,
    cancelDSE,
    validation,
  } = useAppStore()

  return (
    <header className="h-14 bg-gray-950 border-b border-gray-800 px-4 flex items-center justify-between select-none">
      <div className="flex items-center gap-4">
        {/* Project Selector */}
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-400 font-medium">Project:</span>
          <select
            value={currentProjectId || ''}
            onChange={(e) => selectProject(e.target.value)}
            className="bg-gray-900 border border-gray-700 text-gray-200 rounded px-2.5 py-1 text-xs font-semibold focus:outline-none focus:border-blue-500"
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.id})
              </option>
            ))}
          </select>
        </div>

        {/* Validation Status Indicator */}
        {validation && (
          <div className="hidden sm:flex items-center gap-1.5 text-xs">
            {validation.is_valid ? (
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Valid DAG</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-red-400 font-medium" title={validation.errors.map(e => e.message).join('; ')}>
                <AlertCircle className="w-3.5 h-3.5" />
                <span>{validation.errors.length} Issues</span>
              </span>
            )}
          </div>
        )}
      </div>

      {/* Top Right Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={saveCurrentProject}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded transition"
        >
          <Save className="w-3.5 h-3.5" />
          <span>Save</span>
        </button>

        {isExploring ? (
          <button
            onClick={cancelDSE}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white font-bold text-xs rounded transition shadow animate-pulse"
          >
            <Square className="w-3.5 h-3.5 fill-current" />
            <span>Cancel Run</span>
          </button>
        ) : (
          <button
            onClick={startDSE}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded transition shadow-[0_0_12px_rgba(59,130,246,0.5)] cursor-pointer"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>Run DSE</span>
          </button>
        )}
      </div>
    </header>
  )
}
