import React, { useEffect } from 'react'
import { useNodesState, useEdgesState, MarkerType } from '@xyflow/react'
import type { Node, Edge } from '@xyflow/react'
import { useAppStore } from '../../store'
import { getElkLayout } from '../../lib/elkLayout'
import { GraphCanvas } from './GraphCanvas'

export const ApplicationGraphView: React.FC = () => {
  const { currentProject, selectedTaskId, setSelectedTaskId } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])

  useEffect(() => {
    if (!currentProject) return

    const initialNodes: Node[] = currentProject.problem.nodes.map((node) => ({
      id: node.id,
      position: { x: 0, y: 0 },
      data: {
        label: (
          <div className="p-2 text-left">
            <div className="flex items-center justify-between">
              <span className="font-bold text-blue-400 text-sm">{node.id}</span>
              {node.fixed_resource_id && (
                <span className="text-[10px] bg-purple-900/60 text-purple-200 px-1 rounded border border-purple-700">
                  {node.fixed_resource_id}
                </span>
              )}
            </div>
            <div className="text-xs font-semibold text-gray-200 truncate mt-0.5">{node.name}</div>
            <div className="text-[10px] text-gray-400 mt-1 flex justify-between">
              <span>In/Out: {node.input_kb}/{node.output_kb} KB</span>
              <span>Mem: {node.memory_kb} KB</span>
            </div>
          </div>
        ),
      },
      style: {
        background: selectedTaskId === node.id ? '#1e293b' : '#0f172a',
        borderColor: selectedTaskId === node.id ? '#3b82f6' : '#334155',
        borderWidth: selectedTaskId === node.id ? 2 : 1,
        borderRadius: 8,
        width: 170,
        boxShadow: selectedTaskId === node.id ? '0 0 10px rgba(59, 130, 246, 0.4)' : undefined,
      },
    }))

    const initialEdges: Edge[] = currentProject.problem.edges.map((e, idx) => ({
      id: e.comm_id || `e_${e.from}_${e.to}_${idx}`,
      source: e.from,
      target: e.to,
      label: `${e.data_kb} KB`,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#64748b' },
      style: { stroke: '#64748b', strokeWidth: 1.5 },
      labelStyle: { fill: '#94a3b8', fontSize: 10, fontWeight: 500 },
      labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
    }))

    getElkLayout(initialNodes, initialEdges, 'RIGHT').then(({ nodes: layoutedNodes, edges: layoutedEdges }) => {
      setNodes(layoutedNodes)
      setEdges(layoutedEdges)
    })
  }, [currentProject, selectedTaskId])

  return (
    <GraphCanvas
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={(_, node) => setSelectedTaskId(node.id)}
      badge="Application Problem Graph (DAG) · Click task to inspect"
    />
  )
}
