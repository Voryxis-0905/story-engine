import { describe, expect, it, vi } from 'vitest';

import {
  FALLBACK_REGION_NAME, NODE_HIT_RADIUS, buildRegions, buildRouteModel, distanceBetween, findRegion,
  hasKnownTags, isHidden, layoutLabels, layoutRegionLabels, placeAtPoint, placeKind, placeLabel,
  placeStatus, regionAtPoint, regionContaining, regionNameOf, selectVisiblePlaces, visiblePlaces,
  type MapLocation,
} from './mapModel';

const place = (overrides: Partial<MapLocation> & { id: string }): MapLocation => ({
  name: overrides.id,
  x: 50,
  y: 50,
  is_unlocked: true,
  ...overrides,
});

describe('region resolution', () => {
  it('prefers the explicit zone field', () => {
    expect(regionNameOf(place({ id: 'a', name: 'Anything', zone: 'Kamakura North' }))).toBe('Kamakura North');
  });

  it('falls back to the "Zone - Place" convention when zone is missing', () => {
    expect(regionNameOf(place({ id: 'a', name: 'Minase Bookshop - Back Room' }))).toBe('Minase Bookshop');
    expect(regionNameOf(place({ id: 'a', name: 'Salt Court — Chart Room' }))).toBe('Salt Court');
  });

  it('derives a region from the name convention when zone is missing', () => {
    // Without a separator there is no convention to apply, so the whole name
    // becomes the region and the place keeps its own label.
    expect(regionNameOf(place({ id: 'a', name: 'Somewhere' }))).toBe('Somewhere');
    expect(placeLabel(place({ id: 'a', name: 'Somewhere' }), 'Somewhere')).toBe('Somewhere');
  });

  it('uses a neutral fallback when the name carries nothing at all', () => {
    expect(regionNameOf(place({ id: 'a', name: '   ' }))).toBe(FALLBACK_REGION_NAME);
    expect(regionNameOf(place({ id: 'a', name: '' }))).toBe(FALLBACK_REGION_NAME);
  });

  it('never invents an empty region name from a malformed separator', () => {
    // A leading separator has nothing usable before it, so the whole name is the
    // only honest label; the result must never be an empty string.
    expect(regionNameOf(place({ id: 'a', name: ' - Orphan' }))).toBe('- Orphan');
    expect(regionNameOf(place({ id: 'a', name: 'Orphan -' }))).toBe('Orphan -');
  });

  it('does not repeat the region name inside a place label', () => {
    expect(placeLabel(place({ id: 'a', name: 'Minase Bookshop - Back Room' }), 'Minase Bookshop')).toBe('Back Room');
    expect(placeLabel(place({ id: 'a', name: 'Yuigahama Beach', zone: 'Kamakura Seaside' }), 'Kamakura Seaside')).toBe('Yuigahama Beach');
  });
});

describe('buildRegions', () => {
  const kamakura = [
    place({ id: 'book_1', name: 'Minase Bookshop - Front Counter', x: 40, y: 68, tags: ['urban', 'shop'] }),
    place({ id: 'book_2', name: 'Minase Bookshop - Back Room', x: 34, y: 76, tags: ['urban'] }),
    place({ id: 'station', name: 'Kamakura Station - South Exit', x: 50, y: 64, tags: ['urban', 'road'] }),
    place({ id: 'shrine', name: 'Tsurugaoka Hachimangu Shrine', x: 33, y: 88, zone: 'Kamakura North', tags: ['temple'] }),
  ];

  it('groups by zone, then by the name convention', () => {
    const regions = buildRegions(kamakura);
    const names = regions.map((region) => region.name).sort();
    expect(names).toEqual(['Kamakura North', 'Kamakura Station', 'Minase Bookshop']);
    expect(findRegion(regions, 'region:minase bookshop')?.places).toHaveLength(2);
  });

  it('centres a region on the mean of its real places, not on a guessed anchor', () => {
    const region = regionContaining(buildRegions(kamakura), kamakura[0])!;
    // The two bookshop places sit at x 0.40 / 0.34 on the x axis. Camera y is
    // flipped for the canvas, so y 0.68 / 0.76 becomes 0.32 / 0.24.
    expect(region.center.x).toBeCloseTo((0.40 + 0.34) / 2, 5);
    expect(region.center.y).toBeCloseTo(((1 - 0.68) + (1 - 0.76)) / 2, 5);
  });

  it('keeps the region disc from collapsing to a point', () => {
    const regions = buildRegions([place({ id: 'solo', name: 'Solo', zone: 'Empty Reach', x: 50, y: 50 })]);
    expect(regions[0].radius).toBeGreaterThan(0.1);
  });

  it('flags the region holding the protagonist', () => {
    const regions = buildRegions(kamakura, 'book_1');
    expect(findRegion(regions, 'region:minase bookshop')?.hasCurrent).toBe(true);
    expect(regions[0].name).toBe('Minase Bookshop');
  });

  it('never counts, places or hints at a hidden location', () => {
    const withHidden = [
      ...kamakura,
      place({ id: 'secret', name: 'Unknown location', zone: 'Hidden Vault', discovery_status: 'creator_only', description: '', tags: [] }),
    ];
    const regions = buildRegions(withHidden);
    expect(regions.map((region) => region.name)).not.toContain('Hidden Vault');
    expect(visiblePlaces(withHidden).map((item) => item.id)).not.toContain('secret');
  });
});

describe('placeStatus', () => {
  it('separates locked from unreachable from undiscovered', () => {
    expect(placeStatus(place({ id: 'a', is_unlocked: false, is_reachable: true }), undefined)).toBe('locked');
    expect(placeStatus(place({ id: 'a', is_unlocked: false, is_reachable: false }), undefined)).toBe('unreachable');
    expect(placeStatus(place({ id: 'a', is_unlocked: true, is_reachable: false }), undefined)).toBe('unreachable');
    expect(placeStatus(place({ id: 'a', discovery_status: 'unknown' }), undefined)).toBe('undiscovered');
  });

  it('treats the scrubbed "Unknown location" name as undiscovered even without a status field', () => {
    expect(isHidden(place({ id: 'a', name: 'Unknown location' }))).toBe(true);
    expect(placeStatus(place({ id: 'a', name: 'Unknown location' }), undefined)).toBe('undiscovered');
  });

  it('reports the current place first, whatever else is true of it', () => {
    expect(placeStatus(place({ id: 'here', name: 'Here', is_unlocked: false }), 'here')).toBe('current');
  });
});

describe('buildRouteModel', () => {
  const world = [
    place({ id: 'a', name: 'Alpha', x: 10, y: 10 }),
    place({ id: 'b', name: 'Beta', x: 40, y: 40 }),
    place({ id: 'c', name: 'Gamma', x: 70, y: 70 }),
  ];

  it('draws only adjacent stops of an ordered route', () => {
    const model = buildRouteModel(['Alpha', 'Beta', 'Gamma'], world);
    expect(model.segments.map((segment) => `${segment.from.id}->${segment.to.id}`)).toEqual(['a->b', 'b->c']);
  });

  it('never draws a line between two non-adjacent route stops', () => {
    const model = buildRouteModel(['Alpha', 'Beta', 'Gamma'], world);
    const pairs = model.segments.map((segment) => [segment.from.id, segment.to.id].sort().join('-'));
    expect(pairs).not.toContain('a-c');
    expect(pairs).toEqual(['a-b', 'b-c']);
  });

  it('reports route stops that are not on this map instead of inventing a line across it', () => {
    const model = buildRouteModel(['Off Map Origin', 'Beta', 'Gamma'], world);
    expect(model.segments.map((segment) => `${segment.from.id}->${segment.to.id}`)).toEqual(['b->c']);
    expect(model.unsupported).toEqual(['Off Map Origin']);
  });

  it('is not drawable for a single-stop or empty route', () => {
    expect(buildRouteModel(['Alpha'], world).drawable).toBe(false);
    expect(buildRouteModel([], world).drawable).toBe(false);
    expect(buildRouteModel(undefined, world).drawable).toBe(false);
  });

  it('ignores a zero-length hop between a place and itself', () => {
    const model = buildRouteModel(['Alpha', 'Alpha', 'Beta'], world);
    expect(model.segments).toHaveLength(1);
    expect(model.segments[0].from.id).toBe('a');
  });
});

describe('selectVisiblePlaces', () => {
  const regions = buildRegions([
    place({ id: 'room_1', name: 'School - Room 101', zone: 'School', x: 20, y: 20, tags: ['interior'] }),
    place({ id: 'room_2', name: 'School - Room 102', zone: 'School', x: 22, y: 24, tags: ['interior'] }),
    place({ id: 'yard', name: 'School - Yard', zone: 'School', x: 26, y: 18, tags: ['outdoor'] }),
    place({ id: 'city', name: 'Downtown - Plaza', zone: 'Downtown', x: 80, y: 80, tags: ['urban'] }),
  ]);

  it('shows one representative per region in the overview, not every room', () => {
    const selection = selectVisiblePlaces(regions.flatMap((region) => region.places), regions, { zoom: 1 });
    expect(selection.local).toBe(false);
    const schoolNames = selection.places.filter((item) => regionNameOf(item) === 'School').map((item) => item.id);
    expect(schoolNames).toHaveLength(1);
  });

  it('always keeps the protagonist, even when another place represents its region', () => {
    const all = regions.flatMap((region) => region.places);
    const selection = selectVisiblePlaces(all, regions, { zoom: 1, currentRef: 'room_2' });
    const schoolNames = selection.places.filter((item) => regionNameOf(item) === 'School').map((item) => item.id);
    expect(schoolNames).toContain('room_2');
  });

  it('discloses every child place of the focused region at the local tier', () => {
    const all = regions.flatMap((region) => region.places);
    const school = buildRegions(all).find((region) => region.name === 'School')!;
    const selection = selectVisiblePlaces(all, regions,
      { zoom: 3, focusedRegionKey: school.key, currentRef: 'room_1' });
    expect(selection.local).toBe(true);
    const ids = selection.places.map((item) => item.id);
    expect(ids).toEqual(expect.arrayContaining(['room_1', 'room_2', 'yard']));
  });

  it('never lets a region become unopenable because its members were filtered out', () => {
    const selection = selectVisiblePlaces(regions.flatMap((region) => region.places), regions, { zoom: 1 });
    for (const region of regions) {
      expect(selection.places.some((item) => regionNameOf(item) === region.name)).toBe(true);
    }
  });

  it('pins a place on the previewed route so its highlight is visible', () => {
    const selection = selectVisiblePlaces(regions.flatMap((region) => region.places), regions,
      { zoom: 1, routeRefs: new Set(['yard']) });
    expect(selection.places.map((item) => item.id)).toContain('yard');
  });

  it('pins the live selection and the protagonist out of the overview too', () => {
    const bySelection = selectVisiblePlaces(regions.flatMap((region) => region.places), regions, { zoom: 1, selectedId: 'yard' });
    expect(bySelection.places.map((item) => item.id)).toContain('yard');
    const byCurrent = selectVisiblePlaces(regions.flatMap((region) => region.places), regions, { zoom: 1, currentRef: 'room_2' });
    expect(byCurrent.places.map((item) => item.id)).toContain('room_2');
  });
});

describe('layoutLabels', () => {
  const measure = (text: string) => text.length * 6.2;

  it('never overlaps two placed labels', () => {
    const entries = [
      place({ id: 'a', name: 'Alpha' }),
      place({ id: 'b', name: 'Bravo' }),
      place({ id: 'c', name: 'Charlie' }),
    ];
    const placements = layoutLabels(entries, [
      { id: 'a', x: 100, y: 100 }, { id: 'b', x: 104, y: 104 }, { id: 'c', x: 108, y: 108 },
    ], { size: 400, regionOf: () => null, force: () => false, measure });

    for (let i = 0; i < placements.length; i += 1) {
      for (let j = i + 1; j < placements.length; j += 1) {
        const a = placements[i].box;
        const b = placements[j].box;
        const overlaps = a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
        expect(overlaps).toBe(false);
      }
    }
  });

  it('always keeps a forced label, even when it must overlap to do so', () => {
    const entries = [place({ id: 'a', name: 'Alpha' }), place({ id: 'b', name: 'Bravo' })];
    const placements = layoutLabels(entries, [{ id: 'a', x: 100, y: 100 }, { id: 'b', x: 100, y: 100 }],
      { size: 400, regionOf: () => null, force: (location) => location.id === 'a', measure });
    expect(placements.map((item) => item.id)).toContain('a');
    expect(placements[0].id).toBe('a');
  });

  it('drops a label that would leave the canvas rather than clipping it', () => {
    const placements = layoutLabels([place({ id: 'a', name: 'Alpha' })], [{ id: 'a', x: 399, y: 399 }],
      { size: 100, regionOf: () => null, force: () => false, measure });
    expect(placements).toHaveLength(0);
  });

  it('flips a label to the left of its node near the right edge', () => {
    const placements = layoutLabels([place({ id: 'a', name: 'Alpha' })], [{ id: 'a', x: 470, y: 200 }],
      { size: 500, regionOf: () => null, force: () => false, measure });
    expect(placements[0].side).toBe('left');
  });
});

describe('layoutRegionLabels', () => {
  it('keeps region names apart', () => {
    const placements = layoutRegionLabels([
      { key: 'a', name: 'Drowned Roads', x: 100, y: 100, radius: 60, focus: false },
      { key: 'b', name: 'Lyr Harbor', x: 108, y: 104, radius: 60, focus: false },
    ], 400, (text) => text.length * 6.2);
    for (let i = 0; i < placements.length; i += 1) {
      for (let j = i + 1; j < placements.length; j += 1) {
        const a = placements[i].box;
        const b = placements[j].box;
        expect(a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top).toBe(false);
      }
    }
  });

  it('gives the focused region the first attempt at a position', () => {
    const placements = layoutRegionLabels([
      { key: 'a', name: 'Drowned Roads', x: 200, y: 200, radius: 60, focus: false },
      { key: 'b', name: 'Lyr Harbor', x: 200, y: 200, radius: 40, focus: true },
    ], 400, (text) => text.length * 6.2);
    expect(placements[0].key).toBe('b');
  });
});

describe('hit testing', () => {
  const project = (location: MapLocation) => ({ x: location.x, y: location.y });

  it('picks the closest place within the hit radius', () => {
    const places = [place({ id: 'a', x: 100, y: 100 }), place({ id: 'b', x: 110, y: 100 })];
    expect(placeAtPoint(places, { x: 108, y: 100 }, project)?.id).toBe('b');
    expect(placeAtPoint(places, { x: 100, y: 100 }, project)?.id).toBe('a');
  });

  it('returns nothing outside the hit radius', () => {
    expect(placeAtPoint([place({ id: 'a', x: 100, y: 100 })], { x: 100 + NODE_HIT_RADIUS + 1, y: 100 }, project)).toBeNull();
  });

  it('never hit-tests a hidden place', () => {
    const hidden = place({ id: 'h', name: 'Unknown location', x: 100, y: 100, discovery_status: 'unknown' });
    expect(placeAtPoint([hidden], { x: 100, y: 100 }, project)).toBeNull();
  });

  it('ignores a place that is projected outside the canvas', () => {
    // Regression from the real defect: at high zoom a cropped-out node sits
    // just outside the canvas, and because the map is cropped it can land
    // within the hit radius of a point near the canvas edge. Without the
    // bounds guard the click selects a place that is painted nowhere.
    const bounds = { width: 335, height: 335 };
    // 8px outside the left edge, i.e. closer to the edge point than the radius.
    const cropped = place({ id: 'cropped', x: -8, y: 100 });
    const pointer = { x: 4, y: 100 };

    // Precondition: distance-wise the cropped node is the nearer candidate, so
    // only the bounds check can reject it.
    expect(Math.hypot(-8 - pointer.x, 0)).toBeLessThan(NODE_HIT_RADIUS);

    // Without bounds the cropped node wins - this is the bug being guarded.
    expect(placeAtPoint([cropped], pointer, project)?.id).toBe('cropped');
    // With the canvas bounds it is rejected: not painted, not clickable.
    expect(placeAtPoint([cropped], pointer, project, NODE_HIT_RADIUS, bounds)).toBeNull();
  });

  it('still hits a painted place when a cropped one is nearer', () => {
    const bounds = { width: 335, height: 335 };
    const cropped = place({ id: 'cropped', x: -8, y: 100 });
    const painted = place({ id: 'painted', x: 10, y: 100 });
    // The cropped node is nearer to the pointer, but must not be selectable.
    expect(placeAtPoint([cropped, painted], { x: 4, y: 100 }, project, NODE_HIT_RADIUS, bounds)?.id).toBe('painted');
  });

  it('treats a node exactly on the canvas edge as visible', () => {
    const edge = place({ id: 'edge', x: 0, y: 100 });
    expect(placeAtPoint([edge], { x: 0, y: 100 }, project, NODE_HIT_RADIUS, { width: 335, height: 335 })?.id).toBe('edge');
  });

  it('hits a region disc, which is the click target for opening it', () => {
    const regions = buildRegions([place({ id: 'a', name: 'Zone A - One', zone: 'Zone A', x: 20, y: 20 })]);
    const hit = regionAtPoint(regions, { x: 100, y: 100 }, () => ({ x: 100, y: 100, radius: 60 }));
    expect(hit?.name).toBe('Zone A');
    expect(regionAtPoint(regions, { x: 400, y: 400 }, () => ({ x: 100, y: 100, radius: 60 }))).toBeNull();
  });
});

describe('place vocabulary', () => {
  it('reads a category out of the tags that already exist', () => {
    expect(placeKind({ tags: ['safe', 'urban', 'shop'] })).toBe('settlement');
    expect(placeKind({ tags: ['temple', 'landmark'] })).toBe('landmark');
    expect(placeKind({ tags: ['wilderness'] })).toBe('wild');
    expect(placeKind({ tags: ['indoor'] })).toBe('interior');
    expect(placeKind({ tags: ['road'] })).toBe('path');
  });

  it('prefers the terrain over a generic danger flag when a place carries both', () => {
    // A "dangerous harbor" is water; drawing it as a hazard triangle would
    // misdescribe the place, so the terrain tag outranks the danger tag.
    expect(placeKind({ tags: ['dangerous', 'harbor'] })).toBe('water');
    expect(placeKind({ tags: ['dangerous', 'wilderness'] })).toBe('wild');
    expect(placeKind({ tags: ['restricted', 'palace'] })).toBe('landmark');
    // With nothing but a danger flag, hazard is the honest answer.
    expect(placeKind({ tags: ['dangerous'] })).toBe('hazard');
  });

  it('falls back to a neutral category for an unknown genre', () => {
    expect(placeKind({ tags: ['qi_condensation', 'sect_hall'] })).toBe('interior');
    expect(placeKind({ tags: [] })).toBe('interior');
    expect(placeKind({})).toBe('interior');
    expect(hasKnownTags({ tags: ['qi_condensation'] })).toBe(false);
  });

  it('does not mistake a realm name for a terrain', () => {
    // "mountain" is a terrain; a fictional realm called "Mountain Sea Sect"
    // is tagged as its own thing and must land on the neutral fallback.
    expect(placeKind({ tags: ['mountain_sea_sect'] })).toBe('interior');
  });
});

describe('distanceBetween', () => {
  it('measures in normalised world units and flips y once', () => {
    expect(distanceBetween({ x: 0, y: 0 }, { x: 100, y: 0 })).toBeCloseTo(1, 5);
    expect(distanceBetween({ x: 0, y: 0 }, { x: 0, y: 100 })).toBeCloseTo(1, 5);
    expect(distanceBetween({ x: 50, y: 50 }, { x: 50, y: 50 })).toBe(0);
  });

  it('is what a caller can use to order regions by proximity', () => {
    const spy = vi.fn(distanceBetween);
    spy({ x: 10, y: 10 }, { x: 90, y: 90 });
    expect(spy).toHaveReturnedWith(expect.closeTo(Math.hypot(0.8, 0.8), 5));
  });
});
