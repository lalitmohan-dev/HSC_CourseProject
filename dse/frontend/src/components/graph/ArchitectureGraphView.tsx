import React, { useEffect } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useAppStore } from '../../store'
import { getElkLayout } from '../../lib/elkLayout'

export const ArchitectureGraphView: React.FC = () => {
  const { currentProject, selectedResourceId, setSelectedResourceId } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!currentProject) return

    const initialNodes: Node[] = currentProject.architecture.resources.map((res) => {
      const isBus = res.kind === 'bus'
      const isProcessor = res.kind === 'processor'
      const isSelected = selectedResourceId === res.id

      let bg = '#0f172a'
      let border = '#334155'
      let badgeBg = 'bg-blue-900/60 text-blue-200 border-blue-700'

      if (isBus) {
        border = isSelected ? '#f59e0b' : '#b45309'
        badgeBg = 'bg-amber-900/60 text-amber-200 border-amber-700'
      } else if (isProcessor) {
        border = isSelected ? '#3b82f6' : '#1d4ed8'
        badgeBg = 'bg-blue-900/60 text-blue-200 border-blue-700'
      } else {
        border = isSelected ? '#a855f7' : '#7e22ce'
        badgeBg = 'bg-purple-900/60 text-purple-200 border-purple-700'
      }

      return {
        id: res.id,
        position: { x: 0, y: 0 },
        data: {
          label: (
            <div className="p-2 text-left">
              <div className="flex items-center justify-between">
                <span className="font-bold text-gray-100 text-sm">{res.id}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded border ${badgeBg}`}>
                  {res.kind}
                </span>
              </div>
              <div className="text-xs text-gray-300 font-medium truncate mt-0.5">{res.name}</div>
              <div className="text-[10px] text-gray-400 mt-1 flex justify-between">
                <span>Cost: {res.allocation_cost ?? 0}</span>
                {isBus ? (
                  <span>BW: {res.bandwidth_mb_per_s ?? '∞'} MB/s</span>
                ) : (
                  <span>Parallel: {res.max_parallel ?? 1}</span>
                )}
              </div>
            </div>
          ),
        },
        style: {
          background: isSelected ? '#1e293b' : bg,
          borderColor: border,
          borderWidth: isSelected ? 2 : 1,
          borderRadius: 8,
          width: 180,
          boxShadow: isSelected ? `0 0 10px ${border}88` : undefined,
        },
      }
    })

    const initialEdges: Edge[] = []
    currentProject.architecture.resources.forEach((res) => {
      if (res.kind === 'bus' && res.connects) {
        res.connects.forEach((endpoint) => {
          initialEdges.push({
            id: `edge_${res.id}_${endpoint}`,
            source: res.id,
            target: endpoint,
            style: { stroke: '#b45309', strokeWidth: 2, strokeDasharray: '4 4' },
          })
        })
      }
    })

    getElkLayout(initialNodes, initialEdges, 'DOWN').then(({ nodes: layoutedNodes, edges: layoutedEdges }) => {
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    })
  }, [currentProject, selectedResourceId])

  return (
    <div className="w-full h-full min-h-[500px] bg-gray-950 relative rounded-lg border border-gray-800 overflow-hidden">
      <div className="absolute top-3 left-3 z-10 bg-gray-900/90 backdrop-blur px-3 py-1.5 rounded border border-gray-800 text-xs text-gray-400">
        Architecture Graph · Processors (Blue), Accelerators (Purple), Buses (Amber)
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={(_, node) => setSelectedResourceId(node.id)}
        fitView
      >
        <Background color="#1e293b" gap={16} />
        <Controls className="bg-gray-900 border-gray-800 text-gray-300" />
      </ReactFlow>
    </div>
  )
}
