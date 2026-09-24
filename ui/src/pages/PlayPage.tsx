import { useParams } from 'react-router-dom';
import { usePlaySession } from '../features/play/usePlaySession';
import { PlaySidebar } from '../features/play/PlaySidebar';
import { PlayNarrative } from '../features/play/PlayNarrative';
import { PlayInspector } from '../features/play/PlayInspector';

export function PlayPage() {
  const { name } = useParams<{ name: string }>();
  const session = usePlaySession(name || 'Valdris_Realm');

  /**
   * The three play columns are one non-wrapping flex row inside
   * `overflow-hidden`: sidebar + transcript + inspector.
   *
   * There is deliberately no scroll-into-view logic here. An earlier revision
   * scrolled this row so an opening drawer would be visible, which treated the
   * symptom: the row is ~1194px wide against a 390px viewport, so scrolling
   * only moved the problem around (measured, it pushed the map off the *left*
   * edge instead). The drawer now escapes the row entirely below `md` via
   * `fixed` positioning in PlayInspector, so it is always on screen and nothing
   * needs to be scrolled. On wider screens the row fits and there is nothing to
   * scroll. Keeping the horizontal scroller untouched also matters because the
   * map canvas lives inside it.
   */
  return (
    <div className="w-full flex-1 h-full min-h-0 flex overflow-hidden relative">
      <PlaySidebar {...session} />
      <PlayNarrative {...session} />
      <PlayInspector {...session} />
    </div>
  );
}
