import type { PlaySession } from './usePlaySession';
import { ArrowPathIcon, ChevronDownIcon, ChevronUpIcon, PaperAirplaneIcon, PlayIcon, SparklesIcon, XMarkIcon } from '@heroicons/react/24/outline';

type Props = Pick<PlaySession, 'turns' | 'input' | 'setInput' | 'loading' | 'error' | 'setError' | 'outputLength' | 'setOutputLength' | 'expandedTurns' | 'toggleTurnExpanded' | 'collapseAllPrevious' | 'expandAllTurns' | 'preludeText' | 'draft' | 'handleDismissDraft' | 'handleRetryDraft' | 'epilogue' | 'lifecycleStatus' | 'epilogueChoices' | 'handleLoadEndgameChoices' | 'handleChooseEnding' | 'chatEndRef' | 'handleSend' | 'handleStartChapter' | 'handleRegenerate' | 'handleGeneratePrelude' | 'handleConfirmPrelude'>;

export function PlayNarrative({ turns, input, setInput, loading, error, setError, outputLength, setOutputLength, expandedTurns, toggleTurnExpanded, collapseAllPrevious, expandAllTurns, preludeText, draft, handleDismissDraft, handleRetryDraft, epilogue, lifecycleStatus, epilogueChoices, handleLoadEndgameChoices, handleChooseEnding, chatEndRef, handleSend, handleStartChapter, handleRegenerate, handleGeneratePrelude, handleConfirmPrelude }: Props) {
  return (<>
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

        {/* Not-saved draft: the checker blocked the turn, so nothing was
            committed. Keep the text visible and offer a retry path. */}
        {draft && (
          <div className="mx-6 mt-4 p-4 rounded-xl bg-[rgba(var(--warn-rgb),0.10)] border border-[rgba(var(--warn-rgb),0.35)] text-[var(--ink-main)] shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--warn)]">
                Draft — not saved ({draft.status})
              </span>
              <button
                onClick={handleDismissDraft}
                className="text-xs font-bold text-[var(--ink-soft)] hover:text-[var(--ink-main)] underline decoration-dotted"
              >
                Dismiss
              </button>
            </div>
            {draft.message && <p className="mt-1 text-xs text-[var(--ink-soft)]">{draft.message}</p>}
            <div className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap text-sm font-serif leading-relaxed border-t border-[var(--line-2)] pt-2">
              {draft.text}
            </div>
            <div className="mt-3 flex items-center justify-end">
              <button
                onClick={handleRetryDraft}
                disabled={loading}
                className="pill-btn pill-btn-primary px-4 py-2 text-xs font-bold disabled:opacity-50"
              >
                Retry action
              </button>
            </div>
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

                    <div className="text-[var(--ink-main)] text-[16px] leading-loose font-serif space-y-5 whitespace-pre-wrap">
                      {turn.output}
                    </div>

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

        {/* Endgame / Epilogue */}
        {lifecycleStatus === 'endgame_pending' && (
          <div className="mx-6 mt-4 p-4 rounded-xl bg-[rgba(var(--sakura-rgb),0.10)] border border-[rgba(var(--sakura-rgb),0.35)]">
            <p className="text-sm font-bold text-[var(--ink-main)]">The ending is within reach.</p>
            {epilogueChoices.length === 0 ? (
              <button
                onClick={handleLoadEndgameChoices}
                disabled={loading}
                className="pill-btn pill-btn-primary mt-3 px-4 py-2 text-xs font-bold disabled:opacity-50"
              >
                Choose how it ends
              </button>
            ) : (
              <div className="mt-3 flex flex-col gap-2">
                {epilogueChoices.map((choice) => (
                  <button
                    key={choice}
                    onClick={() => handleChooseEnding(choice)}
                    disabled={loading}
                    className="pill-btn pill-btn-secondary px-4 py-2 text-xs font-bold text-left disabled:opacity-50"
                  >
                    {choice}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {lifecycleStatus === 'completed' && epilogue && (
          <div className="mx-6 mt-4 p-5 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line-2)]">
            <p className="text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2">Epilogue</p>
            <div className="text-[15px] leading-relaxed font-serif whitespace-pre-wrap text-[var(--ink-main)]">{epilogue.text}</div>
            <p className="mt-3 text-xs text-[var(--ink-soft)]">The story has ended. Create a branch from a save to explore another path.</p>
          </div>
        )}

        {/* Bottom Action Input Bar */}
        {lifecycleStatus !== 'completed' && (
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
        )}
      </main>


  </>);
}
