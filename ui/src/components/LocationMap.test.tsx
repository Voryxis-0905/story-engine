import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { LocationMap } from './LocationMap';
import { KEY_PAN_PIXELS } from './mapCamera';
import { normalizedCoordinate } from './mapCoordinates';

describe('LocationMap coordinates', () => {
  it('normalizes backend 0-100 coordinates for canvas drawing and hit testing', () => {
    expect(normalizedCoordinate(0)).toBe(0);
    expect(normalizedCoordinate(20)).toBe(0.2);
    expect(normalizedCoordinate(100)).toBe(1);
    expect(normalizedCoordinate(140)).toBe(1);
  });
});

const SIZE = 500;
const CENTER = SIZE / 2;

const LOCATION = {
  id: 'loc_fog_harbor',
  name: 'Fog Harbor',
  description: 'Docks wrapped in cold mist.',
  x: 50,
  y: 50,
  zone: 'Outer Reach',
  is_unlocked: true,
};

describe('LocationMap keyboard interaction', () => {
  beforeEach(() => {
    // jsdom has no canvas implementation; the component already tolerates a null context.
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  });

  const setup = (props: Record<string, unknown> = {}) => {
    const { container } = render(<LocationMap locations={[LOCATION]} {...props} />);
    const canvas = container.querySelector('canvas') as HTMLCanvasElement;
    // jsdom reports a zero-sized box; the component derives its viewport and hit tests from it.
    canvas.getBoundingClientRect = () => ({
      width: SIZE, height: SIZE, top: 0, left: 0, right: SIZE, bottom: SIZE, x: 0, y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
    return canvas;
  };

  const press = (canvas: HTMLCanvasElement, key: string) => fireEvent.keyDown(canvas, { key });
  const clickAt = (canvas: HTMLCanvasElement, x: number, y: number) => {
    fireEvent.mouseDown(canvas, { clientX: x, clientY: y });
    fireEvent.mouseUp(canvas, { clientX: x, clientY: y });
  };
  // The zoom readout is the user-visible projection of the camera state.
  const zoomLabel = () => screen.getByText(/% · (regions|local detail)/).textContent;

  it('is focusable and describes its keyboard controls', () => {
    const canvas = setup();

    expect(canvas).toHaveAttribute('tabindex', '0');
    expect(canvas).toHaveAttribute('role', 'application');
    expect(screen.getByLabelText('Interactive world map')).toBe(canvas);

    canvas.focus();
    expect(canvas).toHaveFocus();

    const instructions = document.getElementById(canvas.getAttribute('aria-describedby') || '');
    expect(instructions).not.toBeNull();
    expect(instructions?.textContent).toMatch(/arrow keys pan/i);
    expect(instructions?.textContent).toMatch(/Home recenters/i);
    expect(instructions?.textContent).toMatch(/Escape clears/i);
  });

  it('zooms in with + and =, and out with - and _', () => {
    const canvas = setup();

    expect(zoomLabel()).toBe('100% · regions');
    press(canvas, '+');
    expect(zoomLabel()).toBe('116% · regions');
    press(canvas, '=');
    expect(zoomLabel()).toBe('135% · local detail');
    press(canvas, '-');
    expect(zoomLabel()).toBe('116% · regions');
    press(canvas, '_');
    expect(zoomLabel()).toBe('100% · regions');
  });

  it('clamps keyboard zoom at both ends of the range', () => {
    const canvas = setup();

    for (let i = 0; i < 12; i += 1) press(canvas, '-');
    expect(zoomLabel()).toBe('65% · regions');

    for (let i = 0; i < 20; i += 1) press(canvas, '+');
    expect(zoomLabel()).toBe('350% · local detail');
  });

  it('pans with the arrow keys and consumes the key press', () => {
    const canvas = setup();

    // Arrow keys must not scroll the page behind the map.
    expect(fireEvent.keyDown(canvas, { key: 'ArrowRight' })).toBe(false);

    // The viewport moved right, so the location now paints one step to the left.
    clickAt(canvas, CENTER, CENTER);
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();
    clickAt(canvas, CENTER - KEY_PAN_PIXELS, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('stops panning at the world edge instead of drifting off the map', () => {
    const canvas = setup();

    for (let i = 0; i < 20; i += 1) press(canvas, 'ArrowLeft');

    // With the camera clamped to x = 0 the centre of the world sits on the right edge.
    clickAt(canvas, SIZE, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();
  });

  it('recenters on the protagonist with Home', () => {
    const canvas = setup({ currentLocation: LOCATION.name });

    press(canvas, 'ArrowRight');
    clickAt(canvas, CENTER, CENTER);
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();

    press(canvas, 'Home');
    clickAt(canvas, CENTER, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    press(canvas, '+');
    expect(zoomLabel()).toBe('261% · local detail');
    press(canvas, 'Home');
    expect(zoomLabel()).toBe('225% · local detail');
  });

  it('falls back to the whole-world view when Home is pressed with no protagonist', () => {
    const canvas = setup();

    press(canvas, '+');
    expect(zoomLabel()).toBe('116% · regions');
    press(canvas, 'Home');
    expect(zoomLabel()).toBe('100% · regions');
  });

  it('clears the selected location with Escape', () => {
    const canvas = setup();

    clickAt(canvas, CENTER, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    press(canvas, 'Escape');
    expect(screen.queryByText('Fog Harbor')).not.toBeInTheDocument();
  });

  it('keeps pointer drag, selection and journey preview working', () => {
    const onPreview = vi.fn();
    const canvas = setup({ onPreview, currentLocation: 'loc_elsewhere' });

    fireEvent.mouseDown(canvas, { clientX: 100, clientY: CENTER });
    fireEvent.mouseMove(canvas, { clientX: 100 + KEY_PAN_PIXELS, clientY: CENTER });
    fireEvent.mouseUp(canvas, { clientX: 100 + KEY_PAN_PIXELS, clientY: CENTER });

    // Dragging right moves the map right, so the location follows the pointer.
    clickAt(canvas, CENTER + KEY_PAN_PIXELS, CENTER);
    expect(screen.getByText('Fog Harbor')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Preview journey' }));
    expect(onPreview).toHaveBeenCalledWith(expect.objectContaining({ id: LOCATION.id }));
  });
});
