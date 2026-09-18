import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PlayNarrative } from './PlayNarrative';

function props(turns: any[]) {
  return {
    turns,
    input: '',
    setInput: () => {},
    loading: false,
    error: null,
    setError: () => {},
    outputLength: 'medium',
    setOutputLength: () => {},
    expandedTurns: { 0: true },
    toggleTurnExpanded: () => {},
    collapseAllPrevious: () => {},
    expandAllTurns: () => {},
    preludeText: null,
    draft: null,
    handleDismissDraft: () => {},
    handleRetryDraft: () => {},
    epilogue: null,
    lifecycleStatus: 'active',
    epilogueChoices: [],
    handleLoadEndgameChoices: () => {},
    handleChooseEnding: () => {},
    chatEndRef: { current: null },
    handleSend: () => {},
    handleStartChapter: () => {},
    handleRegenerate: () => {},
    handleGeneratePrelude: () => {},
    handleConfirmPrelude: () => {},
  } as any;
}

describe('PlayNarrative story rendering', () => {
  it('renders model output as text and does not execute injected HTML', () => {
    (window as any).__pwned = false;
    const output = 'Safe line\n<img src=x onerror="window.__pwned=true"><script>window.__pwned=true</script>';
    const { container } = render(
      <PlayNarrative {...props([{
        input: 'go',
        output,
        chapterIndex: 1,
        turnIndex: 1,
        checkpointId: 'cp_0',
        timestamp: Date.now(),
      }])} />
    );

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('script')).toBeNull();
    expect((window as any).__pwned).toBe(false);
    expect(container.textContent).toContain('<img src=x onerror="window.__pwned=true">');
  });

  it('shows a not-saved draft with its text and a retry path', () => {
    const handleSend = vi.fn();
    const handleRetryDraft = vi.fn();
    const handleDismissDraft = vi.fn();
    render(
      <PlayNarrative {...props([])} draft={{
        worldName: 'WorldA',
        userInput: 'open the door',
        text: 'The draft scene that was not committed.',
        status: 'failed',
        reason: 'consistency_check_failed',
        message: 'Kept as a draft, retry the action.',
        createdAt: 1,
      }} handleDismissDraft={handleDismissDraft} handleRetryDraft={handleRetryDraft} handleSend={handleSend} />
    );

    expect(screen.getByText(/not saved/i)).toBeInTheDocument();
    expect(screen.getByText('The draft scene that was not committed.')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Retry action'));
    expect(handleRetryDraft).toHaveBeenCalledTimes(1);
    expect(handleSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('Dismiss'));
    expect(handleDismissDraft).toHaveBeenCalledTimes(1);
  });
});
