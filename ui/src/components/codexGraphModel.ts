export interface AffinityNode { id: string; label: string; type: string }
export interface AffinityEdge { source: string; target: string; label: string }

/** One person's known relationships, independent of input order or render timing. */
export function focusedRelationships(nodes: AffinityNode[], edges: AffinityEdge[], requestedId?: string) {
  const characters = nodes.filter((node) => node.type === 'character');
  const byId = new Map(characters.map((node) => [node.id, node]));
  const focus = byId.get(requestedId || '') || characters[0] || null;
  if (!focus) return { characters, focus: null, relationships: [], neighbors: [] };
  const relationships = edges
    .filter((edge) => edge.source !== edge.target
      && byId.has(edge.source) && byId.has(edge.target)
      && (edge.source === focus.id || edge.target === focus.id))
    .map((edge) => ({
      ...edge,
      other: byId.get(edge.source === focus.id ? edge.target : edge.source)!,
      outgoing: edge.source === focus.id,
    }));
  const neighbors = [...new Map(relationships.map((edge) => [edge.other.id, edge.other])).values()]
    .sort((a, b) => a.label.localeCompare(b.label));
  return { characters, focus, relationships, neighbors };
}
