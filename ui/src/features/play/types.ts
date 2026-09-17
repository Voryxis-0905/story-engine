export type DrawerTab = 'inventory' | 'map' | 'codex' | 'status' | 'skills' | 'foreshadowing' | null;

export interface Turn {
  input: string;
  output: string;
  chapterIndex: number;
  turnIndex: number;
  checkpointId: string;
  timestamp: number;
}
