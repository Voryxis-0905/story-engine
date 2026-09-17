import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  XMarkIcon,
  SparklesIcon,
  ArrowRightIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  ChatBubbleLeftEllipsisIcon,
  CpuChipIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/react/24/solid';
import { SparklesIcon as MagicWand } from '@heroicons/react/24/outline';
import { api } from '../../api/client';

interface WorldBuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (worldName: string) => void;
}

export const WorldBuilderModal: React.FC<WorldBuilderModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const navigate = useNavigate();

  // Wizard Steps: 1 (Concept), 2 (Interview), 3 (Generating Pipeline), 4 (Prelude Review)
  const [step, setStep] = useState<number>(1);
  const [worldName, setWorldName] = useState('');
  const [conceptPrompt, setConceptPrompt] = useState('');
  const [scopeType, setScopeType] = useState<'arc-only' | 'one-shot' | 'full-story'>('arc-only');

  // Step 2: Interview state
  const [questions, setQuestions] = useState<string[]>([]);
  const [answers, setAnswers] = useState<string[]>([]);

  // Step 3: Generation pipeline status
  const [genPhase, setGenPhase] = useState<'skeleton' | 'cards' | 'characters' | 'prelude'>('skeleton');
  const [genProgressText, setGenProgressText] = useState('Synthesizing world timeline & checkpoints...');

  // Step 4: Prelude text
  const [preludeText, setPreludeText] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Sync DOM textarea value with React state for programmatic changes
  useEffect(() => {
    if (textareaRef.current && textareaRef.current.value !== conceptPrompt) {
      setConceptPrompt(textareaRef.current.value);
    }
  }, [conceptPrompt]);

  if (!isOpen) return null;

  // Step 1 -> Step 2: Trigger AI Interview
  const handleStartInterview = async () => {
    if (!worldName.trim()) {
      setError('Please enter a world identifier / name.');
      return;
    }
    if (!conceptPrompt.trim()) {
      setError('Please enter a story concept or world idea.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await api.builder.interview(conceptPrompt.trim(), scopeType);
      const qList = res?.questions || [
        'What is the main tone of this world (dark, humorous, epic)?',
        'What role will the protagonist play and what is their core goal?',
        'What is the power system or most unique rule of this realm?',
      ];
      setQuestions(qList);
      setAnswers(new Array(qList.length).fill(''));
      setStep(2);
    } catch (e: any) {
      setError(e.message || 'Failed to start AI interview. Check your backend connection.');
    } finally {
      setLoading(false);
    }
  };

  // Step 2 -> Step 3 & 4: Submit Interview Answers and execute Multi-Step AI Generation
  const handleGenerateWorld = async () => {
    const sanitizedName = worldName.trim().replace(/\s+/g, '_');
    setLoading(true);
    setError(null);
    setStep(3);

    try {
      // 1. Send interview answers to get refined prompt
      setGenProgressText('Formulating refined world concept from interview answers...');
      const respondRes = await api.builder.interviewRespond(conceptPrompt.trim(), answers, scopeType);
      const finalPrompt = respondRes.refined_prompt || conceptPrompt.trim();

      // 2. Create World with initial prompt & scope
      setGenProgressText('Initializing world repository...');
      await api.worlds.create(sanitizedName, {
        prompt: finalPrompt,
        scope_type: scopeType,
        interaction_mode: 'normal',
      });

      // 3. Phase 1: Skeleton & Checkpoints Timeline
      setGenPhase('skeleton');
      setGenProgressText('Phase 1/4: Generating narrative skeleton & canon checkpoints...');
      await api.builder.step(sanitizedName);

      // Confirm Checkpoints to transition status to "cards"
      await api.builder.confirmCheckpoints(sanitizedName);

      // 4. Phase 2: Lore Cards
      setGenPhase('cards');
      setGenProgressText('Phase 2/4: Generating world lore, factions, & items...');
      await api.builder.step(sanitizedName);

      // 5. Phase 3: Characters & Location Map
      setGenPhase('characters');
      setGenProgressText('Phase 3/4: Synthesizing character attributes & location map...');
      await api.builder.step(sanitizedName);

      // 6. Phase 4: Narrative Prelude
      setGenPhase('prelude');
      setGenProgressText('Phase 4/4: Writing opening prelude...');
      const preludeRes = await api.play.prelude.generate(sanitizedName);
      setPreludeText(preludeRes?.prelude?.chapter_text || preludeRes?.prelude_text || 'In an ancient realm bound by mysterious covenants...');

      // Complete! Transition to Step 4
      setStep(4);
    } catch (e: any) {
      setError(e.message || 'World generation failed. Ensure your API Key is configured in Settings.');
      setStep(2); // Return to step 2 on error so user can retry
    } finally {
      setLoading(false);
    }
  };

  // Step 4: Confirm Prelude & Navigate to Play
  const handleConfirmPrelude = async () => {
    const sanitizedName = worldName.trim().replace(/\s+/g, '_');
    setLoading(true);
    setError(null);
    try {
      await api.play.prelude.confirm(sanitizedName);
      if (onSuccess) onSuccess(sanitizedName);
      onClose();
      navigate(`/worlds/${sanitizedName}/play`);
    } catch (e: any) {
      setError(e.message || 'Failed to confirm prelude');
    } finally {
      setLoading(false);
    }
  };

  const handleRegeneratePrelude = async () => {
    const sanitizedName = worldName.trim().replace(/\s+/g, '_');
    setLoading(true);
    setError(null);
    try {
      const preludeRes = await api.play.prelude.regenerate(sanitizedName);
      setPreludeText(preludeRes?.prelude?.chapter_text || preludeRes?.prelude_text || 'Prelude regenerated...');
    } catch (e: any) {
      setError(e.message || 'Failed to regenerate prelude');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--ink-main)]/50 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-2xl bg-[var(--bg-surface)] border border-[var(--line)] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] transition-all duration-300">
        
        {/* Header */}
        <div className="px-8 py-5 border-b border-[var(--line-2)] flex items-center justify-between bg-[var(--bg-subtle)]/50 shrink-0">
          <div className="flex items-center gap-3">
            <MagicWand className="w-6 h-6 text-[var(--accent-sage)]" />
            <div>
              <h2 className="text-lg font-extrabold tracking-tight text-[var(--ink-main)] font-[var(--font-display)]">
                AI World Builder Wizard
              </h2>
              <p className="text-xs text-[var(--ink-soft)]">
                {step === 1 && 'Step 1: Enter raw concept & story scope'}
                {step === 2 && 'Step 2: AI Clarification Interview'}
                {step === 3 && 'Step 3: Multi-step AI lore synthesis'}
                {step === 4 && 'Step 4: Review opening prelude'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--line-2)] transition-colors"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Progress Step Bar */}
        <div className="px-8 py-2.5 bg-[var(--bg-subtle)]/30 border-b border-[var(--line-2)] flex items-center justify-between text-xs font-mono text-[var(--ink-soft)]">
          <span className={`flex items-center gap-1.5 ${step >= 1 ? 'text-[var(--accent-sage)] font-bold' : ''}`}>
            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">1</span>
            Concept
          </span>
          <span className="text-[var(--line-2)]">&rarr;</span>
          <span className={`flex items-center gap-1.5 ${step >= 2 ? 'text-[var(--accent-sage)] font-bold' : ''}`}>
            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">2</span>
            Interview
          </span>
          <span className="text-[var(--line-2)]">&rarr;</span>
          <span className={`flex items-center gap-1.5 ${step >= 3 ? 'text-[var(--accent-sage)] font-bold' : ''}`}>
            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">3</span>
            Synthesis
          </span>
          <span className="text-[var(--line-2)]">&rarr;</span>
          <span className={`flex items-center gap-1.5 ${step >= 4 ? 'text-[var(--accent-sage)] font-bold' : ''}`}>
            <span className="w-5 h-5 rounded-full border border-current flex items-center justify-center text-[10px]">4</span>
            Prelude
          </span>
        </div>

        {/* Modal Body */}
        <div className="p-8 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-600 dark:text-red-400 text-sm font-semibold shadow-sm space-y-1">
              <div className="flex items-center gap-2">
                <QuestionMarkCircleIcon className="w-5 h-5 text-red-500 shrink-0" />
                <span>{error}</span>
              </div>
            </div>
          )}

          {/* STEP 1: CONCEPT & SCOPE INPUT */}
          {step === 1 && (
            <div className="space-y-5">
              <div>
                <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2">
                  World Identifier / Name *
                </label>
                <input
                  type="text"
                  value={worldName}
                  onChange={(e) => setWorldName(e.target.value)}
                  placeholder="e.g. Valdris_Realm"
                  className="w-full px-4 py-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[var(--ink-main)] font-bold text-sm focus:outline-none focus:border-[var(--accent-sage)] shadow-inner placeholder:text-[var(--ink-faint)]"
                />
              </div>

              <div>
                <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2">
                  Narrative Concept / Raw Idea *
                </label>
                <textarea
                  ref={textareaRef}
                  value={conceptPrompt}
                  onChange={(e) => setConceptPrompt(e.target.value)}
                  onInput={() => {
                    if (textareaRef.current) {
                      setConceptPrompt(textareaRef.current.value);
                    }
                  }}
                  rows={4}
                  placeholder="Describe your world idea freely in any language (e.g. Một thế giới tu tiên nơi linh khí suy giảm, ma giáo trỗi dậy và nhân vật chính mang trong mình ngọn lửa rồng cổ xưa...)"
                  className="w-full px-4 py-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[var(--ink-main)] text-sm focus:outline-none focus:border-[var(--accent-sage)] shadow-inner resize-none placeholder:text-[var(--ink-faint)] leading-relaxed"
                />
              </div>

              <div>
                <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2">
                  Narrative Scope (Length of Story Arc)
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { id: 'arc-only', title: 'Single Arc', desc: '5 Checkpoints' },
                    { id: 'one-shot', title: 'One-Shot', desc: '3 Checkpoints' },
                    { id: 'full-story', title: 'Full Story', desc: 'Multi-Arc Roadmap' },
                  ].map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setScopeType(item.id as any)}
                      className={`p-3.5 rounded-xl border text-left transition-all ${
                        scopeType === item.id
                          ? 'border-[var(--accent-sage)] bg-[var(--accent-sage)]/10 text-[var(--ink-main)] shadow-sm'
                          : 'border-[var(--line-2)] bg-[var(--bg-subtle)] text-[var(--ink-soft)] hover:border-[var(--line)]'
                      }`}
                    >
                      <div className="font-bold text-sm">{item.title}</div>
                      <div className="text-xs opacity-75">{item.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: AI INTERVIEW CLARIFICATIONS */}
          {step === 2 && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-xs text-[var(--ink-soft)] flex items-start gap-3">
                <ChatBubbleLeftEllipsisIcon className="w-5 h-5 text-[var(--accent-sage)] shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold text-[var(--ink-main)] block mb-1">AI World-Builder Interview</span>
                  To craft a coherent world skeleton, answer these clarifying questions or leave blank to let AI decide:
                </div>
              </div>

              <div className="space-y-4">
                {questions.map((q, idx) => (
                  <div key={idx} className="space-y-1.5">
                    <label className="block text-xs font-bold text-[var(--ink-main)]">
                      {idx + 1}. {q}
                    </label>
                    <input
                      type="text"
                      value={answers[idx] || ''}
                      onChange={(e) => {
                        const newAns = [...answers];
                        newAns[idx] = e.target.value;
                        setAnswers(newAns);
                      }}
                      placeholder="Type your answer or preference..."
                      className="w-full px-4 py-2.5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[var(--ink-main)] text-sm focus:outline-none focus:border-[var(--accent-sage)]"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 3: GENERATION PIPELINE Visualizer */}
          {step === 3 && (
            <div className="py-8 space-y-6 text-center">
              <div className="relative inline-flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-[var(--accent-sage)]/10 border border-[var(--accent-sage)]/30 flex items-center justify-center animate-pulse">
                  <CpuChipIcon className="w-8 h-8 text-[var(--accent-sage)] animate-spin" />
                </div>
              </div>

              <div>
                <h3 className="text-base font-bold text-[var(--ink-main)] mb-1">Synthesizing World & Lore</h3>
                <p className="text-xs font-mono text-[var(--ink-soft)]">{genProgressText}</p>
              </div>

              <div className="max-w-md mx-auto space-y-2 text-left text-xs font-mono">
                {[
                  { phase: 'skeleton', label: 'Phase 1: Skeleton & Checkpoints' },
                  { phase: 'cards', label: 'Phase 2: World Lore & Factions' },
                  { phase: 'characters', label: 'Phase 3: Characters & Map' },
                  { phase: 'prelude', label: 'Phase 4: Story Prelude' },
                ].map((item, idx) => {
                  const phases = ['skeleton', 'cards', 'characters', 'prelude'];
                  const curIdx = phases.indexOf(genPhase);
                  const itemIdx = phases.indexOf(item.phase);
                  const isDone = itemIdx < curIdx;
                  const isCurrent = itemIdx === curIdx;

                  return (
                    <div
                      key={item.phase}
                      className={`p-3 rounded-lg border flex items-center justify-between ${
                        isDone
                          ? 'border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400'
                          : isCurrent
                          ? 'border-[var(--accent-sage)] bg-[var(--accent-sage)]/10 text-[var(--ink-main)] font-bold'
                          : 'border-[var(--line-2)] text-[var(--ink-faint)] opacity-60'
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        {isDone ? (
                          <CheckCircleIcon className="w-4 h-4 text-emerald-500" />
                        ) : isCurrent ? (
                          <ArrowPathIcon className="w-4 h-4 animate-spin text-[var(--accent-sage)]" />
                        ) : (
                          <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[9px]">{idx + 1}</span>
                        )}
                        {item.label}
                      </span>
                      <span>{isDone ? 'DONE' : isCurrent ? 'GENERATING...' : 'WAITING'}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* STEP 4: PRELUDE REVIEW */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-bold flex items-center gap-2 shadow-sm">
                <CheckCircleIcon className="w-5 h-5 flex-shrink-0" />
                <span>World creation complete! Read the opening narrative prelude below:</span>
              </div>

              <div className="p-5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[var(--ink-main)] text-sm leading-relaxed font-serif max-h-64 overflow-y-auto shadow-inner whitespace-pre-wrap">
                {preludeText || 'Narrative prelude loading...'}
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-8 py-5 border-t border-[var(--line-2)] flex flex-wrap items-center justify-between gap-4 bg-[var(--bg-subtle)] shrink-0">
          {step === 1 && (
            <>
              <button
                onClick={onClose}
                className="pill-btn pill-btn-secondary px-6 py-2.5 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleStartInterview}
                disabled={loading || !worldName.trim() || !conceptPrompt.trim()}
                className="pill-btn pill-btn-primary px-6 py-2.5 text-sm flex items-center gap-2 shadow-sm disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <ArrowPathIcon className="w-4 h-4 animate-spin" />
                    <span>Analyzing Concept...</span>
                  </>
                ) : (
                  <>
                    <span>Next: AI Interview</span>
                    <ArrowRightIcon className="w-4 h-4" />
                  </>
                )}
              </button>
            </>
          )}

          {step === 2 && (
            <>
              <button
                onClick={() => setStep(1)}
                disabled={loading}
                className="pill-btn pill-btn-secondary px-5 py-2 text-xs"
              >
                &larr; Back to Idea
              </button>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleGenerateWorld}
                  disabled={loading}
                  className="pill-btn pill-btn-primary px-6 py-2.5 text-sm flex items-center gap-2 shadow-sm disabled:opacity-50"
                >
                  <SparklesIcon className="w-4 h-4" />
                  <span>Generate Full World</span>
                </button>
              </div>
            </>
          )}

          {step === 3 && (
            <div className="w-full text-center text-xs font-mono text-[var(--ink-soft)]">
              AI synthesis in progress, please do not close this window...
            </div>
          )}

          {step === 4 && (
            <>
              <button
                onClick={handleRegeneratePrelude}
                disabled={loading}
                className="pill-btn pill-btn-secondary px-5 py-2 text-xs flex items-center gap-1.5"
              >
                <ArrowPathIcon className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>Regenerate Prelude</span>
              </button>
              <button
                onClick={handleConfirmPrelude}
                disabled={loading}
                className="pill-btn pill-btn-primary px-6 py-2.5 text-sm flex items-center gap-2 shadow-sm disabled:opacity-50"
              >
                {loading ? (
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Confirm Prelude & Start Play</span>
                    <ArrowRightIcon className="w-4 h-4" />
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
