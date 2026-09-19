import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { PlayInspector } from './PlayInspector';

describe('PlayInspector inventory', () => {
  it('renders owned inventory instances instead of unlocked item cards', () => {
    const handleItemAction = vi.fn();
    render(<PlayInspector {...({
      playState: { unlocked_cards: [{ id: 'known_only', type: 'item', name: 'Known only' }] },
      activeDrawer: 'inventory', setActiveDrawer: vi.fn(), locations: [],
      affinityGraph: { nodes: [], edges: [] }, quests: [], journal: [],
      handleTravelTo: vi.fn(),
      handlePreviewTravel: vi.fn(), travelPreview: null, previewLoading: false,
      handleItemAction, handleContinueJourney: vi.fn(),
      protagonist: { inventory: [{
        instance_id: 'inv_blade', name: 'Moon Blade', category: 'weapon', quantity: 1,
        description: 'A cold silver blade.', attributes: { damage: 7 },
        abilities: [{ name: 'Moon Cut', effect: 'Cuts spectral bindings.' }],
        condition: 'worn', equipped: false, charges: null,
      }] },
    } as any)} />);

    expect(screen.getByText('Moon Blade')).toBeInTheDocument();
    expect(screen.getByText('damage:')).toBeInTheDocument();
    expect(screen.getByText('Moon Cut')).toBeInTheDocument();
    expect(screen.queryByText('Known only')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Equip' }));
    expect(handleItemAction).toHaveBeenCalledWith('Equip', expect.objectContaining({ instance_id: 'inv_blade' }));
  });
});
