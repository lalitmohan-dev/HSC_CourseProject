import React, { useEffect } from 'react'
import { useNodesState, useEdgesState, MarkerType } from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import { useAppStore } from '../../store'
import { getElkLayout } from '../../lib/elkLayout'
import { GraphCanvas } from './GraphCanvas'

const RESOURCE_PALETTE = ['#3b82f6', '#a855f7', '#10b981', '#f59e0b', '#ec4899', '#06b6d4']

export const MappingGraphView: React.FC = () => {
  const { currentProject, selectedDesign } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!currentProject) return

    const bindings = selectedDesign?.bindings || {}
    const resourceList = currentProject.architecture.resources.map((r) => r.id)
    const colorMap: Record<string, string> = {}
    resourceList.forEach((rid, idx) => {
      colorMap[rid] = RESOURCE_PALETTE[idx % RESOURCE_PALETTE.length]
    })

    const initialNodes: Node[] = currentProject.problem.nodes.map((node) => {
      const boundRes = bindings[node.id] || 'Unbound'
      const resColor = colorMap[boundRes] || '#64748b'

      return {
        id: node.id,
        position: { x: 0, y: 0 },
        data: {
          label: (
            <div className="p-2 text-left">
              <div className="flex items-center justify-between">
                <span className="font-bold text-gray-100 text-sm">{node.id}</span>
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded font-semibold text-white"
                  style={{ backgroundColor: resColor }}
                >
                  {boundRes}
                </span>
              </div>
              <div className="text-xs text-gray-300 font-medium truncate mt-0.5">{node.name}</div>
            </div>
          ),
        },
        style: {
          background: '#0f172a',
          borderColor: resColor,
          borderWidth: 2,
          borderRadius: 8,
          width: 170,
        },
      }
    })

    const initialEdges: Edge[] = currentProject.problem.edges.map((e, idx) => {
      const srcRes = bindings[e.from]
      const dstRes = bindings[e.to]
      const isLocal = srcRes && dstRes && srcRes === dstRes

      return {
        id: e.comm_id || `e_${e.from}_${e.to}_${idx}`,
        source: e.from,
        target: e.to,
        label: isLocal ? 'Local (0 ms)' : `${e.data_kb} KB (Bus)`,
        markerEnd: { type: MarkerType.ArrowClosed, color: isLocal ? '#10b981' : '#f59e0b' },
        style: {
          stroke: isLocal ? '#10b981' : '#f59e0b',
          strokeWidth: 2,
          strokeDasharray: isLocal ? '2 2' : undefined,
        },
        labelStyle: { fill: isLocal ? '#10b981' : '#f59e0b', fontSize: 10, fontWeight: 500 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
      }
    })

    getElkLayout(initialNodes, initialEdges, 'RIGHT').then(({ nodes: layoutedNodes, edges: layoutedEdges }) => {
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    })
  }, [currentProject, selectedDesign])

  return (
    <GraphCanvas
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      badge={
        <div className="flex items-center gap-3">
          <span>Mapping View · Active Design: <strong className="text-white">{selectedDesign?.id || 'None Selected'}</strong></span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span> Local Comm (0 ms)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span> Bus Route
          </span>
        </div>
      }
    />
  )
}
