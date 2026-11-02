import ELK from 'elkjs/lib/elk.bundled.js'
import type { Edge, Node } from '@xyflow/react'

const elk = new ELK()

export async function getElkLayout(
  nodes: Node[],
  edges: Edge[],
  direction: 'RIGHT' | 'DOWN' = 'RIGHT'
): Promise<{ nodes: Node[]; edges: Edge[] }> {
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': direction,
      'elk.spacing.nodeNode': '60',
      'elk.layered.spacing.nodeNodeBetweenLayers': '80',
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: node.width || 180,
      height: node.height || 70,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  }

  try {
    const layoutedGraph = await elk.layout(graph)
    const layoutedNodes = nodes.map((node) => {
      const elkNode = layoutedGraph.children?.find((c) => c.id === node.id)
      return {
        ...node,
        position: {
          x: elkNode?.x ?? node.position.x,
          y: elkNode?.y ?? node.position.y,
        },
      }
    })
    return { nodes: layoutedNodes, edges }
  } catch (err) {
    console.warn('ELK layout failed, using default positions:', err)
    return { nodes, edges }
  }
}
