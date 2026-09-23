import { test, expect, type Locator, type Page } from '@playwright/test';

import { RECENTER_ZOOM, worldToScreen, type Camera } from '../src/components/mapCamera';

/**
 * UI journeys that only a real browser can verify.
 *
 * The unit suite asserts hook logic with jsdom; these tests assert what a
 * player actually sees and clicks: the play surface renders world state, the
 * output-length control reaches the backend, and the canvas map can be driven
 * to a destination and travelled to.
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

/** Same normalisation the map uses: world coordinates are 0..100. */
const norm = (v: number) => Math.max(0, Math.min(1, v / 100));

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
  unlock_realm?: string;
  unlock_exp?: number;
  unlock_reason_missing?: string | null;
};

/**
 * Where the map points its camera when it snaps to a location — on load and
 * when "Recenter" is pressed. Camera x/y are normalised world coordinates and
 * y is flipped to match the canvas, exactly like the component's own recenter,
 * so this stays true even if the protagonist moves.
 */
const recenteredCamera = (current: MapLocation): Camera => ({
  x: norm(current.x),
  y: 1 - norm(current.y),
  zoom: RECENTER_ZOOM,
});

/** The zoom badge is the only text the viewport exposes: "225% · local detail". */
const zoomBadge = (page: Page) => page.getByText(/^\d+% · (regions|local detail)$/);

async function readViewport(page: Page) {
  const badge = zoomBadge(page);
  await expect(badge).toBeVisible();
  const text = await badge.innerText();
  return { text, zoom: Number(text.match(/^(\d+)%/)?.[1]) / 100, detailed: text.includes('local detail') };
}

/**
 * Click a location the way a player has to.
 *
 * The map is a camera viewport, not the static full-world image it used to be:
 * a fixed fraction of the canvas means nothing now, and a node outside the
 * viewport cannot be clicked at all. Nodes are only drawn from 125% zoom, so
 * this zooms out until the destination is genuinely on screen — using the
 * component's own projection, so the coordinates cannot drift from the map.
 */
async function clickMapLocation(page: Page, canvas: Locator, location: MapLocation, camera: Camera) {
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const viewport = await readViewport(page);
    const box = await canvas.boundingBox();
    if (!box) throw new Error('map canvas has no layout box');
    const point = worldToScreen(location, box.width, { ...camera, zoom: viewport.zoom });
    // Leave room for the largest node radius so the node itself is on screen.
    const margin = 12;
    const onScreen = point.x > margin && point.x < box.width - margin && point.y > margin && point.y < box.height - margin;
    if (onScreen && viewport.detailed) {
      await page.mouse.click(box.x + point.x, box.y + point.y);
      return;
    }
    await page.getByRole('button', { name: 'Zoom out' }).click();
    await expect(zoomBadge(page)).not.toHaveText(viewport.text);
  }
  throw new Error(`${location.name} never came into view`);
}

async function openMap(page: Page) {
  // The map lives behind a drawer; a player has to open it before travel is
  // even an option.
  await page.getByTitle('World Map').click();
  await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();
}

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
  route_preview: [],
};

/**
 * A locked destination: reachable, but gated behind a realm the player has not
 * reached yet. Its coordinates sit well outside the window the map shows once
 * it recenters on the protagonist, so reaching it takes a deliberate zoom out.
 */
const DESERT: MapLocation = {
  id: 'desert', name: 'Great Desert', x: 20, y: 80, zone: 'wilds',
  is_unlocked: false, is_reachable: true, discovery_status: 'discovered',
  route_preview: ['Sect Gate', 'Great Desert'],
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
  route_preview: ['Sect Gate', 'Quiet Harbor'],
};

/**
 * Fulfils every request the play surface makes. `locations` is what the map
 * endpoints return, so each test controls the world's geography without a
 * backend, and `travelPreview` is the engine's verdict on a journey.
 */
async function mockPlayApi(page: Page, options: { locations: MapLocation[]; travelPreview?: unknown }) {
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

test('a realm gate is shown on the map before the player tries to travel', async ({ page }) => {
  await mockPlayApi(page, { locations: [GATE, DESERT] });

  await page.goto(`/worlds/${WORLD}/play`);
  await openMap(page);

  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();

  // The map opens zoomed onto the protagonist, which crops the far-off gate out
  // of the viewport entirely; it only becomes clickable after zooming back out.
  await page.getByRole('button', { name: 'Recenter' }).click();
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · local detail`);
  await clickMapLocation(page, canvas, DESERT, recenteredCamera(GATE));

  // Getting there took a deliberate zoom out — the destination was cropped out
  // of the recentered viewport — yet the map is still drawing individual nodes.
  const viewport = await readViewport(page);
  expect(viewport.zoom).toBeLessThan(RECENTER_ZOOM);
  expect(viewport.detailed).toBe(true);

  // Location names are painted into the canvas, so getByText can never see
  // them. The detail panel is the DOM surface that proves what got selected.
  await expect(page.getByText('Great Desert').first()).toBeVisible();
  await expect(page.getByText(/Cần đạt Foundation Establishment/)).toBeVisible();
  // A locked destination must not offer a travel button, or the gate is
  // decorative — the player would hit the rejection only after committing.
  await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);

  // The location the player is standing on stays selectable, but offers no
  // journey — the panel marks it "Here" instead.
  await clickMapLocation(page, canvas, GATE, recenteredCamera(GATE));
  await expect(page.getByText('Here', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);
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
  await expect(zoomBadge(page)).toHaveText(`${Math.round(RECENTER_ZOOM * 100)}% · local detail`);

  // Quiet Harbor sits inside the viewport the map shows around the protagonist,
  // so this is a destination the player can see and click straight away.
  await clickMapLocation(page, canvas, HARBOR, recenteredCamera(GATE));
  await expect(page.getByText('Quiet Harbor').first()).toBeVisible();

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
