import { describe, expect, it } from 'vitest';
import {
  KEY_PAN_PIXELS, MAX_ZOOM, MIN_ZOOM, RECENTER_ZOOM, REGION_FOCUS_ZOOM,
  boundsOf, cameraCenteredOn, clamp, fitToBounds, panCamera, screenToWorld,
  worldDistanceToScreen, worldToScreen, zoomCamera, zoomCameraAt, type Camera,
} from './mapCamera';

const SIZE = 500;
const CENTER = SIZE / 2;
const IDLE: Camera = { x: .5, y: .5, zoom: 1 };

describe('mapCamera clamp', () => {
  it('bounds a value on both sides', () => {
    expect(clamp(5, 0, 1)).toBe(1);
    expect(clamp(-5, 0, 1)).toBe(0);
    expect(clamp(0.4, 0, 1)).toBe(0.4);
  });
});

describe('mapCamera worldToScreen', () => {
  it('centres the world centre on the canvas centre', () => {
    const point = worldToScreen({ x: 50, y: 50 }, SIZE, IDLE);
    expect(point.x).toBeCloseTo(CENTER);
    expect(point.y).toBeCloseTo(CENTER);
  });

  it('flips the backend y axis exactly once', () => {
    // The backend measures y from the bottom; the canvas from the top.
    const low = worldToScreen({ x: 50, y: 0 }, SIZE, IDLE);
    const high = worldToScreen({ x: 50, y: 100 }, SIZE, IDLE);
    expect(low.y).toBeGreaterThan(high.y);
    expect(low.y).toBeCloseTo(SIZE);
    expect(high.y).toBeCloseTo(0);
  });

  it('scales distances with zoom', () => {
    const a = worldToScreen({ x: 50, y: 50 }, SIZE, IDLE);
    const b = worldToScreen({ x: 60, y: 50 }, SIZE, IDLE);
    const c = worldToScreen({ x: 60, y: 50 }, SIZE, { ...IDLE, zoom: 2 });
    expect(b.x - a.x).toBeCloseTo(50);
    expect(c.x - a.x).toBeCloseTo(100);
  });
});

describe('mapCamera screenToWorld', () => {
  it('is the inverse of worldToScreen', () => {
    for (const camera of [IDLE, { x: .2, y: .8, zoom: 1.5 }, { x: 0, y: 1, zoom: 3.5 }]) {
      for (const point of [{ x: 0, y: 0 }, { x: 33, y: 71 }, { x: 100, y: 100 }]) {
        const screen = worldToScreen(point, SIZE, camera);
        const back = screenToWorld(screen, SIZE, camera);
        expect(back.x).toBeCloseTo(point.x / 100, 6);
        // screenToWorld works in flipped space; y is compared after one flip.
        expect(back.y).toBeCloseTo(1 - point.y / 100, 6);
      }
    }
  });
});

describe('mapCamera panCamera', () => {
  it('moves the camera so the content follows the pointer', () => {
    // Panning right moves the camera right, so content is drawn further left.
    const after = panCamera(IDLE, KEY_PAN_PIXELS, 0, SIZE);
    expect(after.x).toBeGreaterThan(IDLE.x);
    expect(worldToScreen({ x: 50, y: 50 }, SIZE, after).x).toBeLessThan(CENTER);
  });

  it('clamps at the world edges instead of drifting away', () => {
    let camera = IDLE;
    for (let i = 0; i < 50; i += 1) camera = panCamera(camera, -KEY_PAN_PIXELS, 0, SIZE);
    expect(camera.x).toBe(0);

    for (let i = 0; i < 100; i += 1) camera = panCamera(camera, KEY_PAN_PIXELS, 0, SIZE);
    expect(camera.x).toBe(1);
  });

  it('scales the step by zoom so a key press feels the same at any distance', () => {
    const near = panCamera(IDLE, KEY_PAN_PIXELS, 0, SIZE);
    const far = panCamera({ ...IDLE, zoom: 2 }, KEY_PAN_PIXELS, 0, SIZE);
    expect(far.x - IDLE.x).toBeLessThan(near.x - IDLE.x);
  });

  it('does not divide by zero on an unmeasured canvas', () => {
    expect(() => panCamera(IDLE, KEY_PAN_PIXELS, 0, 0)).not.toThrow();
  });
});

describe('mapCamera zoomCamera', () => {
  it('clamps at the ends of the range', () => {
    expect(zoomCamera(IDLE, 100).zoom).toBe(MAX_ZOOM);
    expect(zoomCamera(IDLE, 0.001).zoom).toBe(MIN_ZOOM);
  });
});

describe('mapCamera zoomCameraAt', () => {
  it('keeps the world point under the pointer pinned', () => {
    const aim = { x: 120, y: 380 };
    const before = screenToWorld(aim, SIZE, IDLE);
    const after = zoomCameraAt(IDLE, 1.6, SIZE, aim);

    expect(after.zoom).toBeGreaterThan(IDLE.zoom);
    const still = screenToWorld(aim, SIZE, after);
    expect(still.x).toBeCloseTo(before.x, 6);
    expect(still.y).toBeCloseTo(before.y, 6);
  });

  it('leaves the camera alone when the zoom is already clamped', () => {
    const atMax: Camera = { x: .3, y: .7, zoom: MAX_ZOOM };
    expect(zoomCameraAt(atMax, 2, SIZE, { x: 10, y: 10 })).toEqual(atMax);
  });

  it('still pins the anchor when the new camera needs clamping', () => {
    // Anchored near a corner, the clamp may bite; the anchor must not swing.
    const aim = { x: 5, y: 5 };
    const after = zoomCameraAt(IDLE, 1.4, SIZE, aim);
    expect(after.x).toBeGreaterThanOrEqual(0);
    expect(after.x).toBeLessThanOrEqual(1);
    expect(after.y).toBeGreaterThanOrEqual(0);
    expect(after.y).toBeLessThanOrEqual(1);
  });

  it('tolerates an unmeasured canvas', () => {
    expect(zoomCameraAt(IDLE, 1.5, 0, { x: 10, y: 10 }).zoom).toBeCloseTo(1.5);
  });
});

describe('mapCamera worldDistanceToScreen', () => {
  it('converts normalised distance to pixels at the current zoom', () => {
    expect(worldDistanceToScreen(0.1, SIZE, IDLE)).toBeCloseTo(50);
    expect(worldDistanceToScreen(0.1, SIZE, { ...IDLE, zoom: 2 })).toBeCloseTo(100);
  });
});

describe('mapCamera boundsOf', () => {
  it('returns the whole world for an empty set', () => {
    expect(boundsOf([])).toEqual({ minX: 0, maxX: 1, minY: 0, maxY: 1 });
  });

  it('encloses every point and pads without leaving the world', () => {
    const bounds = boundsOf([{ x: .2, y: .3 }, { x: .6, y: .8 }], 0.1);
    expect(bounds.minX).toBeCloseTo(0.1);
    expect(bounds.maxX).toBeCloseTo(0.7);
    expect(bounds.minY).toBeCloseTo(0.2);
    expect(bounds.maxY).toBeCloseTo(0.9);

    const pinned = boundsOf([{ x: 0, y: 0 }, { x: 1, y: 1 }], 0.5);
    expect(pinned).toEqual({ minX: 0, maxX: 1, minY: 0, maxY: 1 });
  });
});

describe('mapCamera cameraCenteredOn', () => {
  it('centres on a point and clamps the zoom', () => {
    expect(cameraCenteredOn({ x: .25, y: .75 })).toEqual({ x: .25, y: .75, zoom: RECENTER_ZOOM });
    expect(cameraCenteredOn({ x: 5, y: -5 }, 99)).toEqual({ x: 1, y: 0, zoom: MAX_ZOOM });
  });
});

describe('mapCamera fitToBounds', () => {
  it('centres on the box and frames it inside the canvas', () => {
    const bounds = { minX: .4, maxX: .6, minY: .4, maxY: .6 };
    const camera = fitToBounds(bounds, SIZE);

    expect(camera.x).toBeCloseTo(0.5);
    expect(camera.y).toBeCloseTo(0.5);

    // The contract is geometric, not a magic number: both opposite corners must
    // land inside the viewport, generously inset by the padding.
    const topLeft = worldToScreen({ x: bounds.minX * 100, y: 100 - bounds.minY * 100 }, SIZE, camera);
    const bottomRight = worldToScreen({ x: bounds.maxX * 100, y: 100 - bounds.maxY * 100 }, SIZE, camera);
    expect(topLeft.x).toBeGreaterThan(0);
    expect(topLeft.y).toBeGreaterThan(0);
    expect(bottomRight.x).toBeLessThan(SIZE);
    expect(bottomRight.y).toBeLessThan(SIZE);
    // And it does not shrink the region into a speck.
    expect(bottomRight.x - topLeft.x).toBeGreaterThan(SIZE * 0.5);
  });

  it('never frames a region closer than the detail threshold', () => {
    // A box far larger than the viewport would otherwise zoom far out.
    const camera = fitToBounds({ minX: 0, maxX: 0.95, minY: 0, maxY: 0.95 }, SIZE);
    expect(camera.zoom).toBeGreaterThanOrEqual(REGION_FOCUS_ZOOM);
    expect(camera.zoom).toBeLessThanOrEqual(MAX_ZOOM);
  });

  it('honours an explicit minZoom', () => {
    const camera = fitToBounds({ minX: .49, maxX: .51, minY: .49, maxY: .51 }, SIZE, { minZoom: 1.2 });
    expect(camera.zoom).toBeGreaterThanOrEqual(1.2);
  });

  it('never exceeds the zoom ceiling for a tiny box', () => {
    const camera = fitToBounds({ minX: .499, maxX: .501, minY: .499, maxY: .501 }, SIZE);
    expect(camera.zoom).toBeLessThanOrEqual(MAX_ZOOM);
  });

  it('tolerates a degenerate box with no extent', () => {
    const camera = fitToBounds({ minX: .5, maxX: .5, minY: .5, maxY: .5 }, SIZE);
    expect(camera.zoom).toBeLessThanOrEqual(MAX_ZOOM);
    expect(camera.zoom).toBeGreaterThanOrEqual(MIN_ZOOM);
  });
});
