/**
 * Play-screen layout across the widths the product has to work at.
 *
 * The bug this file is built around: the play screen is one non-wrapping flex
 * row (sidebar + transcript + inspector), and the drawer only escaped that row
 * below the `md` breakpoint. At `md` the drawer returned to being the fourth
 * column, which does not fit: a 288px sidebar + 384px drawer + 64px icon strip
 * is 736px of chrome before the transcript gets a single pixel. A map that
 * "opens" into a 90px sliver of prose, with the column itself partly off the
 * right edge, is not an open map.
 *
 * So the widths are enumerated rather than spot-checked, and each one asserts
 * the properties a player actually depends on:
 *   - the way in (the map button) is inside the viewport,
 *   - the open panel and its controls are inside the viewport,
 *   - the transcript has enough room left to read the story in,
 *   - the document does not overflow horizontally at all.
 *
 * `scrollLeft` is deliberately never touched. An earlier revision of the touch
 * suite scrolled an ancestor so an off-screen canvas became measurable, which
 * made the suite pass while the product was still broken.
 */
import { expect, test, type Locator, type Page } from '@playwright/test';

const API = 'http://localhost:8000';
const WORLD = 'layout';

/** Room the transcript must keep before the layout counts as "usable". */
const MIN_READING_WIDTH = 300;
/** Room the transcript must keep specifically at desktop widths. */
const MIN_DESKTOP_READING_WIDTH = 380;
/**
 * Floor for the open map drawer's own panel width.
 *
 * At 360px the panel spans the viewport minus the 64px icon strip = 296px, and
 * the map inside it measures 263px. That is the arithmetic maximum for a phone
 * that narrow, so the floor is set just under it and exists to catch a panel
 * that has collapsed to a sliver - not to demand room the viewport cannot give.
 */
const MIN_PANEL_WIDTH = 250;
/**
 * Allowance for device-pixel rounding. The mobile profiles declare a
 * fractional `deviceScaleFactor` (Pixel 7 = 2.625), so a `100vw` element in a
 * 412px viewport measures ~414.07 CSS px. That is rounding, not overflow.
 */
const SLACK = 3;

const corsPreflight = {
  status: 204,
  headers: {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'GET,POST,OPTIONS',
    'access-control-allow-headers': 'content-type',
  },
  body: '',
};
const json = (body: unknown) => ({
  status: 200,
  headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
  body: JSON.stringify(body),
});

const LOCATIONS = [
  { id: 'dorm', name: 'Dormitory', x: 46, y: 52, zone: 'Campus', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'visited' },
  { id: 'hall', name: 'Lecture Hall', x: 58, y: 44, zone: 'Campus', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'discovered' },
  { id: 'mall', name: 'River Mall', x: 84, y: 34, zone: 'City', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'discovered' },
];

/** A chapter, so the transcript column has real prose to lay out. */
const CHAPTERS = [{
  chapter_index: 1, turn_index: 1, checkpoint_id: 'cp_0',
  user_input: 'Look around.', chapter_text: 'The hall was quiet. '.repeat(40),
}];

const playState = {
  protagonist: {
    id: 'c1', name: 'Xueli', location: 'Dormitory',
    power_stat: { realm: 'Qi Condensation', exp: 12, known_skills: [] },
    traits: {}, knowledge_flags: [], alive: true, relationships: {}, age: '16', inventory: [],
  },
  arc_progress: { current_checkpoint_id: 'cp_0', current_index: 0, total_checkpoints: 2, completed: [] },
  unlocked_cards: [], story_clock: { tick: 3, year: 1, month: 1, day: 3, time_of_day: 'morning' },
  foreshadowing_tracker: [], style_card: {}, output_length: 'Standard', lifecycle_status: 'active',
};

async function mount(page: Page) {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'OPTIONS') return route.fulfill(corsPreflight);
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json(CHAPTERS));
    if (url.includes('/travel/preview')) return route.fulfill(json({}));
    if (url.includes('/location-map')) return route.fulfill(json({ locations: LOCATIONS }));
    if (url.includes('/affinity-graph')) return route.fulfill(json({ nodes: [], edges: [] }));
    if (url.includes('/quest_board')) return route.fulfill(json({ quests: [] }));
    if (url.includes('/journal')) return route.fulfill(json({ entries: [] }));
    if (url.includes('/runtime-config')) return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    return route.fulfill(json({}));
  });
  await page.goto(`/worlds/${WORLD}/play`);
  await expect(page.getByRole('button', { name: 'Start Chapter' })).toBeVisible();
}

/** The prose column: its width is what the layout is ultimately protecting. */
const transcript = (page: Page) => page.getByRole('main').last();

async function boxOf(locator: Locator, label: string) {
  const box = await locator.boundingBox();
  expect(box, `${label} has no layout box`).not.toBeNull();
  return box!;
}

function expectInsideViewport(box: { x: number; width: number; y: number }, viewportWidth: number, label: string) {
  expect(box.x, `${label} starts left of the viewport (x=${box.x})`).toBeGreaterThanOrEqual(-SLACK);
  expect(box.x + box.width, `${label} ends right of the ${viewportWidth}px viewport (right=${box.x + box.width})`)
    .toBeLessThanOrEqual(viewportWidth + SLACK);
  expect(box.y, `${label} sits above the viewport (y=${box.y})`).toBeGreaterThanOrEqual(-SLACK);
}

/** `document.body.scrollWidth` past the viewport is exactly "you must scroll sideways". */
async function expectNoHorizontalOverflow(page: Page, label: string) {
  const overflow = await page.evaluate(() => ({
    doc: document.documentElement.scrollWidth - window.innerWidth,
    body: document.body.scrollWidth - window.innerWidth,
  }));
  expect(overflow.doc, `${label}: page overflows horizontally by ${overflow.doc}px`).toBeLessThanOrEqual(1);
  expect(overflow.body, `${label}: body overflows horizontally by ${overflow.body}px`).toBeLessThanOrEqual(1);
}

/**
 * One row per width the reviewer asked about. `minReading` is the transcript
 * floor; the two desktop widths that used to break are held to the desktop
 * number so the regression cannot come back as "technically 300px".
 */
const WIDTHS = [
  { width: 360, minReading: 260 },
  { width: 412, minReading: 300 },
  { width: 768, minReading: MIN_DESKTOP_READING_WIDTH },
  { width: 820, minReading: MIN_DESKTOP_READING_WIDTH },
  { width: 1024, minReading: MIN_DESKTOP_READING_WIDTH },
];

for (const { width, minReading } of WIDTHS) {
  test(`layout is usable at ${width}px with the map closed`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);

    // The entry point to the panel must be reachable, or nothing else matters.
    expectInsideViewport(await boxOf(page.getByTitle('World Map'), 'map entry button'), width, 'map entry button');

    // The prose column keeps real reading room.
    const prose = await boxOf(transcript(page), 'transcript');
    expectInsideViewport(prose, width, 'transcript');
    expect(prose.width, `transcript only has ${prose.width}px to read in at ${width}px`).toBeGreaterThanOrEqual(minReading);

    // The composer - the thing the player types into - is fully usable.
    const composer = page.getByPlaceholder(/What do you do/);
    expectInsideViewport(await boxOf(composer, 'composer'), width, 'composer');

    await expectNoHorizontalOverflow(page, `${width}px, map closed`);
  });

  test(`layout is usable at ${width}px with the map open`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await page.getByTitle('World Map').click();
    await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();

    // Wait for the drawer's slide-in to settle before measuring anything.
    await page.waitForFunction(() => {
      const el = document.querySelector('.location-map canvas');
      if (!el) return false;
      const first = el.getBoundingClientRect().x;
      return new Promise<boolean>((resolve) => {
        requestAnimationFrame(() => {
          const second = document.querySelector('.location-map canvas')!.getBoundingClientRect().x;
          resolve(Math.abs(first - second) < 0.5);
        });
      });
    });

    // Every control the player needs to operate the map.
    const panelBox = await boxOf(page.locator('.location-map').first(), 'map panel');
    expectInsideViewport(panelBox, width, 'map panel');
    expect(panelBox.width, `map panel is only ${panelBox.width}px wide at ${width}px`).toBeGreaterThanOrEqual(MIN_PANEL_WIDTH);

    for (const [label, locator] of [
      ['close button', page.getByTitle('Close panel')],
      ['zoom in', page.getByRole('button', { name: 'Zoom in' })],
      ['zoom out', page.getByRole('button', { name: 'Zoom out' })],
      ['recenter', page.getByRole('button', { name: 'Recenter' })],
    ] as const) {
      expectInsideViewport(await boxOf(locator, label), width, label);
      await expect(locator).toBeEnabled();
    }

    const canvas = await boxOf(page.locator('.location-map canvas'), 'canvas');
    expectInsideViewport(canvas, width, 'canvas');
    expect(canvas.width, `canvas is only ${canvas.width}px wide at ${width}px`).toBeGreaterThan(120);

    // At desktop widths the transcript stays visible next to the drawer, so the
    // story the player is reading is never fully covered.
    if (width >= 768) {
      const prose = await boxOf(transcript(page), 'transcript');
      expect(prose.width, `transcript is down to ${prose.width}px with the map open at ${width}px`)
        .toBeGreaterThanOrEqual(minReading);
    }

    await expectNoHorizontalOverflow(page, `${width}px, map open`);
  });
}

/**
 * The map entry point must stay reachable *while a panel is open* too - the
 * mobile overlay covers the viewport, so the strip has to sit above it, and the
 * desktop column must not be pushed off the right edge by its own drawer.
 */
test('the icon strip stays on screen while the map is open', async ({ page }) => {
  for (const width of [360, 412, 768, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);
    await page.getByTitle('World Map').click();
    await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();
    expectInsideViewport(await boxOf(page.getByTitle('World Map'), 'map entry button'), width, `map entry at ${width}px`);
    // Switching panels from the strip must actually work, not just be visible.
    await page.getByTitle('Inventory').click();
    await expect(page.getByRole('heading', { name: 'inventory', exact: true })).toBeVisible();
    await page.getByTitle('World Map').click();
    await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();
    await expectNoHorizontalOverflow(page, `${width}px after switching panels`);
  }
});

/**
 * The World State rail.
 *
 * The bug: below `xl` the rail was a dead control. It flipped `sidebarOpen`,
 * the chevron turned and the label changed to "Collapse sidebar", while the
 * content stayed `hidden xl:block` and never appeared - so a player on a phone
 * or a tablet had no way at all to read World State, and the button reported a
 * state it could not reach. The fix makes the panel a real overlay below `xl`
 * and keeps the in-flow column at `xl` and up.
 *
 * These tests drive the toggle the way a player does, and check the two things
 * the overlay exists to protect: the prose column loses nothing, and the map
 * entry point is still genuinely clickable (not merely inside the viewport).
 */
for (const width of [360, 768, 1024]) {
  test(`the world state rail opens and closes at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mount(page);

    const panel = page.getByRole('region', { name: 'World State' });
    const proseWidth = async () => (await boxOf(transcript(page), 'transcript')).width;

    // It starts closed, and the button says so.
    await expect(panel).toHaveCount(0);
    const expand = page.getByRole('button', { name: 'Expand sidebar' });
    await expect(expand).toBeVisible();
    await expect(expand).toHaveAttribute('aria-expanded', 'false');
    const proseClosed = await proseWidth();

    // First click: the content the button promised is really there.
    await expand.click();
    await expect(panel).toBeVisible();
    await expect(panel.getByText('Story Timeline')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Collapse sidebar' })).toHaveAttribute('aria-expanded', 'true');

    expectInsideViewport(await boxOf(panel, 'world state panel'), width, 'world state panel');

    // The whole point of an overlay: it costs the prose column nothing.
    expect(await proseWidth(), 'opening world state squeezed the transcript').toBe(proseClosed);

    // The map entry point is not just inside the viewport - it still receives
    // the click. `trial: true` runs every actionability check without clicking,
    // so a panel covering the button fails here.
    const mapEntry = page.getByTitle('World Map');
    expectInsideViewport(await boxOf(mapEntry, 'map entry button'), width, 'map entry button');
    await mapEntry.click({ trial: true });

    await expectNoHorizontalOverflow(page, `${width}px with world state open`);

    // Second click on the same control closes it again.
    await page.getByRole('button', { name: 'Collapse sidebar' }).click();
    await expect(panel).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Expand sidebar' })).toBeVisible();
    expect(await proseWidth()).toBe(proseClosed);
  });
}

test('the desktop world state column is unchanged at 1280px', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await mount(page);

  // Desktop has always opened with the column showing, and it is in flow - not
  // an overlay - so it starts at the left edge and takes real width.
  const panel = page.getByRole('region', { name: 'World State' });
  await expect(panel).toBeVisible();
  await expect(page.getByRole('button', { name: 'Collapse sidebar' })).toHaveAttribute('aria-expanded', 'true');

  const panelBox = await boxOf(panel, 'world state column');
  expectInsideViewport(panelBox, 1280, 'world state column');
  expect(panelBox.x, `desktop world state is offset to x=${panelBox.x}`).toBeLessThanOrEqual(SLACK);
  expect(panelBox.width, `desktop world state column collapsed to ${panelBox.width}px`).toBeGreaterThan(240);

  const prose = await boxOf(transcript(page), 'transcript');
  expect(prose.width).toBeGreaterThanOrEqual(MIN_DESKTOP_READING_WIDTH);
  await expectNoHorizontalOverflow(page, '1280px with world state open');

  // Collapsing is a real 288px handover, not a no-op.
  await page.getByRole('button', { name: 'Collapse sidebar' }).click();
  await expect(panel).toHaveCount(0);
  await expect.poll(async () => (await boxOf(transcript(page), 'transcript')).width,
    { message: 'collapsing the column did not give the room back' }).toBeGreaterThan(prose.width);
});
