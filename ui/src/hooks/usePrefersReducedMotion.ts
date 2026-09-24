import { useEffect, useState } from 'react';

/**
 * Reports whether the player asked the platform to reduce motion.
 *
 * The map's ambient motion is decorative; when this is true the map renders one
 * static frame instead of animating, which is the only correct behaviour for a
 * vestibular-sensitivity preference.
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener?.('change', handler);
    return () => query.removeEventListener?.('change', handler);
  }, []);

  return reduced;
}
