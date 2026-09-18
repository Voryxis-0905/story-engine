import { useRef, useEffect, useState } from 'react';

import { normalizedCoordinate } from './mapCoordinates';

interface Location {
  id: string;
  name: string;
  description?: string;
  x: number;
  y: number;
  zone?: string;
  tags?: string[];
  connected_to?: Array<string | { to?: string; location_id?: string; id?: string; travel_time_minutes?: number; danger?: number }>;
  is_unlocked: boolean;
  unlock_reason_missing?: string | null;
  unlock_realm?: string | null;
  unlock_exp?: number;
  unlock_checkpoint_id?: string | null;
  is_starting_location?: boolean;
  is_reachable?: boolean;
  route_preview?: string[];
}

interface LocationMapProps {
  locations: Location[];
  onSelect?: (id: string) => void;
  onTravel?: (location: Location) => void;
  currentLocation?: string;
}

function drawMap(
  ctx: CanvasRenderingContext2D,
  size: number,
  locs: Location[],
  hoverId: string | null,
  selId: string | null,
) {
  const byId = new Map(locs.map((l) => [l.id, l]));
  const byName = new Map(locs.map((l) => [l.name, l]));
  const resolveLoc = (ref: string): Location | undefined => byId.get(ref) || byName.get(ref);

  ctx.clearRect(0, 0, size, size);

  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size * 0.7);
  grad.addColorStop(0, '#1a1a2e');
  grad.addColorStop(1, '#0a0a12');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  ctx.strokeStyle = '#1a1a2e';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 10; i++) {
    const p = (i / 10) * size;
    ctx.beginPath();
    ctx.moveTo(p, 0);
    ctx.lineTo(p, size);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, p);
    ctx.lineTo(size, p);
    ctx.stroke();
  }

  for (const loc of locs) {
    const from = loc;
    const connIds = loc.connected_to || [];
    for (const connection of connIds) {
      const connRef = typeof connection === 'string'
        ? connection
        : (connection.to || connection.location_id || connection.id || '');
      const to = resolveLoc(connRef);
      if (!to) continue;

      const x1 = normalizedCoordinate(from.x) * size;
      const y1 = normalizedCoordinate(from.y) * size;
      const x2 = normalizedCoordinate(to.x) * size;
      const y2 = normalizedCoordinate(to.y) * size;

      const bothUnlocked = from.is_unlocked && to.is_unlocked;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = bothUnlocked ? '#3a3a5a' : '#18182a';
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  for (const loc of locs) {
    const x = normalizedCoordinate(loc.x) * size;
    const y = normalizedCoordinate(loc.y) * size;
    const isHover = hoverId === loc.id;
    const isSel = selId === loc.id;
    const isUnlocked = loc.is_unlocked;

    if (!isUnlocked) {
      ctx.fillStyle = 'rgba(0,0,0,0.75)';
      ctx.beginPath();
      ctx.arc(x, y, 18, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = '#4a4a5a';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(x, y, 18, 0, Math.PI * 2);
      ctx.stroke();

      ctx.fillStyle = '#5a5a6a';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('đŸ”’', x, y);

      ctx.fillStyle = '#6b7280';
      ctx.font = `${isHover ? '10px' : '8px'} sans-serif`;
      ctx.fillText(loc.name, x, y + 28);
      continue;
    }

    if (isHover || isSel) {
      ctx.shadowColor = '#6366f1';
      ctx.shadowBlur = 20;
    }

    const radius = isHover || isSel ? 12 : 7;
    ctx.fillStyle = isHover || isSel ? '#818cf8' : '#4f46e5';
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    if (loc.is_starting_location) {
      ctx.strokeStyle = '#22c55e';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(x, y, radius + 3, 0, Math.PI * 2);
      ctx.stroke();
    }

    ctx.fillStyle = '#e4e4e7';
    ctx.font = `${isHover ? '11px' : '9px'} sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    ctx.fillText(loc.name, x, y - radius - 6);

    if (loc.zone) {
      ctx.fillStyle = '#6b7280';
      ctx.font = '7px sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText(loc.zone, x, y + radius + 4);
    }
  }
}

export function LocationMap({
  locations,
  onSelect,
  onTravel,
  currentLocation,
}: LocationMapProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const rect = canvas.parentElement?.getBoundingClientRect();
    const size = Math.min(rect?.width || 500, 500);
    canvas.width = size * 2;
    canvas.height = size * 2;
    canvas.style.width = `${size}px`;
    canvas.style.height = `${size}px`;
    ctx.scale(2, 2);

    drawMap(ctx, size, locations, hoveredId, selectedId);
  }, [locations, hoveredId, selectedId]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const size = rect.width;
    const mx = (e.clientX - rect.left) / size;
    const my = (e.clientY - rect.top) / size;

    const found = locations.find((loc) => {
      const dx = normalizedCoordinate(loc.x) - mx;
      const dy = normalizedCoordinate(loc.y) - my;
      return dx * dx + dy * dy < 0.003;
    });
    setHoveredId(found?.id || null);

    if (found && found.is_unlocked && onSelect) {
      canvas.style.cursor = 'pointer';
    } else {
      canvas.style.cursor = 'default';
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const size = rect.width;
    const mx = (e.clientX - rect.left) / size;
    const my = (e.clientY - rect.top) / size;

    const found = locations.find((loc) => {
      const dx = normalizedCoordinate(loc.x) - mx;
      const dy = normalizedCoordinate(loc.y) - my;
      return dx * dx + dy * dy < 0.003;
    });
    if (found) {
      setSelectedId(selectedId === found.id ? null : found.id);
      if (found.is_unlocked && onSelect) onSelect(found.id);
    }
  };

  const selectedLoc = selectedId
    ? (locations.find((l) => l.id === selectedId) || locations.find((l) => l.name === selectedId) || null)
    : null;

  return (
    <div className="location-map space-y-3">
      <h3 className="text-xs font-mono uppercase tracking-wider text-[var(--ink-soft)] font-bold">
        World Map
      </h3>
      <div style={{ position: 'relative' }}>
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredId(null)}
          onClick={handleClick}
          style={{ width: '100%', maxWidth: '500px', aspectRatio: '1/1', borderRadius: '12px' }}
        />
      </div>

      {selectedLoc && (
        <div className="p-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-1.5 text-xs">
          <div className="font-bold text-[var(--ink-main)] text-sm">
            {selectedLoc.name}
          </div>
          {selectedLoc.description && (
            <p className="text-[var(--ink-soft)] leading-relaxed">
              {selectedLoc.description}
            </p>
          )}
          <div className="flex flex-wrap gap-1 pt-1">
            {selectedLoc.zone && (
              <span className="px-2 py-0.5 rounded-full bg-[var(--bg-subtle)] text-[var(--ink-soft)] font-mono text-[10px] border border-[var(--line)]">
                {selectedLoc.zone}
              </span>
            )}
            {selectedLoc.tags?.map((tag) => (
              <span key={tag} className="px-2 py-0.5 rounded-full bg-[rgba(var(--periwinkle-rgb),0.12)] text-[var(--periwinkle-dark)] font-mono text-[10px] border border-[rgba(var(--periwinkle-rgb),0.2)]">
                {tag}
              </span>
            ))}
          </div>
          {selectedLoc.is_starting_location && (
            <div className="text-[var(--ok)] text-[10px] font-bold pt-1">
              â— Starting Location
            </div>
          )}
          {!selectedLoc.is_unlocked && selectedLoc.unlock_reason_missing && (
            <div className="text-[var(--warn)] text-[10px] font-bold pt-1">
              đŸ”’ {selectedLoc.unlock_reason_missing}
            </div>
          )}
          {selectedLoc.route_preview && selectedLoc.route_preview.length > 1 && (
            <p className="text-xs text-[var(--ink-muted)]">
              Route: {selectedLoc.route_preview.join(' → ')}
            </p>
          )}
          {selectedLoc.is_unlocked && ![selectedLoc.id, selectedLoc.name].includes(currentLocation || '') && onTravel && (
            <button
              type="button"
              onClick={() => onTravel(selectedLoc)}
              className="mt-2 w-full rounded-lg bg-[var(--periwinkle-dark)] px-3 py-2 text-xs font-bold text-white hover:opacity-90"
            >
              Travel here
            </button>
          )}
          {[selectedLoc.id, selectedLoc.name].includes(currentLocation || '') && (
            <div className="text-[var(--ok)] text-[10px] font-bold pt-1">● Current location</div>
          )}
        </div>
      )}
    </div>
  );
}
