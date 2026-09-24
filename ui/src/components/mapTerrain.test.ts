import { describe, expect, it } from 'vitest';
import { placeRelief, regionRelief, reliefLabel } from './mapTerrain';
import type { MapLocation } from './mapModel';

const place = (overrides: Partial<MapLocation> & { id: string }): MapLocation => ({
  name: overrides.id, x: 50, y: 50, is_unlocked: true, ...overrides,
});

describe('text-driven terrain hints', () => {
  it('keeps an unsupported height unknown instead of drawing a mountain', () => {
    expect(placeRelief(place({ id: 'hall', tags: ['palace', 'magical'] }))).toEqual({
      terrain: 'unknown', elevation: null, layer: 'unknown',
    });
    expect(reliefLabel(placeRelief(place({ id: 'hall' })))).toBeNull();
  });

  it('reads literal old-world tags without rewriting their data', () => {
    expect(placeRelief(place({ id: 'cave', tags: ['underground', 'water'] }))).toEqual({
      terrain: 'water', elevation: null, layer: 'underground',
    });
    expect(placeRelief(place({ id: 'ridge', tags: ['mountain'] })).elevation).toBe(2);
  });

  it('lets explicit metadata outrank tags but rejects malformed values', () => {
    expect(placeRelief(place({ id: 'cliff', terrain: 'coast', elevation: 1, layer: 'surface', tags: ['urban'] }))).toEqual({
      terrain: 'coast', elevation: 1, layer: 'surface',
    });
    expect(placeRelief(place({ id: 'bad', terrain: 'volcano', elevation: 99, layer: 'abyss' }))).toEqual({
      terrain: 'unknown', elevation: null, layer: 'unknown',
    });
    expect(placeRelief(place({ id: 'nave', terrain: 'unknown', elevation: null, layer: 'underground', tags: ['water', 'mountain'] }))).toEqual({
      terrain: 'unknown', elevation: null, layer: 'underground',
    });
  });

  it('uses a visible region majority, not its highest peak, as the background', () => {
    const region = { places: [
      place({ id: 'low-a', terrain: 'coast', elevation: 0 }),
      place({ id: 'low-b', terrain: 'coast', elevation: 0 }),
      place({ id: 'peak', terrain: 'mountain', elevation: 2 }),
    ] };
    expect(regionRelief(region)).toEqual({ terrain: 'coast', elevation: 0, layer: 'unknown' });
  });
});
