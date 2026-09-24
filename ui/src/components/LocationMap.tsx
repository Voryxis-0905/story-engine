import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react';

import {
  KEY_PAN_PIXELS, MAX_ZOOM, MIN_ZOOM,
  panCamera, screenToWorld, worldDistanceToScreen,
  worldToScreen, type Camera,
} from './mapCamera';
import { overviewCamera, regionCamera, worldOverviewCamera, zoomedCamera } from './mapView';
import {
  NODE_HIT_RADIUS, buildRegions, buildRouteModel, findRegion, labelMetrics, layoutLabels,
  layoutRegionLabels, placeAtPoint, placeStatus, regionAtPoint, regionContaining, regionNameOf,
  selectVisiblePlaces,
  type AtlasRegion, type LabelPlacement, type MapLocation,
} from './mapModel';
import { drawScene } from './mapRender';
import { placeRelief, regionRelief, reliefLabel } from './mapTerrain';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import type { TravelPreview } from '../api/client';

interface LocationMapProps {
  locations: MapLocation[];
  onTravel?: (location: MapLocation) => void;
  onPreview?: (location: MapLocation) => void;
  travelPreview?: TravelPreview | null;
  previewLoading?: boolean;
  currentLocation?: string;
}

/** Arrow keys pan the viewport in the direction the key points at. */
const PAN_KEYS: Record<string, [number, number]> = {
  ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
};

const ZOOM_IN_FACTOR = 1.16;
const ZOOM_OUT_FACTOR = .86;
/** A wheel notch scrolls ~100px; this turns that into a comfortable step. */
const WHEEL_ZOOM_STEP = 0.0015;

/** The map never draws larger than this, so the drawer stays readable at 500px and below. */
const MAX_CANVAS_SIZE = 520;

function locationMatches(location: MapLocation, reference?: string) {
  return Boolean(reference && (location.id === reference || location.name === reference));
}

const STATUS_TEXT: Record<string, string> = {
  current: 'You are here',
  discovered: 'Discovered',
  locked: 'Locked',
  unreachable: 'No route',
  undiscovered: 'Undiscovered',
};

export function LocationMap({ locations, onTravel, onPreview, travelPreview, previewLoading, currentLocation }: LocationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ x: number; y: number; moved: boolean; pointerId: number } | null>(null);
  const instructionsId = useId();
  const statusId = useId();
  const regionListId = useId();

  const reducedMotion = usePrefersReducedMotion();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusedRegionKey, setFocusedRegionKey] = useState<string | null>(null);
  const [camera, setCamera] = useState<Camera>({ x: .5, y: .5, zoom: 1 });
  const [size, setSize] = useState(MAX_CANVAS_SIZE);
  const [hoveredRegionKey, setHoveredRegionKey] = useState<string | null>(null);
  const [cursorWorld, setCursorWorld] = useState<{ x: number; y: number } | null>(null);

  /** Derived region model; recomputed only when the geography or the player moves. */
  const regions = useMemo(() => buildRegions(locations, currentLocation), [locations, currentLocation]);

  const currentPlace = useMemo(
    () => locations.find((location) => locationMatches(location, currentLocation)) || null,
    [locations, currentLocation],
  );

  /**
   * Ordinal motion cadence. The map gets its "alive" quality from things that
   * move on their own schedule (the protagonist's halo breathing, an incoming
   * preview) rather than from graph arrows. `frame` is that clock; it is not
   * started at all when the player asked for reduced motion.
   */
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (reducedMotion) return;
    const id = window.setInterval(() => setFrame((value) => value + 1), 2000);
    return () => window.clearInterval(id);
  }, [reducedMotion]);

  /**
   * Previewed route. Only the engine's ordered sequence is projected, and it is
   * dropped the moment the preview clears, fails, or changes destination.
   *
   * The destination check is the part that is easy to get wrong: a preview is
   * stored in the session, so after the player selects somewhere else the old
   * response is still in hand. Drawing it then would paint a route to a place
   * the player is no longer looking at - and a `blocked` or `unreachable`
   * preview must never be drawn as if it were a journey at all. So the route is
   * only "active" when the engine said available AND the destination is still
   * the selected place. Everything downstream reads this one value.
   */
  const selectedLoc = selectedId ? locations.find((location) => location.id === selectedId) || null : null;
  const activeRoute = travelPreview
    && travelPreview.status === 'available'
    && selectedLoc
    && travelPreview.destination === selectedLoc.name
    ? travelPreview
    : null;

  const routeModel = useMemo(() => {
    if (!activeRoute) return null;
    // A redacted route is deliberately empty. Drawing it would fall through to
    // `buildRouteModel`'s "drawable: false" and paint nothing - which is right -
    // but it must not then be reported as "off the map", so the redaction is
    // checked here and the route is simply not drawn at all.
    if (activeRoute.route_redacted) return null;
    const model = buildRouteModel(activeRoute.route, locations);
    return model.drawable ? model : null;
  }, [activeRoute, locations]);

  const routeRefs = useMemo(() => {
    const refs = new Set<string>();
    (activeRoute?.route || []).forEach((stop) => refs.add(stop));
    return refs;
  }, [activeRoute]);

  const selection = useMemo(() => selectVisiblePlaces(locations, regions, {
    zoom: camera.zoom, focusedRegionKey, currentRef: currentLocation, selectedId, routeRefs,
    // Opening a region is an explicit request to see inside it, so disclosure
    // follows that rather than the zoom number. Matters for a region wider than
    // the viewport, which the camera can only enclose by zooming out.
    regionOpen: focusedRegionKey !== null,
  }), [locations, regions, camera.zoom, focusedRegionKey, currentLocation, selectedId, routeRefs]);

  const focusedRegion = findRegion(regions, focusedRegionKey);

  /**
   * Canvas projection for every interactive element the DOM mirrors.
   *
   * Region discs are hit-tested as discs; a place node uses its drawn radius
   * plus a generous pad, because a 5px dot is not a thumb target. Both the
   * visual layer and the DOM overlay read from these two functions, so a target
   * can never drift from the shape a player sees.
   */
  const projectRegion = useCallback((region: AtlasRegion) => {
    const point = worldToScreen({ x: region.center.x * 100, y: (1 - region.center.y) * 100 }, size, camera);
    return { x: point.x, y: point.y, radius: worldDistanceToScreen(region.radius, size, camera) };
  }, [size, camera]);

  const projectPlace = useCallback(
    (location: MapLocation) => worldToScreen(location, size, camera),
    [size, camera],
  );

  /**
   * Draw one frame.
   *
   * Label placement needs real text metrics, so it runs here on the committed
   * canvas rather than during render: `measureText` is only meaningful with a
   * context, and the layout must match the frame it is drawn into.
   */
  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const scale = window.devicePixelRatio || 1;
    canvas.width = Math.round(size * scale);
    canvas.height = Math.round(size * scale);
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.font = labelMetrics.font;
    const measure = (text: string) => ctx.measureText(text).width;

    // Region names sit inside their disc while the region is open, and just
    // below it in the legible overview, so the name never covers its own places.
    const regionInputs = regions.map((region) => {
      const disc = projectRegion(region);
      const focused = region.key === focusedRegionKey;
      const offset = focused ? Math.max(12, disc.radius * 0.42) : Math.max(14, disc.radius * 0.55);
      return {
        key: region.key, name: region.name, x: disc.x, y: disc.y + offset,
        radius: disc.radius, focus: focused,
        onScreen: disc.x > -80 && disc.x < size + 80 && disc.y > -80 && disc.y < size + 80,
      };
    });

    const regionLabels: Array<{ key: string; name: string; x: number; y: number; radius: number; focus: boolean }> = [];
    if (!selection.local) {
      const placements = layoutRegionLabels(
        regionInputs.filter((item) => item.onScreen).map(({ onScreen, ...rest }) => { void onScreen; return rest; }),
        size,
        measure,
      );
      placements.forEach((placement) => {
        regionLabels.push({ key: placement.key, name: placement.name, x: placement.x, y: placement.box.top, radius: placement.radius, focus: placement.focus });
      });
    }

    const positions = selection.places.map((place) => ({ id: place.id, ...projectPlace(place) }));
    const placedLabels = layoutLabels(selection.places, positions, {
      size,
      regionOf: (location) => regionContaining(regions, location),
      force: (location) => locationMatches(location, currentLocation) || location.id === selectedId || location.id === hoveredId,
      measure,
    });
    // Off-screen labels are computed (so ordering is stable) but not drawn.
    const placeLabels: LabelPlacement[] = placedLabels.filter((label) =>
      label.box.right > -24 && label.box.left < size + 24 && label.box.bottom > -24 && label.box.top < size + 24);

    drawScene(ctx, {
      size, camera, locations, regions,
      focusedRegionKey,
      currentRef: currentLocation,
      hoveredId, selectedId,
      route: routeModel,
      drawnPlaces: selection.places,
      regionLabels,
      placeLabels,
      local: selection.local,
      t: reducedMotion ? 0 : frame,
    });
  }, [size, camera, locations, regions, focusedRegionKey, currentLocation, hoveredId, selectedId,
    routeModel, selection, projectRegion, projectPlace, reducedMotion, frame]);

  /** Keep the canvas backing store in step with the container and the DPR. */
  useLayoutEffect(() => {
    const host = rootRef.current;
    if (!host) return;
    const apply = () => {
      const measured = host.getBoundingClientRect().width;
      if (measured > 0) setSize(Math.min(measured, MAX_CANVAS_SIZE));
    };
    apply();
    if (typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(apply);
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  /** Camera moves: recentering, region focus and returning to the overview. */
  const recenter = useCallback(() => {
    setFocusedRegionKey(null);
    setCamera(overviewCamera(currentPlace));
  }, [currentPlace]);

  /**
   * Landing on a world recenters once, exactly like the previous map did, so the
   * first thing a player sees is the place their character is standing in.
   */
  const didInitialRecenter = useRef<string | null>(null);
  useEffect(() => {
    if (didInitialRecenter.current === (currentLocation ?? null)) return;
    didInitialRecenter.current = currentLocation ?? null;
    setFocusedRegionKey(null);
    setSelectedId(null);
    setCamera(overviewCamera(currentPlace));
  }, [currentLocation, currentPlace]);

  /** Open a region: frame it and disclose its interior. Never travels. */
  const openRegion = useCallback((region: AtlasRegion) => {
    if (!region.interactive) return;
    setFocusedRegionKey(region.key);
    setSelectedId(null);
    setCamera(regionCamera(region, size));
  }, [size]);

  /** Return to the overview that shows every region at once. */
  const showOverview = useCallback(() => {
    setFocusedRegionKey(null);
    setSelectedId(null);
    setCamera(worldOverviewCamera());
  }, []);

  const zoomBy = useCallback((factor: number) => {
    setCamera((value) => zoomedCamera(value, factor, size, { x: size / 2, y: size / 2 }));
  }, [size]);

  const zoomAtPointer = useCallback((factor: number, screen: { x: number; y: number }) => {
    setCamera((value) => zoomedCamera(value, factor, size, screen));
  }, [size]);

  const selectPlace = useCallback((location: MapLocation) => {
    setSelectedId((id) => (id === location.id ? null : location.id));
    // Selecting a place while already inside a region follows it into the
    // correct region. Gated on "a region is open" rather than on zoom, so it
    // still works for a wide region that had to be framed zoomed out.
    const region = regionContaining(regions, location);
    if (region && focusedRegionKey !== null && region.key !== focusedRegionKey) {
      setFocusedRegionKey(region.key);
    }
  }, [regions, focusedRegionKey]);

  const selectedStatus = selectedLoc ? placeStatus(selectedLoc, currentLocation) : null;

  /** Pointer position in canvas pixels. `scale` converts the CSS box to the canvas grid. */
  const pointerAt = (event: { clientX: number; clientY: number }) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return { x: size / 2, y: size / 2, scale: 1 };
    return {
      x: ((event.clientX - rect.left) / rect.width) * size,
      y: ((event.clientY - rect.top) / rect.height) * size,
      scale: size / rect.width,
    };
  };

  /**
   * Nearest *painted* place to a canvas point, so two overlapping nodes resolve
   * to the closer one and a cropped-out node can never be clicked.
   */
  const findAtPointer = (pointer: { x: number; y: number }) =>
    placeAtPoint(selection.places, pointer, projectPlace, NODE_HIT_RADIUS, { width: size, height: size });

  /**
   * World point under the cursor, used to keep the visible readout honest about
   * what the camera is actually showing after a pointer-anchored zoom.
   */
  const worldUnderCursor = (pointer: { x: number; y: number }) => screenToWorld(pointer, size, camera);

  const findRegionAt = (pointer: { x: number; y: number }) =>
    selection.local ? null : regionAtPoint(regions, pointer, projectRegion);

  // Keyboard parity with the pointer: arrows pan, +/- zoom, Home recenters,
  // Escape clears the selection, and the region list is reachable by Tab.
  const onKeyDown = (event: React.KeyboardEvent<HTMLCanvasElement>) => {
    const key = event.key;
    if (key === '+' || key === '=') { event.preventDefault(); zoomBy(ZOOM_IN_FACTOR); return; }
    if (key === '-' || key === '_') { event.preventDefault(); zoomBy(ZOOM_OUT_FACTOR); return; }
    if (key === 'Home') { event.preventDefault(); recenter(); return; }
    if (key === 'Escape') {
      if (focusedRegionKey) { event.preventDefault(); setFocusedRegionKey(null); return; }
      if (selectedId) { event.preventDefault(); setSelectedId(null); }
      return;
    }
    const direction = PAN_KEYS[key];
    if (!direction) return;
    event.preventDefault();
    setCamera((value) => panCamera(value, direction[0] * KEY_PAN_PIXELS, direction[1] * KEY_PAN_PIXELS, size));
  };

  /**
   * One pan gesture, shared by the canvas and by the transparent region/place
   * controls layered above it.
   *
   * Why this is not just a canvas handler: the region discs and place nodes are
   * real DOM buttons (so keyboard and assistive tech can reach them) sitting on
   * top of the canvas. A finger landing on one of them starts its gesture on
   * the *button*, so the canvas never receives a `pointerdown` and the map does
   * not pan. Measured: dragging from a place node did nothing, while dragging
   * the bare canvas a few pixels away panned normally.
   *
   * So the same handlers are attached to both. The gesture decides what it was
   * when it ends: a drag pans, a tap activates whatever is under it. That
   * keeps the controls tappable (they must stay tappable - a region that cannot
   * be opened is not a fix) while letting a drag begin anywhere.
   *
   * Pointer capture is taken on the element that received the `pointerdown`, so
   * a drag that wanders off it still delivers its `pointerup` and is not
   * stranded mid-pan.
   */
  const beginDrag = (event: React.PointerEvent<HTMLElement>) => {
    if (event.button !== 0) return;
    markPointerGesture(event.currentTarget);
    const pointer = pointerAt(event);
    dragRef.current = { x: pointer.x, y: pointer.y, moved: false, pointerId: event.pointerId };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const continueDrag = (event: React.PointerEvent<HTMLElement>): boolean => {
    const pointer = pointerAt(event);
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return false;
    const dx = pointer.x - drag.x;
    const dy = pointer.y - drag.y;
    // A finger is far less precise than a mouse, so the slop that decides
    // "drag" over "tap" is larger for touch.
    const slop = event.pointerType === 'mouse' ? 3 : 8;
    if (Math.abs(dx) + Math.abs(dy) > slop) drag.moved = true;
    dragRef.current = { ...drag, x: pointer.x, y: pointer.y };
    setCamera((value) => panCamera(value, -dx / (pointer.scale || 1), -dy / (pointer.scale || 1), size));
    return true;
  };

  /** Ends the gesture. Returns true when the gesture was a drag, not a tap. */
  const endDrag = (event: React.PointerEvent<HTMLElement>): boolean => {
    const drag = dragRef.current;
    if (drag && drag.pointerId !== event.pointerId) return false;
    const dragged = Boolean(drag?.moved);
    dragRef.current = null;
    // Arm the guard for the control this gesture started on. Both outcomes need
    // it, for different reasons:
    //
    //   - a tap already activated the control in `pointerup`, so the `click`
    //     the browser fires next is that same activation arriving a second time;
    //   - a mouse drag pans, and Chromium still dispatches the trailing `click`
    //     afterwards. Measured on a button with pointer capture:
    //     pointerdown -> pointermove -> pointerup -> click, detail = 1.
    //
    // The case that must NOT leave the guard armed is a touch drag: no
    // compatibility `click` follows it, so an armed guard would simply sit
    // there and eat the player's next Enter/Space. That is the bug this shape
    // already fixed once (see `activate`), which is why the guard is armed only
    // when the pointer actually delivers a click.
    const deliversCompatibilityClick = event.pointerType !== 'touch';
    gestureClickRef.current = dragged && !deliversCompatibilityClick ? null : event.currentTarget;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
    return dragged;
  };

  const cancelDrag = () => { dragRef.current = null; gestureClickRef.current = null; };

  /**
   * Activation guard for the region discs and place nodes.
   *
   * Those controls need four things at once:
   *
   *   1. a *tap* activates them, exactly once;
   *   2. a *drag* that starts on them pans instead, and must not also activate;
   *   3. a keyboard Enter/Space, or any synthetic `click` with no pointer
   *      gesture behind it, activates them normally;
   *   4. none of the above may leave state behind that eats a later activation.
   *
   * Activation happens in `pointerup`, where the gesture is known to be a tap,
   * which covers (1) without waiting for a `click`. A drag is skipped there and
   * arms the guard, which covers (2). (3) is why the guard exists rather than
   * being a blanket "ignore clicks" rule.
   *
   * What separates (2) from (3) is `event.detail`, the click count: a pointer
   * click carries `detail >= 1`, while Enter/Space on a button - and synthetic
   * clicks from assistive tech - dispatch `click` with `detail === 0`. Without
   * that distinction the guard has to choose between swallowing the player's
   * keyboard activation and letting a drag's trailing click open a region it
   * was not meant to open. Measured in Chromium: dragging a region disc panned
   * the camera *and* opened the region, because the drag disarmed the guard and
   * the trailing `click` then read as a fresh activation.
   *
   * The guard is consumed by the first click that reaches the control, whether
   * or not that click is swallowed, so it can never outlive the gesture that
   * set it. The bug this shape fixes: the flag used to be a single global
   * boolean armed by *any* `pointerdown` - including the canvas's - and only
   * cleared when an overlay control was clicked. After a canvas drag it was
   * left armed forever, because a drag synthesises no compatibility `click` to
   * clear it, so the next Enter/Space on a region disc or place node was
   * swallowed as a trailing click. Measured: drag the bare canvas, then
   * activate a region by keyboard - the region did not open and only the second
   * Enter worked. Holding the *element* instead of a boolean is what makes this
   * safe: the canvas can never arm a guard for a control it does not own.
   */
  const gestureClickRef = useRef<EventTarget | null>(null);

  /** Runs an activation unless a pointer gesture on this same control owns the click. */
  const activate = (event: React.MouseEvent<HTMLElement>, action: () => void) => {
    const target = event.currentTarget;
    const armed = gestureClickRef.current;
    // Consume on the first click for this control, swallowed or not.
    gestureClickRef.current = null;
    if (armed === target && event.detail > 0) {
      // This control's own gesture already handled the click: the tap activated
      // it in `pointerup`, or the drag panned and must activate nothing.
      event.preventDefault();
      return;
    }
    action();
  };

  /** Arms the guard for the control a drag started on. */
  const markPointerGesture = (target: EventTarget | null) => { gestureClickRef.current = target; };

  const activeRegion = findRegion(regions, hoveredRegionKey) || focusedRegion;  // Mirrors the model: an opened region reports 'places' even at a low zoom,
  // because that is what the map is actually drawing.
  const disclosureLabel = focusedRegion ? 'places' : 'regions';
  const gestureLabel = selection.local
    ? 'Drag to pan · scroll to zoom · select a place'
    : 'Drag to pan · scroll to zoom · open a region to see its places';
  const directPlaces = selection.local ? selection.places : selection.places.filter((place) => placeStatus(place, currentLocation) === 'current');
  const focusedReliefLabel = focusedRegion ? reliefLabel(regionRelief(focusedRegion)) : null;
  const selectedReliefLabel = selectedLoc ? reliefLabel(placeRelief(selectedLoc)) : null;

  return <section className="location-map space-y-3" aria-label="World map">
    <div className="flex items-end justify-between gap-3">
      <div>
        <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--ink-soft)] font-bold">Atlas</h3>
        <p className="mt-1 text-[11px] text-[var(--ink-muted)]">{gestureLabel}</p>
      </div>
      <div className="flex shrink-0 gap-1.5">
        {focusedRegion && <button type="button" onClick={showOverview} className="rounded-lg border border-[var(--line)] px-2 py-1 text-[10px] font-bold text-[var(--ink-soft)] hover:bg-[var(--bg-subtle)]">All regions</button>}
        <button type="button" onClick={recenter} className="rounded-lg border border-[var(--line)] px-2 py-1 text-[10px] font-bold text-[var(--ink-soft)] hover:bg-[var(--bg-subtle)]">Recenter</button>
      </div>
    </div>

    <div className="sticky top-0 z-20 min-h-[74px] rounded-xl border border-[var(--line-2)] bg-[var(--bg-surface)] p-2.5 shadow-[var(--shadow-sm)]">
      {selectedLoc ? <>
        <div className="mb-2 min-w-0 truncate text-xs font-bold text-[var(--ink-main)]" title={selectedLoc.name}>Selected: {selectedLoc.name}</div>
        <div className="flex gap-2">
          {selectedLoc.is_unlocked && !locationMatches(selectedLoc, currentLocation) && onPreview
            ? <button type="button" disabled={previewLoading} onClick={() => onPreview(selectedLoc)} className="min-w-0 flex-1 rounded-lg bg-[var(--periwinkle-dark)] px-2 py-2 text-xs font-bold text-white hover:opacity-90 disabled:opacity-50">{previewLoading ? 'Checking route…' : 'Preview journey'}</button>
            : <span className="self-center text-[11px] font-medium text-[var(--ink-soft)]">{locationMatches(selectedLoc, currentLocation) ? 'You are here' : 'Journey unavailable from here'}</span>}
          {activeRoute && onTravel && <button type="button" onClick={() => onTravel(selectedLoc)} className="min-w-0 flex-1 rounded-lg border border-[var(--periwinkle-dark)] px-2 py-2 text-xs font-bold text-[var(--periwinkle-dark)] hover:bg-[var(--bg-subtle)]">Travel here</button>}
        </div>
      </> : <div className="flex min-h-[52px] items-center text-xs text-[var(--ink-soft)]">Select a place to preview a journey.</div>}
    </div>

    <div className="relative">
      <div
        ref={rootRef}
        className="relative aspect-square w-full overflow-hidden rounded-2xl border border-[var(--line-2)] bg-[var(--bg-surface)] shadow-[var(--shadow-sm)]"
      >
        <canvas
          ref={canvasRef}
          tabIndex={0}
          role="application"
          aria-label="Interactive world map"
          aria-describedby={`${instructionsId} ${statusId}`}
          aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Home Escape + -"
          onKeyDown={onKeyDown}
          onPointerDown={(event) => {
            // Pointer Events cover mouse, touch and pen with one code path. The
            // old mouse-only handlers left `touch-none` blocking the browser's
            // own scrolling while no touch pan existed at all, so the map was
            // frozen under a finger.
            beginDrag(event);
          }}
          onPointerMove={(event) => {
            if (continueDrag(event)) return;
            // Hover only exists for a mouse; a touch has no hover state to draw.
            if (event.pointerType !== 'mouse') return;
            const pointer = pointerAt(event);
            const found = findAtPointer(pointer);
            setHoveredId(found?.id || null);
            setHoveredRegionKey(found ? null : findRegionAt(pointer)?.key || null);
            setCursorWorld(found ? null : worldUnderCursor(pointer));
            event.currentTarget.style.cursor = found || (!selection.local && findRegionAt(pointer)) ? 'pointer' : 'grab';
          }}
          onPointerUp={(event) => {
            // A drag pans and must not also select; only a tap selects.
            if (endDrag(event)) return;
            const pointer = pointerAt(event);
            const found = findAtPointer(pointer);
            if (found) { selectPlace(found); return; }
            const region = findRegionAt(pointer);
            if (region) openRegion(region);
            else setSelectedId(null);
          }}
          onPointerCancel={cancelDrag}
          onPointerLeave={() => {
            // Only a mouse leaves. A captured touch reports leave too, and
            // clearing the drag there would abort a pan that is still running.
            if (dragRef.current) return;
            setHoveredId(null); setHoveredRegionKey(null); setCursorWorld(null);
          }}
          onWheel={(event) => {
            event.preventDefault();
            // Wheel zoom is anchored on the pointer, so the place under the
            // cursor stays under the cursor while the player explores.
            const pointer = pointerAt(event);
            const factor = Math.exp(-event.deltaY * WHEEL_ZOOM_STEP) * (event.deltaY < 0 ? ZOOM_IN_FACTOR / 1.16 : 1);
            zoomAtPointer(factor, pointer);
          }}
          className="block h-full w-full touch-none cursor-grab focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--periwinkle-dark)]"
        />

        {/*
          Regions are real DOM buttons laid over their discs. The canvas visually
          draws the disc; this transparent control is the same disc, so a
          keyboard or assistive-tech player can open a region without a canvas,
          and its hit area covers exactly what is drawn. Region clicks focus the
          camera - they never travel.

          They also carry the pan handlers: a finger that lands on a disc must
          still be able to drag the map. `endDrag` reports whether the gesture
          became a drag, and only a genuine tap opens the region.
        */}
        {!selection.local && regions.map((region) => {
          const disc = projectRegion(region);
          const diameter = Math.max(38, disc.radius * 2);
          return <button
            key={region.key}
            type="button"
            aria-label={`Open region ${region.name}${region.undiscoveredCount ? '' : ''}`}
            aria-pressed={focusedRegionKey === region.key}
            disabled={!region.interactive}
            onPointerDown={beginDrag}
            onPointerMove={continueDrag}
            onPointerUp={(event) => { if (endDrag(event)) return; openRegion(region); }}
            onPointerCancel={cancelDrag}
            onClick={(event) => activate(event, () => openRegion(region))}
            onMouseEnter={() => setHoveredRegionKey(region.key)}
            onMouseLeave={() => setHoveredRegionKey((key) => (key === region.key ? null : key))}
            className="absolute rounded-full bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--periwinkle-dark)] disabled:cursor-default"
            style={{ left: disc.x, top: disc.y, width: diameter, height: diameter, transform: 'translate(-50%, -50%)' }}
          />;
        })}

        {/*
          The place under the protagonist is always a real control too: the one
          node whose name must be reachable without a pointer. It carries the
          pan handlers for the same reason the region discs do.
        */}
        {directPlaces.map((place) => {
          const point = projectPlace(place);
          return <button
            key={`direct-${place.id}`}
            type="button"
            aria-label={`${place.name}, ${STATUS_TEXT[placeStatus(place, currentLocation)] || 'place'}`}
            onPointerDown={beginDrag}
            onPointerMove={continueDrag}
            onPointerUp={(event) => { if (endDrag(event)) return; selectPlace(place); }}
            onPointerCancel={cancelDrag}
            onClick={(event) => activate(event, () => selectPlace(place))}
            className="absolute h-9 w-9 -translate-x-1/2 -translate-y-1/2 rounded-full bg-transparent focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--periwinkle-dark)]"
            style={{ left: point.x, top: point.y }}
          />;
        })}

        <div className="absolute right-3 top-3 flex flex-col overflow-hidden rounded-xl border border-[var(--line)] bg-[rgba(255,253,251,.92)] shadow-[var(--shadow-sm)] backdrop-blur">
          <button type="button" onClick={() => zoomBy(1.25)} disabled={camera.zoom >= MAX_ZOOM} className="h-8 w-8 text-lg font-bold text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] disabled:opacity-40" aria-label="Zoom in">+</button>
          <button type="button" onClick={() => zoomBy(.8)} disabled={camera.zoom <= MIN_ZOOM} className="h-8 w-8 border-t border-[var(--line)] text-lg font-bold text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] disabled:opacity-40" aria-label="Zoom out">−</button>
        </div>

        <p id={instructionsId} className="sr-only">
          Interactive world map. With a keyboard: arrow keys pan, plus and minus zoom, Home recenters on your character,
          Escape clears the selected place and then steps back out of a region. Opening a region only moves the view -
          it never travels.
        </p>
        <p id={statusId} className="sr-only" aria-live="polite">
          {focusedRegion ? `${focusedRegion.name}, ${focusedRegion.places.length} places` : `Overview of ${regions.length} regions`}
          {selectedLoc ? `. Selected ${selectedLoc.name}. ${STATUS_TEXT[selectedStatus || ''] || ''}` : ''}
        </p>

        <div className="pointer-events-none absolute bottom-3 left-3 flex flex-col items-start gap-1">
          <span className="rounded-full border border-[var(--line)] bg-[rgba(255,253,251,.92)] px-2.5 py-1 text-[10px] font-semibold text-[var(--ink-soft)]">{Math.round(camera.zoom * 100)}% · {disclosureLabel}</span>
          {activeRegion && <span className="rounded-full border border-[var(--line)] bg-[rgba(255,253,251,.92)] px-2.5 py-1 text-[10px] font-semibold text-[var(--ink-main)]">{activeRegion.name} · {activeRegion.places.length} {activeRegion.places.length === 1 ? 'place' : 'places'}</span>}
          {cursorWorld && <span className="rounded-full border border-[var(--line)] bg-[rgba(255,253,251,.92)] px-2.5 py-1 font-mono text-[10px] text-[var(--ink-muted)]">{Math.round(cursorWorld.x * 100)}, {Math.round((1 - cursorWorld.y) * 100)}</span>}
        </div>
      </div>

      {/*
        A named, focusable entry point for every region that is on the map.
        Regions are the map's primary structure; without this the only way to
        learn their names would be to read a canvas.
      */}
      <div className="mt-2">
        <span id={regionListId} className="sr-only">Regions on this map</span>
        <div className="flex flex-wrap gap-1.5" role="group" aria-labelledby={regionListId}>
          <button
            type="button"
            onClick={showOverview}
            aria-pressed={!focusedRegion}
            className={`rounded-full border px-2.5 py-1 text-[10px] font-bold transition-colors ${!focusedRegion ? 'border-[var(--periwinkle-dark)] bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)]' : 'border-[var(--line)] text-[var(--ink-soft)] hover:bg-[var(--bg-subtle)]'}`}
          >Overview</button>
          {regions.map((region) => <button
            key={region.key}
            type="button"
            onClick={() => openRegion(region)}
            aria-pressed={focusedRegionKey === region.key}
            className={`rounded-full border px-2.5 py-1 text-[10px] font-bold transition-colors ${focusedRegionKey === region.key ? 'border-[var(--periwinkle-dark)] bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)]' : region.hasCurrent ? 'border-[var(--ok)] text-[var(--ok)] hover:bg-[var(--bg-subtle)]' : 'border-[var(--line)] text-[var(--ink-soft)] hover:bg-[var(--bg-subtle)]'}`}
          >{region.name}</button>)}
        </div>
        {focusedReliefLabel && <p className="mt-1.5 text-[10px] text-[var(--ink-soft)]">
          Region terrain: {focusedReliefLabel}
        </p>}
      </div>
    </div>

    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[var(--ink-muted)]">
      <span className="inline-flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--ok)]" />You are here</span>
      <span className="inline-flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--gold-dark)]" />Previewed route</span>
      <span className="inline-flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--periwinkle)]" />Discovered</span>
      <span className="inline-flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--ink-faint)]" />Locked</span>
      <span className="inline-flex items-center gap-1"><i className="inline-block h-2.5 w-2.5 rounded-full border border-dashed border-[var(--periwinkle)] bg-transparent" />Region</span>
    </div>

    {routeModel && routeModel.unsupported.length > 0 && <p className="text-[10px] text-[var(--ink-muted)]">
      Part of this route is off the map, so only the legs between places shown here are drawn.
    </p>}

    {/*
      A redacted route is still a real, walkable journey - the player may take
      it - so the map says what it can (there is unexplored ground in between)
      and draws no line. A straight line between origin and destination would be
      the one thing the engine refused to promise.
    */}
    {activeRoute?.route_redacted && <p className="text-[10px] text-[var(--ink-muted)]">
      {activeRoute.route_note || 'Route passes through unexplored territory'} - no road is drawn for it.
    </p>}

    {selectedLoc && <div className="space-y-2 rounded-xl border border-[var(--line)] bg-[var(--bg-surface)] p-3 text-xs shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-bold text-[var(--ink-main)]">{selectedLoc.name}</div>
          <div className="mt-.5 text-[10px] font-mono text-[var(--ink-muted)]">{regionNameOf(selectedLoc)}</div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className={`rounded-full px-2 py-.5 text-[10px] font-bold ${selectedStatus === 'current' ? 'bg-[rgba(79,190,147,.14)] text-[var(--ok)]' : selectedStatus === 'locked' ? 'bg-[var(--bg-subtle)] text-[var(--warn)]' : selectedStatus === 'unreachable' ? 'bg-[var(--bg-subtle)] text-[var(--danger)]' : 'bg-[var(--bg-subtle)] text-[var(--ink-soft)]'}`}>{STATUS_TEXT[selectedStatus || ''] || 'Place'}</span>
          {placeStatus(selectedLoc, currentLocation) === 'current' && <span className="rounded-full border border-[var(--ok)] px-2 py-.5 text-[10px] font-bold text-[var(--ok)]">Here</span>}
        </div>
      </div>
      {selectedLoc.description && <p className="leading-relaxed text-[var(--ink-soft)]">{selectedLoc.description}</p>}
      {selectedReliefLabel && <div className="text-[10px] font-medium text-[var(--ink-soft)]">Terrain: {selectedReliefLabel}</div>}
      <div className="flex flex-wrap gap-1">
        <span className="rounded-full border border-[var(--line)] px-2 py-.5 text-[10px] font-mono text-[var(--ink-muted)]">{placeKindLabel(selectedLoc.tags)}</span>
        {(selectedLoc.tags || []).slice(0, 4).map((tag) => <span key={tag} className="rounded-full border border-[var(--line)] px-2 py-.5 text-[10px] font-mono text-[var(--ink-muted)]">{tag}</span>)}
      </div>
      {!selectedLoc.is_unlocked && selectedLoc.unlock_reason_missing && <div className="text-[10px] font-bold text-[var(--warn)]">🔒 {selectedLoc.unlock_reason_missing}</div>}
      {activeRoute && <div className="rounded-lg border border-[var(--line)] bg-[var(--bg-subtle)] p-2 leading-relaxed">
        <div>Estimated time: {activeRoute.elapsed_minutes} minutes</div>
        <div>Risk: {activeRoute.risk?.level || 'unknown'}</div>
        {/*
          A redacted route has an empty `route` array, and an empty array is not
          the same claim as "no stops". Printing nothing, or joining it into a
          bare "Route:", would read as a direct path - so the engine's own note
          is shown instead and the shape is never invented.
        */}
        {activeRoute.route_redacted
          ? <div>{activeRoute.route_note || 'Route passes through unexplored territory'}</div>
          : activeRoute.route.length > 1 && <div>Route: {activeRoute.route.join(' → ')}</div>}
      </div>}
    </div>}
  </section>;
}

/** Human-readable category for the detail panel, from the same tag vocabulary. */
function placeKindLabel(tags?: string[]): string {
  const list = (tags || []).map((tag) => String(tag).toLowerCase());
  if (list.some((tag) => ['water', 'coastal', 'harbor', 'seaside', 'tide'].includes(tag))) return 'waterside';
  if (list.some((tag) => ['wilderness', 'forest', 'mountain', 'outdoor', 'wild'].includes(tag))) return 'open ground';
  if (list.some((tag) => ['dangerous', 'hazard', 'ruined', 'combat'].includes(tag))) return 'hazard';
  if (list.some((tag) => ['temple', 'shrine', 'palace', 'landmark', 'dungeon'].includes(tag))) return 'landmark';
  if (list.some((tag) => ['urban', 'settlement', 'city', 'town', 'village', 'shop'].includes(tag))) return 'settlement';
  if (list.some((tag) => ['road', 'path', 'street', 'route', 'train', 'station'].includes(tag))) return 'route';
  return 'place';
}
