import { z } from 'zod';
import { parseSSE, type StreamEvent } from './sse';

const AdventureSchema = z.object({
  session_id: z.string(),
  client_session_id: z.string().nullable(),
  name: z.string(),
  archetype: z.string(),
  location_id: z.string(),
  status: z.string(),
});
export type Adventure = z.infer<typeof AdventureSchema>;
const ErrorBody = z.object({ error: z.string() });

export interface TurnRequest {
  message?: string;
  newGame?: { name: string; archetype: 'warrior' | 'mage' | 'bard' };
}

async function errorOf(r: Response): Promise<string> {
  const body = ErrorBody.safeParse(await r.json().catch(() => null));
  return body.success ? body.data.error : `HTTP ${r.status}`;
}

export async function listAdventures(): Promise<Adventure[]> {
  const r = await fetch('/api/adventures');
  if (!r.ok) throw new Error(await errorOf(r));
  return z.object({ adventures: z.array(AdventureSchema) }).parse(await r.json()).adventures;
}

export async function playTurn(sessionId: string, input: TurnRequest, onEvent: (e: StreamEvent) => void): Promise<void> {
  const r = await fetch('/api/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, ...input }),
  });
  if (!r.ok || !r.body) throw new Error(await errorOf(r));
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const { events, rest } = parseSSE(buffer + decoder.decode(value, { stream: true }));
    buffer = rest;
    for (const e of events) {
      if (e.event === 'run.completed' || e.event === 'run.failed') completed = true;
      onEvent(e);
    }
  }
  if (!completed) throw new Error('The connection to the realm faltered mid-turn.');
}
