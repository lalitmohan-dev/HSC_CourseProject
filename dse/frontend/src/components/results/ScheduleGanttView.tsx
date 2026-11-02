import React from 'react'
import { useAppStore } from '../../store'
import type { ScheduledObject } from '../../types'

export const ScheduleGanttView: React.FC = () => {
  const { currentProject, selectedDesign } = useAppStore()
  const schedule = selectedDesign?.evaluation?.schedule

  if (!schedule || schedule.objects.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center p-8 bg-gray-900 border border-gray-800 rounded-lg text-gray-500">
        No schedule available. Run DSE or select an evaluated design.
      </div>
    )
  }

  const maxTime = Math.max(schedule.latency, 1)
  const criticalPathSet = new Set(schedule.critical_path)

  // Group objects by resource
  const resourceLanes: string[] = []
  currentProject?.architecture.resources.forEach((r) => {
    if (selectedDesign.allocated_resources.includes(r.id)) {
      resourceLanes.push(r.id)
    }
  })

  // Also include any resources that have scheduled objects
  schedule.objects.forEach((o) => {
    if (o.resource_id && o.resource_id !== 'local' && !resourceLanes.includes(o.resource_id)) {
      resourceLanes.push(o.resource_id)
    }
  })

  const objectsByResource: Record<string, ScheduledObject[]> = {}
  resourceLanes.forEach((r) => {
    objectsByResource[r] = schedule.objects.filter((o) => o.resource_id === r)
  })

  const localEvents = schedule.objects.filter((o) => o.duration === 0)

  return (
    <div className="w-full h-full p-4 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-100 flex items-center gap-2">
            <span>Resource Schedule (Gantt) · Latency:</span>
            <span className="font-mono text-blue-400 font-bold">
              {schedule.latency} {currentProject?.meta.time_unit || 'ms'}
            </span>
          </h3>
          <p className="text-xs text-gray-400">
            Gold border marks objects on the Critical Path. Amber blocks are bus transfers; Blue/Purple are compute tasks.
          </p>
        </div>
      </div>

      {/* Time axis header */}
      <div className="flex items-center mb-2 pl-36 pr-4">
        <div className="w-full flex justify-between text-[11px] font-mono text-gray-400 border-b border-gray-800 pb-1">
          <span>0</span>
          <span>{(maxTime * 0.25).toFixed(1)}</span>
          <span>{(maxTime * 0.5).toFixed(1)}</span>
          <span>{(maxTime * 0.75).toFixed(1)}</span>
          <span>{maxTime.toFixed(1)} {currentProject?.meta.time_unit || 'ms'}</span>
        </div>
      </div>

      {/* Resource Lanes */}
      <div className="space-y-3 flex-1 min-h-[300px]">
        {resourceLanes.map((resId) => {
          const objs = objectsByResource[resId] || []
          const resObj = currentProject?.architecture.resources.find((r) => r.id === resId)
          const isBus = resObj?.kind === 'bus'

          return (
            <div key={resId} className="flex items-center group">
              {/* Lane Label */}
              <div className="w-36 pr-3 flex flex-col justify-center text-right shrink-0">
                <span className="font-semibold text-xs text-gray-200">{resId}</span>
                <span className="text-[10px] text-gray-500">{resObj?.kind || 'resource'}</span>
              </div>

              {/* Lane Timeline Bar */}
              <div className="flex-1 h-9 bg-gray-950/80 rounded border border-gray-800/80 relative overflow-hidden">
                {objs.map((o) => {
                  const leftPct = (o.start_time / maxTime) * 100
                  const widthPct = Math.max((o.duration / maxTime) * 100, 1.5)
                  const isCrit = criticalPathSet.has(o.id)

                  let blockBg = isBus ? 'bg-amber-600/80' : 'bg-blue-600/80'
                  let borderStyle = isCrit ? 'border-2 border-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)]' : 'border border-white/20'

                  return (
                    <div
                      key={o.id}
                      style={{
                        left: `${leftPct}%`,
                        width: `${widthPct}%`,
                      }}
                      className={`absolute top-1 bottom-1 rounded px-1.5 flex items-center justify-between text-[11px] font-medium text-white transition-all cursor-pointer ${blockBg} ${borderStyle}`}
                      title={`${o.name} (${o.id})\nStart: ${o.start_time}\nDuration: ${o.duration}\nFinish: ${o.finish_time}`}
                    >
                      <span className="truncate">{o.id}</span>
                      <span className="text-[9px] opacity-80 shrink-0 font-mono hidden sm:inline ml-1">
                        {o.duration}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Local zero-duration events indicator */}
        {localEvents.length > 0 && (
          <div className="pt-2 border-t border-gray-800/80 flex items-center text-xs text-gray-400 gap-2">
            <span className="font-semibold text-emerald-400">Local Transfers (0 ms):</span>
            <span className="text-gray-300">
              {localEvents.map((e) => `${e.id} at t=${e.start_time}`).join(', ')}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
