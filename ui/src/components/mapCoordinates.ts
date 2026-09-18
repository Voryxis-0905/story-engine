export const normalizedCoordinate = (value: number) =>
  Math.max(0, Math.min(1, Number(value || 0) / 100));
