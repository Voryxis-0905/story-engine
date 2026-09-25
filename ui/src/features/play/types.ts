export type DrawerTab = 'inventory' | 'map' | 'codex' | 'status' | 'skills' | 'foreshadowing' | 'quests' | 'journal' | null;

export const WORLD_RESTORED_EVENT = 'story-engine:world-restored';

export const DRAFT_STORAGE_PREFIX = 'story-engine:draft:';

/**
 * Where the experimental-pacing switch is remembered, one key per world.
 *
 * The choice is a player preference, not world state: it is deliberately kept
 * out of the world's save files so that turning it on can never rewrite a turn
 * that was already saved, and so two worlds on the same machine can disagree.
 * Only the non-default value is stored, so "no key" reads back as off.
 */
export const NARRATION_MODE_STORAGE_PREFIX = 'story-engine:narration-mode:';

export const narrationModeStorageKey = (worldName: string) =>
  `${NARRATION_MODE_STORAGE_PREFIX}${worldName}`;

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
