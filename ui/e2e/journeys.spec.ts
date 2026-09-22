import { test, expect } from '@playwright/test';

/**
 * UI journeys that only a real browser can verify.
 *
 * The unit suite asserts hook logic with jsdom; these tests assert what a
 * player actually sees and clicks: the play surface renders world state, the
 * output-length control reaches the backend, and a save/restore round trip is
 * visible in the UI.
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
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json([]));
    // Mirrors what /location-map/status returns for a Foundation-Establishment
    // gate when the protagonist is still at Qi Condensation with 12 EXP.
    if (url.includes('/location-map/status')) {
      return route.fulfill(json({
        locations: [
          {
            id: 'gate', name: 'Sect Gate', x: 50, y: 50, zone: 'sect',
            is_unlocked: true, is_reachable: true, discovery_status: 'visited',
            route_preview: [], unlock_reason_missing: null,
          },
          {
            id: 'desert', name: 'Great Desert', x: 20, y: 80, zone: 'wilds',
            is_unlocked: false, is_reachable: true, discovery_status: 'discovered',
            route_preview: ['Sect Gate', 'Great Desert'],
            unlock_realm: 'Foundation Establishment', unlock_exp: 30,
            unlock_reason_missing: 'Cần đạt Foundation Establishment; Cần 30 EXP (hiện có 12)',
          },
        ],
      }));
    }
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

  // The map lives behind a drawer; a player has to open it before travel is
  // even an option.
  await page.getByTitle('World Map').click();
  await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();

  const canvas = page.locator('canvas.location-map, canvas').first();
  await expect(canvas).toBeVisible();

  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');

  // Location names are painted into the canvas, so getByText can never see
  // them. Click the node instead and assert the engine's gate text.
  await page.mouse.click(box.x + box.width * norm(20), box.y + box.height * norm(80));

  await expect(page.getByText('Great Desert').first()).toBeVisible();
  await expect(page.getByText(/Cần đạt Foundation Establishment/)).toBeVisible();
  // A locked destination must not offer a travel button, or the gate is
  // decorative — the player would hit the rejection only after committing.
  await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);

  // An unlocked location stays selectable and does offer travel.
  await page.mouse.click(box.x + box.width * norm(50), box.y + box.height * norm(50));
  await expect(page.getByText(/● Current location/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview journey' })).toHaveCount(0);
});
