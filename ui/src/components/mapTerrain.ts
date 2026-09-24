/** Factual relief hints, never a synthetic heightmap or a movement rule. */
import type { AtlasRegion, MapLocation } from './mapModel';

export type Terrain = 'unknown' | 'coast' | 'water' | 'plain' | 'forest' | 'desert' | 'mountain' | 'wetland' | 'urban';
export type Layer = 'unknown' | 'surface' | 'underground' | 'sky';
export interface Relief { terrain: Terrain; elevation: number | null; layer: Layer }

const TERRAINS: Terrain[] = ['unknown', 'coast', 'water', 'plain', 'forest', 'desert', 'mountain', 'wetland', 'urban'];
const LAYERS: Layer[] = ['unknown', 'surface', 'underground', 'sky'];

/** Existing worlds have tags but no relief fields. Infer only literal cues. */
export function placeRelief(place: Pick<MapLocation, 'terrain' | 'elevation' | 'layer' | 'tags'>): Relief {
  const tags = new Set((place.tags || []).map((tag) => String(tag).toLowerCase().trim()));
  const explicitTerrain = TERRAINS.includes(place.terrain as Terrain) ? place.terrain as Terrain : 'unknown';
  const terrain: Terrain = place.terrain !== undefined ? explicitTerrain
    : tags.has('mountain') ? 'mountain'
      : tags.has('forest') ? 'forest'
        : tags.has('desert') ? 'desert'
          : tags.has('wetland') || tags.has('marsh') ? 'wetland'
            : tags.has('coastal') || tags.has('harbor') || tags.has('seaside') ? 'coast'
              : tags.has('water') ? 'water'
                : tags.has('plain') || tags.has('plains') ? 'plain'
                  : tags.has('urban') || tags.has('settlement') ? 'urban' : 'unknown';
  const explicitLayer = LAYERS.includes(place.layer as Layer) ? place.layer as Layer : 'unknown';
  const layer: Layer = place.layer !== undefined ? explicitLayer
    : tags.has('underground') ? 'underground'
      : tags.has('sky') || tags.has('floating') ? 'sky' : 'unknown';
  const explicitHeight = place.elevation;
  const elevation = explicitHeight !== undefined
    ? Number.isInteger(explicitHeight) && explicitHeight! >= -2 && explicitHeight! <= 2 ? explicitHeight as number : null
    : tags.has('mountain') ? 2 : tags.has('valley') || tags.has('lowland') ? -1 : null;
  return { terrain, elevation, layer };
}

function mostCommon<T extends string>(values: T[], fallback: T): T {
  const known = values.filter((value) => value !== 'unknown');
  if (!known.length) return fallback;
  const counts = new Map<T, number>();
  known.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0][0];
}

/** A region inherits only hints from its player-visible member places. */
export function regionRelief(region: Pick<AtlasRegion, 'places'>): Relief {
  const hints = region.places.map(placeRelief);
  const terrain = mostCommon(hints.map((hint) => hint.terrain), 'unknown' as Terrain);
  const layer = mostCommon(hints.map((hint) => hint.layer), 'unknown' as Layer);
  const heights = hints.map((hint) => hint.elevation).filter((value): value is number => value !== null).sort((a, b) => a - b);
  const elevation = heights.length ? heights[Math.floor((heights.length - 1) / 2)] : null;
  return { terrain, elevation, layer };
}

export function reliefLabel(relief: Relief): string | null {
  const pieces: string[] = [];
  if (relief.terrain !== 'unknown') pieces.push(relief.terrain);
  if (relief.layer !== 'unknown' && relief.layer !== 'surface') pieces.push(relief.layer);
  if (relief.elevation !== null) pieces.push(relief.elevation > 0 ? 'higher ground' : relief.elevation < 0 ? 'lower ground' : 'level ground');
  return pieces.length ? pieces.join(' · ') : null;
}
