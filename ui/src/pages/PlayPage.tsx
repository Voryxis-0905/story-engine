import { useParams } from 'react-router-dom';
import { usePlaySession } from '../features/play/usePlaySession';
import { PlaySidebar } from '../features/play/PlaySidebar';
import { PlayNarrative } from '../features/play/PlayNarrative';
import { PlayInspector } from '../features/play/PlayInspector';

export function PlayPage() {
  const { name } = useParams<{ name: string }>();
  const session = usePlaySession(name || 'Valdris_Realm');
  return (
    <div className="w-full flex-1 h-full min-h-0 flex overflow-hidden relative">
      <PlaySidebar {...session} />
      <PlayNarrative {...session} />
      <PlayInspector {...session} />
    </div>
  );
}
