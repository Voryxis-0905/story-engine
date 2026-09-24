import { useMemo, useState } from 'react';
import { Background, ReactFlow } from '@xyflow/react';
import type { Edge, Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { focusedRelationships, type AffinityEdge, type AffinityNode } from './codexGraphModel';

interface CodexGraphProps { nodes: AffinityNode[]; edges: AffinityEdge[] }

const MAX_VISIBLE_NEIGHBORS = 4;
const SATELLITES = [
  { x: 105, y: -14 }, { x: 254, y: 84 },
  { x: 105, y: 182 }, { x: -44, y: 84 },
];

export function CodexGraph({ nodes, edges }: CodexGraphProps) {
  const [requestedId, setRequestedId] = useState<string>();
  const [showAll, setShowAll] = useState(false);
  const { characters, focus, relationships, neighbors } = useMemo(
    () => focusedRelationships(nodes, edges, requestedId),
    [nodes, edges, requestedId],
  );
  const visibleNeighbors = neighbors.slice(0, MAX_VISIBLE_NEIGHBORS);
  const visibleIds = new Set(visibleNeighbors.map((node) => node.id));

  const flowNodes: Node[] = useMemo(() => {
    if (!focus) return [];
    return [focus, ...visibleNeighbors].map((node, index) => ({
      id: node.id,
      data: { label: node.label },
      position: index === 0 ? { x: 105, y: 84 } : SATELLITES[index - 1],
      style: {
        width: 132, minHeight: 42, borderRadius: 12,
        border: index === 0 ? '2px solid #6A6FD6' : '1px solid #D9D7EC',
        background: index === 0 ? '#EEEFFD' : '#FFFDFB', color: '#453D63',
        boxShadow: index === 0 ? '0 6px 20px rgba(106,111,214,.16)' : '0 2px 8px rgba(69,61,99,.08)',
        fontSize: 11, fontWeight: index === 0 ? 700 : 600,
        lineHeight: 1.3, textAlign: 'center',
      },
    }));
  }, [focus, visibleNeighbors]);

  const flowEdges: Edge[] = useMemo(() => {
    if (!focus) return [];
    // One quiet stroke per person. Direction and the full relation text live
    // in the readable list below, not on top of intersecting graph lines.
    return visibleNeighbors.map((node) => ({
      id: `${focus.id}:${node.id}`, source: focus.id, target: node.id,
      type: 'straight', style: { stroke: '#A8A9D6', strokeWidth: 1.6 },
    }));
  }, [focus, visibleNeighbors]);

  if (!focus) return <p className="p-5 text-center text-xs text-[var(--ink-soft)]">No character relationships discovered yet.</p>;
  const shown = showAll ? relationships : relationships.filter((edge) => visibleIds.has(edge.other.id));

  return <div className="space-y-3 p-3">
    <div className="flex items-center justify-between gap-2">
      <div>
        <h4 className="text-xs font-bold text-[var(--ink-main)]">Character relationships</h4>
        <p className="text-[10px] text-[var(--ink-muted)]">Choose a person to untangle their connections.</p>
      </div>
      <select aria-label="Focus character" value={focus.id}
        onChange={(event) => { setRequestedId(event.target.value); setShowAll(false); }}
        className="min-w-0 max-w-40 rounded-lg border border-[var(--line)] bg-[var(--bg-surface)] px-2 py-1.5 text-[11px] font-semibold text-[var(--ink-main)]">
        {characters.map((node) => <option key={node.id} value={node.id}>{node.label}</option>)}
      </select>
    </div>

    <div className="codex-relationship-graph h-56 overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--bg-subtle)]" aria-label={`Relationships around ${focus.label}`}>
      <ReactFlow key={focus.id} nodes={flowNodes} edges={flowEdges} fitView fitViewOptions={{ padding: .18 }}
        nodesDraggable={false} nodesConnectable={false} panOnDrag={false}
        zoomOnScroll={false} zoomOnPinch={false} zoomOnDoubleClick={false}
        onNodeClick={(_, node) => { setRequestedId(node.id); setShowAll(false); }}>
        <Background color="#D8D6EA" gap={24} size={1} />
      </ReactFlow>
    </div>

    {neighbors.length > MAX_VISIBLE_NEIGHBORS && <p className="text-[10px] text-[var(--ink-muted)]">
      Showing {MAX_VISIBLE_NEIGHBORS} of {neighbors.length} connected people in the diagram. Expand the list for everyone.
    </p>}
    {relationships.length ? <div className="space-y-1.5">
      {shown.map((edge, index) => <div key={`${edge.source}:${edge.target}:${index}`} className="rounded-lg border border-[var(--line)] bg-[var(--bg-surface)] p-2 text-[11px]">
        <div className="font-bold text-[var(--ink-main)]">{edge.outgoing ? `${focus.label} → ${edge.other.label}` : `${edge.other.label} → ${focus.label}`}</div>
        <p className="mt-0.5 leading-relaxed text-[var(--ink-soft)]">{edge.label}</p>
      </div>)}
      {neighbors.length > MAX_VISIBLE_NEIGHBORS && <button type="button" onClick={() => setShowAll((value) => !value)} className="w-full rounded-lg border border-[var(--line)] px-2 py-1.5 text-[11px] font-bold text-[var(--periwinkle-dark)] hover:bg-[var(--bg-subtle)]">
        {showAll ? 'Show fewer connections' : `Show all ${relationships.length} relationships`}
      </button>}
    </div> : <p className="text-xs text-[var(--ink-soft)]">No known relationships for this character yet.</p>}
  </div>;
}
