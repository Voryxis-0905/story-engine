import { test, expect } from '@playwright/test';

const API = 'http://localhost:8000';
const WORLD = 'E2E_World';

const playState = {
  protagonist: {
    id: 'char_xueli', name: 'Xueli', location: 'Sect',
    power_stat: { realm: 'Qi Condensation', exp: 0, known_skills: [] },
    traits: {}, knowledge_flags: [], alive: true, relationships: {}, age: '16',
  },
  arc_progress: { current_checkpoint_id: 'cp_0', current_index: 0, total_checkpoints: 1, completed: [] },
  unlocked_cards: [],
  story_clock: { tick: 0 },
  foreshadowing_tracker: [],
  style_card: {},
  output_length: 'Standard',
};

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

test.beforeEach(async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (url.endsWith('/worlds')) {
      return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    }
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) {
      return route.fulfill(json(playState));
    }
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) {
      return route.fulfill(json([]));
    }
    if (url.includes('/location-map')) {
      return route.fulfill(json({ locations: [] }));
    }
    if (url.includes('/affinity-graph')) {
      return route.fulfill(json({ nodes: [], edges: [] }));
    }
    if (url.includes('/runtime-config')) {
      return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    }
    return route.fulfill(json({}));
  });
});

test('input survives a failed send, retry commits, and HTML output is inert', async ({ page }) => {
  let continueCalls = 0;
  await page.route(`${API}/worlds/${WORLD}/chapter/continue`, async (route) => {
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill(corsPreflight);
    }
    continueCalls += 1;
    if (continueCalls === 1) {
      return route.fulfill(json({
        detail: { message: 'network hiccup, retry the action', retryable: true, persisted: false },
      }, 503));
    }
    return route.fulfill(json({
      chapter: {
        chapter_index: 1, turn_index: 1, chapter_closed: false, chapter_title: null,
        checkpoint_id: 'cp_0', user_input: 'look around',
        chapter_text: 'Retried action lands. <img src=x onerror="window.__pwned=true">',
      },
    }));
  });

  await page.goto(`/worlds/${WORLD}/play`);
  const input = page.getByPlaceholder(/What do you do/);
  await expect(input).toBeVisible();
  await input.fill('look around');
  await page.getByRole('button', { name: 'Send' }).click();

  await expect(page.getByText('network hiccup, retry the action')).toBeVisible();
  await expect(input).toHaveValue('look around');
  expect(continueCalls).toBe(1);

  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/Retried action lands/)).toBeVisible();
  expect(continueCalls).toBe(2);

  // F02 browser check: injected HTML must never become live DOM or run scripts.
  expect(await page.locator('main img').count()).toBe(0);
  expect(await page.evaluate(() => (window as any).__pwned === true)).toBe(false);
});
