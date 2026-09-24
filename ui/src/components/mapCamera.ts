import { normalizedCoordinate } from './mapCoordinates';

export interface Camera { x: number; y: number; zoom: number }

export const MIN_ZOOM = 0.65;
export const MAX_ZOOM = 3.5;

/** Zoom the viewport snaps to when it recenters on a location. */
export const RECENTER_ZOOM = 2.25;

/**
 * Zoom the viewport snaps to when it opens a region's interior. Below this the
 * map draws region discs only; at or above it, individual places are drawn.
 * Kept equal to RECENTER_ZOOM so "recentered on the protagonist" and "local
 * detail available" are the same boundary, not two rules that can drift.
 */
export const REGION_FOCUS_ZOOM = 2.25;

/** Pixel distance the viewport travels for a single arrow-key press. */
export const KEY_PAN_PIXELS = 40;

export const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));

/**
 * Move the viewport by a pixel offset. Positive dx pans the view right and
 * positive dy pans it down; the camera itself travels the opposite way.
 * Used by both pointer dragging and the arrow keys so the two stay in sync.
 */
export function panCamera(camera: Camera, dx: number, dy: number, size: number): Camera {
  const scale = size > 0 ? size * camera.zoom : 1;
  return { ...camera, x: clamp(camera.x + dx / scale, 0, 1), y: clamp(camera.y + dy / scale, 0, 1) };
}

export function zoomCamera(camera: Camera, factor: number): Camera {
  return { ...camera, zoom: clamp(camera.zoom * factor, MIN_ZOOM, MAX_ZOOM) };
}

/**
 * Zoom while keeping the world point under the pointer pinned to the pointer.
 *
 * Without this, wheel zoom always pulls toward the canvas centre and the place
 * a player is inspecting drifts away from the cursor - the exact opposite of
 * what exploring a map should feel like.
 */
export function zoomCameraAt(
  camera: Camera,
  factor: number,
  size: number,
  screen: { x: number; y: number },
): Camera {
  const zoom = clamp(camera.zoom * factor, MIN_ZOOM, MAX_ZOOM);
  if (size <= 0 || zoom === camera.zoom) return { ...camera, zoom };
  // Screen point -> world offset from the camera centre, using the *old* scale,
  // then re-anchored on the new scale so the same world point stays put.
  const offsetX = (screen.x - size / 2) / (size * camera.zoom);
  const offsetY = (screen.y - size / 2) / (size * camera.zoom);
  return {
    zoom,
    x: clamp(camera.x + offsetX - offsetX * (camera.zoom / zoom), 0, 1),
    y: clamp(camera.y + offsetY - offsetY * (camera.zoom / zoom), 0, 1),
  };
}

/**
 * Project a world coordinate onto the canvas. World coordinates are 0..100 and
 * the backend measures y from the bottom up, while the canvas measures it from
 * the top down, so y is flipped here — this is the only place that happens.
 */
export function worldToScreen(point: { x: number; y: number }, size: number, camera: Camera) {
  return {
    x: (normalizedCoordinate(point.x) - camera.x) * size * camera.zoom + size / 2,
    y: ((1 - normalizedCoordinate(point.y)) - camera.y) * size * camera.zoom + size / 2,
  };
}

/**
 * Inverse of `worldToScreen`: canvas pixels back to normalised world
 * coordinates. `x` is already in the 0..1 camera space (y already flipped), so
 * callers that need the backend's 0-100 y must flip it back themselves. Kept
 * here so the forward and inverse projections can never disagree.
 */
export function screenToWorld(screen: { x: number; y: number }, size: number, camera: Camera) {
  const scale = size > 0 ? size * camera.zoom : 1;
  return {
    x: camera.x + (screen.x - size / 2) / scale,
    y: camera.y + (screen.y - size / 2) / scale,
  };
}

/** Normalised world distance converted to canvas pixels. */
export function worldDistanceToScreen(distance: number, size: number, camera: Camera): number {
  return distance * size * camera.zoom;
}

/** Centre the camera on a normalised world point without changing the zoom. */
export function cameraCenteredOn(point: { x: number; y: number }, zoom = RECENTER_ZOOM): Camera {
  return { x: clamp(point.x, 0, 1), y: clamp(point.y, 0, 1), zoom: clamp(zoom, MIN_ZOOM, MAX_ZOOM) };
}

/**
 * Frame a normalised bounding box.
 *
 * Used to show a whole region when the player opens it: the camera ends up
 * centred on the region and no closer than needed to enclose it, so the region
 * fills the viewport instead of floating in the middle of it.
 */
export function fitToBounds(
  bounds: { minX: number; maxX: number; minY: number; maxY: number },
  size: number,
  options: { padding?: number; minZoom?: number } = {},
): Camera {
  const padding = options.padding ?? 0.16;
  const minZoom = options.minZoom ?? REGION_FOCUS_ZOOM;
  const center = { x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2 };
  const extentX = Math.max(bounds.maxX - bounds.minX, 0.01) * (1 + padding * 2);
  const extentY = Math.max(bounds.maxY - bounds.minY, 0.01) * (1 + padding * 2);
  // The viewport is square, so the tighter of the two axes decides the zoom.
  const zoom = size > 0 ? Math.min(1 / extentX, 1 / extentY) : MAX_ZOOM;
  return cameraCenteredOn(center, clamp(Math.max(minZoom, zoom), MIN_ZOOM, MAX_ZOOM));
}

/** Normalised bounding box of a set of points, padded by `pad`. */
export function boundsOf(points: Array<{ x: number; y: number }>, pad = 0) {
  if (points.length === 0) return { minX: 0, maxX: 1, minY: 0, maxY: 1 };
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  return {
    minX: clamp(Math.min(...xs) - pad, 0, 1),
    maxX: clamp(Math.max(...xs) + pad, 0, 1),
    minY: clamp(Math.min(...ys) - pad, 0, 1),
    maxY: clamp(Math.max(...ys) + pad, 0, 1),
  };
}
