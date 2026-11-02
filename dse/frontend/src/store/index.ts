import { create } from 'zustand'
import type {
  BottleneckReport,
  CandidateDesign,
  ProjectIR,
  ProjectMetadata,
  RunSummary,
  ValidationResult,
} from '../types'
import * as api from '../api/client'

export type ViewType =
  | 'dashboard'
  | 'application'
  | 'architecture'
  | 'mapping'
  | 'constraints'
  | 'results'
  | 'schedule'
  | 'bottlenecks'
  | 'compare'

interface AppState {
  projects: ProjectMetadata[]
  currentProjectId: string | null
  currentProject: ProjectIR | null
  activeView: ViewType
  selectedTaskId: string | null
  selectedResourceId: string | null

  // Exploration state
  activeRunId: string | null
  isExploring: boolean
  runSummary: RunSummary | null
  selectedDesignId: string | null
  selectedDesign: CandidateDesign | null
  allDesigns: CandidateDesign[]
  bottleneckReport: BottleneckReport | null
  explorationLogs: Array<{ timestamp: string; level: string; message: string }>
  progress: { evaluated: number; total: number; elapsed_seconds: number } | null
  validation: ValidationResult | null

  // Actions
  loadProjects: () => Promise<void>
  selectProject: (id: string) => Promise<void>
  saveCurrentProject: () => Promise<void>
  updateCurrentProject: (updated: ProjectIR) => void
  validateCurrentProject: () => Promise<void>
  setActiveView: (view: ViewType) => void
  setSelectedTaskId: (id: string | null) => void
  setSelectedResourceId: (id: string | null) => void
  setSelectedDesignId: (id: string | null) => Promise<void>

  startDSE: () => Promise<void>
  cancelDSE: () => Promise<void>
  addLog: (log: { timestamp: string; level: string; message: string }) => void
  setProgress: (prog: { evaluated: number; total: number; elapsed_seconds: number } | null) => void
  setRunSummary: (summary: RunSummary | null) => void
}

export const useAppStore = create<AppState>((set, get) => ({
  projects: [],
  currentProjectId: null,
  currentProject: null,
  activeView: 'dashboard',
  selectedTaskId: null,
  selectedResourceId: null,

  activeRunId: null,
  isExploring: false,
  runSummary: null,
  selectedDesignId: null,
  selectedDesign: null,
  allDesigns: [],
  bottleneckReport: null,
  explorationLogs: [],
  progress: null,
  validation: null,

  loadProjects: async () => {
    try {
      const list = await api.fetchProjects()
      set({ projects: list })
      if (list.length > 0 && !get().currentProjectId) {
        await get().selectProject(list[0].id || 'golden-slide')
      }
    } catch (err) {
      console.error('Failed to load projects:', err)
    }
  },

  selectProject: async (id: string) => {
    try {
      const proj = await api.fetchProject(id)
      set({
        currentProjectId: id,
        currentProject: proj,
        selectedTaskId: proj.problem.nodes[0]?.id ?? null,
        selectedResourceId: proj.architecture.resources[0]?.id ?? null,
      })
      await get().validateCurrentProject()
    } catch (err) {
      console.error('Failed to select project:', err)
    }
  },

  saveCurrentProject: async () => {
    const { currentProjectId, currentProject } = get()
    if (!currentProjectId || !currentProject) return
    try {
      const saved = await api.saveProject(currentProjectId, currentProject)
      set({ currentProject: saved })
      await get().validateCurrentProject()
    } catch (err) {
      console.error('Failed to save project:', err)
    }
  },

  updateCurrentProject: (updated: ProjectIR) => {
    set({ currentProject: updated })
  },

  validateCurrentProject: async () => {
    const { currentProjectId } = get()
    if (!currentProjectId) return
    try {
      const val = await api.validateProject(currentProjectId)
      set({ validation: val })
    } catch (err) {
      console.error('Failed to validate project:', err)
    }
  },

  setActiveView: (view: ViewType) => set({ activeView: view }),
  setSelectedTaskId: (id: string | null) => set({ selectedTaskId: id }),
  setSelectedResourceId: (id: string | null) => set({ selectedResourceId: id }),

  setSelectedDesignId: async (id: string | null) => {
    set({ selectedDesignId: id })
    const { allDesigns, activeRunId } = get()
    const found = allDesigns.find((d) => d.id === id) || null
    set({ selectedDesign: found })

    if (activeRunId && id) {
      try {
        const bn = await api.fetchBottlenecks(activeRunId, id)
        set({ bottleneckReport: bn })
      } catch (err) {
        console.error('Failed to fetch bottlenecks:', err)
      }
    }
  },

  startDSE: async () => {
    const { currentProjectId } = get()
    if (!currentProjectId) return

    set({ isExploring: true, explorationLogs: [], progress: null })
    try {
      const { run_id } = await api.startExploration(currentProjectId)
      set({ activeRunId: run_id })

      // Open SSE EventSource stream
      const eventSource = new EventSource(`/api/runs/${run_id}/events`)

      eventSource.addEventListener('log', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          get().addLog(data)
        } catch {}
      })

      eventSource.addEventListener('progress', (event: any) => {
        try {
          const data = JSON.parse(event.data)
          get().setProgress(data)
        } catch {}
      })

      eventSource.addEventListener('done', async () => {
        eventSource.close()
        set({ isExploring: false })
        const summary = await api.fetchRunSummary(run_id)
        const designsData = await api.fetchRunDesigns(run_id)
        set({
          runSummary: summary,
          allDesigns: designsData.items,
          selectedDesign: summary.recommended_design || designsData.items[0] || null,
          selectedDesignId: summary.recommended_design?.id || designsData.items[0]?.id || null,
        })
        if (summary.recommended_design?.id) {
          await get().setSelectedDesignId(summary.recommended_design.id)
        }
      })

      eventSource.addEventListener('error', () => {
        eventSource.close()
        set({ isExploring: false })
      })
    } catch (err) {
      set({ isExploring: false })
      console.error('Failed to start DSE:', err)
    }
  },

  cancelDSE: async () => {
    const { activeRunId } = get()
    if (!activeRunId) return
    await api.cancelExploration(activeRunId)
    set({ isExploring: false })
  },

  addLog: (log) => set((s) => ({ explorationLogs: [...s.explorationLogs, log] })),
  setProgress: (prog) => set({ progress: prog }),
  setRunSummary: (summary) => set({ runSummary: summary }),
}))
