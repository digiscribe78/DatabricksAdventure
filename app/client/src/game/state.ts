import { z } from 'zod';
import type { StreamEvent } from './sse';

// Everything from the DM is validated here: the browser trusts nothing it hasn't parsed.
export const TurnEventSchema = z.object({ type: z.string(), summary: z.string(), detail: z.unknown().optional() });
export type TurnEvent = z.infer<typeof TurnEventSchema>;

export const GameSnapshotSchema = z.object({
  character: z.object({
    name: z.string(), archetype: z.string(), hp: z.number(), max_hp: z.number(), might: z.number(),
    wits: z.number(), charm: z.number(), gold: z.number(), xp: z.number(), inventory: z.array(z.string()),
  }),
  location_id: z.string(),
  location_name: z.string(),
  exits: z.array(z.object({ id: z.string(), name: z.string() })),
  flags: z.record(z.string(), z.string()),
  npcs: z.array(z.object({ npc_id: z.string(), name: z.string(), disposition: z.number() })),
  traces_url: z.string().nullable(),
});
export type GameSnapshot = z.infer<typeof GameSnapshotSchema>;

const NodeData = z.object({ node: z.string() });
const TurnData = z.object({
  turn: z.object({
    narration: z.string().optional(),
    choices: z.array(z.string()).optional(),
    events: z.array(TurnEventSchema).optional(),
    game_over: z.string().nullable().optional(),
  }),
});
const GameData = z.object({ game: GameSnapshotSchema });

export interface LastRequest {
  message?: string;
  newGame?: { name: string; archetype: 'warrior' | 'mage' | 'bard' };
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
  lastRequest?: LastRequest; // what Try again resends: the exact request that failed
}

const HISTORY_LIMIT = 20;
const keep = (lines: string[]) => lines.slice(-HISTORY_LIMIT);

export const newView = (sessionId: string): GameView => ({
  sessionId, narration: '', choices: [], events: [], nodes: [], busy: false, history: [],
});

export function startTurn(v: GameView, now: number, playerText?: string, request?: LastRequest): GameView {
  return {
    ...v, lastRequest: request ?? v.lastRequest, busy: true, error: undefined, nodes: [], events: [], startedAt: now, elapsedMs: undefined,
    history: playerText ? keep([...v.history, `> ${playerText}`]) : v.history,
  };
}

/** The player may act unless the DM is mid-turn or the adventure has ended. */
export function canAct(v: GameView): boolean {
  return !v.busy && !v.gameOver;
}

export function failTurn(v: GameView, message: string): GameView {
  return { ...v, busy: false, error: message };
}

export function applyEvent(v: GameView, e: StreamEvent, now: number): GameView {
  switch (e.event) {
    case 'node': {
      const d = NodeData.safeParse(e.data);
      return d.success ? { ...v, nodes: [...v.nodes, d.data.node] } : v;
    }
    case 'turn': {
      const d = TurnData.safeParse(e.data);
      if (!d.success) return v;
      const t = d.data.turn;
      const narration = t.narration ?? '';
      return {
        ...v, narration, choices: t.choices ?? [], events: t.events ?? [],
        gameOver: t.game_over ?? null, history: keep([...v.history, narration]),
      };
    }
    case 'game': {
      const d = GameData.safeParse(e.data);
      return d.success ? { ...v, game: d.data.game } : v;
    }
    case 'run.completed':
      return { ...v, busy: false, elapsedMs: v.startedAt !== undefined ? now - v.startedAt : undefined };
    case 'run.failed':
      return failTurn(v, 'The realm shudders and the Dungeon Master loses the thread. Try again.');
    default:
      return v;
  }
}
