/**
 * The experimental pacing switch, in a real browser.
 *
 * The unit tests already pin down that the mode is sent per request and stored
 * per world. What only a browser can confirm is the part the player actually
 * touches: the switch is off until they turn it on, the copy does not read as
 * "this turn will not be saved", the choice survives a refresh, and a second
 * world is untouched by the first world's choice.
 *
 * The API is mocked, so no provider call and no real world is involved.
 */
import { test, expect, type Page } from '@playwright/test';

const API = 'http://localhost:8000';
const WORLD_A = 'E2E_Pacing_A';
const WORLD_B = 'E2E_Pacing_B';

const playState = {
  protagonist: {
    id: 'char_xueli', name: 'Xueli', location: 'Sect',
    power_stat: { realm: 'Qi Condensation', exp: 0, known_skills: [] },
    traits: {}, knowledge_flags: [], alive: true, relationships: {}, age: '16', inventory: [],
  },
  arc_progress: { current_checkpoint_id: 'cp_0', current_index: 0, total_checkpoints: 1, completed: [] },
  unlocked_cards: [],
  story_clock: { tick: 0 },
  foreshadowing_tracker: [],
  style_card: {},
  output_length: 'Standard',
  lifecycle_status: 'active',
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

/** Read-only endpoints shared by every world under test. */
async function mockWorlds(page: Page, worlds: string[]) {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (url.endsWith('/worlds')) {
      return route.fulfill(json({ worlds: worlds.map((name) => ({ name, status: 'complete' })) }));
    }
    for (const world of worlds) {
      if (url.endsWith(`/worlds/${world}/play-state`)) {
        return route.fulfill(json(playState));
      }
      if (url.endsWith(`/worlds/${world}/chapters`)) {
        return route.fulfill(json([]));
      }
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
}

/** Record the body of every generated turn and answer as if it committed. */
async function captureTurns(page: Page, world: string) {
  const bodies: any[] = [];
  await page.route(`${API}/worlds/${world}/chapter/continue`, async (route) => {
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill(corsPreflight);
    }
    bodies.push(JSON.parse(route.request().postData() || '{}'));
    const turn = bodies.length;
    return route.fulfill(json({
      chapter: {
        chapter_index: 1, turn_index: turn, chapter_closed: false, chapter_title: null,
        checkpoint_id: 'cp_0', user_input: 'action', chapter_text: `Turn ${turn} committed.`,
      },
    }));
  });
  return bodies;
}

const pacingSwitch = (page: Page) => page.getByRole('checkbox', { name: 'Experimental pacing' });

async function send(page: Page, action: string, turn: number) {
  await page.getByPlaceholder(/What do you do/).fill(action);
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(`Turn ${turn} committed.`)).toBeVisible();
}

test('the switch is opt-in, remembered per world, and turns still commit', async ({ page }) => {
  await mockWorlds(page, [WORLD_A, WORLD_B]);
  const turnsA = await captureTurns(page, WORLD_A);
  const turnsB = await captureTurns(page, WORLD_B);

  await page.goto(`/worlds/${WORLD_A}/play`);
  await expect(pacingSwitch(page)).toBeVisible();
  await expect(pacingSwitch(page)).not.toBeChecked();
  await expect(page.getByText('Experimental pacing')).toBeVisible();

  // Default: the request says nothing about a mode at all, so the server takes
  // the classic path even though the client is new.
  await send(page, 'Ask about the harvest.', 1);
  expect(turnsA[0]).not.toHaveProperty('narration_mode');

  await pacingSwitch(page).check();
  // The reassurance has to be on screen while the switch is on: "experimental"
  // must never read as "this turn is only a draft".
  await expect(page.getByText(/still save normally/)).toBeVisible();

  await send(page, 'Share a meal.', 2);
  expect(turnsA[1].narration_mode).toBe('experimental');

  // A refresh keeps this world's choice.
  await page.reload();
  await expect(pacingSwitch(page)).toBeChecked();

  // A different world keeps its own (default) choice.
  await page.goto(`/worlds/${WORLD_B}/play`);
  await expect(pacingSwitch(page)).not.toBeChecked();
  await send(page, 'Say hello.', 1);
  expect(turnsB[0]).not.toHaveProperty('narration_mode');
});
