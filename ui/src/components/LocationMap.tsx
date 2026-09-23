import { useEffect, useId, useRef, useState } from 'react';

import { normalizedCoordinate } from './mapCoordinates';
import { KEY_PAN_PIXELS, RECENTER_ZOOM, panCamera, worldToScreen, zoomCamera, type Camera } from './mapCamera';
import type { TravelPreview } from '../api/client';

interface Location {
  id: string;
  name: string;
  description?: string;
  x: number;
  y: number;
  zone?: string;
  tags?: string[];
  connected_to?: Array<string | { to?: string; location_id?: string; id?: string }>;
  is_unlocked: boolean;
  unlock_reason_missing?: string | null;
  is_starting_location?: boolean;
  route_preview?: string[];
}

interface LocationMapProps {
  locations: Location[];
  onTravel?: (location: Location) => void;
  onPreview?: (location: Location) => void;
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

function locationMatches(location: Location, reference?: string) {
  return Boolean(reference && (location.id === reference || location.name === reference));
}

function zoneName(location: Location) {
  if (location.zone) return location.zone;
  return location.name.split(/\s[-—]\s/)[0] || 'Uncharted';
}

function drawMap(ctx: CanvasRenderingContext2D, size: number, locations: Location[], camera: Camera,
  hoveredId: string | null, selectedId: string | null, currentLocation?: string, route: string[] = []) {
  const byReference = new Map<string, Location>();
  locations.forEach((location) => { byReference.set(location.id, location); byReference.set(location.name, location); });
  const point = (location: Location) => worldToScreen(location, size, camera);
  const isRoute = (location: Location) => route.includes(location.id) || route.includes(location.name);

  ctx.clearRect(0, 0, size, size);
  const background = ctx.createRadialGradient(size * .45, size * .35, 0, size / 2, size / 2, size * .82);
  background.addColorStop(0, '#2b3159'); background.addColorStop(.55, '#171b35'); background.addColorStop(1, '#090b18');
  ctx.fillStyle = background; ctx.fillRect(0, 0, size, size);

  const gridGap = 80 * camera.zoom;
  const origin = point({ id: '', name: '', x: 0, y: 0, is_unlocked: false });
  ctx.strokeStyle = 'rgba(175, 189, 255, .07)'; ctx.lineWidth = 1;
  for (let x = origin.x % gridGap; x < size; x += gridGap) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, size); ctx.stroke(); }
  for (let y = origin.y % gridGap; y < size; y += gridGap) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(size, y); ctx.stroke(); }

  const drawnEdges = new Set<string>();
  locations.forEach((from) => (from.connected_to || []).forEach((connection) => {
    const ref = typeof connection === 'string' ? connection : (connection.to || connection.location_id || connection.id || '');
    const to = byReference.get(ref); if (!to) return;
    const key = [from.id, to.id].sort().join(':'); if (drawnEdges.has(key)) return; drawnEdges.add(key);
    const a = point(from); const b = point(to); const onRoute = isRoute(from) && isRoute(to);
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = onRoute ? 'rgba(255, 208, 104, .95)' : 'rgba(160, 178, 240, .30)'; ctx.lineWidth = onRoute ? 3 : 1.2;
    ctx.setLineDash(onRoute ? [5, 5] : []); ctx.stroke(); ctx.setLineDash([]);
  }));

  if (camera.zoom < 1.25) {
    const zones = new Map<string, Location[]>();
    locations.forEach((location) => zones.set(zoneName(location), [...(zones.get(zoneName(location)) || []), location]));
    zones.forEach((members, name) => {
      const average = members.reduce((sum, location) => { const p = point(location); return { x: sum.x + p.x, y: sum.y + p.y }; }, { x: 0, y: 0 });
      const x = average.x / members.length; const y = average.y / members.length; const radius = 17 + Math.min(members.length, 8) * 2;
      ctx.fillStyle = 'rgba(120, 137, 255, .16)'; ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(177, 190, 255, .55)'; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = '#edf0ff'; ctx.font = '600 11px sans-serif'; ctx.textAlign = 'center'; ctx.fillText(name, x, y + radius + 14);
    });
    return;
  }

  const labelBoxes: Array<{ left: number; top: number; right: number; bottom: number }> = [];
  const collides = (left: number, top: number, right: number, bottom: number) => labelBoxes.some((box) => left < box.right && right > box.left && top < box.bottom && bottom > box.top);
  locations.forEach((location) => {
    const { x, y } = point(location); if (x < -28 || x > size + 28 || y < -28 || y > size + 28) return;
    const isCurrent = locationMatches(location, currentLocation); const isHovered = hoveredId === location.id; const isSelected = selectedId === location.id;
    const active = isCurrent || isHovered || isSelected || isRoute(location); const radius = isCurrent ? 9 : active ? 7 : 5;
    if (active) { ctx.fillStyle = isCurrent ? 'rgba(117, 244, 180, .24)' : 'rgba(140, 158, 255, .18)'; ctx.beginPath(); ctx.arc(x, y, radius + 8, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillStyle = !location.is_unlocked ? '#566075' : isCurrent ? '#6ee7b7' : isRoute(location) ? '#f6c763' : active ? '#b7c3ff' : '#7889dc';
    ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = !location.is_unlocked ? '#8992aa' : '#edf0ff'; ctx.lineWidth = active ? 1.5 : 1; ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2); ctx.stroke();
    if (!location.is_unlocked) { ctx.fillStyle = '#d5d8e3'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText('🔒', x, y + .5); }
    if (!(active || camera.zoom >= 2.25)) return;
    ctx.font = '600 11px sans-serif'; const text = location.name.length > 26 ? `${location.name.slice(0, 25)}…` : location.name; const width = ctx.measureText(text).width + 12; const left = x - width / 2; const top = y - radius - 27; const forceLabel = isCurrent || isHovered || isSelected;
    if (!forceLabel && collides(left, top, left + width, top + 19)) return;
    labelBoxes.push({ left, top, right: left + width, bottom: top + 19 }); ctx.fillStyle = 'rgba(7, 9, 23, .82)'; ctx.beginPath(); ctx.roundRect(left, top, width, 19, 7); ctx.fill(); ctx.fillStyle = '#f5f6ff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(text, x, top + 10);
  });
}

export function LocationMap({ locations, onTravel, onPreview, travelPreview, previewLoading, currentLocation }: LocationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const instructionsId = useId();
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [camera, setCamera] = useState<Camera>({ x: .5, y: .5, zoom: 1 });

  useEffect(() => {
    const current = locations.find((location) => locationMatches(location, currentLocation));
    if (current) setCamera({ x: normalizedCoordinate(current.x), y: 1 - normalizedCoordinate(current.y), zoom: RECENTER_ZOOM });
  }, [currentLocation, locations]);
  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    const size = Math.min(canvas.parentElement?.getBoundingClientRect().width || 500, 500); const scale = window.devicePixelRatio || 1;
    canvas.width = size * scale; canvas.height = size * scale; canvas.style.width = `${size}px`; canvas.style.height = `${size}px`;
    const ctx = canvas.getContext('2d'); if (!ctx) return; ctx.setTransform(scale, 0, 0, scale, 0, 0);
    drawMap(ctx, size, locations, camera, hoveredId, selectedId, currentLocation, travelPreview?.route || []);
  }, [locations, camera, hoveredId, selectedId, currentLocation, travelPreview]);

  const pointerLocation = (event: React.MouseEvent<HTMLCanvasElement>) => { const rect = canvasRef.current!.getBoundingClientRect(); return { x: event.clientX - rect.left, y: event.clientY - rect.top, size: rect.width }; };
  const findAtPointer = (event: React.MouseEvent<HTMLCanvasElement>) => { const pointer = pointerLocation(event); return locations.find((location) => { const point = worldToScreen(location, pointer.size, camera); return Math.hypot(point.x - pointer.x, point.y - pointer.y) < 16; }); };
  const zoomBy = (factor: number) => setCamera((value) => zoomCamera(value, factor));
  const recenter = () => { const current = locations.find((location) => locationMatches(location, currentLocation)); setCamera(current ? { x: normalizedCoordinate(current.x), y: 1 - normalizedCoordinate(current.y), zoom: RECENTER_ZOOM } : { x: .5, y: .5, zoom: 1 }); };
  const selectedLoc = selectedId ? locations.find((location) => location.id === selectedId) || null : null;

  // Keyboard parity with the pointer: arrows pan, +/- zoom, Home recenters, Escape clears the selection.
  const onKeyDown = (event: React.KeyboardEvent<HTMLCanvasElement>) => {
    const key = event.key;
    if (key === '+' || key === '=') { event.preventDefault(); zoomBy(ZOOM_IN_FACTOR); return; }
    if (key === '-' || key === '_') { event.preventDefault(); zoomBy(ZOOM_OUT_FACTOR); return; }
    if (key === 'Home') { event.preventDefault(); recenter(); return; }
    if (key === 'Escape') { setSelectedId(null); return; }
    const direction = PAN_KEYS[key];
    if (!direction) return;
    event.preventDefault();
    const size = canvasRef.current?.getBoundingClientRect().width || 0;
    setCamera((value) => panCamera(value, direction[0] * KEY_PAN_PIXELS, direction[1] * KEY_PAN_PIXELS, size));
  };

  return <section className="location-map space-y-3" aria-label="World map">
    <div className="flex items-end justify-between gap-3"><div><h3 className="text-xs font-mono uppercase tracking-wider text-[var(--ink-soft)] font-bold">Atlas</h3><p className="mt-1 text-[11px] text-[var(--ink-muted)]">Drag to explore · scroll to zoom · select a destination</p></div><button type="button" onClick={recenter} className="rounded-lg border border-[var(--line)] px-2 py-1 text-[10px] font-bold text-[var(--ink-soft)] hover:bg-[var(--bg-subtle)]">Recenter</button></div>
    <div className="relative overflow-hidden rounded-2xl border border-[#3d4874] shadow-[0_16px_35px_rgba(35,42,96,.22)]">
      <canvas ref={canvasRef} tabIndex={0} role="application" aria-label="Interactive world map" aria-describedby={instructionsId} aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Home Escape + -" onKeyDown={onKeyDown} onMouseDown={(event) => { const p = pointerLocation(event); dragRef.current = { x: p.x, y: p.y, moved: false }; }} onMouseMove={(event) => { const drag = dragRef.current; const p = pointerLocation(event); if (drag) { const dx = p.x - drag.x; const dy = p.y - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true; dragRef.current = { ...drag, x: p.x, y: p.y }; setCamera((value) => panCamera(value, -dx, -dy, p.size)); return; } const found = findAtPointer(event); setHoveredId(found?.id || null); event.currentTarget.style.cursor = found ? 'pointer' : 'grab'; }} onMouseUp={(event) => { const dragged = dragRef.current?.moved; dragRef.current = null; if (dragged) return; const found = findAtPointer(event); if (found) setSelectedId((id) => id === found.id ? null : found.id); }} onMouseLeave={() => { dragRef.current = null; setHoveredId(null); }} onWheel={(event) => { event.preventDefault(); zoomBy(event.deltaY < 0 ? ZOOM_IN_FACTOR : ZOOM_OUT_FACTOR); }} className="block w-full touch-none cursor-grab focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[#9db0ff]" />
      <p id={instructionsId} className="sr-only">Interactive world map. With a keyboard: arrow keys pan, plus and minus zoom, Home recenters on your character, and Escape clears the selected location. With a pointer: drag to pan, scroll to zoom, and click a location to select it.</p>
      <div className="absolute right-3 top-3 flex flex-col overflow-hidden rounded-lg border border-white/15 bg-[#0d1128]/90 shadow-lg"><button type="button" onClick={() => zoomBy(1.25)} className="h-8 w-8 text-lg font-bold text-white hover:bg-white/10" aria-label="Zoom in">+</button><button type="button" onClick={() => zoomBy(.8)} className="h-8 w-8 border-t border-white/15 text-lg font-bold text-white hover:bg-white/10" aria-label="Zoom out">−</button></div>
      <div className="absolute bottom-3 left-3 rounded-full border border-white/10 bg-[#0d1128]/85 px-2.5 py-1 text-[10px] font-semibold text-[#dce2ff]">{Math.round(camera.zoom * 100)}% · {camera.zoom < 1.25 ? 'regions' : 'local detail'}</div>
    </div>
    <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-[var(--ink-muted)]"><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#6ee7b7]" />You are here</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#f6c763]" />Route</span><span><i className="mr-1 inline-block h-2 w-2 rounded-full bg-[#7889dc]" />Discovered</span></div>
    {selectedLoc && <div className="rounded-xl border border-[var(--line)] bg-[var(--bg-surface)] p-3 text-xs shadow-sm space-y-2"><div className="flex items-start justify-between gap-3"><div><div className="font-bold text-[var(--ink-main)] text-sm">{selectedLoc.name}</div><div className="mt-.5 text-[10px] font-mono text-[var(--ink-muted)]">{zoneName(selectedLoc)}</div></div>{locationMatches(selectedLoc, currentLocation) && <span className="rounded-full bg-[rgba(74,222,128,.12)] px-2 py-.5 text-[10px] font-bold text-[var(--ok)]">Here</span>}</div>{selectedLoc.description && <p className="text-[var(--ink-soft)] leading-relaxed">{selectedLoc.description}</p>}{!selectedLoc.is_unlocked && selectedLoc.unlock_reason_missing && <div className="text-[var(--warn)] text-[10px] font-bold">🔒 {selectedLoc.unlock_reason_missing}</div>}{travelPreview?.destination === selectedLoc.name && <div className="rounded-lg border border-[var(--line)] bg-[var(--bg-subtle)] p-2 leading-relaxed"><div>Estimated time: {travelPreview.elapsed_minutes} minutes</div><div>Risk: {travelPreview.risk?.level || 'unknown'}</div>{travelPreview.route.length > 1 && <div>Route: {travelPreview.route.join(' → ')}</div>}</div>}{selectedLoc.is_unlocked && !locationMatches(selectedLoc, currentLocation) && onPreview && <button type="button" disabled={previewLoading} onClick={() => onPreview(selectedLoc)} className="w-full rounded-lg border border-[var(--line)] px-3 py-2 text-xs font-bold hover:bg-[var(--bg-subtle)] disabled:opacity-50">{previewLoading ? 'Checking route…' : 'Preview journey'}</button>}{travelPreview?.destination === selectedLoc.name && travelPreview.status === 'available' && onTravel && <button type="button" onClick={() => onTravel(selectedLoc)} className="w-full rounded-lg bg-[var(--periwinkle-dark)] px-3 py-2 text-xs font-bold text-white hover:opacity-90">Travel here</button>}</div>}
  </section>;
}
