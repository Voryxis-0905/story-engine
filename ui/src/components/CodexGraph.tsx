import { useMemo } from 'react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import type { Node, Edge } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface AffinityNode {
  id: string;
  label: string;
  type: string;
}

interface AffinityEdge {
  source: string;
  target: string;
  label: string;
}

interface CodexGraphProps {
  nodes: AffinityNode[];
  edges: AffinityEdge[];
}

const nodeColors: Record<string, string> = {
  character: '#6366f1',
  location: '#22d3ee',
  faction: '#f472b6',
  item: '#fbbf24',
  default: '#6b7280',
};

export function CodexGraph({ nodes, edges }: CodexGraphProps) {
  const flowNodes: Node[] = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        data: { label: n.label },
        position: { x: Math.random() * 400, y: Math.random() * 400 },
        style: {
          background: nodeColors[n.type] || nodeColors.default,
          color: '#fff',
          borderRadius: '8px',
          padding: '8px 16px',
          fontWeight: 600,
        },
      })),
    [nodes]
  );

  const flowEdges: Edge[] = useMemo(
    () =>
      edges.map((e) => ({
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        label: e.label,
        style: { stroke: '#4b5563' },
        labelStyle: { fill: '#9ca3af', fontSize: 10 },
      })),
    [edges]
  );

  return (
    <div className="codex-graph" style={{ width: '100%', height: '500px' }}>
      <ReactFlow nodes={flowNodes} edges={flowEdges} fitView>
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}