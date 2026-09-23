import { normalizedCoordinate } from './mapCoordinates';

export interface Camera { x: number; y: number; zoom: number }

export const MIN_ZOOM = 0.65;
export const MAX_ZOOM = 3.5;

/** Zoom the viewport snaps to when it recenters on a location. */
export const RECENTER_ZOOM = 2.25;

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
