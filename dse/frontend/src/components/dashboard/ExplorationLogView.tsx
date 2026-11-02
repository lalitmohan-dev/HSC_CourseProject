import React, { useEffect, useRef } from 'react'
import { useAppStore } from '../../store'

export const ExplorationLogView: React.FC = () => {
  const { explorationLogs, progress, isExploring } = useAppStore()
  const logEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [explorationLogs])

  return (
    <div className="w-full h-full flex flex-col bg-gray-950 rounded-lg border border-gray-800 p-3 font-mono text-xs">
      <div className="flex items-center justify-between pb-2 border-b border-gray-800">
        <span className="text-gray-400 font-sans font-semibold text-xs flex items-center gap-2">
          <span>Exploration Run Log</span>
          {isExploring && (
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
          )}
        </span>
        {progress && (
          <span className="text-[11px] text-gray-400">
            {progress.evaluated} / {progress.total} evaluated ({progress.elapsed_seconds}s)
          </span>
        )}
      </div>

      {/* Progress Bar */}
      {isExploring && progress && progress.total > 0 && (
        <div className="w-full h-1.5 bg-gray-900 rounded overflow-hidden my-2">
          <div
            className="h-full bg-blue-500 transition-all duration-200"
            style={{ width: `${Math.min(100, (progress.evaluated / progress.total) * 100)}%` }}
          ></div>
        </div>
      )}

      {/* Log Output Area */}
      <div className="flex-1 overflow-y-auto space-y-1.5 pt-2 text-[11px]">
        {explorationLogs.length === 0 ? (
          <div className="text-gray-600 italic">Logs will appear when an exploration run is started...</div>
        ) : (
          explorationLogs.map((log, idx) => {
            let color = 'text-gray-300'
            if (log.level === 'warning') color = 'text-amber-400'
            if (log.level === 'error') color = 'text-red-400'

            const timeStr = log.timestamp ? log.timestamp.split('T')[1]?.slice(0, 8) : ''

            return (
              <div key={idx} className="flex items-start gap-2">
                <span className="text-gray-600 select-none shrink-0">{timeStr}</span>
                <span className="uppercase text-[9px] font-bold px-1 rounded bg-gray-900 text-gray-400 shrink-0">
                  {log.level}
                </span>
                <span className={color}>{log.message}</span>
              </div>
            )
          })
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
