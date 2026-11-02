import React from 'react'
import { ReactFlow, Background, Controls } from '@xyflow/react'
import type { Node, Edge, OnNodesChange, OnEdgesChange } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

interface GraphCanvasProps {
  nodes: Node[]
  edges: Edge[]
  onNodesChange: OnNodesChange<Node>
  onEdgesChange: OnEdgesChange<Edge>
  onNodeClick?: (_: any, node: Node) => void
  badge?: React.ReactNode
}

export const GraphCanvas: React.FC<GraphCanvasProps> = ({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  badge,
}) => (
  <div className="w-full h-full min-h-[500px] bg-gray-950 relative rounded-lg border border-gray-800 overflow-hidden">
    {badge && (
      <div className="absolute top-3 left-3 z-10 bg-gray-900/90 backdrop-blur px-3 py-1.5 rounded border border-gray-800 text-xs text-gray-400">
        {badge}
      </div>
    )}
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={onNodeClick}
      fitView
    >
      <Background color="#1e293b" gap={16} />
      <Controls className="bg-gray-900 border-gray-800 text-gray-300" />
    </ReactFlow>
  </div>
)
