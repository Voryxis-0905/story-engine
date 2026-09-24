import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { LocationMap } from './LocationMap';
import { KEY_PAN_PIXELS, MAX_ZOOM, MIN_ZOOM, RECENTER_ZOOM, worldToScreen } from './mapCamera';
import { regionCamera } from './mapView';
import { normalizedCoordinate } from './mapCoordinates';
import type { MapLocation } from './mapModel';
import { buildRegions, placeAtPoint } from './mapModel';
import { createFakeContext2D, stubElementRects } from '../test/fakeCanvas';

describe('LocationMap coordinates', () => {
  it('normalizes backend 0-100 coordinates for canvas drawing and hit testing', () => {
    expect(normalizedCoordinate(0)).toBe(0);
    expect(normalizedCoordinate(20)).toBe(0.2);
    expect(normalizedCoordinate(100)).toBe(1);
    expect(normalizedCoordinate(140)).toBe(1);
  });
});

const SIZE = 500;
const CENTER = SIZE / 2;

/**
 * Two places in two regions, deliberately far apart.
 *
 * A single-region fixture would make every click ambiguous: the region disc
 * covers its own places, so a click meant for a node can open the region
 * instead. Keeping the second region's node well outside the first region's
 * disc lets a test target a node unambiguously.
 */
const FOG_HARBOR: MapLocation = {
  id: 'loc_fog_harbor', name: 'Fog Harbor', description: 'Docks wrapped in cold mist.',
  x: 8, y: 8, zone: 'Outer Reach', is_unlocked: true, tags: ['harbor', 'dangerous'],
};
const CAMPUS = [
  { id: 'loc_hall', name: 'Old Hall', x: 88, y: 88, zone: 'North Campus', is_unlocked: true, tags: ['building'] } as MapLocation,
  { id: 'loc_library', name: 'Old Library', x: 74, y: 92, zone: 'North Campus', is_unlocked: true, tags: ['building'] } as MapLocation,
];
const LOCATIONS = [FOG_HARBOR, ...CAMPUS];

/**
 * Screen point of a place, computed with the app's own projection.
 *
 * Never hand-rolled: the map flips the y axis and applies zoom/pan, so a
 * replicated formula silently rots the moment the camera model changes.
 */
function screenOf(location: MapLocation, camera = { x: .5, y: .5, zoom: 1 }) {
  return worldToScreen(location, SIZE, camera);
}

function stubCanvas() {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(createFakeContext2D().ctx);
}

describe('LocationMap', () => {
  beforeEach(() => {
    stubCanvas();
    stubElementRects(SIZE);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const setup = (props: Record<string, unknown> = {}) => {
    const view = render(<LocationMap locations={LOCATIONS} {...props} />);
    const canvas = view.container.querySelector('canvas') as HTMLCanvasElement;
    return { canvas, ...view };
  };

  const press = (canvas: HTMLCanvasElement, key: string) => fireEvent.keyDown(canvas, { key });
  const clickAt = (canvas: HTMLCanvasElement, x: number, y: number) => {
    // Pointer Events, because that is what the map listens to now: the same
    // path serves mouse, touch and pen. `pointerType: 'mouse'` keeps the
    // hover-vs-drag slop identical to what a desktop player gets.
    fireEvent.pointerDown(canvas, { pointerId: 1, pointerType: 'mouse', button: 0, clientX: x, clientY: y });
    fireEvent.pointerUp(canvas, { pointerId: 1, pointerType: 'mouse', button: 0, clientX: x, clientY: y });
  };
  /**
   * Click the node for a place, at the point the app itself would draw it.
   *
   * The camera defaults to the idle overview, which is the only camera under
   * which these tests may click: hit testing rejects a place projected outside
   * the canvas, so a click aimed at a cropped-out node silently does nothing.
   */
  const clickPlace = (canvas: HTMLCanvasElement, location: MapLocation, camera?: { x: number; y: number; zoom: number }) => {
    const point = screenOf(location, camera);
    clickAt(canvas, point.x, point.y);
  };
  /** The zoom readout is the user-visible projection of the camera state. */
  const zoomLabel = () => screen.getByText(/% · (regions|region detail|places)/).textContent;
  const zoomValue = () => Number.parseInt(zoomLabel()!.split('%')[0], 10);
  const disclosure = () => zoomLabel()!.split('·')[1].trim();

  it('is focusable and describes its keyboard controls', () => {
    const { canvas, container } = setup();

    expect(canvas).toHaveAttribute('tabindex', '0');
    expect(canvas).toHaveAttribute('role', 'application');
    expect(screen.getByLabelText('Interactive world map')).toBe(canvas);

    canvas.focus();
    expect(canvas).toHaveFocus();

    // The description is looked up inside the rendered container: testing-library
    // does not guarantee the tree is attached to document.
    const id = canvas.getAttribute('aria-describedby')?.split(' ')[0] || '';
    const instructions = container.querySelector(`#${CSS.escape(id)}`);
    expect(instructions).not.toBeNull();
    expect(instructions?.textContent).toMatch(/arrow keys pan/i);
    expect(instructions?.textContent).toMatch(/Home recenters/i);
    expect(instructions?.textContent).toMatch(/Escape clears/i);
    // The map must say out loud that opening a region is not travel.
    expect(instructions?.textContent).toMatch(/never travels/i);
    expect(canvas).toHaveAttribute('aria-keyshortcuts', expect.stringContaining('Home'));
  });

  it('announces its structure in a live region', () => {
    const { container } = setup();

    const liveId = container.querySelector('canvas')!.getAttribute('aria-describedby')!.split(' ')[1];
    const live = container.querySelector(`#${CSS.escape(liveId)}`);
    expect(live).toHaveAttribute('aria-live', 'polite');
    expect(live?.textContent).toMatch(/Overview of 2 regions/);
  });

  it('zooms in with + and =, and out with - and _', () => {
    const { canvas } = setup();

    expect(zoomValue()).toBe(100);
    press(canvas, '+');
    expect(zoomValue()).toBe(116);
    press(canvas, '=');
    expect(zoomValue()).toBe(135);
    press(canvas, '-');
    expect(zoomValue()).toBe(116);
    press(canvas, '_');
    expect(zoomValue()).toBe(100);
  });

  it('clamps keyboard zoom at both ends of the range', () => {
    const { canvas } = setup();

    for (let i = 0; i < 12; i += 1) press(canvas, '-');
    expect(zoomValue()).toBe(Math.round(MIN_ZOOM * 100));

    for (let i = 0; i < 20; i += 1) press(canvas, '+');
    expect(zoomValue()).toBe(Math.round(MAX_ZOOM * 100));
  });

  it('announces the disclosure tier, not a raw zoom number', () => {
    const { canvas } = setup();

    // Idle: regions are the structure on show, whatever the camera distance,
    // because no region has been opened yet.
    expect(disclosure()).toBe('regions');

    // Opening a region discloses its interior.
    fireEvent.click(screen.getByRole('button', { name: 'Outer Reach' }));
    expect(disclosure()).toBe('places');

    // Returning to the overview collapses the tier again.
    fireEvent.click(screen.getByRole('button', { name: 'Overview' }));
    expect(disclosure()).toBe('regions');

    // Zooming out past the region tier also reports the overview.
    for (let i = 0; i < 20; i += 1) press(canvas, '-');
    expect(disclosure()).toBe('regions');
  });

  it('stays in the region tier when recentred without an open region', () => {
    // Recentring zooms in past the detail threshold, but no region is focused,
    // so the map must not claim to be showing local detail.
    const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
    expect(zoomValue()).toBe(Math.round(RECENTER_ZOOM * 100));
    expect(disclosure()).toBe('regions');
    void canvas;
  });

  it('frames a region wider than the viewport and still shows its places', () => {
    // Two members at opposite edges of the 0-100 map. No zoom can enclose both
    // while staying above the old 2.25 disclosure floor - the region is simply
    // wider than the viewport. Opening it must therefore zoom *out* to fit, and
    // disclosure must follow the opened region rather than the zoom number.
    const wide = [
      { id: 'w_west', name: 'West Span', x: 10, y: 50, zone: 'Great Basin', is_unlocked: true } as MapLocation,
      { id: 'w_east', name: 'East Span', x: 90, y: 50, zone: 'Great Basin', is_unlocked: true } as MapLocation,
      FOG_HARBOR,
    ];
    render(<LocationMap locations={wide} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open region Great Basin' }));

    // Fit, not floor: the camera had to pull back to enclose a 0.8-wide region.
    expect(zoomValue()).toBeLessThan(Math.round(RECENTER_ZOOM * 100));
    expect(zoomValue()).toBeGreaterThanOrEqual(Math.round(MIN_ZOOM * 100));
    // …and the interior is disclosed anyway, because that is what was asked for.
    expect(disclosure()).toBe('places');
    // Each member gets a real control, so the names are reachable by keyboard
    // and assistive tech - not painted on the canvas and nowhere else.
    expect(screen.getByRole('button', { name: /West Span, / })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /East Span, / })).toBeInTheDocument();

    // Both members must be genuinely inside the canvas, or "shown" is a lie.
    const camera = regionCamera(
      { places: [wide[0], wide[1]], radius: 0.4 },
      SIZE,
    );
    for (const place of [wide[0], wide[1]]) {
      const point = worldToScreen(place, SIZE, camera);
      expect(point.x).toBeGreaterThanOrEqual(0);
      expect(point.x).toBeLessThanOrEqual(SIZE);
      expect(point.y).toBeGreaterThanOrEqual(0);
      expect(point.y).toBeLessThanOrEqual(SIZE);
    }
  });

  it('pans with the arrow keys and consumes the key press', () => {
    const { canvas } = setup();

    // Arrow keys must not scroll the page behind the map.
    expect(fireEvent.keyDown(canvas, { key: 'ArrowRight' })).toBe(false);

    // The camera moved right, so the harbour is drawn one step to the left of
    // where the idle projection puts it - and is clicked there.
    //
    // Deliberately no click at the old position: that lands inside the region's
    // disc, which opens the region and changes the camera. Each click below is
    // measured against the same camera, so the two readings stay comparable.
    const start = screenOf(FOG_HARBOR);
    clickAt(canvas, start.x - KEY_PAN_PIXELS, start.y);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    // Stepping back the other way returns it to the projected spot.
    clickAt(canvas, start.x - KEY_PAN_PIXELS, start.y);
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();
    press(canvas, 'ArrowLeft');
    clickAt(canvas, start.x, start.y);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('stops panning at the world edge instead of drifting off the map', () => {
    const { canvas } = setup();

    // Walk the camera hard against the left edge of the world. Panning left
    // moves the camera left, so the content travels right until the camera
    // clamps at x = 0 - where the harbour parks at its own world offset from
    // the canvas's left edge, plus the half-canvas the camera sits over.
    for (let i = 0; i < 20; i += 1) press(canvas, 'ArrowLeft');

    const parkedX = screenOf(FOG_HARBOR, { x: 0, y: .5, zoom: 1 }).x;
    const parkedY = screenOf(FOG_HARBOR, { x: 0, y: .5, zoom: 1 }).y;
    clickAt(canvas, parkedX, parkedY);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    // Clamped: further input leaves the drawn position exactly where it was, so
    // the same point keeps hitting rather than sliding away.
    clickAt(canvas, parkedX, parkedY);
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();
    press(canvas, 'ArrowLeft');
    clickAt(canvas, parkedX, parkedY);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('keeps the place under the pointer fixed while wheel zooming', () => {
    const { canvas } = setup();

    // Aim at the harbour, well away from the canvas centre, so an unanchored
    // zoom would drag it out from under the cursor.
    const aim = screenOf(FOG_HARBOR);
    fireEvent.wheel(canvas, { deltaY: -240, clientX: aim.x, clientY: aim.y });
    expect(zoomValue()).toBeGreaterThan(100);

    // The harbour is still hit-testable at the very point it was aimed at.
    clickAt(canvas, aim.x, aim.y);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('recenters on the protagonist with Home', () => {
    const { canvas } = setup({ currentLocation: FOG_HARBOR.name });

    press(canvas, 'ArrowRight');
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

    press(canvas, 'Home');
    expect(zoomValue()).toBe(Math.round(RECENTER_ZOOM * 100));
    clickAt(canvas, CENTER, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('falls back to the whole-world view when Home is pressed with no protagonist', () => {
    const { canvas } = setup();

    press(canvas, '+');
    expect(zoomValue()).toBe(116);
    press(canvas, 'Home');
    expect(zoomValue()).toBe(100);
  });

  it('clears the selected location with Escape', () => {
    const { canvas } = setup();

    clickPlace(canvas, FOG_HARBOR);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    press(canvas, 'Escape');
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();
  });

  it('steps out of a region on Escape before clearing the selection', () => {
    const { canvas } = setup();

    fireEvent.click(screen.getByRole('button', { name: 'Open region Outer Reach' }));
    expect(disclosure()).toBe('places');
    expect(screen.getByRole('button', { name: 'All regions' })).toBeInTheDocument();

    press(canvas, 'Escape');
    // The first Escape only leaves the region; the overview comes back.
    expect(screen.queryByRole('button', { name: 'All regions' })).not.toBeInTheDocument();
    expect(disclosure()).toBe('regions');
  });

  it('keeps pointer drag, selection and journey preview working', () => {
    const onPreview = vi.fn();
    // Deliberately no protagonist: the idle overview camera keeps both nodes on
    // canvas, and a node that is not painted must not be clickable, so a drag
    // can only be proven against a node the map actually draws.
    const { canvas } = setup({ onPreview });
    const camera = { x: .5, y: .5, zoom: 1 };

    // A drag must pan rather than select the place it started on.
    const start = screenOf(FOG_HARBOR, camera);
    const travel = KEY_PAN_PIXELS * 3;
    fireEvent.pointerDown(canvas, { pointerId: 1, pointerType: 'mouse', button: 0, clientX: start.x, clientY: start.y });
    fireEvent.pointerMove(canvas, { pointerId: 1, pointerType: 'mouse', clientX: start.x + travel, clientY: start.y });
    fireEvent.pointerUp(canvas, { pointerId: 1, pointerType: 'mouse', button: 0, clientX: start.x + travel, clientY: start.y });
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

    // Dragging right moves the map right with the pointer, so the harbour is now
    // drawn a full drag distance to the right of where it started.
    clickAt(canvas, start.x + travel, start.y);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Preview journey' }));
    expect(onPreview).toHaveBeenCalledWith(expect.objectContaining({ id: FOG_HARBOR.id }));
  });

  it('does not travel when a region is opened - it only moves the camera', () => {
    const onTravel = vi.fn();
    render(<LocationMap locations={LOCATIONS} onTravel={onTravel} />);

    fireEvent.click(screen.getByRole('button', { name: 'Open region North Campus' }));

    expect(onTravel).not.toHaveBeenCalled();
    // Opening a region tightens the disclosure to its interior.
    expect(disclosure()).toBe('places');
  });

  it('exposes every region as a real control, not only as canvas pixels', () => {
    render(<LocationMap locations={LOCATIONS} />);

    expect(screen.getByRole('group', { name: 'Regions on this map' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'North Campus' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Outer Reach' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('pans instead of opening when a drag starts on a region disc', () => {
    // The discs are transparent DOM buttons over the canvas. Before the handlers
    // were shared, a finger landing on one began its gesture on the *button*, so
    // the canvas never saw a pointerdown and the map did not move. This pins the
    // behaviour for the disc origin specifically - a drag there must pan, and
    // must not open the region it started on.
    const { canvas } = setup({});
    expect(disclosure()).toBe('regions');

    const disc = screen.getByRole('button', { name: 'Open region North Campus' });
    const box = { x: 100, y: 100 };
    fireEvent.pointerDown(disc, { pointerId: 7, pointerType: 'touch', button: 0, clientX: box.x, clientY: box.y });
    fireEvent.pointerMove(disc, { pointerId: 7, pointerType: 'touch', clientX: box.x + 60, clientY: box.y });
    fireEvent.pointerUp(disc, { pointerId: 7, pointerType: 'touch', button: 0, clientX: box.x + 60, clientY: box.y });

    // The camera moved...
    expect(zoomValue()).toBe(100);
    // ...and the region stayed closed: a pan is not a tap.
    expect(disclosure()).toBe('regions');

    // A click arriving *after* the drag is a fresh input, not the drag's own
    // trailing click, so it opens the region. Suppressing it would require
    // remembering the drag after the gesture ended - and a touch drag sends no
    // trailing click at all, so that memory would be waiting there to eat the
    // player's next Enter/Space instead. The drag itself must simply not
    // activate anything, which is what the assertion above pins.
    fireEvent.click(disc);
    expect(disclosure()).toBe('places');

    // Opening is idempotent, so the point is that the region is open and
    // reachable again - not that the click was counted twice.
    fireEvent.click(disc);
    expect(disclosure()).toBe('places');
    expect(screen.getByRole('button', { name: 'All regions' })).toBeInTheDocument();

    // And the player can still leave, which is the real one-way-door check.
    fireEvent.click(screen.getByRole('button', { name: 'All regions' }));
    expect(disclosure()).toBe('regions');
    void canvas;
  });

  it('selects a place on a tap and pans on a drag starting on the place control', () => {
    // Only the protagonist's own place is exposed as a DOM control, so the
    // fixture puts them at Fog Harbor - that is the node a finger can land on.
    const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
    const control = screen.getByRole('button', { name: /Fog Harbor, / });

    // A drag starting on the place control pans and does not select.
    fireEvent.pointerDown(control, { pointerId: 9, pointerType: 'touch', button: 0, clientX: 40, clientY: 40 });
    fireEvent.pointerMove(control, { pointerId: 9, pointerType: 'touch', clientX: 40, clientY: 90 });
    fireEvent.pointerUp(control, { pointerId: 9, pointerType: 'touch', button: 0, clientX: 40, clientY: 90 });
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

    // A plain click - the keyboard and assistive-tech path - still selects.
    fireEvent.click(control);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
    void canvas;
  });

  /**
   * The activation guard must not outlive the gesture that armed it.
   *
   * The failure mode, measured on the old code: the guard was one global
   * boolean, set by *any* `pointerdown` including the canvas's, and only ever
   * cleared by a `click` on an overlay control. A drag on the bare canvas
   * synthesises no compatibility `click`, so nothing cleared it - and the next
   * Enter/Space on a region disc or place node was swallowed as if it were the
   * drag's trailing click. `fireEvent.click` on a focused button is exactly
   * what the browser dispatches for Enter/Space, so that is what these drive.
   */
  describe('activation after a pointer gesture', () => {
    /** A drag on the bare canvas: down, move past the touch slop, up. */
    const dragCanvas = (canvas: HTMLCanvasElement) => {
      fireEvent.pointerDown(canvas, { pointerId: 21, pointerType: 'touch', button: 0, clientX: 250, clientY: 250 });
      fireEvent.pointerMove(canvas, { pointerId: 21, pointerType: 'touch', clientX: 250, clientY: 160 });
      fireEvent.pointerUp(canvas, { pointerId: 21, pointerType: 'touch', button: 0, clientX: 250, clientY: 160 });
    };

    it('opens a region on the first keyboard activation after a canvas drag', () => {
      const { canvas } = setup();
      expect(disclosure()).toBe('regions');

      dragCanvas(canvas);
      // The drag panned and must not have opened anything on the way.
      expect(disclosure()).toBe('regions');

      // Tab to the disc and press Enter. This is the click that used to be
      // eaten by the stale canvas flag - only a second press worked.
      fireEvent.click(screen.getByRole('button', { name: 'Open region Outer Reach' }));
      expect(disclosure()).toBe('places');
    });

    it('selects a place on the first keyboard activation after a canvas drag', () => {
      const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
      dragCanvas(canvas);
      expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /Fog Harbor, / }));
      expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
    });

    it('activates on the first keyboard press after a drag that started on the control itself', () => {
      // The harder half: here the gesture really did start on the control, so
      // the guard was legitimately armed. It must still be spent by that
      // gesture, not left behind for the player's next keypress.
      const { canvas } = setup();
      const disc = screen.getByRole('button', { name: 'Open region Outer Reach' });

      fireEvent.pointerDown(disc, { pointerId: 31, pointerType: 'touch', button: 0, clientX: 100, clientY: 100 });
      fireEvent.pointerMove(disc, { pointerId: 31, pointerType: 'touch', clientX: 160, clientY: 100 });
      fireEvent.pointerUp(disc, { pointerId: 31, pointerType: 'touch', button: 0, clientX: 160, clientY: 100 });
      // No trailing click: a touch drag does not produce one. The guard must
      // therefore not be waiting for it.
      expect(disclosure()).toBe('regions');

      fireEvent.click(disc);
      expect(disclosure()).toBe('places');
      void canvas;
    });

    it('activates once for a tap, not twice', () => {
      // A tap sends `pointerup` and then a compatibility `click`. Both would
      // select, and selection is a toggle - so a single tap would select and
      // immediately deselect, leaving the detail panel flickering shut.
      //
      // `detail: 1` is not decoration: it is what separates this compatibility
      // click from a keyboard activation. A pointer click carries a click count
      // of 1 or more; Enter/Space on a button dispatches `click` with
      // `detail: 0`. Firing it with the default 0 would model a keypress, and
      // the guard is right not to swallow a keypress.
      const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
      const control = screen.getByRole('button', { name: /Fog Harbor, / });

      fireEvent.pointerDown(control, { pointerId: 41, pointerType: 'touch', button: 0, clientX: 60, clientY: 60 });
      fireEvent.pointerUp(control, { pointerId: 41, pointerType: 'touch', button: 0, clientX: 60, clientY: 60 });
      fireEvent.click(control, { detail: 1 });

      // Selected exactly once: a second activation would have toggled it off.
      expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
      void canvas;
    });

    it('pans on a mouse drag from a region disc without opening the region', () => {
      // The mouse path, and the reason `detail` is needed at all: Chromium
      // dispatches the trailing `click` after a mouse drag even though pointer
      // capture was taken, so the drag cannot simply disarm the guard the way a
      // touch drag does.
      const { canvas } = setup();
      const disc = screen.getByRole('button', { name: 'Open region Outer Reach' });
      expect(disclosure()).toBe('regions');

      fireEvent.pointerDown(disc, { pointerId: 51, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 });
      fireEvent.pointerMove(disc, { pointerId: 51, pointerType: 'mouse', clientX: 160, clientY: 100 });
      fireEvent.pointerUp(disc, { pointerId: 51, pointerType: 'mouse', button: 0, clientX: 160, clientY: 100 });
      // Chromium's trailing click, click count 1.
      fireEvent.click(disc, { detail: 1 });

      expect(disclosure(), 'a mouse drag opened the region it panned from').toBe('regions');
      void canvas;
    });

    it('pans on a mouse drag from a place control without selecting the place', () => {
      const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
      const control = screen.getByRole('button', { name: /Fog Harbor, / });
      expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

      fireEvent.pointerDown(control, { pointerId: 52, pointerType: 'mouse', button: 0, clientX: 60, clientY: 60 });
      fireEvent.pointerMove(control, { pointerId: 52, pointerType: 'mouse', clientX: 60, clientY: 120 });
      fireEvent.pointerUp(control, { pointerId: 52, pointerType: 'mouse', button: 0, clientX: 60, clientY: 120 });
      fireEvent.click(control, { detail: 1 });

      expect(screen.queryByText('Fog Harbor'), 'a mouse drag selected the place it panned from').not.toBeInTheDocument();
      void canvas;
    });

    it('still answers the next keyboard press after a mouse drag and its trailing click', () => {
      // The trailing click spends the guard, so the keyboard is not left
      // waiting behind a flag that a later press has to clear.
      const { canvas } = setup();
      const disc = screen.getByRole('button', { name: 'Open region Outer Reach' });

      fireEvent.pointerDown(disc, { pointerId: 53, pointerType: 'mouse', button: 0, clientX: 100, clientY: 100 });
      fireEvent.pointerMove(disc, { pointerId: 53, pointerType: 'mouse', clientX: 160, clientY: 100 });
      fireEvent.pointerUp(disc, { pointerId: 53, pointerType: 'mouse', button: 0, clientX: 160, clientY: 100 });
      fireEvent.click(disc, { detail: 1 });
      expect(disclosure()).toBe('regions');

      fireEvent.click(disc);
      expect(disclosure()).toBe('places');
      void canvas;
    });

    it('pans on a drag without selecting, and leaves no guard behind for the next keypress', () => {
      const { canvas } = setup({ currentLocation: FOG_HARBOR.id });
      const control = screen.getByRole('button', { name: /Fog Harbor, / });

      // Nothing selected to start with, so a pan that wrongly selected would be
      // visible rather than masked by the already-open panel.
      expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

      fireEvent.pointerDown(control, { pointerId: 42, pointerType: 'touch', button: 0, clientX: 60, clientY: 60 });
      fireEvent.pointerMove(control, { pointerId: 42, pointerType: 'touch', clientX: 60, clientY: 120 });
      fireEvent.pointerUp(control, { pointerId: 42, pointerType: 'touch', button: 0, clientX: 60, clientY: 120 });

      // The drag panned and did not select.
      expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

      // And the very next keyboard activation works - the drag left nothing
      // armed. Note there is no trailing `click` here, because a touch drag
      // does not produce one, which is exactly the case that used to strand the
      // guard.
      fireEvent.click(control);
      expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
      void canvas;
    });
  });

  it('focuses a region from its chip and returns with Overview', () => {
    render(<LocationMap locations={LOCATIONS} />);

    fireEvent.click(screen.getByRole('button', { name: 'North Campus' }));
    expect(screen.getByRole('button', { name: 'North Campus' })).toHaveAttribute('aria-pressed', 'true');
    expect(disclosure()).toBe('places');

    fireEvent.click(screen.getByRole('button', { name: 'Overview' }));
    expect(screen.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-pressed', 'true');
    expect(disclosure()).toBe('regions');
  });

  it('never leaks an undiscovered place through the region aggregate', () => {
    const locations: MapLocation[] = [
      ...CAMPUS,
      { id: 'secret', name: 'Unknown location', x: 90, y: 80, zone: 'North Campus', discovery_status: 'unknown' },
      { id: 'gm', name: 'Hidden Chapel', x: 84, y: 84, zone: 'North Campus', discovery_status: 'creator_only' },
    ];
    const { container } = render(<LocationMap locations={locations} />);

    expect(screen.queryByText('Unknown location')).not.toBeInTheDocument();
    expect(screen.queryByText('Hidden Chapel')).not.toBeInTheDocument();

    // Nor may they inflate the advertised size of the region.
    fireEvent.click(screen.getByRole('button', { name: 'Open region North Campus' }));
    expect(container.textContent).not.toMatch(/4 places/);
    expect(container.textContent).not.toMatch(/Hidden Chapel/);
  });

  it('hides the region a place belongs to when that place is secret', () => {
    const locations: MapLocation[] = [
      { id: 'vault', name: 'Unknown location', x: 30, y: 30, zone: 'Sealed Wing', discovery_status: 'unknown' },
      ...CAMPUS,
    ];
    render(<LocationMap locations={locations} />);

    // A region existing only because of a secret place must not be named.
    expect(screen.queryByRole('button', { name: 'Sealed Wing' })).not.toBeInTheDocument();
  });

  it('keeps the travel button behind the engine preview verdict', () => {
    const onTravel = vi.fn();
    // No protagonist, so the idle overview camera is in force and the harbour is
    // genuinely on canvas - a cropped-out node is not clickable, so a test that
    // selected one would be asserting on a hit target the map never draws.
    const { canvas, rerender } = setup({ onTravel });

    clickPlace(canvas, FOG_HARBOR);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Travel here' })).not.toBeInTheDocument();

    // A preview the engine refuses must not unlock the button - and must not be
    // drawn as a route either, or the player reads a journey that cannot happen.
    rerender(<LocationMap locations={LOCATIONS} onTravel={onTravel} travelPreview={{
      status: 'unavailable', destination: FOG_HARBOR.name, route: [FOG_HARBOR.name],
      legs: [], elapsed_minutes: 0, estimated_ticks: 0, risk: { level: 'high' },
    }} />);
    expect(screen.queryByRole('button', { name: 'Travel here' })).not.toBeInTheDocument();
    expect(screen.queryByText(/Risk: high/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Estimated time/)).not.toBeInTheDocument();

    // Only an available verdict from the engine produces a travel button.
    rerender(<LocationMap locations={LOCATIONS} onTravel={onTravel} travelPreview={{
      status: 'available', destination: FOG_HARBOR.name, route: [FOG_HARBOR.name],
      legs: [], elapsed_minutes: 12, estimated_ticks: 3, risk: { level: 'low' },
    }} />);
    expect(screen.getByText(/Risk: low/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Travel here' }));
    expect(onTravel).toHaveBeenCalledWith(expect.objectContaining({ id: FOG_HARBOR.id }));
  });

  /**
   * A redacted route is the one case where an empty `route` array does NOT mean
   * "no stops". The engine withheld the shape because the journey crosses
   * unexplored ground; the trip is still real and still offered.
   *
   * The failure this guards is subtle and was measured: joining an empty route
   * array renders as nothing, and drawing it would produce a straight segment
   * between the two endpoints - a direct road the engine never promised. So the
   * note must be shown, the button must stay, and nothing may be drawn.
   */
  it('says a redacted route crosses unexplored ground, and draws no road', () => {
    const onTravel = vi.fn();
    const { canvas, rerender } = setup({ onTravel });
    clickPlace(canvas, FOG_HARBOR);

    rerender(<LocationMap locations={LOCATIONS} onTravel={onTravel} travelPreview={{
      status: 'available', destination: FOG_HARBOR.name,
      // Empty on purpose: the engine withheld the shape.
      route: [], legs: [], elapsed_minutes: 45, estimated_ticks: 5,
      risk: { level: 'medium', known_tags: [] },
      route_redacted: true, route_note: 'Route passes through unexplored territory',
    }} />);

    // What the player is told.
    expect(screen.getByText('Route passes through unexplored territory')).toBeInTheDocument();
    // The journey is still offered - redaction hides the road, not the trip.
    expect(screen.getByRole('button', { name: 'Travel here' })).toBeInTheDocument();
    expect(screen.getByText(/Estimated time: 45/)).toBeInTheDocument();
    expect(screen.getByText(/Risk: medium/)).toBeInTheDocument();

    // A bare "Route:" with nothing after it would read as a direct path, and an
    // empty join must never be printed as if it were a route.
    expect(screen.queryByText(/^Route:/)).not.toBeInTheDocument();
    // The map must not repaint a shortcut it invented.
    expect(screen.queryByText(/Part of this route is off the map/)).not.toBeInTheDocument();
    expect(screen.getByText(/no road is drawn for it/)).toBeInTheDocument();
  });

  it('still prints the full route when nothing is hidden', () => {
    // The counterpart to the test above: redaction must not swallow well-known
    // routes, or the fix would be "stop describing journeys at all".
    const { canvas, rerender } = setup({ onTravel: vi.fn() });
    clickPlace(canvas, FOG_HARBOR);

    rerender(<LocationMap locations={LOCATIONS} onTravel={vi.fn()} travelPreview={{
      status: 'available', destination: FOG_HARBOR.name,
      route: [CAMPUS[0].name, FOG_HARBOR.name],
      legs: [{ from: CAMPUS[0].name, to: FOG_HARBOR.name, travel_time_minutes: 20, danger: 0, tags: [] }],
      elapsed_minutes: 20, estimated_ticks: 2, risk: { level: 'low', known_tags: [] },
    }} />);

    expect(screen.getByText(new RegExp(`Route: ${CAMPUS[0].name} → ${FOG_HARBOR.name}`))).toBeInTheDocument();
    expect(screen.queryByText(/unexplored territory/)).not.toBeInTheDocument();
  });

  it('drops a stale preview once the destination changes', () => {
    // The session holds the last preview it received. Selecting another place
    // must not keep drawing the old route - a route line pointing at somewhere
    // the player is no longer looking is worse than no line at all.
    const { canvas, rerender } = setup({ onTravel: vi.fn() });
    clickPlace(canvas, FOG_HARBOR);

    rerender(<LocationMap locations={LOCATIONS} onTravel={vi.fn()} travelPreview={{
      status: 'available', destination: FOG_HARBOR.name, route: [FOG_HARBOR.name, 'Old Hall'],
      legs: [{ from: FOG_HARBOR.name, to: 'Old Hall', travel_time_minutes: 20, danger: 0, tags: [] }],
      elapsed_minutes: 20, estimated_ticks: 1, risk: { level: 'low' },
    }} />);
    expect(screen.getByText(/Estimated time: 20/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Travel here' })).toBeInTheDocument();

    // Same preview object, different selection: the route must go away.
    clickPlace(canvas, CAMPUS[0]);
    expect(screen.queryByText(/Estimated time/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Travel here' })).not.toBeInTheDocument();
  });

  it('reports a locked place and why it is locked', () => {
    const locked: MapLocation = {
      ...FOG_HARBOR, id: 'loc_vault', name: 'Sealed Vault', x: 20, y: 12,
      is_unlocked: false, unlock_reason_missing: 'Needs the harbor key.',
    };
    const { container } = render(<LocationMap locations={[locked, ...CAMPUS]} />);

    clickPlace(container.querySelector('canvas') as HTMLCanvasElement, locked);
    expect(screen.getByText('Sealed Vault')).toBeInTheDocument();
    expect(screen.getByText(/Needs the harbor key\./)).toBeInTheDocument();
  });

  it('names supported relief without inventing height for legacy places', () => {
    const shore = { ...FOG_HARBOR, terrain: 'coast', elevation: -1, layer: 'surface' };
    const { canvas } = setup({ locations: [shore, ...CAMPUS] });
    clickPlace(canvas, shore);
    expect(screen.getByText('Terrain: coast · lower ground')).toBeInTheDocument();
    clickPlace(canvas, CAMPUS[0]);
    expect(screen.queryByText(/Terrain:/)).not.toBeInTheDocument();
  });

  it('renders without a canvas context at all', () => {
    vi.restoreAllMocks();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    stubElementRects(SIZE);

    expect(() => render(<LocationMap locations={LOCATIONS} />)).not.toThrow();
    expect(screen.getByLabelText('Interactive world map')).toBeInTheDocument();
  });
});

/**
 * Guards the fixture the interaction tests rely on: the harbour must sit
 * outside every region disc *other than its own*, so a click aimed at it can
 * never be consumed by a different region.
 */
describe('LocationMap test fixture', () => {
  it('keeps the harbour clear of every foreign region disc', () => {
    const regions = buildRegions(LOCATIONS, undefined);
    expect(regions).toHaveLength(2);

    const harbour = screenOf(FOG_HARBOR);
    const own = regions.find((region) => region.places.some((place) => place.id === FOG_HARBOR.id));
    expect(own).toBeDefined();

    const clearance = regions
      .filter((region) => region.key !== own!.key)
      .map((region) => {
        const centre = screenOf({ ...FOG_HARBOR, x: region.center.x * 100, y: (1 - region.center.y) * 100 });
        return Math.hypot(centre.x - harbour.x, centre.y - harbour.y) - region.radius * SIZE;
      });
    expect(Math.min(...clearance)).toBeGreaterThan(0);

    // And the harbour really is hit-testable at its own projected position,
    // which is the assumption every clickPlace() call in this file makes.
    expect(placeAtPoint(LOCATIONS, harbour, screenOf)?.id).toBe(FOG_HARBOR.id);
  });
});
