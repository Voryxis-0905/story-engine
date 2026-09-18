import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePlaySession } from './usePlaySession';
import { WORLD_RESTORED_EVENT } from './types';

const mocks = vi.hoisted(() => ({
  api: {
    play: {
      state: vi.fn(),
      getChapters: vi.fn(),
      continue: vi.fn(),
      start: vi.fn(),
      regenerate: vi.fn(),
      prelude: { generate: vi.fn(), confirm: vi.fn(), regenerate: vi.fn() },
    },
    map: { status: vi.fn(), get: vi.fn(), previewTravel: vi.fn() },
    worlds: { affinityGraph: vi.fn(), updateConfig: vi.fn() },
    discovery: { questBoard: vi.fn(), journal: vi.fn() },
  },
}));

vi.mock('../../api/client', () => ({ api: mocks.api }));

const api = mocks.api;

function playState(overrides: Record<string, any> = {}) {
  return {
    protagonist: { id: 'char_xueli', name: 'Xueli', location: 'Sect', power_stat: {}, traits: {}, knowledge_flags: [], inventory: [], alive: true, relationships: {}, age: '' },
    arc_progress: { current_checkpoint_id: 'cp_0', current_index: 0, total_checkpoints: 1, completed: [] },
    unlocked_cards: [],
    story_clock: {},
    foreshadowing_tracker: [],
    style_card: {},
    output_length: 'Standard',
    ...overrides,
  };
}

function chapter(overrides: Record<string, any> = {}) {
  return { chapter_index: 1, turn_index: 1, chapter_closed: false, chapter_title: null, checkpoint_id: 'cp_0', user_input: 'go', chapter_text: 'The road opens.', ...overrides };
}

beforeEach(() => {
  sessionStorage.clear();
  api.play.state.mockResolvedValue(playState());
  api.play.getChapters.mockResolvedValue([]);
  api.play.continue.mockResolvedValue({ chapter: chapter() });
  api.play.start.mockResolvedValue({ chapter: chapter() });
  api.play.regenerate.mockResolvedValue({});
  api.play.prelude.generate.mockResolvedValue({});
  api.play.prelude.confirm.mockResolvedValue({});
  api.map.status.mockResolvedValue({ locations: [] });
  api.map.get.mockResolvedValue({ locations: [] });
  api.map.previewTravel.mockResolvedValue({ status: 'available', destination: 'Old Forest', route: ['Sect', 'Old Forest'], legs: [], elapsed_minutes: 90, estimated_ticks: 2, risk: { level: 'low', known_tags: [] } });
  api.worlds.affinityGraph.mockResolvedValue({ nodes: [], edges: [] });
  api.worlds.updateConfig.mockResolvedValue({});
  api.discovery.questBoard.mockResolvedValue({ quests: [], enabled: true });
  api.discovery.journal.mockResolvedValue({ entries: [] });
});

function render(world = 'WorldA') {
  return renderHook(({ name }) => usePlaySession(name), { initialProps: { name: world } });
}

describe('usePlaySession input/retry loop', () => {
  it('turns a map destination into an editable travel intent', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());
    act(() => result.current.handleTravelTo({ id: 'forest', name: 'Old Forest' }));
    expect(result.current.input).toBe('Travel to Old Forest.');
    expect(result.current.activeDrawer).toBeNull();
    expect(api.play.continue).not.toHaveBeenCalled();
  });

  it('previews travel without sending or changing the input', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());
    act(() => result.current.setInput('keep this draft'));
    await act(async () => { await result.current.handlePreviewTravel({ id: 'forest', name: 'Old Forest' }); });
    expect(api.map.previewTravel).toHaveBeenCalledWith('WorldA', 'Old Forest');
    expect(result.current.travelPreview?.elapsed_minutes).toBe(90);
    expect(result.current.input).toBe('keep this draft');
    expect(api.play.continue).not.toHaveBeenCalled();
  });

  it('turns an inventory command into editable input without mutating state', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());
    act(() => result.current.handleItemAction('Equip', { instance_id: 'blade_1', name: 'Moon Blade' } as any));
    expect(result.current.input).toBe('Equip Moon Blade.');
    expect(api.play.continue).not.toHaveBeenCalled();
  });

  it('keeps the typed input when a send fails and retries exactly once', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());

    api.play.continue.mockRejectedValueOnce(new Error('network down'));
    act(() => result.current.setInput('look around the altar'));
    await act(async () => { await result.current.handleSend(); });

    expect(api.play.continue).toHaveBeenCalledTimes(1);
    expect(result.current.input).toBe('look around the altar');
    expect(result.current.error).toMatch(/network down/);

    await act(async () => { await result.current.handleSend(); });
    expect(api.play.continue).toHaveBeenCalledTimes(2);
    expect(result.current.input).toBe('');
    expect(result.current.turns).toHaveLength(1);
  });

  it('does not send twice when the button is clicked again while in flight', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());

    let release: (value: any) => void = () => {};
    api.play.continue.mockImplementation(() => new Promise((resolve) => { release = resolve; }));

    act(() => result.current.setInput('run forward'));
    await act(async () => { result.current.handleSend(); });
    await act(async () => { result.current.handleSend(); });

    expect(api.play.continue).toHaveBeenCalledTimes(1);
    await act(async () => { release({ chapter: chapter() }); });
  });

  it('keeps newer typing instead of overwriting it after a successful send', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());

    let release: (value: any) => void = () => {};
    api.play.continue.mockImplementation(() => new Promise((resolve) => { release = resolve; }));

    act(() => result.current.setInput('first action'));
    await act(async () => { result.current.handleSend(); });
    act(() => result.current.setInput('next action typed while waiting'));
    await act(async () => { release({ chapter: chapter() }); });

    expect(result.current.input).toBe('next action typed while waiting');
  });
});

describe('usePlaySession world isolation', () => {
  it('ignores a response from the previous world after switching', async () => {
    const { result, rerender } = render('WorldA');
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldA'));

    let release: (value: any) => void = () => {};
    api.play.continue.mockImplementation(() => new Promise((resolve) => { release = resolve; }));

    act(() => result.current.setInput('act in A'));
    await act(async () => { result.current.handleSend(); });

    rerender({ name: 'WorldB' });
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldB'));

    await act(async () => { release({ chapter: chapter({ chapter_text: 'Old world reply' }) }); });

    expect(result.current.turns).toHaveLength(0);
    expect(result.current.playState).toEqual(playState());
  });

  it('a late success from a previous world does not unlock the new world request', async () => {
    const { result, rerender } = render('WorldA');
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldA'));

    let releaseA: (value: any) => void = () => {};
    api.play.continue.mockImplementationOnce(() => new Promise((resolve) => { releaseA = resolve; }));
    act(() => result.current.setInput('act A'));
    await act(async () => { result.current.handleSend(); });

    rerender({ name: 'WorldB' });
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldB'));

    let releaseB: (value: any) => void = () => {};
    api.play.continue.mockImplementationOnce(() => new Promise((resolve) => { releaseB = resolve; }));
    act(() => result.current.setInput('act B'));
    await act(async () => { result.current.handleSend(); });

    await act(async () => { releaseA({ chapter: chapter({ chapter_text: 'Old A reply' }) }); });

    expect(result.current.loading).toBe(true);
    await act(async () => { result.current.handleSend(); });
    expect(api.play.continue).toHaveBeenCalledTimes(2);

    await act(async () => { releaseB({ chapter: chapter({ chapter_text: 'B reply' }) }); });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.turns).toHaveLength(1);
  });

  it('a late error from a previous world does not set the new world error', async () => {
    const { result, rerender } = render('WorldA');
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldA'));

    let rejectA: (reason: any) => void = () => {};
    api.play.continue.mockImplementationOnce(() => new Promise((_resolve, reject) => { rejectA = reject; }));
    act(() => result.current.setInput('act A'));
    await act(async () => { result.current.handleSend(); });

    rerender({ name: 'WorldB' });
    await waitFor(() => expect(api.play.state).toHaveBeenCalledWith('WorldB'));

    await act(async () => { rejectA(new Error('late A failure')); });

    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });
});

describe('usePlaySession committed data refresh', () => {
  it('reloads map and affinity graph after a committed turn', async () => {
    const { result } = render();
    await waitFor(() => expect(api.map.status).toHaveBeenCalledTimes(1));
    const mapCalls = api.map.status.mock.calls.length;
    const graphCalls = api.worlds.affinityGraph.mock.calls.length;

    act(() => result.current.setInput('go'));
    await act(async () => { await result.current.handleSend(); });

    expect(api.map.status.mock.calls.length).toBe(mapCalls + 1);
    expect(api.worlds.affinityGraph.mock.calls.length).toBe(graphCalls + 1);
  });

  it('reloads chapters, map and affinity graph after regenerate', async () => {
    const { result } = render();
    await waitFor(() => expect(api.map.status).toHaveBeenCalledTimes(1));
    const chapterCalls = api.play.getChapters.mock.calls.length;
    const mapCalls = api.map.status.mock.calls.length;
    const graphCalls = api.worlds.affinityGraph.mock.calls.length;

    await act(async () => { await result.current.handleRegenerate(); });

    expect(api.play.regenerate).toHaveBeenCalledTimes(1);
    expect(api.play.getChapters.mock.calls.length).toBe(chapterCalls + 1);
    expect(api.map.status.mock.calls.length).toBe(mapCalls + 1);
    expect(api.worlds.affinityGraph.mock.calls.length).toBe(graphCalls + 1);
  });

  it('loads quests and journal and refreshes them after a committed turn', async () => {
    api.discovery.questBoard.mockResolvedValue({
      quests: [{ quest_id: 'q1', title: 'Find the relic', status: 'active' }], enabled: true,
    });
    api.discovery.journal.mockResolvedValue({
      entries: [{ quest_id: 'q1', title: 'Find the relic', status: 'active', source: { kind: 'start' }, discovered_at_tick: 0 }],
    });
    const { result } = render();
    await waitFor(() => expect(result.current.quests).toHaveLength(1));
    expect(result.current.journal).toHaveLength(1);

    const questCalls = api.discovery.questBoard.mock.calls.length;
    act(() => result.current.setInput('go'));
    await act(async () => { await result.current.handleSend(); });
    await waitFor(() => expect(api.discovery.questBoard.mock.calls.length).toBe(questCalls + 1));
  });

  it('reloads on a restore event for the matching world', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalledTimes(1));

    await act(async () => {
      window.dispatchEvent(new CustomEvent(WORLD_RESTORED_EVENT, { detail: { worldName: 'WorldA' } }));
    });

    expect(api.play.state.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(result.current).toBeTruthy();
  });
});

describe('usePlaySession output length', () => {
  it('loads the saved length and persists a new one to the backend', async () => {
    api.play.state.mockResolvedValue(playState({ output_length: 'Detailed' }));
    const { result } = render();
    await waitFor(() => expect(result.current.outputLength).toBe('long'));

    act(() => result.current.setOutputLength('short'));
    expect(result.current.outputLength).toBe('short');
    expect(api.worlds.updateConfig).toHaveBeenCalledWith('WorldA', { output_length: 'Concise' });
  });
});

describe('usePlaySession request ids', () => {
  it('reuses the id for a retry of the same action and uses a new one for a new action', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());

    api.play.continue.mockRejectedValueOnce(new Error('network down'));
    act(() => result.current.setInput('open the door'));
    await act(async () => { await result.current.handleSend(); });
    const firstId = api.play.continue.mock.calls[0][2].requestId;
    expect(firstId).toBeTruthy();

    await act(async () => { await result.current.handleSend(); });
    const retryId = api.play.continue.mock.calls[1][2].requestId;
    expect(retryId).toBe(firstId);

    act(() => result.current.setInput('run away'));
    await act(async () => { await result.current.handleSend(); });
    const newId = api.play.continue.mock.calls[2][2].requestId;
    expect(newId).toBeTruthy();
    expect(newId).not.toBe(firstId);
  });
});

describe('usePlaySession not-saved drafts', () => {
  it('stores a blocked turn as a draft and clears it on dismiss', async () => {
    const { result } = render();
    await waitFor(() => expect(api.play.state).toHaveBeenCalled());

    const blocked: any = new Error('Kept as a draft and was NOT saved.');
    blocked.detail = {
      reason: 'consistency_check_failed', status: 'failed', persisted: false,
      draft_chapter_text: 'Draft scene text', message: 'Retry the action.',
    };
    api.play.continue.mockRejectedValueOnce(blocked);

    act(() => result.current.setInput('open the door'));
    await act(async () => { await result.current.handleSend(); });

    expect(result.current.draft?.text).toBe('Draft scene text');
    expect(result.current.draft?.status).toBe('failed');
    expect(result.current.input).toBe('open the door');
    expect(sessionStorage.getItem('story-engine:draft:WorldA')).toContain('Draft scene text');
    expect(result.current.turns).toHaveLength(0);

    act(() => result.current.handleDismissDraft());
    expect(result.current.draft).toBeNull();
    expect(sessionStorage.getItem('story-engine:draft:WorldA')).toBeNull();
  });

  it('clears a stored draft after a successful commit', async () => {
    sessionStorage.setItem('story-engine:draft:WorldA', JSON.stringify({
      worldName: 'WorldA', userInput: 'old', text: 'old draft',
      status: 'unavailable', reason: 'x', message: 'y', createdAt: 1,
    }));
    const { result } = render();
    await waitFor(() => expect(result.current.draft?.text).toBe('old draft'));

    act(() => result.current.setInput('try again'));
    await act(async () => { await result.current.handleSend(); });

    expect(result.current.draft).toBeNull();
    expect(sessionStorage.getItem('story-engine:draft:WorldA')).toBeNull();
    expect(result.current.turns).toHaveLength(1);
  });

  it('retryDraft resends the stored action after reload even with an empty input', async () => {
    sessionStorage.setItem('story-engine:draft:WorldA', JSON.stringify({
      worldName: 'WorldA', userInput: 'open the door', text: 'draft scene',
      status: 'failed', reason: 'consistency_check_failed', message: 'retry', createdAt: 1,
    }));
    const { result } = render();
    await waitFor(() => expect(result.current.draft?.userInput).toBe('open the door'));
    expect(result.current.input).toBe('');

    await act(async () => { await result.current.handleRetryDraft(); });

    expect(api.play.continue).toHaveBeenCalledWith('WorldA', 'open the door', expect.anything());
    expect(result.current.draft).toBeNull();
    expect(result.current.input).toBe('');
    expect(result.current.turns).toHaveLength(1);
  });

  it('retryDraft sends the draft action and keeps what the player is typing', async () => {
    sessionStorage.setItem('story-engine:draft:WorldA', JSON.stringify({
      worldName: 'WorldA', userInput: 'open the door', text: 'draft scene',
      status: 'failed', reason: 'consistency_check_failed', message: 'retry', createdAt: 1,
    }));
    const { result } = render();
    await waitFor(() => expect(result.current.draft).not.toBeNull());

    act(() => result.current.setInput('a different action'));
    await act(async () => { await result.current.handleRetryDraft(); });

    expect(api.play.continue).toHaveBeenCalledWith('WorldA', 'open the door', expect.anything());
    expect(result.current.input).toBe('a different action');
    expect(result.current.turns).toHaveLength(1);
  });
});
