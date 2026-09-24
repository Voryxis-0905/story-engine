/**
 * Pure model behind the story atlas.
 *
 * The backend hands the map locations with a 0-100 coordinate pair, an optional
 * `zone`, a name, tags and a movement graph (`connected_to`). Newer maps may
 * also carry compact terrain/height/layer hints. Neither format defines exact
 * roads, coastlines or terrain borders, so the map never invents them. What it
 * does is derive, deterministically:
 *
 *   1. an ordered region hierarchy - which places belong together,
 *   2. a disclosure level   - what may be named at a given camera distance,
 *   3. label placement      - which label wins a collision,
 *   4. route legs           - adjacent pairs of an engine route, never shortcuts,
 *   5. a shape category     - a neutral silhouette family from the place's tags.
 *
 * Everything here is a pure function of its inputs so the drawing code in
 * LocationMap.tsx stays a renderer, and so the risky parts (privacy, label
 * overlap, route adjacency) are unit-testable without a canvas.
 */

import { normalizedCoordinate } from './mapCoordinates';

/** A place the map knows about, after the backend has applied visibility rules. */
export interface MapLocation {
  id: string;
  name: string;
  description?: string;
  x: number;
  y: number;
  zone?: string;
  /** Optional, text-generated relief hints. Missing values mean unknown. */
  terrain?: string;
  elevation?: number | null;
  layer?: string;
  tags?: string[];
  connected_to?: Array<string | { to?: string; location_id?: string; id?: string }>;
  is_unlocked: boolean;
  is_reachable?: boolean;
  discovery_status?: string;
  unlock_reason_missing?: string | null;
  is_starting_location?: boolean;
  route_preview?: string[];
}

/** Statuses whose name, description, tags, connections and routes are all private. */
const HIDDEN_STATUSES = new Set(['unknown', 'creator_only']);

/** Fallback region name when neither `zone` nor the "Zone - Place" convention applies. */
export const FALLBACK_REGION_NAME = 'Uncharted';

/**
 * Display status of a place. `undiscovered` exists because the engine can hand
 * back a hidden place with a scrubbed name ("Unknown location") and no
 * `discovery_status` at all - the scrubbed name is the only remaining signal.
 */
export type PlaceStatus = 'undiscovered' | 'locked' | 'unreachable' | 'current' | 'discovered';

/** Neutral silhouette families. Deliberately genre-free; see `placeKind`. */
export type PlaceKind = 'settlement' | 'interior' | 'landmark' | 'wild' | 'water' | 'hazard' | 'path';

/** How much detail the camera distance allows. */
export type Disclosure = 'overview' | 'region' | 'local';

/** Normalised world position (0..1, y already flipped for the canvas). */
export interface AtlasPoint { x: number; y: number }

export interface AtlasRegion {
  /** Stable key, derived from the region name. */
  key: string;
  name: string;
  /** Places in declaration order, so the model is stable between renders. */
  places: MapLocation[];
  /** Normalised centroid of the real places - label anchor and focus target. */
  center: AtlasPoint;
  /** Normalised radius that encloses every real place, with a floor. */
  radius: number;
  hasCurrent: boolean;
  undiscoveredCount: number;
  lockedCount: number;
  /** True when at least one place inside is clickable. */
  interactive: boolean;
}

export interface LabelPlacement {
  id: string;
  text: string;
  /** Anchored to the right of the node unless the label would leave the canvas. */
  side: 'left' | 'right' | 'center';
  box: { left: number; top: number; right: number; bottom: number };
}

/* ------------------------------------------------------------------ parsing */

/**
 * Zone resolution order, exactly as the product requires it:
 * explicit `zone` -> the existing "Zone - Place" naming convention -> neutral.
 *
 * A name with a separator but nothing usable before it (`" - Orphan"`) yields no
 * prefix; the part after the separator is then the only real label, so it
 * becomes the region name and the place keeps it as its own label too.
 */
export function regionNameOf(location: Pick<MapLocation, 'name' | 'zone'>): string {
  const zone = (location.zone || '').trim();
  if (zone) return zone;
  const parts = splitZoneName(location.name);
  return parts.region || parts.place || FALLBACK_REGION_NAME;
}

/**
 * Split a display name into its region prefix and its own label.
 *
 * Only the "Zone - Place" separator (a spaced hyphen, en dash or em dash) is
 * treated as a boundary, because that is the convention the world builder
 * already writes. A name with no separator is a region in its own right.
 */
export function splitZoneName(name: string | undefined): { region: string; place: string } {
  const trimmed = (name || '').trim();
  const [head = '', ...tail] = trimmed.split(/\s+[-—–]\s+/);
  const region = head.trim();
  const place = tail.join(' - ').trim();
  if (region && place) return { region, place };
  if (region) return { region, place: region };
  return { region: '', place };
}

/** Strip the "Zone - " prefix so a place does not repeat its region on its own label. */
export function placeLabel(location: Pick<MapLocation, 'name' | 'zone'>, region: string): string {
  const name = (location.name || '').trim();
  const parts = splitZoneName(name);
  // An explicit zone plus a conventional name still means the prefix is noise.
  if (parts.region && region && parts.region.toLowerCase() === region.toLowerCase()) return parts.place || name;
  const prefix = `${region} - `;
  if (region && name.toLowerCase().startsWith(prefix.toLowerCase())) {
    return name.slice(prefix.length).trim() || name;
  }
  return name;
}

export function isHidden(location: MapLocation): boolean {
  if (location.discovery_status && HIDDEN_STATUSES.has(location.discovery_status)) return true;
  // Defence in depth: a server that forgets discovery_status still ships the
  // scrubbed name for hidden places, and that must not become a real label.
  return (location.name || '').trim().toLowerCase() === 'unknown location';
}

export function placeStatus(location: MapLocation, currentRef?: string): PlaceStatus {
  if (isHidden(location)) return 'undiscovered';
  if (matchesReference(location, currentRef)) return 'current';
  if (!location.is_unlocked) {
    if (location.is_reachable === false) return 'unreachable';
    return 'locked';
  }
  if (location.is_reachable === false) return 'unreachable';
  return 'discovered';
}

export function matchesReference(location: MapLocation, reference?: string): boolean {
  if (!reference) return false;
  return location.id === reference || location.name === reference;
}

/** Places the map is allowed to name and draw. */
export function visiblePlaces(locations: MapLocation[]): MapLocation[] {
  return locations.filter((location) => !isHidden(location));
}

/** Places a region overview may count. Hidden places never contribute. */
export function isRegionInteractive(region: AtlasRegion): boolean {
  return region.places.some((location) => !isHidden(location));
}

/* --------------------------------------------------------------- projection */

export function toPoint(location: Pick<MapLocation, 'x' | 'y'>): AtlasPoint {
  return { x: normalizedCoordinate(location.x), y: 1 - normalizedCoordinate(location.y) };
}

/** Normalised euclidean distance between two places. */
export function distanceBetween(a: Pick<MapLocation, 'x' | 'y'>, b: Pick<MapLocation, 'x' | 'y'>): number {
  const pa = toPoint(a);
  const pb = toPoint(b);
  return Math.hypot(pa.x - pb.x, pa.y - pb.y);
}

/* ------------------------------------------------------------- aggregation */

/**
 * Group visible places into regions and measure each one.
 *
 * Hidden places are excluded from the aggregation entirely - not merely from
 * the label - so a region guarded by an undiscovered place cannot leak its
 * position, its count, or the fact that anything is there at all.
 */
export function buildRegions(locations: MapLocation[], currentRef?: string): AtlasRegion[] {
  const groups = new Map<string, AtlasRegion>();
  for (const location of visiblePlaces(locations)) {
    const name = regionNameOf(location);
    const key = `region:${name.toLowerCase()}`;
    let region = groups.get(key);
    if (!region) {
      region = { key, name, places: [], center: { x: 0.5, y: 0.5 }, radius: 0.1, hasCurrent: false, undiscoveredCount: 0, lockedCount: 0, interactive: false };
      groups.set(key, region);
    }
    region.places.push(location);
    if (matchesReference(location, currentRef)) region.hasCurrent = true;
    const status = placeStatus(location, currentRef);
    if (status === 'locked' || status === 'unreachable') region.lockedCount += 1;
  }

  const regions = [...groups.values()];
  for (const region of regions) {
    let sx = 0; let sy = 0;
    let minX = 1; let maxX = 0; let minY = 1; let maxY = 0;
    for (const place of region.places) {
      const point = toPoint(place);
      sx += point.x; sy += point.y;
      minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x);
      minY = Math.min(minY, point.y); maxY = Math.max(maxY, point.y);
    }
    region.center = { x: sx / region.places.length, y: sy / region.places.length };
    // Enclose every member, then keep a floor so a single place still reads as
    // an area instead of a point.
    region.radius = Math.max(MIN_REGION_RADIUS, Math.hypot((maxX - minX) / 2, (maxY - minY) / 2));
    region.interactive = region.places.length > 0;
  }

  // Stable order: regions with the protagonist first, then biggest, then name.
  return regions.sort((a, b) =>
    Number(b.hasCurrent) - Number(a.hasCurrent)
    || b.places.length - a.places.length
    || a.name.localeCompare(b.name));
}

/** Smallest a region disc may be, in normalised units (13% of the world). */
export const MIN_REGION_RADIUS = 0.13;

export function findRegion(regions: AtlasRegion[], key: string | null): AtlasRegion | null {
  if (!key) return null;
  return regions.find((region) => region.key === key) || null;
}

export function regionContaining(regions: AtlasRegion[], location: MapLocation | null | undefined): AtlasRegion | null {
  if (!location) return null;
  const name = regionNameOf(location).toLowerCase();
  return regions.find((region) => region.name.toLowerCase() === name) || null;
}

/* ----------------------------------------------------------- disclosure */

/**
 * Zoom thresholds, expressed once so the renderer and the interaction code
 * cannot drift apart.
 *
 *   zoom < LOCAL_DETAIL_ZOOM  places are picked by importance (protagonist,
 *                             region representatives, route, selection)
 *   zoom >= LOCAL_DETAIL_ZOOM every place in the focused region is disclosed
 *
 * `LOCAL_DETAIL_ZOOM` is only a *convenience* threshold, not the rule. Opening a
 * region is an explicit request to see inside it, so the disclosure level
 * follows the open region and the camera then fits that region at whatever zoom
 * actually encloses it - a region spanning most of the map opens at a low zoom
 * and still shows its places. Gating disclosure on a hard zoom floor made wide
 * regions impossible to display: they either zoomed in and cropped their own
 * members, or sat below the floor and drew nothing.
 */
export const REGION_MARK_ZOOM = 2.25;
export const LOCAL_DETAIL_ZOOM = 2.25;

export function disclosureFor(
  zoom: number,
  focusedRegion: AtlasRegion | null | undefined,
  options: { regionOpen?: boolean } = {},
): Disclosure {
  if (options.regionOpen ?? zoom >= LOCAL_DETAIL_ZOOM) {
    return focusedRegion ? 'local' : 'overview';
  }
  return 'overview';
}

/**
 * Which places are drawn as individual nodes.
 *
 * In local tier the whole focused region is disclosed. Otherwise a place is
 * drawn only when it is a landmark the camera is close enough to read: the
 * protagonist, a region representative, a place on the previewed route, the
 * live selection, or an isolated place that no region covers.
 */
export interface NodeSelection {
  places: MapLocation[];
  /** True when the camera is close enough for every place in focus. */
  local: boolean;
  focusedRegion: AtlasRegion | null;
  /** One representative per region, used to anchor region labels in the legible tier. */
  representatives: MapLocation[];
}

export interface VisiblePlacesOptions {
  /** Current camera zoom; a convenience trigger for the local tier. */
  zoom: number;
  focusedRegionKey?: string | null;
  currentRef?: string;
  selectedId?: string | null;
  routeRefs?: ReadonlySet<string>;
  /**
   * True when the player explicitly opened a region. Disclosure then follows
   * that intent rather than the zoom number, so a region wider than the viewport
   * still discloses its places. Omit it (or pass false) to fall back to the zoom
   * threshold.
   */
  regionOpen?: boolean;
}

export function selectVisiblePlaces(
  locations: MapLocation[],
  regions: AtlasRegion[],
  options: VisiblePlacesOptions,
): NodeSelection {
  const visible = visiblePlaces(locations);
  const focusedRegion = findRegion(regions, options.focusedRegionKey ?? null);
  // An opened region discloses its interior regardless of zoom: the camera may
  // have had to zoom out to enclose it, and that must not hide what was asked
  // for. Without a focused region there is nothing to disclose either way.
  const local = Boolean(focusedRegion)
    && (options.regionOpen ?? options.zoom >= LOCAL_DETAIL_ZOOM);

  const representatives: MapLocation[] = [];
  for (const region of regions) {
    // The protagonist anchors its own region; otherwise the least-restricted
    // place stands in, which is the one the player is most likely to reach.
    const best = region.places.find((place) => matchesReference(place, options.currentRef))
      || [...region.places].sort((a, b) => Number(b.is_unlocked) - Number(a.is_unlocked))[0];
    if (best) representatives.push(best);
  }
  // Resolve a place's region through the model rather than by rebuilding its
  // key, so trimming or separators can never make the two disagree.
  const regionOf = (location: MapLocation) => regionContaining(regions, location);
  const sameRegion = (a: MapLocation, b: AtlasRegion) => regionOf(a)?.key === b.key;

  if (local) {
    const inFocus = visible.filter((place) => sameRegion(place, focusedRegion!));
    const elsewhere = representatives.filter((place) => !inFocus.some((item) => item.id === place.id));
    return { places: [...inFocus, ...elsewhere], local: true, focusedRegion, representatives };
  }

  // Pinned places are chosen before the representative guarantee so that a
  // pinned place which is also its region's representative survives the merge.
  const pinned = visible.filter((place) =>
    matchesReference(place, options.currentRef)
    || place.id === options.selectedId
    || options.routeRefs?.has(place.id)
    || options.routeRefs?.has(place.name));

  const kept = new Map<string, MapLocation>();
  for (const place of [...representatives, ...pinned]) kept.set(place.id, place);

  // Anything the region model does not cover still needs a node, or it would be
  // unreachable and unclickable from the overview.
  for (const place of visible) {
    if (!regionOf(place)) kept.set(place.id, place);
  }

  // Guarantee that every region has at least one clickable place: a region
  // whose only members were filtered out could never be expanded by clicking.
  for (const region of regions) {
    if (region.places.length === 0) continue;
    if ([...kept.values()].some((place) => sameRegion(place, region))) continue;
    const fallback = region.places.find((place) => matchesReference(place, options.currentRef)) || region.places[0];
    kept.set(fallback.id, fallback);
  }

  return { places: [...kept.values()], local: false, focusedRegion, representatives };
}

/* --------------------------------------------------------------- labelling */

const LABEL_FONT = '600 12px "Plus Jakarta Sans", sans-serif';
const LABEL_HEIGHT = 18;
const LABEL_PAD = 8;

export interface LabelLayoutOptions {
  size: number;
  regionOf: (location: MapLocation) => AtlasRegion | null;
  force: (location: MapLocation) => boolean;
  measure: (text: string) => number;
  /** Region receiving priority among non-forced labels. */
  focusedRegion?: AtlasRegion | null;
}

/**
 * Place labels without letting them overlap.
 *
 * Priority is explicit and stable: forced labels (protagonist, hover, live
 * selection) first, then the focused region, then whatever order the caller
 * passed. A label that cannot be placed without colliding is dropped rather
 * than drawn on top of its neighbour.
 */
export function layoutLabels(
  entries: MapLocation[],
  positions: Array<{ id: string; x: number; y: number }>,
  options: LabelLayoutOptions,
): LabelPlacement[] {
  const positionOf = new Map(positions.map((item) => [item.id, item]));
  const boxes: Array<{ left: number; top: number; right: number; bottom: number }> = [];
  const placements: LabelPlacement[] = [];
  const priorityOf = new Map<string, number>();

  const rank = (location: MapLocation) => {
    if (options.force(location)) return 0;
    const region = options.regionOf(location);
    return region && region === options.focusedRegion ? 1 : 2;
  };

  const ordered = [...entries].sort((a, b) => rank(a) - rank(b) || entries.indexOf(a) - entries.indexOf(b));
  ordered.forEach((location) => {
    if (!priorityOf.has(location.id)) priorityOf.set(location.id, rank(location));
  });

  for (const location of ordered) {
    const point = positionOf.get(location.id);
    if (!point) continue;
    const text = placeLabel(location, regionNameOf(location));
    if (!text) continue;
    const width = options.measure(text) + LABEL_PAD * 2;
    const height = LABEL_HEIGHT;
    const isForced = options.force(location) || rank(location) === 1;
    const top = point.y - height / 2;
    // Two candidate anchors: to the right of the node, then to its left near the
    // right edge. Both keep the label vertically centred on the node, so the
    // visual anchor and the hit target remain the same place.
    const candidates: Array<{ side: LabelPlacement['side']; left: number }> = [
      { side: 'right', left: point.x + 12 },
      { side: 'left', left: point.x - 12 - width },
    ];
    let placed: LabelPlacement | null = null;
    for (const candidate of candidates) {
      const box = { left: candidate.left, top, right: candidate.left + width, bottom: top + height };
      const outside = box.left < 4 || box.right > options.size - 4 || box.top < 4 || box.bottom > options.size - 4;
      const collides = boxes.some((other) =>
        box.left < other.right + 4 && box.right + 4 > other.left && box.top < other.bottom + 3 && box.bottom + 3 > other.top);
      if (!collides && (!outside || isForced)) {
        placed = { id: location.id, text, side: candidate.side, box };
        break;
      }
    }
    if (!placed) continue;
    boxes.push(placed.box);
    placements.push(placed);
  }

  // Forced labels come first in the output so a caller can trivially assert on
  // what must never be dropped. `priority` is captured per placement rather
  // than recomputed from the node, because two labels can share one node.
  return placements
    .map((placement, index) => ({ placement, priority: priorityOf.get(placement.id) ?? 2, index }))
    .sort((a, b) => a.priority - b.priority || a.index - b.index)
    .map((entry) => entry.placement);
}

/** Region names get the same anti-overlap treatment as place labels. */
export interface RegionLabelInput { key: string; name: string; x: number; y: number; radius: number; focus: boolean }

export function layoutRegionLabels(
  inputs: RegionLabelInput[],
  size: number,
  measure: (text: string) => number,
): Array<RegionLabelInput & { box: { left: number; top: number; right: number; bottom: number } }> {
  const boxes: Array<{ left: number; top: number; right: number; bottom: number }> = [];
  const out: Array<RegionLabelInput & { box: { left: number; top: number; right: number; bottom: number } }> = [];
  const ordered = [...inputs].sort((a, b) => Number(b.focus) - Number(a.focus) || b.radius - a.radius);
  for (const input of ordered) {
    const width = measure(input.name) + LABEL_PAD * 2;
    const height = 20;
    const block = Math.max(14, input.radius * size * 0.55);
    // A label wider than the canvas would never fit at either anchor, so the
    // horizontal position is clamped into the canvas before collision testing
    // instead of dropping the region's name entirely.
    const clampLeft = (left: number) => Math.max(4, Math.min(left, size - 4 - width));
    const anchors = [
      { left: clampLeft(input.x - width / 2), top: input.y - block - height },
      { left: clampLeft(input.x - width / 2), top: input.y + block },
      { left: clampLeft(input.x - width / 2), top: input.y - height / 2 },
    ];
    let chosen: { left: number; top: number; right: number; bottom: number } | null = null;
    for (const anchor of anchors) {
      const box = { left: anchor.left, top: anchor.top, right: anchor.left + width, bottom: anchor.top + height };
      const outside = box.left < 4 || box.right > size - 4 || box.top < 2 || box.bottom > size - 2;
      const collides = boxes.some((other) => box.left < other.right && box.right > other.left && box.top < other.bottom && box.bottom > other.top);
      if (!collides && !outside) { chosen = box; break; }
    }
    if (!chosen) continue;
    boxes.push(chosen);
    out.push({ ...input, box: chosen });
  }
  return out;
}

/* ------------------------------------------------------------------- route */

/**
 * Adjacent pairs of an engine route, matched back to real map places.
 *
 * `travelPreview.route` is an ordered sequence of *names*; some of them (the
 * origin, or an intermediate stop that is not on the current map) may not
 * resolve. Unresolvable hops are returned separately so the renderer can say
 * "part of this route is off the map" instead of drawing a straight line
 * across the world, which would invent a shortcut the engine never allowed.
 */
export interface RouteSegment {
  from: MapLocation;
  to: MapLocation;
}

export interface RouteModel {
  segments: RouteSegment[];
  /** Route names that are not on the map: origin outside the map, hidden stop, etc. */
  unsupported: string[];
  /** False when the route is a single point (already there). */
  drawable: boolean;
}

export function buildRouteModel(route: readonly string[] | undefined, locations: MapLocation[]): RouteModel {
  const stops = route || [];
  if (stops.length < 2) return { segments: [], unsupported: [], drawable: false };
  const resolved: Array<MapLocation | null> = stops.map((stop) =>
    locations.find((location) => location.id === stop || location.name === stop) || null);
  const segments: RouteSegment[] = [];
  const unsupported: string[] = [];
  for (let index = 0; index < resolved.length - 1; index += 1) {
    const from = resolved[index];
    const to = resolved[index + 1];
    if (from && to && from.id !== to.id) {
      segments.push({ from, to });
      continue;
    }
    if (!from) unsupported.push(stops[index]);
    if (!to && index + 1 === resolved.length - 1) unsupported.push(stops[index + 1]);
  }
  return { segments, unsupported: [...new Set(unsupported)], drawable: segments.length > 0 };
}

/**
 * Tag -> category vocabulary, in resolution order.
 *
 * Order matters and is deliberate: a place tagged
 * `["dangerous", "wilderness", "combat"]` is dangerous *ground*, and drawing it
 * as a water shape would be wrong, so `wilderness` outranks `dangerous`.
 * `dangerous` only decides the shape when nothing else describes the terrain.
 */
const KIND_TAGS_ORDERED: Array<[string, PlaceKind]> = [
  // Terrain first: it is the most specific claim the data makes about a place.
  ['water', 'water'], ['coastal', 'water'], ['harbor', 'water'], ['seaside', 'water'], ['tide', 'water'],
  ['wilderness', 'wild'], ['forest', 'wild'], ['mountain', 'wild'], ['outdoor', 'wild'], ['wild', 'wild'],
  // A landmark is a named built thing; also more specific than a hazard flag.
  ['palace', 'landmark'], ['temple', 'landmark'], ['shrine', 'landmark'], ['castle', 'landmark'],
  ['dungeon', 'landmark'], ['monument', 'landmark'], ['sacred', 'landmark'], ['landmark', 'landmark'],
  ['ruined', 'hazard'], ['cursed', 'hazard'], ['combat', 'hazard'], ['hazard', 'hazard'], ['dangerous', 'hazard'],
  ['smuggler', 'hazard'], ['smugglers', 'hazard'],
  ['urban', 'settlement'], ['settlement', 'settlement'], ['city', 'settlement'], ['town', 'settlement'],
  ['village', 'settlement'], ['shop', 'settlement'], ['market', 'settlement'], ['inn', 'settlement'],
  ['tavern', 'settlement'],
  ['indoor', 'interior'], ['interior', 'interior'], ['room', 'interior'], ['building', 'interior'],
  ['house', 'interior'], ['home', 'interior'],
  ['road', 'path'], ['path', 'path'], ['street', 'path'], ['route', 'path'], ['trail', 'path'],
  ['train', 'path'], ['station', 'path'], ['bridge', 'path'],
];

const KIND_TAGS: Record<string, { kind: PlaceKind; rank: number }> = Object.fromEntries(
  KIND_TAGS_ORDERED.map(([tag, kind], rank) => [tag, { kind, rank }]),
);

/**
 * Silhouette family for a place, from its own tags only.
 *
 * The vocabulary is deliberately abstract - a disc, a burrow, a notch, a step
 * block - so it reads the same for a school corridor, a sect hall and a tidal
 * flat without the map asserting a genre the world never declared.
 */
export function placeKind(location: Pick<MapLocation, 'tags'>): PlaceKind {
  const tags = (location.tags || []).map((tag) => String(tag).toLowerCase().trim());
  let best: { kind: PlaceKind; rank: number } | null = null;
  for (const tag of tags) {
    const entry = KIND_TAGS[tag];
    if (!entry) continue;
    // Lowest rank wins, so specificity beats a generic "dangerous" flag.
    if (!best || entry.rank < best.rank) best = entry;
  }
  return best ? best.kind : 'interior';
}

/** True when the place carries tags the map understands at all. */
export function hasKnownTags(location: Pick<MapLocation, 'tags'>): boolean {
  return (location.tags || []).some((tag) => Boolean(KIND_TAGS[String(tag).toLowerCase().trim()]));
}

/* --------------------------------------------------------------- hit model */

export const NODE_HIT_RADIUS = 15;

/**
 * Nearest place to a canvas point, within the hit radius.
 *
 * Hit testing runs through this instead of `find` so the closest node wins when
 * two clickable shapes overlap - matching what the eye picks.
 *
 * `bounds` is the canvas, and it is not optional bookkeeping. A place outside
 * the viewport is not painted, so it must not be clickable either: at high zoom
 * an off-screen node can sit inside the hit radius of a point in the middle of
 * a 335px canvas purely because the map is cropped, and without this guard the
 * click silently selects an invisible place. Visual position and click target
 * are the same coordinate, or the hit test is lying.
 *
 * A place exactly on the edge is still counted as visible, matching the
 * renderer's inclusive culling.
 */
export function placeAtPoint(
  places: MapLocation[],
  pointer: { x: number; y: number },
  project: (place: MapLocation) => { x: number; y: number },
  radius = NODE_HIT_RADIUS,
  bounds?: { width: number; height: number },
): MapLocation | null {
  let best: MapLocation | null = null;
  let bestDistance = radius;
  for (const place of places) {
    if (isHidden(place)) continue;
    const point = project(place);
    if (bounds && (point.x < 0 || point.y < 0 || point.x > bounds.width || point.y > bounds.height)) continue;
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    if (distance < bestDistance) { bestDistance = distance; best = place; }
  }
  return best;
}

/** Nearest region disc to a canvas point. Regions are always hit-testable. */
export function regionAtPoint(
  regions: AtlasRegion[],
  pointer: { x: number; y: number },
  project: (region: AtlasRegion) => { x: number; y: number; radius: number },
  pad = 10,
): AtlasRegion | null {
  let best: AtlasRegion | null = null;
  let bestDistance = Infinity;
  for (const region of regions) {
    if (!region.interactive) continue;
    const point = project(region);
    const distance = Math.hypot(point.x - pointer.x, point.y - pointer.y);
    if (distance <= point.radius + pad && distance < bestDistance) { bestDistance = distance; best = region; }
  }
  return best;
}

/** Label metrics shared by the renderer and the layout tests. */
export const labelMetrics = { font: LABEL_FONT, height: LABEL_HEIGHT, pad: LABEL_PAD };
