import { useState, useEffect, useRef } from 'react';
import { api } from '../../api/client';
import type { PlayState } from '../../api/client';
import type { DrawerTab, Turn } from './types';

export function usePlaySession(worldName: string) {
  const [playState, setPlayState] = useState<PlayState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Controls
  // const [pacingLevel, setPacingLevel] = useState<'slow' | 'normal' | 'fast'>('normal'); // Commented out: AI story engine handles pacing dynamically
  const [outputLength, setOutputLength] = useState<'short' | 'medium' | 'long'>('medium');

  // Sidebar collapse
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Collapsible turns history state
  const [expandedTurns, setExpandedTurns] = useState<Record<number, boolean>>({});

  const toggleTurnExpanded = (index: number) => {
    setExpandedTurns(prev => {
      const isCurrentlyExpanded = prev[index] !== undefined
        ? prev[index]
        : (index === turns.length - 1 || turns.length <= 2);
      return { ...prev, [index]: !isCurrentlyExpanded };
    });
  };

  const collapseAllPrevious = () => {
    const newExpanded: Record<number, boolean> = {};
    turns.forEach((_, idx) => {
      newExpanded[idx] = idx === turns.length - 1;
    });
    setExpandedTurns(newExpanded);
  };

  const expandAllTurns = () => {
    const newExpanded: Record<number, boolean> = {};
    turns.forEach((_, idx) => {
      newExpanded[idx] = true;
    });
    setExpandedTurns(newExpanded);
  };

  // Right Drawer tab
  const [activeDrawer, setActiveDrawer] = useState<DrawerTab>(null);

  // Extra data for drawers
  const [locations, setLocations] = useState<any[]>([]);
  const [affinityGraph, setAffinityGraph] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [preludeText, setPreludeText] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (worldName) {
      loadPlayState();
      loadMap();
      loadAffinityGraph();
      loadExistingChapters();
    }
  }, [worldName]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  const loadPlayState = async () => {
    try {
      const state = await api.play.state(worldName);
      setPlayState(state);
      setError(null);
    } catch (e: any) {
      setError(e.message || 'Failed to load world state');
    }
  };

  const loadMap = async () => {
    try {
      const mapData = await api.map.status(worldName);
      setLocations(mapData.locations || []);
    } catch {
      try {
        const fallback = await api.map.get(worldName);
        setLocations(fallback.locations || []);
      } catch {
        setLocations([]);
      }
    }
  };

  const loadAffinityGraph = async () => {
    try {
      const graph = await api.worlds.affinityGraph(worldName);
      setAffinityGraph(graph || { nodes: [], edges: [] });
    } catch {
      setAffinityGraph({ nodes: [], edges: [] });
    }
  };

  const loadExistingChapters = async () => {
    try {
      const chapters = await api.play.getChapters(worldName);
      if (!chapters || chapters.length === 0) return;

      const preludeChapter = chapters.find((c: any) => c.chapter_index === 0);
      if (preludeChapter && preludeChapter.chapter_text) {
        setPreludeText(preludeChapter.chapter_text);
      }

      const nonPrelude = chapters.filter((c: any) => c.chapter_index !== 0);
      if (nonPrelude.length === 0) return;
      const formatted = nonPrelude.map((c: any) => ({
        input: c.user_input || 'Start Chapter',
        output: c.chapter_text,
        chapterIndex: c.chapter_index,
        turnIndex: c.turn_index,
        checkpointId: c.checkpoint_id,
        timestamp: Date.now(),
      }));
      setTurns(formatted);
    } catch {
      // No chapters yet — ignore
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userInput = input.trim();
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const res = await api.play.continue(worldName, userInput);
      const chapter = res.chapter;
      setTurns(prev => [...prev, {
        input: userInput,
        output: chapter.chapter_text,
        chapterIndex: chapter.chapter_index,
        turnIndex: chapter.turn_index,
        checkpointId: chapter.checkpoint_id,
        timestamp: Date.now(),
      }]);
      await loadPlayState();
    } catch (e: any) {
      setError(e.message || 'Failed to submit action turn');
    } finally {
      setLoading(false);
    }
  };

  const handleStartChapter = async () => {
    setLoading(true);
    setError(null);
    try {
      // Check if chapters already exist
      if (playState && playState.arc_progress.current_index > 0) {
        // Chapters exist — reload them instead
        await loadExistingChapters();
        setLoading(false);
        return;
      }
      const res = await api.play.start(worldName, { opening_mode: 'ai_generate' });
      if (res?.chapter?.chapter_text) {
        setTurns([{
          input: 'Start Chapter',
          output: res.chapter.chapter_text,
          chapterIndex: res.chapter.chapter_index || 1,
          turnIndex: res.chapter.turn_index || 0,
          checkpointId: res.chapter.checkpoint_id || 'cp_1',
          timestamp: Date.now(),
        }]);
      }
      await loadPlayState();
    } catch (e: any) {
      setError(e.message || 'Failed to start chapter');
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.play.regenerate(worldName);
      await loadPlayState();
    } catch (e: any) {
      setError(e.message || 'Failed to regenerate chapter');
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePrelude = async () => {
    setLoading(true);
    try {
      const p = await api.play.prelude.generate(worldName);
      setPreludeText(p?.prelude?.chapter_text || p?.prelude_text || '');
    } catch (e: any) {
      setError(e.message || 'Failed to generate prelude');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmPrelude = async () => {
    setLoading(true);
    try {
      await api.play.prelude.confirm(worldName);
      setPreludeText(null);
      // After confirming prelude, start the first chapter
      const res = await api.play.start(worldName, { opening_mode: 'ai_generate' });
      if (res?.chapter?.chapter_text) {
        setTurns([{
          input: 'Start Chapter',
          output: res.chapter.chapter_text,
          chapterIndex: res.chapter.chapter_index || 1,
          turnIndex: res.chapter.turn_index || 0,
          checkpointId: res.chapter.checkpoint_id || 'cp_1',
          timestamp: Date.now(),
        }]);
      }
      await loadPlayState();
    } catch (e: any) {
      setError(e.message || 'Failed to confirm prelude');
    } finally {
      setLoading(false);
    }
  };

  const protagonist = playState?.protagonist;
  const arc = playState?.arc_progress;
  const clock = playState?.story_clock || {};


  return { playState, turns, input, setInput, loading, error, setError, outputLength, setOutputLength, sidebarOpen, setSidebarOpen, expandedTurns, toggleTurnExpanded, collapseAllPrevious, expandAllTurns, activeDrawer, setActiveDrawer, locations, affinityGraph, preludeText, chatEndRef, handleSend, handleStartChapter, handleRegenerate, handleGeneratePrelude, handleConfirmPrelude, protagonist, arc, clock };
}

export type PlaySession = ReturnType<typeof usePlaySession>;
