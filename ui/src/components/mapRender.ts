/**
 * Canvas rendering for the story atlas.
 *
 * Only painting happens here: every decision (which places are disclosed, which
 * labels fit, where a route runs) is computed by the pure functions in
 * `mapModel.ts` and handed in. Nothing in this file derives geography the world
 * did not declare - the region discs are hulls around real places, and routes
 * follow the engine's ordered sequence.
 */
import { labelMetrics, placeKind, type AtlasRegion, type LabelPlacement, type MapLocation, type RouteModel } from './mapModel';
import { worldToScreen, type Camera } from './mapCamera';
import { placeRelief, regionRelief, type Relief } from './mapTerrain';

/** One label family per place category, drawn as a neutral pictogram. */
const GLYPHS: Record<string, string> = {
  settlement: '◆',
  interior: '▢',
  landmark: '⬟',
  wild: '🌲',
  water: '≈',
  hazard: '⚠',
  path: '›',
};

const NODE_RADIUS = { current: 9, landmark: 7, normal: 5 } as const;

/** Warm daylight atlas palette; low-contrast so the ink stays readable. */
const PALETTE = {
  paperTop: '#FDF7F1',
  paperMid: '#F7EEF7',
  paperEdge: '#EDE4F8',
  grid: 'rgba(139, 144, 232, .10)',
  regionFill: 'rgba(139, 144, 232, .13)',
  regionFillCurrent: 'rgba(79, 190, 147, .17)',
  regionFocusFill: 'rgba(139, 144, 232, .22)',
  regionLine: 'rgba(106, 111, 214, .44)',
  regionLineFocus: '#6A6FD6',
  regionLabel: '#5B5480',
  regionLabelCurrent: '#2F7A5C',
  node: '#8B90E8',
  nodeLocked: '#B9B3CE',
  nodeCurrent: '#4FBE93',
  nodeRoute: '#D4A322',
  nodeUndiscovered: '#CFC9DE',
  halo: 'rgba(139, 144, 232, .18)',
  haloCurrent: 'rgba(79, 190, 147, .22)',
  haloRoute: 'rgba(212, 163, 34, .22)',
  route: '#D4A322',
  routeSoft: 'rgba(212, 163, 34, .45)',
} as const;

export interface DrawScene {
  size: number;
  camera: Camera;
  locations: MapLocation[];
  regions: AtlasRegion[];
  focusedRegionKey: string | null;
  currentRef?: string;
  hoveredId: string | null;
  selectedId: string | null;
  route: RouteModel | null;
  /** Places that may be drawn as individual nodes. */
  drawnPlaces: MapLocation[];
  /** Region labels that survived collision resolution, in canvas coordinates. */
  regionLabels: Array<{ key: string; name: string; x: number; y: number; radius: number; focus: boolean }>;
  /** Place labels after collision resolution, in canvas coordinates. */
  placeLabels: LabelPlacement[];
  local: boolean;
  /**
   * Discrete motion tick. Ambient animation is a slow, wide step (0 or 1, two
   * seconds apart) instead of a fast loop: it should read as a living map, not
   * as a slideshow, and it is frozen entirely under reduced motion.
   */
  t: number;
}

function regionDisc(region: AtlasRegion, size: number, camera: Camera) {
  const point = worldToScreen({ x: region.center.x * 100, y: (1 - region.center.y) * 100 }, size, camera);
  return { x: point.x, y: point.y, radius: region.radius * size * camera.zoom };
}

function drawPaper(ctx: CanvasRenderingContext2D, size: number) {
  ctx.clearRect(0, 0, size, size);
  const wash = ctx.createRadialGradient(size * .38, size * .3, 0, size / 2, size / 2, size * .85);
  wash.addColorStop(0, PALETTE.paperTop);
  wash.addColorStop(.55, PALETTE.paperMid);
  wash.addColorStop(1, PALETTE.paperEdge);
  ctx.fillStyle = wash;
  ctx.fillRect(0, 0, size, size);
}

/**
 * Faint graticule: a reading aid for the eye, not a claim about terrain.
 * Its spacing follows the zoom so panning reads as movement.
 */
function drawGraticule(ctx: CanvasRenderingContext2D, size: number, camera: Camera) {
  const gap = Math.max(28, 72 * camera.zoom);
  const originX = (0 - camera.x) * size * camera.zoom + size / 2;
  const originY = (0 - camera.y) * size * camera.zoom + size / 2;
  ctx.strokeStyle = PALETTE.grid;
  ctx.lineWidth = 1;
  for (let x = originX % gap; x < size; x += gap) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, size); ctx.stroke();
  }
  for (let y = originY % gap; y < size; y += gap) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(size, y); ctx.stroke();
  }
}

const TERRAIN_WASH: Record<string, [string, string]> = {
  coast: ['#F3F4E8', '#C9DFE9'], water: ['#ECF6FA', '#BDD9ED'],
  plain: ['#F5F0DC', '#DDE6D3'], forest: ['#EEF3E4', '#BED9C4'],
  desert: ['#FAF2DD', '#E9D5AE'], mountain: ['#F7EBDD', '#D8C3B6'],
  wetland: ['#E8F2E8', '#C4DDD5'], urban: ['#F3EEF2', '#D9D3E2'],
};

/**
 * Contour ink is a visual encoding of a *known relative height band*, never a
 * claim that a particular ridge or shoreline has these precise coordinates.
 * The tiny deterministic irregularity avoids plastic concentric rings while
 * keeping every pan/repaint identical and the area outline hit-testable.
 */
function contour(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number, seed: number) {
  ctx.beginPath();
  for (let step = 0; step <= 48; step += 1) {
    const angle = (step / 48) * Math.PI * 2;
    const wobble = 1 + .075 * Math.sin(angle * 3 + seed) + .035 * Math.sin(angle * 7 - seed);
    const px = x + Math.cos(angle) * radius * wobble;
    const py = y + Math.sin(angle) * radius * wobble * .83;
    if (step === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.stroke();
}

function drawRelief(ctx: CanvasRenderingContext2D, disc: { x: number; y: number; radius: number }, relief: Relief, seed: number) {
  if (relief.terrain === 'unknown' && relief.elevation === null && relief.layer === 'unknown') return;
  ctx.save();
  ctx.beginPath();
  ctx.arc(disc.x, disc.y, disc.radius, 0, Math.PI * 2);
  ctx.clip();
  const watery = relief.terrain === 'water' || relief.terrain === 'coast' || relief.terrain === 'wetland';
  if (watery) {
    // Fine wave lines suggest water; they are not drawn as a coastline.
    ctx.strokeStyle = 'rgba(72, 127, 158, .18)';
    ctx.lineWidth = 1;
    for (let offset = -disc.radius; offset <= disc.radius; offset += 19) {
      const y = disc.y + offset;
      ctx.beginPath();
      ctx.moveTo(disc.x - disc.radius, y);
      ctx.quadraticCurveTo(disc.x - disc.radius * .4, y - 5, disc.x, y);
      ctx.quadraticCurveTo(disc.x + disc.radius * .4, y + 5, disc.x + disc.radius, y);
      ctx.stroke();
    }
  }
  const underground = relief.layer === 'underground';
  const raised = relief.elevation !== null && relief.elevation > 0;
  const lowered = relief.elevation !== null && relief.elevation < 0;
  if (underground) {
    // A shaded inset, not a stack of circular "levels" or a claimed cave wall.
    ctx.strokeStyle = 'rgba(88, 69, 109, .14)';
    ctx.lineWidth = 1;
    for (let offset = -disc.radius * 2; offset < disc.radius * 2; offset += 14) {
      ctx.beginPath();
      ctx.moveTo(disc.x + offset, disc.y - disc.radius);
      ctx.lineTo(disc.x + offset + disc.radius, disc.y + disc.radius);
      ctx.stroke();
    }
  }
  const count = raised || lowered ? 2 + Math.abs(relief.elevation!) : 0;
  if (count) {
    ctx.strokeStyle = raised ? 'rgba(124, 90, 65, .32)' : 'rgba(72, 111, 150, .32)';
    ctx.lineWidth = 1.25;
    for (let index = 0; index < count; index += 1) {
      contour(ctx, disc.x + index * 4, disc.y - index * 3,
        disc.radius * (.82 - index * .13), seed + index * .5);
    }
  }
  ctx.restore();
}

/**
 * Region bodies. A soft filled disc with a single hairline ring reads as
 * "somewhere around here", which is exactly what the backend's sparse 0-100
 * coordinates support - anything more detailed would be invented.
 */
function drawRegions(ctx: CanvasRenderingContext2D, scene: DrawScene) {
  const { size, camera, regions, focusedRegionKey } = scene;
  for (const region of regions) {
    const disc = regionDisc(region, size, camera);
    if (disc.x < -disc.radius || disc.x > size + disc.radius || disc.y < -disc.radius || disc.y > size + disc.radius) continue;
    const focused = region.key === focusedRegionKey;
    const relief = regionRelief(region);
    // A halo on the open region while the camera is still close to the overview:
    // it is the one region whose inside is currently reachable.
    if (focused && scene.t) {
      ctx.beginPath();
      ctx.arc(disc.x, disc.y, disc.radius + 4, 0, Math.PI * 2);
      ctx.fillStyle = PALETTE.regionFocusFill;
      ctx.fill();
    }
    ctx.save();
    if (relief.elevation !== null && relief.elevation > 0) {
      ctx.shadowColor = 'rgba(86, 71, 74, .22)';
      ctx.shadowBlur = 13;
      ctx.shadowOffsetY = 7;
    }
    ctx.beginPath();
    ctx.arc(disc.x, disc.y, disc.radius, 0, Math.PI * 2);
    ctx.fillStyle = region.hasCurrent ? PALETTE.regionFillCurrent : focused ? PALETTE.regionFocusFill : PALETTE.regionFill;
    ctx.fill();
    ctx.restore();
    const wash = TERRAIN_WASH[relief.terrain] || (relief.layer === 'underground' ? ['#F0E9F2', '#D8CAE2'] : null);
    if (wash) {
      const gradient = ctx.createRadialGradient(disc.x - disc.radius * .3, disc.y - disc.radius * .35, 0,
        disc.x, disc.y, disc.radius);
      gradient.addColorStop(0, wash[0]);
      gradient.addColorStop(1, wash[1]);
      ctx.beginPath();
      ctx.arc(disc.x, disc.y, disc.radius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.globalAlpha = region.hasCurrent ? .72 : .82;
      ctx.fill();
      ctx.globalAlpha = 1;
    }
    drawRelief(ctx, disc, relief, region.key.length * .37);
    ctx.beginPath();
    ctx.arc(disc.x, disc.y, disc.radius, 0, Math.PI * 2);
    // A focused region gets a solid, heavier ring: visible state, not decoration.
    ctx.strokeStyle = focused ? PALETTE.regionLineFocus : PALETTE.regionLine;
    ctx.lineWidth = focused ? 2 : 1;
    if (!focused) ctx.setLineDash([6, 5]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

/** Named region labels for the legible tiers, already de-overlapped. */
function drawRegionLabels(ctx: CanvasRenderingContext2D, scene: DrawScene) {
  const { regionLabels, regions } = scene;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (const label of regionLabels) {
    const region = regions.find((item) => item.key === label.key);
    const focused = label.focus;
    ctx.font = focused ? '700 13px "Plus Jakarta Sans", sans-serif' : '600 11px "Plus Jakarta Sans", sans-serif';
    const width = ctx.measureText(label.name).width + 16;
    const box = { left: label.x - width / 2, top: label.y, right: label.x + width / 2, bottom: label.y + 20 };
    ctx.fillStyle = focused ? 'rgba(255, 253, 251, .95)' : 'rgba(255, 253, 251, .82)';
    ctx.beginPath();
    ctx.roundRect(box.left, box.top, box.right - box.left, box.bottom - box.top, 8);
    ctx.fill();
    ctx.strokeStyle = focused ? PALETTE.regionLineFocus : 'rgba(139, 144, 232, .35)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = region?.hasCurrent ? PALETTE.regionLabelCurrent : PALETTE.regionLabel;
    ctx.fillText(label.name, label.x, box.top + 10);
  }
}

/** Highlight layer for the previewed route: only adjacent stops of the engine's sequence. */
function drawRoute(ctx: CanvasRenderingContext2D, scene: DrawScene) {
  const { size, camera, route } = scene;
  if (!route || !route.drawable) return;
  ctx.save();
  for (const segment of route.segments) {
    const from = worldToScreen(segment.from, size, camera);
    const to = worldToScreen(segment.to, size, camera);
    // A gentle arc so the line reads as travel, not as a straight road the
    // world never claimed; the bow is a fraction of the drawn length.
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy) || 1;
    const bow = Math.min(46, length * 0.18);
    const midX = (from.x + to.x) / 2 - (dy / length) * bow;
    const midY = (from.y + to.y) / 2 + (dx / length) * bow;

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo(midX, midY, to.x, to.y);
    ctx.strokeStyle = PALETTE.routeSoft;
    ctx.lineWidth = 9;
    ctx.lineCap = 'round';
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.quadraticCurveTo(midX, midY, to.x, to.y);
    ctx.setLineDash([9, 7]);
    ctx.strokeStyle = PALETTE.route;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.setLineDash([]);
  }
  // Direction ticks: without them a bowed dashed line can be read either way.
  for (const segment of route.segments) {
    const from = worldToScreen(segment.from, size, camera);
    const to = worldToScreen(segment.to, size, camera);
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    ctx.save();
    ctx.translate(midX, midY);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(-3, -6);
    ctx.lineTo(5, 0);
    ctx.lineTo(-3, 6);
    ctx.strokeStyle = PALETTE.route;
    ctx.lineWidth = 2.5;
    ctx.stroke();
    ctx.restore();
  }
  ctx.restore();
}

/** Silhouette plus dot for one place, so status is shape + colour, not colour alone. */
function drawPlace(ctx: CanvasRenderingContext2D, scene: DrawScene, location: MapLocation) {
  const { size, camera } = scene;
  const point = worldToScreen(location, size, camera);
  const isCurrent = Boolean(scene.currentRef && (location.id === scene.currentRef || location.name === scene.currentRef));
  const selected = location.id === scene.selectedId;
  const hovered = location.id === scene.hoveredId;
  const onRoute = Boolean(scene.route?.segments.some((segment) => segment.from.id === location.id || segment.to.id === location.id));
  const active = isCurrent || selected || hovered || onRoute;
  const radius = isCurrent ? NODE_RADIUS.current : active || location.is_starting_location ? NODE_RADIUS.landmark : NODE_RADIUS.normal;
  const relief = placeRelief(location);

  // A local height/layer marker remains visible when a mixed region's median
  // is level ground. It encodes only this place, not an invented area boundary.
  if (relief.elevation !== null && relief.elevation !== 0 || relief.layer === 'underground' || relief.layer === 'sky') {
    ctx.save();
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius + 6, 0, Math.PI * 2);
    ctx.strokeStyle = relief.layer === 'underground' ? 'rgba(91, 72, 117, .72)'
      : relief.layer === 'sky' ? 'rgba(94, 135, 170, .72)'
        : relief.elevation! > 0 ? 'rgba(142, 100, 72, .78)' : 'rgba(80, 116, 153, .78)';
    ctx.lineWidth = 2;
    if (relief.layer === 'underground' || relief.elevation! < 0) ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.restore();
  }

  const fill = isCurrent ? PALETTE.nodeCurrent
    : onRoute ? PALETTE.nodeRoute
      : !location.is_unlocked ? PALETTE.nodeLocked
        : PALETTE.node;

  if (active) {
    // The protagonist's halo breathes on the ambient tick; a hover or selection
    // halo is steady, so only the one thing the player owns animates.
    const breathe = isCurrent ? (scene.t ? 2 : 0) : 0;
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius + 9 + breathe, 0, Math.PI * 2);
    ctx.fillStyle = isCurrent ? PALETTE.haloCurrent : onRoute ? PALETTE.haloRoute : PALETTE.halo;
    ctx.fill();
  }

  ctx.lineWidth = isCurrent || selected ? 2.2 : 1.4;
  ctx.strokeStyle = '#FFFDFB';
  const kind = placeKind(location);
  ctx.fillStyle = fill;
  if (kind === 'landmark') {
    // A squat notch: a landmark reads as a built thing without naming a genre.
    ctx.beginPath();
    ctx.roundRect(point.x - radius, point.y - radius, radius * 2, radius * 2, 3);
    ctx.fill();
    ctx.stroke();
  } else if (kind === 'wild') {
    // A burrow: wider than tall, so open ground is distinguishable at a glance.
    ctx.beginPath();
    ctx.ellipse(point.x, point.y, radius * 1.15, radius * .8, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (kind === 'hazard') {
    ctx.beginPath();
    ctx.moveTo(point.x, point.y - radius * 1.25);
    ctx.lineTo(point.x + radius * 1.15, point.y + radius);
    ctx.lineTo(point.x - radius * 1.15, point.y + radius);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  } else if (kind === 'path') {
    // A step block: a passage, not a destination.
    ctx.beginPath();
    ctx.roundRect(point.x - radius * 1.2, point.y - radius * .7, radius * 2.4, radius * 1.4, 3);
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }

  // Status is also spelled out as a pictogram: a locked place keeps its glyph
  // clear of the fill so the two never blend into a third, unreadable colour.
  if (!location.is_unlocked && location.is_reachable === false) {
    ctx.fillStyle = '#FFFDFB';
    ctx.font = '700 10px "Plus Jakarta Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('✕', point.x, point.y);
  } else if (!location.is_unlocked) {
    ctx.fillStyle = '#FFFDFB';
    ctx.font = '700 10px "Plus Jakarta Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(GLYPHS[placeKind(location)] === '≈' ? '~' : '·', point.x, point.y);
  }

  if (selected) {
    ctx.beginPath();
    ctx.arc(point.x, point.y, radius + 5, 0, Math.PI * 2);
    ctx.strokeStyle = PALETTE.regionLineFocus;
    ctx.lineWidth = 1.6;
    ctx.stroke();
  }
}

function drawPlaceLabels(ctx: CanvasRenderingContext2D, scene: DrawScene) {
  ctx.font = labelMetrics.font;
  ctx.textBaseline = 'middle';
  for (const label of scene.placeLabels) {
    const location = scene.locations.find((item) => item.id === label.id);
    // A label may sit over an unplaced node; only use the node for colouring.
    const isCurrent = Boolean(location && scene.currentRef && (location.id === scene.currentRef || location.name === scene.currentRef));
    const selected = label.id === scene.selectedId;
    const width = label.box.right - label.box.left;
    ctx.fillStyle = isCurrent ? 'rgba(233, 250, 242, .96)' : selected ? 'rgba(239, 236, 252, .96)' : 'rgba(255, 253, 251, .92)';
    ctx.beginPath();
    ctx.roundRect(label.box.left, label.box.top, width, label.box.bottom - label.box.top, 7);
    ctx.fill();
    ctx.strokeStyle = isCurrent ? 'rgba(79, 190, 147, .55)' : 'rgba(139, 144, 232, .30)';
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = isCurrent ? '#2F7A5C' : location && !location.is_unlocked ? '#847DA3' : '#453D63';
    ctx.textAlign = 'left';
    ctx.fillText(label.text, label.box.left + labelMetrics.pad, label.box.top + (label.box.bottom - label.box.top) / 2);
  }
}

export function drawScene(ctx: CanvasRenderingContext2D, scene: DrawScene) {
  drawPaper(ctx, scene.size);
  drawGraticule(ctx, scene.size, scene.camera);
  drawRegions(ctx, scene);
  if (!scene.local) drawRegionLabels(ctx, scene);
  drawRoute(ctx, scene);
  for (const location of scene.drawnPlaces) drawPlace(ctx, scene, location);
  drawPlaceLabels(ctx, scene);
}
