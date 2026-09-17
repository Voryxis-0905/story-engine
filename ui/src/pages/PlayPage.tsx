import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { ChevronLeftIcon, ChevronRightIcon, BriefcaseIcon, MapIcon, BookOpenIcon, UserIcon, BoltIcon, EyeIcon, PaperAirplaneIcon, ArrowPathIcon, PlayIcon, SparklesIcon, ClockIcon, GlobeAltIcon, XMarkIcon, FireIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';
import type { PlayState } from '../api/client';
import { LocationMap } from '../components/LocationMap';
import { CodexGraph } from '../components/CodexGraph';

type DrawerTab = 'inventory' | 'map' | 'codex' | 'status' | 'skills' | 'foreshadowing' | null;

interface Turn {
  input: string;
  output: string;
  chapterIndex: number;
  turnIndex: number;
  checkpointId: string;
  timestamp: number;
}

export const PlayPage: React.FC = () => {
  const { name: worldNameParam } = useParams<{ name: string }>();
  const worldName = worldNameParam || 'Valdris_Realm';

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

  return (
    <div className="w-full flex-1 h-full min-h-0 flex overflow-hidden relative">
      {/* LEFT SIDEBAR */}
      <aside 
        className={`glass-panel rounded-none border-y-0 border-l-0 transition-all duration-300 flex flex-col z-20 h-full shrink-0 ${
          sidebarOpen ? 'w-72' : 'w-12'
        }`}
      >
        {/* Toggle Button Header */}
        <div className="p-3 border-b border-[var(--line-2)] flex items-center justify-between shrink-0 bg-[var(--bg-surface)] sticky top-0 z-10">
          {sidebarOpen && (
            <span className="text-xs font-mono uppercase tracking-wider text-[var(--periwinkle-dark)] font-bold">
              World State
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors mx-auto"
            title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen ? <ChevronLeftIcon className="w-5 h-5" /> : <ChevronRightIcon className="w-5 h-5" />}
          </button>
        </div>

        {sidebarOpen && (
          <div className="p-4 flex-1 overflow-y-auto space-y-6">
            {/* World Clock & Season */}
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-2.5 shadow-sm">
              <div className="flex items-center gap-2 text-[var(--ink-soft)] text-xs font-bold uppercase tracking-wider">
                <ClockIcon  className="w-5 h-5 text-[var(--periwinkle-dark)]" />
                <span>Story Timeline</span>
              </div>
              <div className="text-sm font-bold text-[var(--ink-main)]">
                {clock.season || 'Autumn'} • {clock.time_of_day || 'Dawn'}
              </div>
              <div className="text-xs text-[var(--ink-soft)] font-mono font-bold">
                Year {clock.year || 1024}, Day {clock.day || 14}
              </div>
              <div className="text-xs text-[var(--periwinkle-dark)] flex items-center gap-1 font-bold">
                <GlobeAltIcon className="w-5 h-5" />
                <span>{protagonist?.location || 'Valdris Estate'}</span>
              </div>
            </div>

            {/* Arc Progress Meter */}
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-3 shadow-sm">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[var(--ink-soft)] uppercase tracking-wider">Arc Checkpoint</span>
                <span className="px-2 py-0.5 rounded-full bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line)] font-mono font-bold text-[10px]">
                  {arc?.current_checkpoint_id || 'cp_0'}
                </span>
              </div>

              <div className="w-full h-2 rounded-full bg-[var(--line)] overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[var(--periwinkle)] to-[var(--sakura)] rounded-full transition-all duration-500 shadow-sm"
                  style={{
                    width: `${Math.min(100, (((arc?.current_index ?? 0) + 1) / (arc?.total_checkpoints || 1)) * 100)}%`
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs font-mono font-bold text-[var(--ink-soft)]">
                <span>Index: {arc?.current_index ?? 0}</span>
                <span>Total: {arc?.total_checkpoints ?? 0}</span>
              </div>
            </div>

            {/* Protagonist Mini Card */}
            {protagonist && (
              <div className="p-4 rounded-xl bg-gradient-to-b from-[var(--bg-subtle)] to-[var(--bg-surface)] border border-[var(--line)] space-y-2 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--periwinkle)] to-[var(--periwinkle-dark)] shadow-[var(--shadow-sm)] flex items-center justify-center font-bold text-white text-lg font-[var(--font-display)]">
                    {protagonist.name.charAt(0)}
                  </div>
                  <div>
                    <h4 className="font-bold text-[var(--ink-main)] text-sm">{protagonist.name}</h4>
                    <span className="text-xs text-[var(--periwinkle-dark)] font-mono font-bold">{protagonist.power_stat?.realm || 'Mortal'}</span>
                  </div>
                </div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--ink-soft)] pt-2 border-t border-[var(--line-2)] flex items-center justify-between font-mono">
                  <span>EXP: <span className="text-[var(--ink-main)]">{protagonist.power_stat?.exp || 0}</span></span>
                  <span className={protagonist.alive ? 'text-[var(--ok)]' : 'text-[var(--danger)]'}>
                    {protagonist.alive ? '● Alive' : '✕ Fallen'}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
      </aside>

      {/* CENTER NARRATIVE MAIN VIEW */}
      <main className="flex-1 flex flex-col h-full bg-[var(--bg-surface)] relative">
        {/* Top Control Bar */}
        <div className="px-6 py-3 border-b border-[var(--line-2)] flex items-center justify-between glass-panel shadow-sm z-10">
          <div className="flex items-center gap-4 text-xs font-mono font-bold text-[var(--ink-soft)]">
            {/* Pacing control commented out: AI story engine handles pacing dynamically based on plot beat */}
            {/* 
            <div className="flex items-center gap-1.5">
              <span>Pacing:</span>
              <select
                value={pacingLevel}
                onChange={(e) => setPacingLevel(e.target.value as any)}
                className="bg-[var(--bg-subtle)] border border-[var(--line)] rounded px-2 py-1 text-[var(--ink-main)] focus:outline-none cursor-pointer hover:bg-[var(--line)] transition-colors"
              >
                <option value="slow">Slow</option>
                <option value="normal">Normal</option>
                <option value="fast">Fast</option>
              </select>
            </div>
            */}

            <div className="flex items-center gap-1.5">
              <span>Length:</span>
              <select
                value={outputLength}
                onChange={(e) => setOutputLength(e.target.value as any)}
                className="bg-[var(--bg-subtle)] border border-[var(--line)] rounded px-2 py-1 text-[var(--ink-main)] focus:outline-none cursor-pointer hover:bg-[var(--line)] transition-colors"
              >
                <option value="short">Short</option>
                <option value="medium">Medium</option>
                <option value="long">Long</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleStartChapter}
              disabled={loading}
              className="pill-btn pill-btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5 shadow-sm disabled:opacity-50"
            >
              <PlayIcon className="w-4 h-4" />
              <span>Start Chapter</span>
            </button>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl bg-[rgba(var(--danger-rgb),0.12)] border border-[rgba(var(--danger-rgb),0.3)] text-[var(--danger)] text-xs font-bold flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}><XMarkIcon className="w-5 h-5" /></button>
          </div>
        )}

        {/* Narrative Reading History */}
        <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6 max-w-4xl mx-auto w-full">
          {/* Prelude Flow Component */}
          {turns.length === 0 && (
            <div className="story-card mt-6 p-8 text-center space-y-6 animate-fade-in">
              <div className="w-16 h-16 rounded-full bg-[var(--bg-subtle)] border border-[var(--line)] flex items-center justify-center text-[var(--periwinkle-dark)] mx-auto shadow-sm">
                <SparklesIcon className="w-5 h-5" />
              </div>

              <div>
                <h3 className="text-2xl font-bold text-[var(--ink-main)] font-[var(--font-display)]">World Prelude Setup</h3>
                <p className="text-[var(--ink-soft)] font-medium text-sm mt-1 max-w-md mx-auto">
                  Before stepping into the world, synthesize the initial narrative prelude or confirm the opening conditions.
                </p>
              </div>

              {preludeText ? (
                <div className="p-6 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line-2)] text-left text-[var(--ink-main)] text-[15px] leading-relaxed font-serif max-h-60 overflow-y-auto shadow-inner">
                  {preludeText}
                </div>
              ) : null}

              <div className="flex items-center justify-center gap-4 pt-4 border-t border-[var(--line)]">
                <button
                  onClick={handleGeneratePrelude}
                  disabled={loading}
                  className="pill-btn pill-btn-secondary px-6 py-2.5 text-sm font-bold shadow-sm disabled:opacity-50"
                >
                  Generate Prelude
                </button>
                <button
                  onClick={handleConfirmPrelude}
                  disabled={loading}
                  className="pill-btn pill-btn-primary px-6 py-2.5 text-sm font-bold shadow-sm disabled:opacity-50"
                >
                  Confirm Prelude & Play
                </button>
              </div>
            </div>
          )}

          {/* History Collapse / Expand Bar */}
          {turns.length > 1 && (
            <div className="flex items-center justify-between text-xs font-mono font-bold text-[var(--ink-soft)] px-1 pb-2">
              <span>Chapter Timeline ({turns.length} turns)</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={collapseAllPrevious}
                  className="hover:text-[var(--periwinkle-dark)] transition-colors underline decoration-dotted"
                >
                  Collapse Previous
                </button>
                <span>•</span>
                <button
                  onClick={expandAllTurns}
                  className="hover:text-[var(--periwinkle-dark)] transition-colors underline decoration-dotted"
                >
                  Expand All
                </button>
              </div>
            </div>
          )}

          {/* Chapters and Turns Prose */}
          {turns.map((turn, i) => {
            const isLatest = i === turns.length - 1;
            const isExpanded = expandedTurns[i] !== undefined 
              ? expandedTurns[i] 
              : (isLatest || turns.length <= 2);

            return (
              <div key={i} className="space-y-4 animate-fade-in">
                {/* User Action Prompt */}
                {turn.input && turn.input !== 'Start Chapter' && (
                  <div className="flex justify-end">
                    <div className="px-5 py-3 rounded-3xl rounded-tr-sm bg-gradient-to-r from-[var(--periwinkle)] to-[var(--periwinkle-dark)] text-white text-[15px] font-medium max-w-lg shadow-[var(--shadow-sm)] leading-snug">
                      <span className="text-white opacity-70 font-mono mr-1.5">▶</span>
                      {turn.input}
                    </div>
                  </div>
                )}

                {/* Collapsed View */}
                {!isExpanded ? (
                  <div 
                    onClick={() => toggleTurnExpanded(i)}
                    className="story-card p-4 shadow-sm hover:shadow-md transition-all border border-[var(--line)] hover:border-[var(--periwinkle-dark)] cursor-pointer bg-[var(--bg-surface)] flex items-center justify-between rounded-2xl group"
                  >
                    <div className="flex items-center gap-3 overflow-hidden flex-1 mr-3">
                      <span className="px-2.5 py-1 rounded-lg bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] font-mono text-xs font-bold shrink-0 border border-[var(--line)]">
                        Ch. {turn.chapterIndex} • Turn {turn.turnIndex}
                      </span>
                      <span className="text-xs font-medium text-[var(--ink-soft)] group-hover:text-[var(--ink-main)] truncate transition-colors">
                        {turn.output.replace(/<[^>]+>/g, '').slice(0, 100)}...
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 text-xs font-mono text-[var(--ink-soft)] font-bold">
                      <span className="hidden sm:inline">CP: {turn.checkpointId}</span>
                      <ChevronDownIcon className="w-4 h-4 text-[var(--ink-soft)] group-hover:text-[var(--periwinkle-dark)] transition-colors" />
                    </div>
                  </div>
                ) : (
                  /* Expanded Full Narrative Prose Output */
                  <div className="story-card p-7 space-y-4 shadow-[var(--shadow-md)] relative">
                    <div className="flex items-center justify-between text-xs font-mono font-bold text-[var(--ink-soft)] border-b border-[var(--line-2)] pb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[var(--periwinkle-dark)] uppercase tracking-wider">
                          Chapter {turn.chapterIndex} • Turn {turn.turnIndex}
                        </span>
                        {!isLatest && (
                          <span className="px-2 py-0.5 rounded text-[10px] bg-[var(--bg-subtle)] text-[var(--ink-soft)] border border-[var(--line)]">
                            History
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        <span>CP: {turn.checkpointId}</span>
                        {turns.length > 1 && (
                          <button
                            onClick={() => toggleTurnExpanded(i)}
                            className="p-1 rounded hover:bg-[var(--bg-subtle)] text-[var(--ink-soft)] hover:text-[var(--ink-main)] transition-colors"
                            title="Collapse Turn"
                          >
                            <ChevronUpIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>

                    <div 
                      className="text-[var(--ink-main)] text-[16px] leading-loose font-serif space-y-5 whitespace-pre-wrap"
                      dangerouslySetInnerHTML={{ __html: turn.output.replace(/\n/g, '<br />') }}
                    />

                    {/* Turn Card Footer & Contextual Reroll Button */}
                    <div className="flex items-center justify-between pt-4 border-t border-[var(--line-2)] text-xs text-[var(--ink-soft)] font-mono">
                      <span>{turn.timestamp ? new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                      {isLatest && (
                        <button
                          onClick={handleRegenerate}
                          disabled={loading}
                          className="pill-btn px-3 py-1.5 text-xs flex items-center gap-1.5 shadow-sm disabled:opacity-50 hover:border-[var(--periwinkle-dark)] transition-colors"
                          title="Reroll/Regenerate this latest turn"
                        >
                          <ArrowPathIcon className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                          <span>Reroll Turn</span>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          <div ref={chatEndRef} />
        </div>

        {/* Bottom Action Input Bar */}
        <div className="p-4 border-t border-[var(--line-2)] glass-panel z-10">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
              placeholder="What do you do? (e.g., Step forward and inspect the glowing dragon altar...)"
              disabled={loading}
              className="flex-1 px-5 py-3.5 rounded-2xl bg-[var(--bg-surface)] border-2 border-[var(--line)] text-[var(--ink-main)] font-medium text-[15px] focus:outline-none focus:border-[var(--accent-sage)] transition-colors shadow-inner placeholder:text-[var(--ink-faint)] focus:bg-[var(--bg-subtle)] disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="pill-btn pill-btn-primary px-6 py-3.5 rounded-2xl text-[15px] flex items-center gap-2 shadow-[var(--shadow-sm)] disabled:opacity-50"
            >
              <span>{loading ? 'Thinking...' : 'Send'}</span>
              <PaperAirplaneIcon className="w-5 h-5" />
            </button>
          </div>
        </div>
      </main>

      {/* RIGHT ICON STRIP & SLIDE-IN DRAWERS */}
      <div className="flex z-20 h-full shrink-0">
        {/* Active Drawer Panel */}
        {activeDrawer && (
          <div className="w-96 glass-panel rounded-none border-y-0 border-r-0 p-6 flex flex-col h-full animate-slide-in-right shadow-[var(--shadow-md)]">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--line-2)] mb-6">
              <h3 className="text-[15px] font-bold text-[var(--ink-main)] uppercase tracking-wider font-mono flex items-center gap-2">
                {activeDrawer === 'inventory' && <BriefcaseIcon   className="w-5 h-5 text-[var(--accent-peach)]" />}
                {activeDrawer === 'map' && <MapIcon   className="w-5 h-5 text-[var(--accent-sage)]" />}
                {activeDrawer === 'codex' && <BookOpenIcon   className="w-5 h-5 text-[var(--gold-dark)]" />}
                {activeDrawer === 'status' && <UserIcon   className="w-5 h-5 text-[var(--ok)]" />}
                {activeDrawer === 'skills' && <BoltIcon   className="w-5 h-5 text-[var(--warn)]" />}
                {activeDrawer === 'foreshadowing' && <EyeIcon   className="w-5 h-5 text-[var(--danger)]" />}
                <span>{activeDrawer}</span>
              </h3>
              <button
                onClick={() => setActiveDrawer(null)}
                className="p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4">
              {/* 1. Inventory Drawer */}
              {activeDrawer === 'inventory' && (
                <div className="space-y-3">
                  {playState?.unlocked_cards?.filter((c: any) => c.type === 'item').length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No items in inventory.</p>
                  ) : (
                    playState?.unlocked_cards?.filter((c: any) => c.type === 'item').map((item: any) => (
                      <div key={item.id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[15px] text-[var(--ink-main)]">{item.name}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[var(--bg-subtle)] text-[var(--accent-sage)] border border-[var(--line)]">{item.rarity || 'Common'}</span>
                        </div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{item.content}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 2. Map Drawer */}
              {activeDrawer === 'map' && (
                <div className="space-y-4">
                  <LocationMap locations={locations} />
                </div>
              )}

              {/* 3. Codex Drawer */}
              {activeDrawer === 'codex' && (
                <div className="space-y-6">
                  <div className="h-64 rounded-2xl border-2 border-[var(--line)] overflow-hidden shadow-inner bg-[var(--bg-surface)]">
                    <CodexGraph nodes={affinityGraph.nodes} edges={affinityGraph.edges} />
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-[11px] font-mono uppercase font-bold text-[var(--ink-soft)] pl-1">Unlocked Lore Cards</h4>
                    {playState?.unlocked_cards?.map((card: any) => (
                      <div key={card.id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[14px] text-[var(--ink-main)] font-[var(--font-display)]">{card.name}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[rgba(var(--sakura-rgb),0.15)] text-[var(--accent-peach)] border border-[rgba(var(--sakura-rgb),0.3)]">{card.type}</span>
                        </div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{card.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Status Drawer */}
              {activeDrawer === 'status' && protagonist && (
                <div className="space-y-4">
                  <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-4">
                    <div className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)]">{protagonist.name}</div>
                    <div className="grid grid-cols-2 gap-3 text-[13px] font-mono font-bold">
                      <div className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line)]">
                        <span className="text-[var(--ink-soft)] block uppercase text-[10px] tracking-wider mb-1">Realm</span>
                        <span className="text-[var(--accent-sage)]">{protagonist.power_stat?.realm || 'Mortal'}</span>
                      </div>
                      <div className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line)]">
                        <span className="text-[var(--ink-soft)] block uppercase text-[10px] tracking-wider mb-1">EXP</span>
                        <span className="text-[var(--accent-peach)]">{protagonist.power_stat?.exp || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Knowledge Flags */}
                  {protagonist.knowledge_flags?.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <h4 className="text-[11px] font-mono uppercase font-bold text-[var(--ink-soft)] pl-1">Knowledge Flags</h4>
                      {protagonist.knowledge_flags.map((flag: string) => (
                        <div key={flag} className="p-2.5 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] text-[12px] text-[var(--ink-main)] font-mono font-bold shadow-sm">
                          ◆ {flag}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 5. Skills Drawer */}
              {activeDrawer === 'skills' && (
                <div className="space-y-3">
                  {protagonist?.power_stat?.known_skills?.map((skill: string) => (
                    <div key={skill} className="p-3.5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm text-[14px] font-bold text-[var(--ink-main)] flex items-center gap-3">
                      <FireIcon   className="w-5 h-5 text-[var(--gold-dark)]" />
                      <span>{skill}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 6. Foreshadowing Drawer */}
              {activeDrawer === 'foreshadowing' && (
                <div className="space-y-3">
                  {playState?.foreshadowing_tracker?.length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No active foreshadowings.</p>
                  ) : (
                    playState?.foreshadowing_tracker?.map((f: any, i: number) => (
                      <div key={i} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="text-[14px] font-bold text-[var(--danger)] font-[var(--font-display)]">{f.title || f.id}</div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{f.description || JSON.stringify(f)}</p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Right Vertical Icon Strip */}
        <div className="w-16 glass-panel border-y-0 border-r-0 flex flex-col items-center py-6 space-y-5 z-10 shadow-sm">
          <button
            onClick={() => setActiveDrawer(activeDrawer === 'inventory' ? null : 'inventory')}
            title="Inventory"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'inventory' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BriefcaseIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'map' ? null : 'map')}
            title="World Map"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'map' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <MapIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'codex' ? null : 'codex')}
            title="Codex & Affinity Graph"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'codex' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BookOpenIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'status' ? null : 'status')}
            title="Protagonist Status"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'status' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <UserIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'skills' ? null : 'skills')}
            title="Known Skills"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'skills' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BoltIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'foreshadowing' ? null : 'foreshadowing')}
            title="Foreshadowing Tracker"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'foreshadowing' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <EyeIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};
