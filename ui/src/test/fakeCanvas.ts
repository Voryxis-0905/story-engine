/**
 * A minimal 2D context for jsdom.
 *
 * jsdom ships no canvas implementation, so a component that draws returns early
 * and its drawing logic is never exercised. This stub keeps `measureText`
 * behaving like a proportional font, which is what the label layout depends on,
 * and records the calls the map makes so tests can assert on real output.
 */
export interface FakeContext2D {
  ctx: CanvasRenderingContext2D;
  calls: {
    fillTexts: Array<{ text: string; x: number; y: number }>;
    strokes: number;
    arcs: Array<{ x: number; y: number; radius: number }>;
    roundRects: Array<{ x: number; y: number; width: number; height: number }>;
    strokesSeen: string[];
    fillsSeen: string[];
  };
}

/** Rough advance widths (~0.55em) so longer names really do measure wider. */
const CHAR_WIDTH = 6.2;

/**
 * Give every element a real bounding box.
 *
 * jsdom reports a zero-sized rect, which two parts of the map depend on: the
 * container sizes the viewport from its own rect, and pointer conversion reads
 * the canvas rect. If they disagree, a click lands somewhere the node is not
 * drawn. `HTMLCanvasElement` has its own `getBoundingClientRect`, so patching
 * `HTMLElement.prototype` alone leaves canvas reporting zero.
 *
 * `vi.spyOn` is not enough here - the jsdom property does not accept it and the
 * mock silently never runs - so the prototype is redefined directly.
 */
export function stubElementRects(size = 500) {
  const box = () => ({
    width: size, height: size, top: 0, left: 0, right: size, bottom: size, x: 0, y: 0,
    toJSON: () => ({}),
  }) as DOMRect;
  for (const proto of [HTMLElement.prototype, HTMLCanvasElement.prototype]) {
    Object.defineProperty(proto, 'getBoundingClientRect', {
      configurable: true, writable: true, value: box,
    });
  }
}

export function createFakeContext2D(): FakeContext2D {
  const calls: FakeContext2D['calls'] = { fillTexts: [], strokes: 0, arcs: [], roundRects: [], strokesSeen: [], fillsSeen: [] };
  const state: Record<string, unknown> = {};

  const ctx = {
    canvas: { width: 0, height: 0 },
    font: '10px sans-serif',
    fillStyle: '#000',
    strokeStyle: '#000',
    lineWidth: 1,
    lineCap: 'butt',
    lineJoin: 'miter',
    textAlign: 'left',
    textBaseline: 'alphabetic',
    globalAlpha: 1,
    globalCompositeOperation: 'source-over',
    shadowBlur: 0,
    shadowColor: 'transparent',
    shadowOffsetX: 0,
    shadowOffsetY: 0,
    save() { state.saved = true; },
    restore() { state.saved = false; },
    setTransform() {},
    resetTransform() {},
    translate() {},
    rotate() {},
    scale() {},
    beginPath() {},
    closePath() {},
    moveTo() {},
    lineTo() {},
    bezierCurveTo() {},
    quadraticCurveTo() {},
    arc(x: number, y: number, radius: number) { calls.arcs.push({ x, y, radius }); },
    ellipse(x: number, y: number) { calls.arcs.push({ x, y, radius: 0 }); },
    rect() {},
    roundRect(x: number, y: number, width: number, height: number) { calls.roundRects.push({ x, y, width, height }); },
    fill() { calls.fillsSeen.push(String(ctx.fillStyle)); },
    stroke() { calls.strokes += 1; calls.strokesSeen.push(String(ctx.strokeStyle)); },
    clip() {},
    setLineDash() {},
    getLineDash() { return []; },
    measureText(text: string) {
      const width = String(text).length * CHAR_WIDTH;
      return { width, actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 } as TextMetrics;
    },
    fillText(text: string, x: number, y: number) { calls.fillTexts.push({ text: String(text), x, y }); },
    strokeText() {},
    drawImage() {},
    clearRect() {},
    fillRect() {},
    strokeRect() {},
    createLinearGradient() {
      return { addColorStop() {}, _kind: 'linear' };
    },
    createRadialGradient() {
      return { addColorStop() {}, _kind: 'radial' };
    },
    createPattern() { return null; },
    getImageData() { return { data: new Uint8ClampedArray(4), width: 1, height: 1 } as ImageData; },
    putImageData() {},
  };

  return { ctx: ctx as unknown as CanvasRenderingContext2D, calls };
}
