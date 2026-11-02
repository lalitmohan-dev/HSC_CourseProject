import { useEffect } from 'react'
import { useAppStore } from './store'
import { Sidebar } from './components/shell/Sidebar'
import { TopBar } from './components/shell/TopBar'
import { DashboardView } from './components/dashboard/DashboardView'
import { ApplicationGraphView } from './components/graph/ApplicationGraphView'
import { ArchitectureGraphView } from './components/graph/ArchitectureGraphView'
import { MappingGraphView } from './components/graph/MappingGraphView'
import { ConstraintsSettingsView } from './components/forms/ConstraintsSettingsView'
import { ParetoChartView } from './components/results/ParetoChartView'
import { ScheduleGanttView } from './components/results/ScheduleGanttView'
import { BottleneckAnalysisView } from './components/results/BottleneckAnalysisView'
import { DesignsTableView } from './components/results/DesignsTableView'
import { CompareDesignsView } from './components/compare/CompareDesignsView'

export function App() {
  const { activeView, loadProjects } = useAppStore()

  useEffect(() => {
    loadProjects()
  }, [])

  return (
    <div className="flex h-screen w-screen bg-gray-950 text-gray-100 overflow-hidden font-sans">
      <Sidebar />
      <div className="flex flex-col flex-1 h-full min-w-0">
        <TopBar />
        <main className="flex-1 p-4 overflow-auto min-h-0 bg-gray-950/50">
          {activeView === 'dashboard' && <DashboardView />}
          {activeView === 'application' && <ApplicationGraphView />}
          {activeView === 'architecture' && <ArchitectureGraphView />}
          {activeView === 'mapping' && <MappingGraphView />}
          {activeView === 'constraints' && <ConstraintsSettingsView />}
          {activeView === 'results' && (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 h-full">
              <ParetoChartView />
              <DesignsTableView />
            </div>
          )}
          {activeView === 'schedule' && <ScheduleGanttView />}
          {activeView === 'bottlenecks' && <BottleneckAnalysisView />}
          {activeView === 'compare' && <CompareDesignsView />}
        </main>
      </div>
    </div>
  )
}

export default App
