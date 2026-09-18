export type DrawerTab = 'inventory' | 'map' | 'codex' | 'status' | 'skills' | 'foreshadowing' | 'quests' | 'journal' | null;

export const WORLD_RESTORED_EVENT = 'story-engine:world-restored';

export const DRAFT_STORAGE_PREFIX = 'story-engine:draft:';

export interface PlayDraft {
  worldName: string;
  userInput: string;
  requestId?: string;
  text: string;
  status: string;
  reason: string;
  message: string;
  createdAt: number;
}

export interface Turn {
  input: string;
  output: string;
  chapterIndex: number;
  turnIndex: number;
  checkpointId: string;
  timestamp: number;
}
