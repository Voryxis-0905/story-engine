import { useState } from 'react';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';
import { Navbar } from './components/layout/Navbar';
import { HomePage } from './pages/HomePage';
import { WorldsPage } from './pages/WorldsPage';
import { PlayPage } from './pages/PlayPage';
import { SettingsPage } from './pages/SettingsPage';
import { WorldBuilderModal } from './components/builder/WorldBuilderModal';

function AppContent() {
  const [currentWorld, setCurrentWorld] = useState<string>('Valdris_Realm');
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="h-dvh w-full flex flex-col overflow-hidden font-sans selection:bg-[rgba(var(--periwinkle-rgb),0.28)] selection:text-[var(--ink-main)]">
      <Navbar currentWorld={currentWorld} onWorldChange={(w) => setCurrentWorld(w)} />

      <main className="flex-1 min-h-0 w-full overflow-hidden relative">
        <Routes>
          <Route path="/" element={<div className="h-full overflow-y-auto"><HomePage onOpenBuilder={() => setIsBuilderOpen(true)} /></div>} />
          <Route path="/worlds" element={<div className="h-full overflow-y-auto"><WorldsPage /></div>} />
          <Route path="/worlds/:name/play" element={<PlayPage />} />
          <Route path="/settings" element={<div className="h-full overflow-y-auto"><SettingsPage /></div>} />
        </Routes>
      </main>

      <WorldBuilderModal
        isOpen={isBuilderOpen}
        onClose={() => setIsBuilderOpen(false)}
        onSuccess={(worldName) => {
          setCurrentWorld(worldName);
          navigate(`/worlds/${worldName}/play`);
        }}
      />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}