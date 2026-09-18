import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../api/client';
import type { PlayState } from '../../api/client';
import type { DrawerTab, Turn, PlayDraft } from './types';
import { WORLD_RESTORED_EVENT, DRAFT_STORAGE_PREFIX } from './types';

export type OutputLength = 'short' | 'medium' | 'long';

const LENGTH_TO_BACKEND: Record<OutputLength, string> = {
  short: 'Concise',
  medium: 'Standard',
  long: 'Detailed',
};

const backendToLength = (value?: string): OutputLength => {
  if (value === 'Concise') return 'short';
  if (value === 'Detailed') return 'long';
  return 'medium';
};

const draftKey = (name: string) => `${DRAFT_STORAGE_PREFIX}${name}`;

export function usePlaySession(worldName: string) {
  const [playState, setPlayState] = useState<PlayState | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Controls
  const [outputLength, setOutputLengthState] = useState<OutputLength>('medium');

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
  const [draft, setDraft] = useState<PlayDraft | null>(null);
  const [quests, setQuests] = useState<any[]>([]);
  const [journal, setJournal] = useState<any[]>([]);
  const [epilogueChoices, setEpilogueChoices] = useState<string[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Guards against duplicate submissions (a click cannot fire twice before the
  // first request settles) and against late responses of a previous world.
  const sendingRef = useRef(false);
  const worldTokenRef = useRef(0);
  // The action currently in flight (or awaiting retry). Reusing its id lets the
  // backend replay a committed turn instead of calling the model again.
  const pendingActionRef = useRef<{ id: string; userInput: string } | null>(null);
  const revisionRef = useRef<number | undefined>(undefined);

  const makeRequestId = () =>
    (globalThis.crypto?.randomUUID?.() ?? `req_${Date.now()}_${Math.random().toString(36).slice(2)}`);

  const readStoredDraft = useCallback((name: string): PlayDraft | null => {
    try {
      const raw = sessionStorage.getItem(draftKey(name));
      return raw ? (JSON.parse(raw) as PlayDraft) : null;
    } catch {
      return null;
    }
  }, []);

  const storeDraft = useCallback((next: PlayDraft | null) => {
    try {
      if (next) {
        sessionStorage.setItem(draftKey(next.worldName), JSON.stringify(next));
      } else {
        sessionStorage.removeItem(draftKey(worldName));
      }
    } catch {
      // sessionStorage can be unavailable; the in-memory draft still works
    }
  }, [worldName]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns]);

  const loadPlayState = useCallback(async () => {
    const token = worldTokenRef.current;
    try {
      const state = await api.play.state(worldName);
      if (token !== worldTokenRef.current) return;
      setPlayState(state);
      setOutputLengthState(backendToLength(state?.output_length));
      revisionRef.current = typeof state?.revision === 'number' ? state.revision : undefined;
      setError(null);
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to load world state');
    }
  }, [worldName]);

  const loadMap = useCallback(async () => {
    const token = worldTokenRef.current;
    try {
      const mapData = await api.map.status(worldName);
      if (token !== worldTokenRef.current) return;
      setLocations(mapData.locations || []);
    } catch {
      try {
        const fallback = await api.map.get(worldName);
        if (token !== worldTokenRef.current) return;
        setLocations(fallback.locations || []);
      } catch {
        if (token !== worldTokenRef.current) return;
        setLocations([]);
      }
    }
  }, [worldName]);

  const loadAffinityGraph = useCallback(async () => {
    const token = worldTokenRef.current;
    try {
      const graph = await api.worlds.affinityGraph(worldName);
      if (token !== worldTokenRef.current) return;
      setAffinityGraph(graph || { nodes: [], edges: [] });
    } catch {
      if (token !== worldTokenRef.current) return;
      setAffinityGraph({ nodes: [], edges: [] });
    }
  }, [worldName]);

  const loadDiscovery = useCallback(async () => {
    const token = worldTokenRef.current;
    try {
      const [qb, jn] = await Promise.all([
        api.discovery.questBoard(worldName),
        api.discovery.journal(worldName),
      ]);
      if (token !== worldTokenRef.current) return;
      setQuests(qb?.quests || []);
      setJournal(jn?.entries || []);
    } catch {
      if (token !== worldTokenRef.current) return;
      setQuests([]);
      setJournal([]);
    }
  }, [worldName]);

  const loadExistingChapters = useCallback(async () => {
    const token = worldTokenRef.current;
    try {
      const chapters = await api.play.getChapters(worldName);
      if (token !== worldTokenRef.current) return;
      if (!chapters || chapters.length === 0) {
        setTurns([]);
        return;
      }

      const preludeChapter = chapters.find((c: any) => c.chapter_index === 0);
      if (preludeChapter && preludeChapter.chapter_text) {
        setPreludeText(preludeChapter.chapter_text);
      }

      const nonPrelude = chapters.filter((c: any) => c.chapter_index !== 0);
      if (nonPrelude.length === 0) {
        setTurns([]);
        return;
      }
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
  }, [worldName]);

  useEffect(() => {
    worldTokenRef.current += 1;
    // Reset the in-flight lock together with the data, so the new world can send
    // while a late response of the previous world is still outstanding.
    sendingRef.current = false;
    pendingActionRef.current = null;
    revisionRef.current = undefined;
    setLoading(false);
    setTurns([]);
    setPlayState(null);
    setLocations([]);
    setAffinityGraph({ nodes: [], edges: [] });
    setPreludeText(null);
    setDraft(readStoredDraft(worldName));
    setQuests([]);
    setJournal([]);
    setEpilogueChoices([]);
    setError(null);
    if (worldName) {
      loadPlayState();
      loadMap();
      loadAffinityGraph();
      loadExistingChapters();
      loadDiscovery();
    }
  }, [worldName, readStoredDraft, loadPlayState, loadMap, loadAffinityGraph, loadExistingChapters, loadDiscovery]);

  // A creator restore can happen outside this screen; refresh committed data.
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (!detail || detail.worldName === worldName) {
        loadPlayState();
        loadMap();
        loadAffinityGraph();
        loadExistingChapters();
        loadDiscovery();
      }
    };
    window.addEventListener(WORLD_RESTORED_EVENT, handler);
    return () => window.removeEventListener(WORLD_RESTORED_EVENT, handler);
  }, [worldName, loadPlayState, loadMap, loadAffinityGraph, loadExistingChapters, loadDiscovery]);

  const reloadCommittedData = async () => {
    await Promise.all([loadPlayState(), loadMap(), loadAffinityGraph(), loadDiscovery()]);
  };

  const setOutputLength = (value: OutputLength) => {
    setOutputLengthState(value);
    api.worlds.updateConfig(worldName, { output_length: LENGTH_TO_BACKEND[value] }).catch(() => {
      setError('Failed to save the output length setting');
    });
  };

  const submitAction = async (rawInput: string, options: { clearInputOnSuccess: boolean; requestId?: string }) => {
    const userInput = rawInput.trim();
    if (!userInput || sendingRef.current) return;
    const token = worldTokenRef.current;
    sendingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const res = await api.play.continue(worldName, userInput, {
        requestId: options.requestId,
        expectedRevision: revisionRef.current,
      });
      if (token !== worldTokenRef.current) return;
      if (typeof res?.revision === 'number') {
        revisionRef.current = res.revision;
      }
      pendingActionRef.current = null;
      const chapter = res.chapter;
      setTurns(prev => [...prev, {
        input: userInput,
        output: chapter.chapter_text,
        chapterIndex: chapter.chapter_index,
        turnIndex: chapter.turn_index,
        checkpointId: chapter.checkpoint_id,
        timestamp: Date.now(),
      }]);
      // Only clear the box if the player has not already typed the next action,
      // and only on success, so a failed send can be retried unchanged. A draft
      // retry never touches the box at all.
      if (options.clearInputOnSuccess) {
        setInput(prev => (prev.trim() === userInput ? '' : prev));
      }
      // A committed turn replaces any pending not-saved draft.
      setDraft(null);
      storeDraft(null);
      await reloadCommittedData();
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      const detail = e?.detail;
      if (detail && detail.persisted === false && typeof detail.draft_chapter_text === 'string') {
        const nextDraft: PlayDraft = {
          worldName,
          userInput,
          requestId: options.requestId,
          text: detail.draft_chapter_text,
          status: detail.status || 'unavailable',
          reason: detail.reason || '',
          message: detail.message || e.message || '',
          createdAt: Date.now(),
        };
        setDraft(nextDraft);
        storeDraft(nextDraft);
      }
      setError(e.message || 'Failed to submit action turn');
    } finally {
      // Only the request that still owns the active world may release the lock;
      // a late response from a previous world must not unlock the new one.
      if (token === worldTokenRef.current) {
        sendingRef.current = false;
        setLoading(false);
      }
    }
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text || sendingRef.current) return;
    // Reuse the in-flight id when the player retries the same action, otherwise
    // this is a new action and gets a new id.
    const reuse = pendingActionRef.current?.userInput === text;
    const requestId = reuse ? pendingActionRef.current!.id : makeRequestId();
    pendingActionRef.current = { id: requestId, userInput: text };
    return submitAction(text, { clearInputOnSuccess: true, requestId });
  };

  const handleTravelTo = (location: { name?: string; id?: string }) => {
    const destination = location?.name || location?.id;
    if (!destination) return;
    setInput(`Travel to ${destination}.`);
    setActiveDrawer(null);
  };

  const handleRetryDraft = () => {
    if (!draft) return;
    // Resend the action that produced the draft, regardless of what the player
    // is currently typing. The input box is left untouched. Reusing the stored
    // request id lets the backend replay a turn that actually committed.
    return submitAction(draft.userInput, {
      clearInputOnSuccess: false,
      requestId: draft.requestId,
    });
  };

  const handleStartChapter = async () => {
    if (sendingRef.current) return;
    const token = worldTokenRef.current;
    sendingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      // Check if chapters already exist
      if (playState && playState.arc_progress.current_index > 0) {
        // Chapters exist — reload them instead
        await loadExistingChapters();
        return;
      }
      const res = await api.play.start(worldName, { opening_mode: 'ai_generate' });
      if (token !== worldTokenRef.current) return;
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
      await reloadCommittedData();
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to start chapter');
    } finally {
      // Only the request that still owns the active world may release the lock;
      // a late response from a previous world must not unlock the new one.
      if (token === worldTokenRef.current) {
        sendingRef.current = false;
        setLoading(false);
      }
    }
  };

  const handleRegenerate = async () => {
    if (sendingRef.current) return;
    const token = worldTokenRef.current;
    const reuse = pendingActionRef.current?.userInput === '__regenerate__';
    const requestId = reuse ? pendingActionRef.current!.id : makeRequestId();
    pendingActionRef.current = { id: requestId, userInput: '__regenerate__' };
    sendingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const res = await api.play.regenerate(worldName, {
        requestId,
        expectedRevision: revisionRef.current,
      });
      if (token !== worldTokenRef.current) return;
      if (typeof res?.revision === 'number') {
        revisionRef.current = res.revision;
      }
      pendingActionRef.current = null;
      await Promise.all([loadExistingChapters(), reloadCommittedData()]);
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to regenerate chapter');
    } finally {
      // Only the request that still owns the active world may release the lock;
      // a late response from a previous world must not unlock the new one.
      if (token === worldTokenRef.current) {
        sendingRef.current = false;
        setLoading(false);
      }
    }
  };

  const handleLoadEndgameChoices = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.play.epilogueChoices(worldName);
      setEpilogueChoices(res?.choices || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load epilogue choices');
    } finally {
      setLoading(false);
    }
  };

  const handleChooseEnding = async (choice: string) => {
    if (sendingRef.current) return;
    const token = worldTokenRef.current;
    sendingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      await api.play.generateEpilogue(worldName, choice);
      if (token !== worldTokenRef.current) return;
      setEpilogueChoices([]);
      await Promise.all([loadExistingChapters(), reloadCommittedData()]);
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to write the epilogue');
    } finally {
      if (token === worldTokenRef.current) {
        sendingRef.current = false;
        setLoading(false);
      }
    }
  };

  const handleGeneratePrelude = async () => {
    const token = worldTokenRef.current;
    setLoading(true);
    try {
      const p = await api.play.prelude.generate(worldName);
      if (token !== worldTokenRef.current) return;
      setPreludeText(p?.prelude?.chapter_text || p?.prelude_text || '');
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to generate prelude');
    } finally {
      if (token === worldTokenRef.current) {
        setLoading(false);
      }
    }
  };

  const handleConfirmPrelude = async () => {
    if (sendingRef.current) return;
    const token = worldTokenRef.current;
    sendingRef.current = true;
    setLoading(true);
    try {
      await api.play.prelude.confirm(worldName);
      if (token !== worldTokenRef.current) return;
      setPreludeText(null);
      // After confirming prelude, start the first chapter
      const res = await api.play.start(worldName, { opening_mode: 'ai_generate' });
      if (token !== worldTokenRef.current) return;
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
      await reloadCommittedData();
    } catch (e: any) {
      if (token !== worldTokenRef.current) return;
      setError(e.message || 'Failed to confirm prelude');
    } finally {
      // Only the request that still owns the active world may release the lock;
      // a late response from a previous world must not unlock the new one.
      if (token === worldTokenRef.current) {
        sendingRef.current = false;
        setLoading(false);
      }
    }
  };

  const handleDismissDraft = () => {
    setDraft(null);
    storeDraft(null);
  };

  const protagonist = playState?.protagonist;
  const arc = playState?.arc_progress;
  const clock = playState?.story_clock || {};


  return { playState, turns, input, setInput, loading, error, setError, outputLength, setOutputLength, sidebarOpen, setSidebarOpen, expandedTurns, toggleTurnExpanded, collapseAllPrevious, expandAllTurns, activeDrawer, setActiveDrawer, locations, affinityGraph, preludeText, draft, handleDismissDraft, handleRetryDraft, quests, journal, epilogue: playState?.epilogue || null, lifecycleStatus: playState?.lifecycle_status || 'active', epilogueChoices, handleLoadEndgameChoices, handleChooseEnding, chatEndRef, handleSend, handleTravelTo, handleStartChapter, handleRegenerate, handleGeneratePrelude, handleConfirmPrelude, protagonist, arc, clock };
}

export type PlaySession = ReturnType<typeof usePlaySession>;
