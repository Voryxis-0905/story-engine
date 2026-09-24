/**
 * Camera policy for the story atlas: which camera the map moves to for a given
 * player intent.
 *
 * This lives outside the component because it is a *contract*, not a detail.
 * Both `LocationMap` and the E2E suite need the exact camera that results from
 * "recenter on the protagonist", "open this region" or "zoom about the pointer".
 * Re-deriving any of those in a test produces a projection that is subtly
 * different from the one the map draws with - and then a click lands on empty
 * canvas and the failure looks like a rendering bug. So both sides call in here.
 *
 * Pure: no refs, no state, no canvas.
 */

import {
  RECENTER_ZOOM,
  MIN_ZOOM,
  MAX_ZOOM,
  boundsOf,
  cameraCenteredOn,
  fitToBounds,
  zoomCameraAt,
  clamp,
  type Camera,
} from './mapCamera';
import type { AtlasRegion, MapLocation } from './mapModel';

/** Narrow bounds so this module does not depend on a whole region object. */
export interface RegionLike {
  places: Array<Pick<MapLocation, 'x' | 'y'>>;
  radius: number;
}

/** The zoom the map opens a region at. Exported so tests can read, not guess. */
export const REGION_OPEN_PADDING = 0.22;

/**
 * Bounding box of a region in normalised, canvas-oriented world space.
 *
 * `y` is flipped here because the backend measures it bottom-up. The padding is
 * proportional to the region's own radius so a tight cluster still gets air
 * around it when the camera frames it.
 */
export function regionBounds(region: RegionLike) {
  const points = region.places.map((place) => ({
    x: clamp(Number(place.x || 0) / 100, 0, 1),
    y: 1 - clamp(Number(place.y || 0) / 100, 0, 1),
  }));
  return boundsOf(points, Math.max(0.05, region.radius * 0.35));
}

/**
 * Camera for "open this region".
 *
 * Frame the region: centred on it, zoomed no closer than needed to enclose
 * every member. The zoom is deliberately *not* floored at REGION_FOCUS_ZOOM.
 * A region spanning most of the map cannot be enclosed at that zoom, and forcing
 * it there would crop the very members the player asked to see. Disclosure is
 * tied to the opened region instead (see `selectVisiblePlaces`), so a low zoom
 * here still shows the interior.
 *
 * The floor is MIN_ZOOM: below that the map is too coarse to read at all.
 */
export function regionCamera(region: RegionLike, size: number): Camera {
  const fit = fitToBounds(regionBounds(region), size, { padding: REGION_OPEN_PADDING, minZoom: MIN_ZOOM });
  return { ...fit, zoom: clamp(fit.zoom, MIN_ZOOM, MAX_ZOOM) };
}

/** Camera for "recenter on the protagonist", or the whole world when there is none. */
export function overviewCamera(currentPlace: Pick<MapLocation, 'x' | 'y'> | null | undefined): Camera {
  if (!currentPlace) return { x: .5, y: .5, zoom: 1 };
  return cameraCenteredOn(
    { x: clamp(Number(currentPlace.x || 0) / 100, 0, 1), y: 1 - clamp(Number(currentPlace.y || 0) / 100, 0, 1) },
    RECENTER_ZOOM,
  );
}

/** Camera for "return to the overview": the whole world, no region open. */
export function worldOverviewCamera(): Camera {
  return { x: .5, y: .5, zoom: 1 };
}

/** Camera after a button or wheel zoom, anchored on a pixel in the canvas. */
export function zoomedCamera(camera: Camera, factor: number, size: number, screen: { x: number; y: number }): Camera {
  return zoomCameraAt(camera, factor, size, screen);
}

/** Re-exported so callers of this module do not need a second import for typing. */
export type { AtlasRegion, Camera };
