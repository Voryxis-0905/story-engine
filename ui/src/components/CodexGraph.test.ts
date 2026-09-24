import { describe, expect, it } from 'vitest';
import { focusedRelationships } from './codexGraphModel';

const nodes = [
  { id: 'mara', label: 'Mara', type: 'character' },
  { id: 'tobin', label: 'Tobin', type: 'character' },
  { id: 'corvin', label: 'Corvin', type: 'character' },
  { id: 'quay', label: 'Low Quay', type: 'location' },
];
const edges = [
  { source: 'mara', target: 'tobin', label: 'protects' },
  { source: 'tobin', target: 'mara', label: 'trusts' },
  { source: 'corvin', target: 'mara', label: 'worries for' },
  { source: 'mara', target: 'quay', label: 'visits' },
  { source: 'mara', target: 'missing', label: 'knows' },
];

describe('focusedRelationships', () => {
  it('shows a stable one-person view without places or dangling edges', () => {
    const view = focusedRelationships(nodes, edges);
    expect(view.focus?.id).toBe('mara');
    expect(view.characters.map((node) => node.id)).toEqual(['mara', 'tobin', 'corvin']);
    expect(view.neighbors.map((node) => node.id)).toEqual(['corvin', 'tobin']);
    expect(view.relationships.map((edge) => [edge.other.id, edge.outgoing])).toEqual([
      ['tobin', true], ['tobin', false], ['corvin', false],
    ]);
  });

  it('changes focus without losing the direction of the relationship', () => {
    const view = focusedRelationships(nodes, edges, 'tobin');
    expect(view.focus?.id).toBe('tobin');
    expect(view.relationships.map((edge) => edge.outgoing)).toEqual([false, true]);
  });
});
