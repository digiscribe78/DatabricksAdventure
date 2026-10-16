import type { StreamEvent } from './sse';

export interface TurnEvent {
  type: string;
  summary: string;
  detail?: any;
}

export interface GameSnapshot {
  character: { name: string; archetype: string; hp: number; max_hp: number; might: number; wits: number; charm: number; gold: number; xp: number; inventory: string[] };
  location_id: string;
  location_name: string;
  exits: { id: string; name: string }[];
  flags: Record<string, string>;
  npcs: { npc_id: string; name: string; disposition: number }[];
  traces_url: string | null;
}

export interface GameView {
  sessionId: string;
  narration: string;
  choices: string[];
  events: TurnEvent[];
  nodes: string[];
  game?: GameSnapshot;
  busy: boolean;
  error?: string;
  startedAt?: number;
  elapsedMs?: number;
  gameOver?: string | null;
  history: string[];
}

const HISTORY_LIMIT = 20;
const keep = (lines: string[]) => lines.slice(-HISTORY_LIMIT);

export const newView = (sessionId: string): GameView => ({
  sessionId, narration: '', choices: [], events: [], nodes: [], busy: false, history: [],
});

export function startTurn(v: GameView, now: number, playerText?: string): GameView {
  return {
    ...v, busy: true, error: undefined, nodes: [], events: [], startedAt: now, elapsedMs: undefined,
    history: playerText ? keep([...v.history, `> ${playerText}`]) : v.history,
  };
}

export function failTurn(v: GameView, message: string): GameView {
  return { ...v, busy: false, error: message };
}

export function applyEvent(v: GameView, e: StreamEvent, now: number): GameView {
  switch (e.event) {
    case 'node':
      return { ...v, nodes: [...v.nodes, String(e.data.node)] };
    case 'turn': {
      const t = e.data.turn ?? {};
      return {
        ...v, narration: t.narration ?? '', choices: t.choices ?? [], events: t.events ?? [],
        gameOver: t.game_over ?? null, history: keep([...v.history, t.narration ?? '']),
      };
    }
    case 'game':
      return { ...v, game: e.data.game };
    case 'run.completed':
      return { ...v, busy: false, elapsedMs: v.startedAt !== undefined ? now - v.startedAt : undefined };
    case 'run.failed':
      return failTurn(v, 'The realm shudders and the Dungeon Master loses the thread. Try again.');
    default:
      return v;
  }
}
