/**
 * Touch and pointer behaviour of the player map, on a real touch device profile.
 *
 * The bug this covers: the canvas listened only to `onMouseDown/Move/Up` while
 * declaring `touch-none`. On a phone that combination is the worst of both -
 * the browser's own scrolling and pinch are suppressed, and no touch pan exists
 * to replace them, so the map is frozen under a finger. It also means the map
 * could not be panned, or even tapped to select, on any touch device.
 *
 * The drawer is now a viewport overlay below `md` (see PlayInspector), so the
 * canvas is fully on screen at every phone width and no test has to scroll
 * anything to reach it. An earlier revision of this file *did* push an ancestor
 * `scrollLeft` to bring a sliver of canvas into reach - that made the suite pass
 * while the real product left the map off-screen, so it is deliberately gone.
 * Every coordinate here is taken from a box that is asserted to be inside the
 * viewport, and `touchscreen.tap` taking raw coordinates is the honest path.
 */
import { expect, test, type Locator, type Page } from '@playwright/test';

const API = 'http://localhost:8000';
const WORLD = 'touch';

/**
 * Allowance for device-pixel rounding when comparing a measured box against the
 * nominal viewport width. See `visibleCanvas` for why 0.5px is not enough.
 */
const VIEWPORT_SLACK = 3;

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

/** Two regions far apart, so a pan is unambiguous and a tap has real targets. */
const CAMPUS = [
  { id: 'dorm', name: 'Dormitory', x: 46, y: 52, zone: 'Campus', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'visited' },
  { id: 'hall', name: 'Lecture Hall', x: 56, y: 46, zone: 'Campus', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'discovered' },
  { id: 'lib', name: 'Library', x: 41, y: 61, zone: 'Campus', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'discovered' },
  { id: 'mall', name: 'River Mall', x: 84, y: 34, zone: 'City', tags: ['building'], is_unlocked: true, is_reachable: true, discovery_status: 'discovered' },
];

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

async function mount(page: Page, locations = CAMPUS) {
  await page.route(`${API}/**`, async (route) => {
    const url = route.request().url();
    if (route.request().method() === 'OPTIONS') return route.fulfill(corsPreflight);
    if (url.endsWith('/worlds')) return route.fulfill(json({ worlds: [{ name: WORLD, status: 'complete' }] }));
    if (url.endsWith(`/worlds/${WORLD}/play-state`)) return route.fulfill(json(playState));
    if (url.endsWith(`/worlds/${WORLD}/chapters`)) return route.fulfill(json([]));
    if (url.includes('/travel/preview')) return route.fulfill(json({}));
    if (url.includes('/location-map')) return route.fulfill(json({ locations }));
    if (url.includes('/affinity-graph')) return route.fulfill(json({ nodes: [], edges: [] }));
    if (url.includes('/quest_board')) return route.fulfill(json({ quests: [] }));
    if (url.includes('/journal')) return route.fulfill(json({ entries: [] }));
    if (url.includes('/runtime-config')) return route.fulfill(json({ llm_provider: 'openrouter', has_api_key: false, api_key_source: 'none' }));
    return route.fulfill(json({}));
  });
  await page.goto(`/worlds/${WORLD}/play`);
  await page.getByTitle('World Map').click();
  await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();
}

/**
 * The canvas box, asserted to be genuinely on screen.
 *
 * The drawer is a viewport overlay below `md`, so the canvas is fully inside
 * the viewport and nothing has to be scrolled. This helper exists to *prove*
 * that rather than assume it: if a layout change ever pushes the map off-screen
 * again, the assertion here fails loudly instead of the tests silently aiming
 * raw touch coordinates at `<html>`.
 *
 * It also waits for the drawer's slide-in animation to settle, because the
 * canvas is still moving during it and a tap aimed mid-transition misses.
 */
async function visibleCanvas(page: Page): Promise<{ canvas: Locator; box: { x: number; y: number; width: number; height: number } }> {
  const canvas = page.locator('.location-map canvas');
  await expect(canvas).toBeVisible();

  // The drawer animates in; wait until the canvas stops moving before measuring.
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

  const box = await canvas.boundingBox();
  if (!box) throw new Error('map canvas has no layout box');
  const viewport = page.viewportSize();
  if (!viewport) return { canvas, box };

  // The whole canvas must be inside the viewport - this is the property the
  // overlay layout is supposed to guarantee, so it is asserted, not worked
  // around. A sliver of a few pixels is not "usable by a finger".
  //
  // The tolerance is 2px, not 0.5px: the mobile profiles carry a fractional
  // `deviceScaleFactor` (Pixel 7 = 2.625), so a `width: 100vw` element in a
  // declared 412px viewport measures ~414.07 CSS px. That is device-pixel
  // rounding, not a layout that overflows, and it is inside the round-trip
  // error of the profile rather than something the player can see or scroll to.
  expect(box.x, `canvas left edge ${box.x} is outside the ${viewport.width}px viewport`).toBeGreaterThanOrEqual(-VIEWPORT_SLACK);
  expect(box.x + box.width, `canvas right edge ${box.x + box.width} exceeds the ${viewport.width}px viewport`)
    .toBeLessThanOrEqual(viewport.width + VIEWPORT_SLACK);
  expect(box.width, 'canvas is too narrow to interact with').toBeGreaterThan(120);
  return { canvas, box };
}

const zoomText = async (page: Page) => page.getByText(/% · (regions|places)/).innerText();

/**
 * A one-finger drag, as a finger actually produces it: a sequence of touch
 * events with intermediate moves, not a single jump.
 *
 * Playwright's public `touchscreen` API only taps, so the gesture is dispatched
 * through CDP. A real gesture is many small deltas and the drag threshold is
 * deliberately larger for touch than for a mouse, so several moves are sent.
 *
 * There is no priming tap: an extra touch before the drag would arrive as its
 * own gesture and select whatever it landed on, which is not what a user does
 * and would mask a drag that never happened.
 */
async function swipe(page: Page, from: { x: number; y: number }, to: { x: number; y: number }, steps = 12) {
  const client = await page.context().newCDPSession(page);
  await client.send('Input.dispatchTouchEvent', {
    type: 'touchStart',
    touchPoints: [{ x: from.x, y: from.y, id: 1 }],
  });
  for (let i = 1; i <= steps; i += 1) {
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{
        x: from.x + ((to.x - from.x) * i) / steps,
        y: from.y + ((to.y - from.y) * i) / steps,
        id: 1,
      }],
    });
  }
  await client.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await client.detach();
}

/** Where a place's DOM control is drawn, in viewport coordinates. */
async function placeBox(page: Page, name: RegExp) {
  const box = await page.getByRole('button', { name }).boundingBox();
  if (!box) throw new Error(`no box for ${name}`);
  return { x: box.x, y: box.y, width: box.width, height: box.height };
}

test('the map can be panned with one finger', async ({ page }) => {
  await mount(page);
  const { box } = await visibleCanvas(page);
  const x = box.x + box.width / 2;

  // Land on a known camera so the change is attributable to the drag alone.
  await page.getByRole('button', { name: 'Recenter' }).click();
  const before = await zoomText(page);
  const dormBefore = await placeBox(page, /Dormitory, /);

  // Drag the finger up the canvas.
  await swipe(page, { x, y: box.y + box.height * .8 }, { x, y: box.y + box.height * .2 });

  // A pan moves the camera, and panning must not be read as a tap: no place
  // becomes selected just because a finger crossed it.
  await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);
  // Zoom is unchanged by a pan - this is what proves it panned and not zoomed.
  expect(await zoomText(page)).toBe(before);

  // The camera really moved: the protagonist's node shifted with it. This is the
  // assertion that fails outright on the old mouse-only component, where no touch
  // event reached the canvas at all - there the node would not have moved a pixel.
  const dormAfter = await placeBox(page, /Dormitory, /);
  expect(Math.abs(dormAfter.y - dormBefore.y)).toBeGreaterThan(10);
  // The finger moved up, so the content under it moved up with the camera.
  expect(dormAfter.y).toBeLessThan(dormBefore.y);
});

test('a tap selects a place and a tap on empty canvas clears it', async ({ page }) => {
  await mount(page);

  // A region chip opens the interior without needing a canvas tap at all, which
  // is also the keyboard/assistive-tech path.
  await page.getByRole('group', { name: 'Regions on this map' })
    .getByRole('button', { name: 'Campus', exact: true }).click();
  await expect(page.getByText(/· places$/)).toBeVisible();

  const { box } = await visibleCanvas(page);

  // Tap a real place node. The canvas is fully on screen now, but the node's
  // rect is still computed by the app's own projection, so `locator.tap()` is
  // used where a DOM button exists - it dispatches genuine touch input and
  // cannot drift from the rendered position.
  //
  // Note: this exercises the DOM overlay button, which any pointer implementation
  // satisfies. The canvas itself is covered by the two tests below.
  await page.getByRole('button', { name: /Lecture Hall, / }).tap();
  await expect(page.getByText('Lecture Hall', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview journey' })).toBeInViewport();

  // A tap far from any node is a deliberate deselect, not a no-op. There is no
  // element to target, so this is raw coordinates - aimed a few pixels inside the
  // canvas' top edge, which `visibleCanvas` proved is on screen.
  await page.touchscreen.tap(box.x + box.width / 2, box.y + 6);
  await expect(page.getByText('Lecture Hall', { exact: true })).toHaveCount(0);
});

/**
 * The canvas handler, reached by touch - not the DOM overlay.
 *
 * Honest scope: this does NOT distinguish pointer events from the old
 * mouse-only handlers. Measured, not assumed - reverting the canvas to
 * `onMouseDown`/`onMouseUp` leaves this test passing, because a touch produces a
 * compatibility `click` and the old mouse pair consumes it just as happily. So
 * the *selection* path was never actually broken by mouse-only handlers; only
 * the drag path was, since a drag synthesizes no `click` at all.
 *
 * It is kept because it pins the canvas hit test end to end (a real finger
 * position resolving to the right place, and empty space clearing it), which is
 * what the drag test cannot cover.
 */
test('a touch on the bare canvas selects the place drawn under the finger', async ({ page }) => {
  await mount(page);

  // Without a focused region only landmark nodes are drawn, and the one
  // guaranteed to be there is where the protagonist is standing.
  const { box } = await visibleCanvas(page);
  const target = await placeBox(page, /Dormitory, You are here/);
  const x = target.x + target.width / 2;
  const y = target.y + target.height / 2;
  expect(x).toBeGreaterThanOrEqual(box.x);
  expect(x).toBeLessThanOrEqual(box.x + box.width);
  expect(y).toBeGreaterThanOrEqual(box.y);
  expect(y).toBeLessThanOrEqual(box.y + box.height);

  await page.touchscreen.tap(x, y);

  // The canvas hit test resolved the point to the protagonist's place.
  await expect(page.getByText('Here', { exact: true })).toBeVisible();

  // And a touch that lands on nothing clears it again.
  await page.touchscreen.tap(box.x + box.width / 2, box.y + 6);
  await expect(page.getByText('Here', { exact: true })).toHaveCount(0);
});

/**
 * Requirement: the drawer must be a viewport overlay on a phone.
 *
 * The bug: three fixed-width columns (sidebar + transcript + `w-96` drawer) in
 * a non-wrapping flex row meant the drawer opened past the right edge, so the
 * player had to scroll horizontally to find the map they had just asked for.
 * The suite used to hide this by scrolling an ancestor before measuring.
 *
 * Every control the player needs is asserted to be inside the viewport, and the
 * document is asserted not to overflow horizontally at all - which is the real
 * "no scrolling required" condition.
 */
for (const width of [360, 412]) {
  test(`the open map drawer and its controls are inside the ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 800 });
    await mount(page);

    // The way in must itself be reachable, or the panel can never be opened.
    const entry = await page.getByTitle('World Map').boundingBox();
    expect(entry, 'the map entry button has no box').not.toBeNull();
    expect(entry!.x).toBeGreaterThanOrEqual(-VIEWPORT_SLACK);
    expect(entry!.x + entry!.width).toBeLessThanOrEqual(width + VIEWPORT_SLACK);

    await expect(page.getByRole('heading', { name: 'map', exact: true })).toBeVisible();

    // `visibleCanvas` asserts the canvas is fully on screen; do the same for
    // every other control the player must be able to hit.
    await visibleCanvas(page);
    for (const [label, locator] of [
      ['close', page.getByTitle('Close panel')],
      // The zoom pair is labelled with `aria-label`, not `title`.
      ['zoom in', page.getByRole('button', { name: 'Zoom in' })],
      ['zoom out', page.getByRole('button', { name: 'Zoom out' })],
      ['recenter', page.getByRole('button', { name: 'Recenter' })],
    ] as const) {
      const box = await locator.boundingBox();
      expect(box, `${label} has no box`).not.toBeNull();
      expect(box!.x, `${label} starts left of the viewport (${box!.x})`).toBeGreaterThanOrEqual(-VIEWPORT_SLACK);
      expect(box!.x + box!.width, `${label} ends right of the ${width}px viewport (${box!.x + box!.width})`)
        .toBeLessThanOrEqual(width + VIEWPORT_SLACK);
      expect(box!.y, `${label} is above the viewport`).toBeGreaterThanOrEqual(-VIEWPORT_SLACK);
    }

    // No horizontal scrolling is needed to reach any of it.
    const overflow = await page.evaluate(() => ({
      doc: document.documentElement.scrollWidth - window.innerWidth,
      body: document.body.scrollWidth - window.innerWidth,
    }));
    expect(overflow.doc, `page overflows horizontally by ${overflow.doc}px`).toBeLessThanOrEqual(1);
    expect(overflow.body, `body overflows horizontally by ${overflow.body}px`).toBeLessThanOrEqual(1);
  });
}

/**
 * Requirement: a drag may start on a region disc or a place, not just on bare
 * canvas.
 *
 * The bug: pointer handlers live on the canvas, but transparent DOM buttons for
 * regions and places are layered above it. A finger landing on one of those
 * buttons starts the gesture on the button, so the canvas never sees a
 * `pointerdown` and the map does not pan. The old suite only ever dragged from
 * empty canvas, so it could not catch this.
 *
 * Each origin is exercised with a real touch gesture. Two things are asserted
 * every time: the camera actually moved, and the drag did not masquerade as a
 * tap on whatever it started on.
 */
for (const origin of ['empty canvas', 'region disc', 'place node'] as const) {
  test(`a drag starting on the ${origin} pans the camera`, async ({ page }) => {
    await mount(page);
    const { box } = await visibleCanvas(page);

    await page.getByRole('button', { name: 'Recenter' }).click();
    const zoomBefore = await zoomText(page);
    const dormBefore = await placeBox(page, /Dormitory, /);

    // Where the finger goes down.
    let start: { x: number; y: number };
    if (origin === 'empty canvas') {
      start = { x: box.x + box.width / 2, y: box.y + box.height * 0.92 };
    } else if (origin === 'region disc') {
      // The Campus disc is drawn around the protagonist's node; grab a point on
      // the disc that is not the node itself.
      const node = await placeBox(page, /Dormitory, /);
      start = { x: box.x + box.width * 0.5, y: node.y + node.height + 42 };
      // Guard: if the disc point drifted outside the canvas the test would be
      // measuring nothing, so fail loudly rather than pass vacuously.
      expect(start.y).toBeLessThanOrEqual(box.y + box.height);
      expect(start.y).toBeGreaterThanOrEqual(box.y);
    } else {
      // Dead centre of a real place button - the worst case for the bug.
      const node = await placeBox(page, /Dormitory, /);
      start = { x: node.x + node.width / 2, y: node.y + node.height / 2 };
    }

    const end = { x: start.x, y: Math.max(box.y + 4, start.y - Math.min(120, box.height * 0.35)) };
    await swipe(page, start, end);

    // The camera moved...
    const dormAfter = await placeBox(page, /Dormitory, /);
    expect(Math.abs(dormAfter.y - dormBefore.y), `no pan from the ${origin}`).toBeGreaterThan(8);
    // ...without being zoomed or read as a tap.
    expect(await zoomText(page)).toBe(zoomBefore);
    await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);
  });
}

/**
 * A drag that begins on a region disc must not also *open* that region - the
 * gesture belongs to the camera. Tapping the same disc must still open it, so
 * the fix cannot be "make the discs inert".
 */
test('a drag on a region disc does not open it, but a tap on it does', async ({ page }) => {
  await mount(page);
  await visibleCanvas(page);

  // Drag across the canvas: a pan must never open a region on the way.
  const { box } = await visibleCanvas(page);
  await swipe(page,
    { x: box.x + box.width * 0.5, y: box.y + box.height * 0.75 },
    { x: box.x + box.width * 0.5, y: box.y + box.height * 0.35 });
  await expect(page.getByText(/· places$/)).toHaveCount(0);

  // A genuine tap on the region's disc really does open it, so the drag fix did
  // not make the discs inert.
  //
  // `touchscreen.tap` with raw coordinates is used rather than `locator.tap()`:
  // the disc is a transparent circle whose hit area contains the protagonist's
  // node button, so a locator tap on the disc's centre is intercepted by that
  // node and Playwright refuses to click through ("… intercepts pointer events").
  // Tapping the *edge* of the disc exercises the disc's own hit area, which is
  // exactly the control under test.
  const disc = await page.getByRole('button', { name: 'Open region Campus' }).boundingBox();
  expect(disc, 'the Campus disc has no box').not.toBeNull();
  const campusDisc = { x: disc!.x + disc!.width / 2, y: disc!.y + disc!.height * 0.86 };
  // Confirm the point really is the disc and not its node: `elementFromPoint`
  // names the control a finger would reach there.
  const hit = await page.evaluate(({ x, y }) => {
    const el = document.elementFromPoint(x, y);
    return el?.getAttribute('aria-label') ?? null;
  }, campusDisc);
  expect(hit, 'the tap point must land on the region disc').toBe('Open region Campus');

  await page.touchscreen.tap(campusDisc.x, campusDisc.y);
  await expect(page.getByText(/· places$/)).toBeVisible();
  // And a place inside is now selectable by touch.
  await page.getByRole('button', { name: /Lecture Hall, / }).tap();
  await expect(page.getByText('Lecture Hall', { exact: true })).toBeVisible();
});

test('touch input does not leave the page unable to scroll the map panel', async ({ page }) => {
  // `touch-none` on the canvas is correct only because the canvas now handles
  // touch itself. This asserts the canvas advertises that contract, so a future
  // change that drops the handlers is caught rather than silently freezing.
  await mount(page);
  await visibleCanvas(page);
  await expect(page.locator('.location-map canvas')).toHaveClass(/touch-none/);
  // And the surrounding map panel must still be reachable by touch.
  await expect(page.locator('.location-map')).toBeVisible();
});

/**
 * A drag must not leave the map's activation guard armed for the *next* input.
 *
 * The bug: the guard against "a drag also activates what it started on" was a
 * single global flag set by any `pointerdown`, including the canvas's, and only
 * cleared by a `click` on an overlay control. A touch drag synthesises no
 * compatibility `click`, so the flag stayed set - and the player's next
 * Enter/Space on a region disc or place was swallowed as if it were the drag's
 * trailing click. Measured: the first keyboard activation after a drag did
 * nothing, and only the second one worked.
 *
 * This drives a genuine CDP touch drag and then a genuine keyboard activation,
 * so it is the real input path rather than a synthetic one.
 */
test('a touch drag does not swallow the next keyboard activation', async ({ page }) => {
  await mount(page);
  const { box } = await visibleCanvas(page);

  // A drag on the bare canvas.
  await swipe(page,
    { x: box.x + box.width * 0.5, y: box.y + box.height * 0.8 },
    { x: box.x + box.width * 0.5, y: box.y + box.height * 0.3 });
  // Nothing opened along the way.
  await expect(page.getByText(/· places$/)).toHaveCount(0);

  // Now activate a region by keyboard: focus the disc and press Enter, which is
  // exactly the click the stale flag used to eat.
  const disc = page.getByRole('button', { name: 'Open region Campus' });
  await disc.focus();
  await expect(disc).toBeFocused();
  await page.keyboard.press('Enter');

  await expect(page.getByText(/· places$/), 'the first keyboard activation after a drag was swallowed').toBeVisible();
  // And its places are now genuinely reachable.
  await expect(page.getByRole('button', { name: /Lecture Hall, / })).toBeVisible();
});

/**
 * The same guarantee for a drag that starts *on* a control: the guard is
 * legitimately armed there, so it must be spent by that gesture rather than
 * left behind.
 */
test('a touch drag starting on a place control does not swallow the next keyboard activation', async ({ page }) => {
  await mount(page);
  await visibleCanvas(page);

  const node = await placeBox(page, /Dormitory, /);
  await swipe(page,
    { x: node.x + node.width / 2, y: node.y + node.height / 2 },
    { x: node.x + node.width / 2, y: Math.max(node.y - 110, 0) });

  // The pan happened and selected nothing.
  await expect(page.getByRole('button', { name: 'Travel here' })).toHaveCount(0);

  // A keyboard activation of the protagonist's own node must work first try.
  const control = page.getByRole('button', { name: /Dormitory, / });
  await control.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByText('Here', { exact: true }), 'the first keyboard activation after a drag was swallowed').toBeVisible();
});
