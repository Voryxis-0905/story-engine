const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export interface World {
  name: string;
  status?: string;
  updated_at?: number;
}

export interface WorldDetail {
  world_config: any;
  card_registry: any;
  canon_timeline: any;
  character_state: any;
  saves: any[];
}

export interface PlayState {
  protagonist: {
    id: string;
    name: string;
    location: string;
    power_stat: Record<string, any>;
    traits: Record<string, any>;
    knowledge_flags: string[];
    alive: boolean;
    relationships: Record<string, any>;
    age: string;
  } | null;
  arc_progress: {
    current_checkpoint_id: string;
    current_index: number;
    total_checkpoints: number;
    completed: string[];
  };
  unlocked_cards: any[];
  story_clock: Record<string, any>;
  foreshadowing_tracker: any[];
  style_card: any;
}

export interface ChapterContinueResponse {
  chapter: {
    chapter_index: number;
    turn_index: number;
    chapter_closed: boolean;
    chapter_title: string | null;
    checkpoint_id: string;
    user_input: string;
    chapter_text: string;
    notes?: string;
    boundary_correction?: any;
    consistency_check?: any;
  };
  state_changes_applied: any;
  used_mock_llm: boolean;
  checkpoint_advanced: boolean;
  lore_rag_filter: any;
}

export interface ChapterStartRequest {
  opening_mode?: 'ai_generate' | 'user_defined';
  opening_text?: string;
}

export interface LintChapterRequest {
  chapter_index: number;
  linter_suggestions: any[];
}

export interface RuntimeConfig {
  llm_provider: string;
  api_key?: string;
  model_name?: string;
  temperature?: number;
  base_url?: string;
  api_key_masked?: string;
  model?: string;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  worlds: {
    list: () => fetchJSON<{ worlds: World[] }>('/worlds').then(r => r.worlds),
    get: (name: string) => fetchJSON<WorldDetail>(`/worlds/${name}`),
    create: (name: string, payload?: { prompt?: string; scope_type?: string; interaction_mode?: string }) =>
      fetchJSON<any>(`/worlds/${name}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
      }),
    delete: (name: string) =>
      fetchJSON<any>(`/worlds/${name}`, { method: 'DELETE' }),
    seedDemo: (name: string, overwrite: boolean = false) =>
      fetchJSON<any>(`/worlds/${name}/seed-demo?overwrite=${overwrite}`, { method: 'POST' }),
    affinityGraph: (name: string) =>
      fetchJSON<{ nodes: any[]; edges: any[] }>(`/worlds/${name}/affinity-graph`),
    foreshadowings: {
      get: (name: string) => fetchJSON<any[]>(`/worlds/${name}/foreshadowings`),
      add: (name: string, payload: any) =>
        fetchJSON<any>(`/worlds/${name}/foreshadowings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }),
    },
  },
  play: {
    state: (worldName: string) =>
      fetchJSON<PlayState>(`/worlds/${worldName}/play-state`),
    start: (worldName: string, req: ChapterStartRequest = {}) =>
      fetchJSON<any>(`/worlds/${worldName}/chapter/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }),
    continue: (worldName: string, userInput: string) =>
      fetchJSON<ChapterContinueResponse>(`/worlds/${worldName}/chapter/continue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput }),
      }),
    regenerate: (worldName: string) =>
      fetchJSON<any>(`/worlds/${worldName}/chapter/regenerate`, { method: 'POST' }),
    getChapters: (worldName: string) =>
      fetchJSON<any[]>(`/worlds/${worldName}/chapters`),
    prelude: {
      generate: (worldName: string) =>
        fetchJSON<any>(`/worlds/${worldName}/chapter/generate-prelude`, { method: 'POST' }),
      regenerate: (worldName: string) =>
        fetchJSON<any>(`/worlds/${worldName}/chapter/regenerate-prelude`, { method: 'POST' }),
      confirm: (worldName: string) =>
        fetchJSON<any>(`/worlds/${worldName}/chapter/confirm-prelude`, { method: 'POST' }),
    },
    lint: (worldName: string, req: LintChapterRequest) =>
      fetchJSON<any>(`/worlds/${worldName}/lint-chapter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      }),
    rewrite: (worldName: string, chapterIndex: number, linterSuggestions: any[]) =>
      fetchJSON<any>(`/worlds/${worldName}/chapter/rewrite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_index: chapterIndex, linter_suggestions: linterSuggestions }),
      }),
  },
  builder: {
    interview: (prompt: string, scope_type: string = 'arc-only') =>
      fetchJSON<{ questions: string[] }>('/builder/interview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, scope_type }),
      }),
    interviewRespond: (prompt: string, answers: string[], scope_type: string = 'arc-only') =>
      fetchJSON<{ refined_prompt: string; scope_type?: string }>('/builder/interview/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, answers, scope_type }),
      }),
    confirmCheckpoints: (worldName: string) =>
      fetchJSON<{ status: string }>(`/worlds/${worldName}/builder/confirm-checkpoints`, {
        method: 'POST',
      }),
    step: (worldName: string) =>
      fetchJSON<{ status: string; message?: string; fixed_cards?: any; sanitized_conditions?: any }>(`/worlds/${worldName}/builder/step`, {
        method: 'POST',
      }),
  },
  creator: {
    saves: {
      list: (worldName: string) => fetchJSON<any[]>(`/worlds/${worldName}/saves`),
      create: (worldName: string, label: string) =>
        fetchJSON<any>(`/worlds/${worldName}/saves/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label }),
        }),
      restore: (worldName: string, saveId: string) =>
        fetchJSON<any>(`/worlds/${worldName}/saves/restore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ save_id: saveId }),
        }),
      branch: (worldName: string, saveId: string, newWorldName: string) =>
        fetchJSON<any>(`/worlds/${worldName}/saves/branch`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ save_id: saveId, new_world_name: newWorldName }),
        }),
    },
    styleCard: {
      get: (worldName: string) => fetchJSON<any>(`/worlds/${worldName}/style-card`),
      update: (worldName: string, cardData: any) =>
        fetchJSON<any>(`/worlds/${worldName}/style-card`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cardData),
        }),
    },
    traits: {
      get: (worldName: string) => fetchJSON<any>(`/worlds/${worldName}/traits`),
      update: (worldName: string, traits: any) =>
        fetchJSON<any>(`/worlds/${worldName}/traits`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(traits),
        }),
    },
    canonLog: {
      get: (worldName: string) => fetchJSON<any>(`/worlds/${worldName}/canon-log`),
      add: (worldName: string, entry: any) =>
        fetchJSON<any>(`/worlds/${worldName}/canon-log`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(entry),
        }),
    },
    export: (worldName: string) => fetchJSON<any>(`/worlds/${worldName}/export`),
    fork: (worldName: string, targetName: string) =>
      fetchJSON<any>(`/worlds/${worldName}/fork`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_name: targetName }),
      }),
  },
  config: {
    get: () => fetchJSON<RuntimeConfig>('/runtime-config'),
    update: (config: RuntimeConfig) =>
      fetchJSON<any>('/runtime-config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      }),
    testConnection: () =>
      fetchJSON<{ ok?: boolean; status?: string; message: string }>('/runtime-config/test-connection', { method: 'POST' }),
  },
  codex: {
    get: (worldName: string) =>
      fetchJSON<any>(`/worlds/${worldName}/codex`),
  },
  map: {
    get: (worldName: string) =>
      fetchJSON<{ locations: any[] }>(`/worlds/${worldName}/location-map`),
    status: (worldName: string) =>
      fetchJSON<{ locations: any[] }>(`/worlds/${worldName}/location-map/status`),
  },
};