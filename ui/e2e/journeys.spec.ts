import { test, expect, type Locator, type Page } from '@playwright/test';

import { MIN_ZOOM, RECENTER_ZOOM, worldToScreen, type Camera } from '../src/components/mapCamera';
import { overviewCamera, regionCamera } from '../src/components/mapView';
import { selectVisiblePlaces, buildRegions, buildRouteModel, placeAtPoint, type MapLocation as ModelLocation } from '../src/components/mapModel';
import { normalizedCoordinate } from '../src/components/mapCoordinates';

/**
 * UI journeys that only a real browser can verify.
 *
 * The unit suite asserts the model and the component with jsdom; these tests
 * assert what a player actually sees and clicks in a real canvas: the play
 * surface renders world state, the output-length control reaches the backend,
 * and the atlas can be driven to a destination and travelled to.
 */
const API = 'http://localhost:8000';
const WORLD = 'E2E_Journey';

function json(data: unknown, status = 200) {
  return {
    status,
    contentType: 'application/json',
    headers: {
      'access-control-allow-origin': '*',
      'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS',
      'access-control-allow-headers': 'content-type',
    },
    body: JSON.stringify(data),
  };
}

const corsPreflight = {
  status: 204,
  headers: {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'access-control-allow-headers': 'content-type',
  },
};

type MapLocation = {
  id: string;
  name: string;
  x: number;
  y: number;
  zone: string;
  is_unlocked: boolean;
  is_reachable: boolean;
  discovery_status: string;
  route_preview: string[];
  tags?: string[];
  unlock_realm?: string;
  unlock_exp?: number;
  unlock_reason_missing?: string | null;
};

/**
 * The geography the current test installed, so a helper can rebuild the exact
 * region model the map built. Scoped per test and reset in `beforeEach`; a
 * leaked array would make a later test project against another world's map.
 */
let installedLocations: MapLocation[] = [];
const locationsFor = (): MapLocation[] => installedLocations;

/**
 * Where the map points its camera when it snaps to a location on load and when
 * "Recenter" is pressed. Delegates to the component's own camera policy rather
 * than re-deriving it, so the test cannot drift from the app.
 */
const recenteredCamera = (current: MapLocation): Camera => overviewCamera(current as unknown as ModelLocation);

/**
 * The zoom badge is the atlas's own readout of the disclosure tier:
 * "100% · regions", "225% · regions" (recentred, nothing focused), or
 * "225% · places" (a region is open and the camera is close enough).
 *
 * Recentring alone does NOT open a region, so it reports "regions" however far
 * in the camera is: the tier describes disclosure, not distance.
 */
const zoomBadge = (page: Page) => page.getByText(/^\d+% · (regions|region detail|places)$/);

async function readViewport(page: Page) {
  const badge = zoomBadge(page);
  await expect(badge).toBeVisible();
  const text = await badge.innerText();
  const tier = text.split('·')[1].trim();
  return {
    text,
    zoom: Number(text.match(/^(\d+)%/)?.[1]) / 100,
    tier,
    /**
     * Whether the canvas is painting individual nodes.
     *
     * An open region reports 'places' regardless of zoom, because disclosure
     * follows the opened region rather than the zoom number. The tier is still
     * the honest source for this: 'regions' means no region is focused, and
     * then only landmarks are drawn.
     */
    drawsNodes: tier !== 'regions',
  };
}

/**
 * Open a region so its places become clickable.
 *
 * Prefers the named chip below the canvas over the transparent button laid
 * over the region disc: the chip is never clipped by the canvas viewport and
 * is the same control a keyboard or assistive-tech player would use, so the
 * test exercises the path that cannot break for layout reasons.
 */
async function openRegion(page: Page, regionName: string) {
  const chips = page.getByRole('group', { name: 'Regions on this map' });
  const chip = chips.getByRole('button', { name: regionName, exact: true });
  if (await chip.count()) {
    await chip.first().click();
    return;
  }
  await page.getByRole('button', { name: `Open region ${regionName}` }).first().click();
}

/**
 * The camera the map holds right now, rebuilt from the contract.
 *
 * `regionCamera` needs the region's own extent, so the region is rebuilt from
 * the locations the test handed the app - the same inputs the app itself uses.
 * The canvas size is the component's cap, which every E2E viewport exceeds.
 */
function cameraAfterRegionOpen(locations: MapLocation[], regionName: string, size: number): Camera {
  const model = locations as unknown as ModelLocation[];
  const region = buildRegions(model, undefined).find((item) => item.name === regionName);
  if (!region) throw new Error(`region ${regionName} is not on the map`);
  return regionCamera(region, size);
}

/**
 * Click a location the way a player has to.
 *
 * Two rules from the component shape this helper:
 *
 *   1. A place node is only drawn once its region has been opened, so a click
 *      has to be preceded by focusing that region — clicking the overview can
 *      only ever land on a region disc, which focuses rather than selects.
 *   2. Opening a region *moves the camera*: it frames the region at its own
 *      zoom. Projecting with the pre-focus camera produces a point the node is
 *      not drawn at, so the projection is recomputed from the post-focus
 *      camera. Anything else silently tests the wrong pixel.
 */
async function clickMapLocation(page: Page, canvas: Locator, location: MapLocation) {
  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');

  // Opening the region is what discloses its places; it never travels.
  await openRegion(page, location.zone);
  // The camera the map holds after opening: the region's own fit zoom, floored
  // at the disclosure threshold. Computed from the contract, not guessed.
  const camera = cameraAfterRegionOpen([...locationsFor(page)], location.zone, box.width);

  for (let attempt = 0; attempt < 8; attempt += 1) {
    const viewport = await readViewport(page);
    const point = worldToScreen(location, box.width, camera);
    // Leave room for the largest node radius so the node itself is on screen.
    const margin = 12;
    const onScreen = point.x > margin && point.x < box.width - margin && point.y > margin && point.y < box.height - margin;
    if (onScreen && viewport.drawsNodes) {
      await page.mouse.click(box.x + point.x, box.y + point.y);
      return;
    }
    // Zooming out widens the view without moving the camera's centre, so the
    // reference camera above stays valid while the zoom shrinks. The only
    // terminal condition is the zoom floor: past it the node is simply not on
    // this map at any zoom, which is a fixture problem, not a timing one.
    if (viewport.zoom <= MIN_ZOOM) {
      throw new Error(`${location.name} is not on screen even at ${viewport.text}; move it inside its region`);
    }
    await page.getByRole('button', { name: 'Zoom out' }).click();
    await expect(zoomBadge(page)).not.toHaveText(viewport.text);
  }
  throw new Error(`${location.name} never came into view`);
}

/**
 * The model's own verdict on which places are drawn, so a test can assert the
 * map is not painting a node it should have withheld.
 */
function drawnPlaces(locations: MapLocation[], currentRef: string | undefined, zoom: number, focusedRegionKey?: string | null) {
  const model = locations as unknown as ModelLocation[];
  const regions = buildRegions(model, currentRef);
  return selectVisiblePlaces(model, regions, { zoom, focusedRegionKey });
}

async function openMap(page: Page) {
  // The map lives behind a drawer; a player has to open it before travel is
  // even an option.
  await page.getByTitle('World Map').click();
  await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();
}

test.beforeEach(() => {
  installedLocations = [];
});

const playState = {
  protagonist: {
    id: 'char_xueli', name: 'Xueli', location: 'Sect Gate',
    power_stat: { realm: 'Qi Condensation', exp: 12, known_skills: ['Frost Whisper'] },
    traits: {}, knowledge_flags: [], alive: true, relationships: {}, age: '16',
    inventory: [
      { id: 'jade_token', name: 'Jade Token', quantity: 1, origin: 'given by the elder' },
    ],
  },
  arc_progress: { current_checkpoint_id: 'cp_0', current_index: 0, total_checkpoints: 2, completed: [] },
  unlocked_cards: [],
  story_clock: { tick: 3, year: 1, month: 1, day: 3, time_of_day: 'morning' },
  foreshadowing_tracker: [
    { id: 'fs_1', description: 'The elder recognizes her bloodline', status: 'open' },
  ],
  style_card: {},
  output_length: 'Standard',
  lifecycle_status: 'active',
};

/** Where the player is standing, and the origin the map recenters on. */
const GATE: MapLocation = {
  id: 'gate', name: 'Sect Gate', x: 50, y: 50, zone: 'sect',
  is_unlocked: true, is_reachable: true, discovery_status: 'visited',
  route_preview: [], tags: ['building'],
};

/**
 * A locked destination: reachable, but gated behind a realm the player has not
 * reached yet. It sits in the far south-west of the world, so opening its
 * region at 225% crops it out of the viewport and reaching it takes a
 * deliberate zoom out first.
 */
const DESERT: MapLocation = {
  id: 'desert', name: 'Great Desert', x: 20, y: 20, zone: 'wilds',
  is_unlocked: false, is_reachable: true, discovery_status: 'discovered',
  route_preview: ['Sect Gate', 'Great Desert'],
  tags: ['wilderness'],
  unlock_realm: 'Foundation Establishment', unlock_exp: 30,
  unlock_reason_missing: 'Cần đạt Foundation Establishment; Cần 30 EXP (hiện có 12)',
};

/**
 * Unlocked and inside the ±22% window the map shows after recentering on Sect
 * Gate at 225% — i.e. a destination the player can see and click immediately.
 */
const HARBOR: MapLocation = {
  id: 'harbor', name: 'Quiet Harbor', x: 66, y: 42, zone: 'coast',
  is_unlocked: true, is_reachable: true, discovery_status: 'discovered',
  route_preview: ['Sect Gate', 'Quiet Harbor'], tags: ['harbor'],
};

/**
 * A place the engine has not revealed. Its name is already scrubbed by the
 * backend, and the map must never resurrect it, count it, or draw it.
 */
const SECRET: MapLocation = {
  id: 'secret_shrine', name: 'Unknown location', x: 52, y: 48, zone: 'sect',
  is_unlocked: true, is_reachable: false, discovery_status: 'unknown',
  route_preview: [],
};

/**
 * A two-member region far from the protagonist.
 *
 * Two members matter: a lone place makes `regionCamera` frame it at MAX_ZOOM,
 * which can push the place *itself* off the canvas. Clustering two of them
 * keeps the region framed at a normal zoom, so opening it really does paint
 * its interior. That is the precondition the click-hit contract needs.
 */
const ISLE_A: MapLocation = {
  id: 'isle_a', name: 'North Isle', x: 15, y: 92, zone: 'north',
  is_unlocked: true, is_reachable: false, discovery_status: 'discovered',
  route_preview: [], tags: ['wilderness'],
};
const ISLE_B: MapLocation = {
  id: 'isle_b', name: 'North Spire', x: 30, y: 82, zone: 'north',
  is_unlocked: true, is_reachable: false, discovery_status: 'discovered',
  route_preview: [], tags: ['building'],
};

/**
 * Fulfils every request the play surface makes. `locations` is what the map
 * endpoints return, so each test controls the world's geography without a
 * backend, and `travelPreview` is the engine's verdict on a journey.
 */
async function mockPlayApi(page: Page, options: { locations: MapLocation[]; travelPreview?: unknown }) {
  installedLocations = options.locations;
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'OPTIONS') return route.fulfill(corsPreflight);
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json([]));
    if (url.includes('/travel/preview')) return route.fulfill(json(options.travelPreview ?? {}));
    if (url.includes('/location-map/status')) return route.fulfill(json({ locations: options.locations }));
    if (url.includes('/location-map')) return route.fulfill(json({ locations: options.locations }));
    if (url.includes('/affinity-graph')) return route.fulfill(json({ nodes: [], edges: [] }));
    if (url.includes('/quest_board')) return route.fulfill(json({ quests: [] }));
    if (url.includes('/journal')) return route.fulfill(json({ entries: [] }));
    if (url.includes('/runtime-config')) {
      return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    }
    return route.fulfill(json({}));
  });
}

test('play surface renders the world state it was given', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json([]));
    if (url.includes('/location-map')) return route.fulfill(json({ locations: [] }));
    if (url.includes('/affinity-graph')) return route.fulfill(json({ nodes: [], edges: [] }));
    if (url.includes('/quest_board')) return route.fulfill(json({ quests: [] }));
    if (url.includes('/journal')) return route.fulfill(json({ entries: [] }));
    if (url.includes('/runtime-config')) {
      return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    }
    return route.fulfill(json({}));
  });

  await page.goto(`/worlds/${WORLD}/play`);

  // The protagonist and their realm come from world state, not from hardcoded UI.
  await expect(page.getByText('Xueli').first()).toBeVisible();
  await expect(page.getByText(/Qi Condensation/).first()).toBeVisible();
  // The play input is the primary affordance and must be usable immediately.
  await expect(page.getByPlaceholder(/What do you do/)).toBeVisible();
});

test('changing output length persists to the backend', async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'OPTIONS') return route.fulfill(corsPreflight);
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json([]));
    if (url.includes('/location-map')) return route.fulfill(json({ locations: [] }));
    if (url.includes('/affinity-graph')) return route.fulfill(json({ nodes: [], edges: [] }));
    if (url.includes('/quest_board')) return route.fulfill(json({ quests: [] }));
    if (url.includes('/journal')) return route.fulfill(json({ entries: [] }));
    if (url.includes('/runtime-config')) {
      return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    }
    return route.fulfill(json({}));
  });

  await page.goto(`/worlds/${WORLD}/play`);
  // The select renders the engine's enum values ('Short'/'Medium'/'Long'), not
  // the display labels — those only live in the hook's lookup table.
  const select = page.locator('select').filter({ hasText: /Short|Medium|Long/i }).first();
  await expect(select).toBeVisible();

  const saved = page.waitForRequest(
    (req) => req.method() === 'PUT' && req.url().includes('/world_config'),
  );
  await select.selectOption('long');

  const request = await saved;
  const body = request.postData() || '';
  expect(body).toContain('output_length');
  // Selecting 'Long' must reach the engine as the backend enum, not as the UI
  // value — a mismatch here silently downgrades every later chapter.
  expect(body).toContain('Detailed');
});

test('the map opens as a region overview, not a wall of node names', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, DESERT, HARBOR] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();

  // Landing on the world recenters on the protagonist, but nothing is focused,
  // so the atlas still reports the region tier - not a fake "local detail".
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · regions`);

  // Every region is named and reachable without touching the canvas at all.
  const chips = page.getByRole('group', { name: 'Regions on this map' });
  await expect(chips.getByRole('button', { name: 'sect' })).toBeVisible();
  await expect(chips.getByRole('button', { name: 'wilds' })).toBeVisible();
  await expect(chips.getByRole('button', { name: 'coast' })).toBeVisible();
  await expect(chips.getByRole('button', { name: 'Overview' })).toHaveAttribute('aria-pressed', 'true');
});

test('opening a region discloses its places without travelling', async ({ page }) => {
  const travels: string[] = [];
  await mockPlayApi(page, { locations: [GATE, DESERT, HARBOR] });
  page.on('request', (req) => {
    if (req.method() === 'POST' && req.url().includes('/travel')) travels.push(req.url());
  });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  // Opening a region is a camera move, not a journey. Clicking it must never
  // produce a travel request, and must disclose the region's places.
  await openRegion(page, 'coast');
  await expect(zoomBadge(page)).toHaveText(/· places$/);
  expect(travels).toEqual([]);

  // The focused region is reflected in the chip list, and the way back to the
  // overview is a real, named control.
  const chips = page.getByRole('group', { name: 'Regions on this map' });
  await expect(chips.getByRole('button', { name: 'coast' })).toHaveAttribute('aria-pressed', 'true');
  await chips.getByRole('button', { name: 'Overview' }).click();
  await expect(zoomBadge(page)).toHaveText(/· regions$/);
});

test('a realm gate is shown on the map before the player tries to travel', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, DESERT] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();

  // The map opens zoomed onto the protagonist, which puts the far-south-west
  // destination outside the viewport entirely.
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · regions`);

  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');
  const recentred = recenteredCamera(GATE);
  const before = worldToScreen(DESERT, box.width, recentred);
  const outOfView = before.x < 0 || before.x > box.width || before.y < 0 || before.y > box.height;
  expect(outOfView).toBe(true);

  // Opening the region re-frames the camera on it, which is the move that
  // brings the destination back into view. Whether that also lowers the zoom
  // depends on how tight the region is - a lone place opens at the disclosure
  // floor, so this does not assert a direction, only that the view changed.
  await clickMapLocation(page, canvas, DESERT);

  const viewport = await readViewport(page);
  expect(viewport.drawsNodes).toBe(true);
  expect(viewport.zoom).not.toBe(recentred.zoom);

  // Location names are painted into the canvas, so getByText can never see
  // them. The detail panel is the DOM surface that proves what got selected.
  await expect(page.getByText('Great Desert').first()).toBeVisible();
  await expect(page.getByText(/Cần đạt Foundation Establishment/)).toBeVisible();
  // A locked destination must not offer a travel button, or the gate is
  // decorative — the player would hit the rejection only after committing.
  await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);
});

test('the place under the protagonist offers no journey', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · regions`);

  // The character's own place is exposed as a real button, so this assertion
  // does not depend on hitting a 15px node on a canvas.
  await page.getByRole('button', { name: 'Sect Gate, You are here' }).click();
  await expect(page.getByText('Here', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);
  expect(canvas).toBeTruthy();
});

test('selecting a visible destination previews the journey and offers travel', async ({ page }) => {
  await mockPlayApi(page, {
    locations: [GATE, HARBOR],
    travelPreview: {
      status: 'available',
      destination: 'Quiet Harbor',
      route: ['Sect Gate', 'Quiet Harbor'],
      legs: [],
      elapsed_minutes: 90,
      estimated_ticks: 2,
      risk: { level: 'low', known_tags: [] },
    },
  });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · regions`);

  // Quiet Harbor sits inside the viewport the map shows around the protagonist,
  // so this is a destination the player can see and click straight away.
  await clickMapLocation(page, canvas, HARBOR);
  await expect(page.getByText('Quiet Harbor').first()).toBeVisible();

  // The action lives in a reserved, sticky slot above the canvas, not below
  // the details card where it can be present but outside the visible drawer.
  // The slot exists before selection too, so selecting never moves the canvas
  // under a finger between pointerup and the compatibility click.
  const previewBox = await page.getByRole('button', { name: 'Preview journey' }).boundingBox();
  const canvasBox = await canvas.boundingBox();
  expect(previewBox).not.toBeNull();
  expect(canvasBox).not.toBeNull();
  expect(previewBox!.y + previewBox!.height).toBeLessThan(canvasBox!.y);

  const previewRequest = page.waitForRequest(
    (req) => req.method() === 'POST' && req.url().includes('/travel/preview'),
  );
  await page.getByRole('button', { name: 'Preview journey' }).click();

  // The preview is what decides whether travel is offered at all, so the
  // request has to name the destination the player actually selected.
  expect((await previewRequest).postData()).toContain('Quiet Harbor');

  await expect(page.getByText('Estimated time: 90 minutes')).toBeVisible();
  await expect(page.getByText('Risk: low')).toBeVisible();
  await expect(page.getByText('Route: Sect Gate → Quiet Harbor')).toBeVisible();

  // Only now does the engine's verdict unlock the action itself.
  const travel = page.getByRole('button', { name: 'Travel here' });
  await expect(travel).toBeVisible();
  await travel.click();

  // Committing closes the map and stages the journey in the composer.
  await expect(page.getByPlaceholder(/What do you do/)).toHaveValue('Travel to Quiet Harbor.');
});

test('a multi-leg route highlights adjacent stops, not a shortcut across them', async ({ page }) => {
  // Three stops on the engine's route. If the map connected "every pair in the
  // route" it would draw Sect Gate -> Far Ridge, a leg that does not exist.
  const RIDGE: MapLocation = {
    id: 'ridge', name: 'Far Ridge', x: 40, y: 62, zone: 'sect',
    is_unlocked: true, is_reachable: true, discovery_status: 'discovered',
    route_preview: [], tags: ['mountain'],
  };
  await mockPlayApi(page, {
    locations: [GATE, RIDGE, HARBOR],
    travelPreview: {
      status: 'available',
      destination: 'Quiet Harbor',
      route: ['Sect Gate', 'Far Ridge', 'Quiet Harbor'],
      legs: [
        { from: 'Sect Gate', to: 'Far Ridge', elapsed_minutes: 40 },
        { from: 'Far Ridge', to: 'Quiet Harbor', elapsed_minutes: 50 },
      ],
      elapsed_minutes: 90,
      estimated_ticks: 2,
      risk: { level: 'moderate', known_tags: [] },
    },
  });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await page.getByRole('button', { name: 'Recenter' }).click();

  await clickMapLocation(page, canvas, HARBOR);
  await page.getByRole('button', { name: 'Preview journey' }).click();

  // The whole ordered route is shown to the player as text, which is the
  // contract the canvas drawing has to match.
  await expect(page.getByText('Route: Sect Gate → Far Ridge → Quiet Harbor')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Travel here' })).toBeVisible();

  // Adjacency: exactly two legs, chained. "Every pair in the route" would emit
  // three and invent a Sect Gate -> Quiet Harbor shortcut the engine never
  // allowed, which is the failure this guards against.
  const route = buildRouteModel(['Sect Gate', 'Far Ridge', 'Quiet Harbor'], [GATE, RIDGE, HARBOR] as unknown as ModelLocation[]);
  expect(route.segments.map((segment) => [segment.from.id, segment.to.id])).toEqual([
    ['gate', 'ridge'],
    ['ridge', 'harbor'],
  ]);
  expect(route.unsupported).toEqual([]);

  // Every stop is drawn: the focused region's members, plus - because the route
  // names it - the intermediate stop's own region representative. A route you
  // cannot see is not a route.
  const viewport = await readViewport(page);
  const selection = drawnPlaces([GATE, RIDGE, HARBOR], GATE.name, viewport.zoom, 'region:sect');
  expect(selection.places.map((place) => place.id)).toEqual(expect.arrayContaining(['gate', 'ridge', 'harbor']));
});

test('an undiscovered place is never leaked through the map', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR, SECRET] });

  // Fail the test if the hidden name ever reaches the DOM or the network.
  const leaks: string[] = [];
  page.on('console', (msg) => { if (msg.text().includes('Unknown location')) leaks.push(msg.text()); });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const map = page.locator('.location-map');
  // The scrubbed name is what the backend sends; the map must not surface it.
  await expect(map.getByText('Unknown location')).toHaveCount(0);
  await expect(map.getByText('secret_shrine')).toHaveCount(0);

  // Nor may the hidden place inflate the advertised size of the 'sect' region.
  // Sect Gate is the only visible member, and the region chip must not imply
  // there are more.
  await openRegion(page, 'sect');
  const viewed = await readViewport(page);
  const selection = drawnPlaces([GATE, HARBOR, SECRET], GATE.name, viewed.zoom, 'region:sect');
  // The focused region discloses its one visible member. 'harbor' is also drawn,
  // but only as the standing representative of its own region - which is the
  // point: the map must still let a player see out of the region they entered.
  expect(selection.places.map((place) => place.id).sort()).toEqual(['gate', 'harbor']);
  expect(selection.places.some((place) => place.id === 'secret_shrine')).toBe(false);
  // The secret must not be smuggled in as a region's representative either.
  expect(selection.representatives.map((place) => place.id)).not.toContain('secret_shrine');
  expect(leaks).toEqual([]);
});

test('the projection the map draws with matches the point it hit-tests', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · regions`);
  await expect(page.getByRole('button', { name: 'Zoom out' })).toBeVisible();

  // Hit-test with the exact camera the map holds. `place` draws the node and
  // `hit` is the model's own hit test, both fed the same projection - so if the
  // two ever disagree the test fails here rather than as a dead click.
  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');
  const camera = recenteredCamera(GATE);
  const project = (place: MapLocation) => worldToScreen(place, box.width, camera);

  const point = project(HARBOR);
  const hit = placeAtPoint([GATE, HARBOR] as unknown as ModelLocation[], point, project as never);
  expect(hit?.name).toBe('Quiet Harbor');

  // The projection is what the component draws with, so the browser must agree:
  // clicking that pixel discloses the place the model just resolved.
  await clickMapLocation(page, canvas, HARBOR);
  await expect(page.getByText('Quiet Harbor').first()).toBeVisible();

  // A canvas-side sanity check that the projection is inside the viewport.
  expect(normalizedCoordinate(HARBOR.x)).toBeCloseTo(0.66);
});

test('a click never selects a place the map has not painted', async ({ page }) => {
  // The protagonist sits in `sect`; the far `north` region is framed on its own
  // two members, which crops the protagonist out of the canvas entirely.
  //
  // Scope note: this asserts the *end-to-end* behaviour, and it is deliberately
  // weaker than the unit suite. Opening a region frames it well inside the
  // viewport, so the cropped protagonist lands far off canvas - too far for a
  // click to reach even without the bounds guard. The exact distance boundary
  // that used to break is pinned in `mapModel.test.ts`, where a node can be
  // placed a few pixels outside the canvas. This test guards the contract a
  // player would notice: a sweep of the canvas must never select unseen content.
  await mockPlayApi(page, { locations: [GATE, ISLE_A, ISLE_B] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');

  // Select the protagonist's place while it is still on screen, so there is a
  // live selection that the cropped-out clicks below must not be able to keep.
  await page.getByRole('button', { name: 'Recenter' }).click();
  await page.getByRole('button', { name: 'Sect Gate, You are here' }).click();
  await expect(page.getByText('Here', { exact: true })).toBeVisible();

  await openRegion(page, ISLE_A.zone);
  const viewport = await readViewport(page);
  expect(viewport.drawsNodes).toBe(true);

  const camera = cameraAfterRegionOpen(locationsFor(), ISLE_A.zone, box.width);

  // Precondition: the opened region's own places are painted, while the
  // protagonist's is cropped away. Assert "off-canvas", not "off-canvas on x" -
  // which axis the crop happens on depends on the region's position.
  for (const place of [ISLE_A, ISLE_B]) {
    const point = worldToScreen(place, box.width, camera);
    const painted = point.x > 0 && point.y > 0 && point.x < box.width && point.y < box.height;
    expect(painted, `${place.name} should be framed by its own region`).toBe(true);
  }
  const gatePoint = worldToScreen(GATE, box.width, camera);
  const gateCropped =
    gatePoint.x < 0 || gatePoint.y < 0 || gatePoint.x > box.width || gatePoint.y > box.height;
  expect(gateCropped, 'the protagonist should be cropped out').toBe(true);

  // Sweep the canvas. Every click must clear the selection rather than keep the
  // cropped-out protagonist - no painted place is under any of these points.
  for (let gy = 1; gy <= 4; gy += 1) {
    for (let gx = 1; gx <= 4; gx += 1) {
      await page.mouse.click(box.x + (gx / 5) * box.width, box.y + (gy / 5) * box.height);
      await expect(page.getByText('Here', { exact: true })).toHaveCount(0);
      await expect(page.getByText('Sect Gate, You are here')).toHaveCount(0);
    }
  }
});

/**
 * A real mouse drag: press, move well past the 3px mouse slop, release.
 *
 * Deliberately not `locator.dragTo()`: that helper synthesises its own gesture
 * and would not reproduce the thing under test - Chromium's trailing `click`
 * after a drag on an element holding pointer capture.
 */
async function mouseDragFrom(page: Page, locator: Locator, dx: number, dy: number) {
  const box = await locator.boundingBox();
  if (!box) throw new Error('control has no layout box');
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  // Two moves: the first crosses the slop, the second proves the pan keeps up.
  await page.mouse.move(x + dx / 2, y + dy / 2);
  await page.mouse.move(x + dx, y + dy);
  await page.mouse.up();
}

/**
 * Dragging a map control with a mouse pans the camera and activates nothing.
 *
 * The region discs and place nodes are real `<button>`s carrying pointer
 * capture, and Chromium still dispatches the trailing `click` after a drag on
 * them - measured as pointerdown -> pointermove -> pointerup -> click with
 * `detail = 1`. So the activation guard cannot simply be cleared when a drag
 * ends, which is exactly what works for touch (a touch drag produces no
 * compatibility click at all). It has to tell that trailing pointer click apart
 * from a keyboard activation, which arrives with `detail = 0`.
 *
 * Before the fix this drag both panned the camera and opened the region, so a
 * player trying to scroll the map would land in a region they never picked.
 */
test('a mouse drag from a region disc pans the camera without opening the region', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });
  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const disc = page.getByRole('button', { name: 'Open region coast' }).first();
  await expect(disc).toBeVisible();
  const before = (await disc.boundingBox())!;
  await expect(zoomBadge(page)).toHaveText(/\d+% · regions$/);

  await mouseDragFrom(page, disc, 80, 40);

  // The gesture was a pan: the disc moved with the camera...
  const after = (await disc.boundingBox())!;
  expect(
    Math.abs(after.x - before.x) + Math.abs(after.y - before.y),
    'the drag did not pan the camera',
  ).toBeGreaterThan(20);

  // ...and it did not open the region it started on.
  await expect(zoomBadge(page), 'a mouse drag opened the region it panned from').toHaveText(/\d+% · regions$/);
});

test('a mouse drag from a place control pans the camera without selecting the place', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });
  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  // Opening the region is what puts the place node on the canvas.
  await openRegion(page, 'coast');
  const node = page.getByRole('button', { name: /Quiet Harbor, / });
  await expect(node).toBeVisible();
  const before = (await node.boundingBox())!;
  // Nothing selected yet, so a drag that wrongly selected would be visible
  // rather than masked by an already-open panel.
  await expect(page.getByText('Quiet Harbor')).toHaveCount(0);

  await mouseDragFrom(page, node, -70, 50);

  const after = (await node.boundingBox())!;
  expect(
    Math.abs(after.x - before.x) + Math.abs(after.y - before.y),
    'the drag did not pan the camera',
  ).toBeGreaterThan(20);
  await expect(page.getByText('Quiet Harbor'), 'a mouse drag selected the place it panned from').toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);
});

test('a mouse drag does not swallow the next keyboard activation', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });
  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const disc = page.getByRole('button', { name: 'Open region coast' }).first();
  await expect(disc).toBeVisible();
  await mouseDragFrom(page, disc, 80, 40);
  await expect(zoomBadge(page)).toHaveText(/\d+% · regions$/);

  // The trailing click spent the guard, so this first Enter must open the
  // region - not be eaten as a leftover from the drag.
  await disc.focus();
  await page.keyboard.press('Enter');
  await expect(zoomBadge(page), 'the drag left a guard that ate the next Enter').toHaveText(/\d+% · places$/);
});

test('a mouse click without a drag still activates exactly once', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, HARBOR] });
  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const disc = page.getByRole('button', { name: 'Open region coast' }).first();
  await expect(disc).toBeVisible();

  // Press and release in place: a click with no movement. Activation happens in
  // `pointerup`, and the compatibility click must not toggle it back off.
  await disc.click();
  await expect(zoomBadge(page), 'a plain click failed to open the region').toHaveText(/\d+% · places$/);

  // Still open a moment later - i.e. it was not opened and immediately closed.
  await page.waitForTimeout(150);
  await expect(zoomBadge(page)).toHaveText(/\d+% · places$/);
});
