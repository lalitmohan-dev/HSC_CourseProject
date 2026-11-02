import React from 'react'
import { useAppStore } from '../../store'
import type { ViewType } from '../../store'
import {
  LayoutDashboard,
  Network,
  Cpu,
  Layers,
  Sliders,
  BarChart2,
  Calendar,
  AlertTriangle,
  GitCompare,
} from 'lucide-react'

interface NavItem {
  id: ViewType
  label: string
  icon: React.ComponentType<{ className?: string }>
}

const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'application', label: 'Application Model', icon: Network },
  { id: 'architecture', label: 'Architecture / Platform', icon: Cpu },
  { id: 'mapping', label: 'Mapping & Binding', icon: Layers },
  { id: 'constraints', label: 'Constraints & Search', icon: Sliders },
  { id: 'results', label: 'Pareto & Results', icon: BarChart2 },
  { id: 'schedule', label: 'Schedule (Gantt)', icon: Calendar },
  { id: 'bottlenecks', label: 'Bottlenecks', icon: AlertTriangle },
  { id: 'compare', label: 'Compare Designs', icon: GitCompare },
]

export const Sidebar: React.FC = () => {
  const { activeView, setActiveView } = useAppStore()

  return (
    <aside className="w-56 bg-gray-950 border-r border-gray-800 flex flex-col justify-between p-3 select-none">
      <div className="space-y-4">
        <div className="px-3 py-2">
          <div className="font-extrabold text-blue-400 tracking-wider text-sm flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded bg-blue-500 inline-block shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span>
            <span>DSE FRAMEWORK</span>
          </div>
          <div className="text-[10px] text-gray-500 tracking-tight mt-0.5">HW/SW Co-Design v2.0</div>
        </div>

        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = activeView === item.id
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-xs font-medium transition ${
                  isActive
                    ? 'bg-blue-600 text-white shadow'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-900'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.label}</span>
              </button>
            )
          })}
        </nav>
      </div>

      <div className="px-3 py-2 border-t border-gray-900 text-[10px] text-gray-600">
        System-Level Synthesis Engine
      </div>
    </aside>
  )
}
