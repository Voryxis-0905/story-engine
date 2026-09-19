import { describe, expect, it } from 'vitest';
import { normalizedCoordinate } from './mapCoordinates';

describe('LocationMap coordinates', () => {
  it('normalizes backend 0-100 coordinates for canvas drawing and hit testing', () => {
    expect(normalizedCoordinate(0)).toBe(0);
    expect(normalizedCoordinate(20)).toBe(0.2);
    expect(normalizedCoordinate(100)).toBe(1);
    expect(normalizedCoordinate(140)).toBe(1);
  });
});
