// Talking to the Dungeon Master agent as the signed-in player.
import { randomUUID } from 'node:crypto';

export const FORWARD_EVENTS = new Set(['run.started', 'node', 'turn', 'game', 'run.completed', 'run.failed']);

export class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type Env = Record<string, string | undefined>;
type Headers = Record<string, string | string[] | undefined>;

export function userToken(headers: Headers, env: Env = process.env): string {
  const forwarded = headers['x-forwarded-access-token'];
  // DM_DEV_TOKEN is for local `make app-dev` only: a deployed app must never act as the developer.
  const deployed = env.NODE_ENV === 'production' || Boolean(env.DATABRICKS_APP_NAME);
  const token = (Array.isArray(forwarded) ? forwarded[0] : forwarded) || (deployed ? undefined : env.DM_DEV_TOKEN);
  if (!token) {
    // Never fall back to the app's own identity: every player would become the same player.
    throw new HttpError(401, 'No player token: open the game through Databricks Apps (or set DM_DEV_TOKEN locally).');
  }
  return token;
}

export type Archetype = 'warrior' | 'mage' | 'bard';
export interface TurnInput {
  message?: string;
  newGame?: { name: string; archetype: Archetype };
  listAdventures?: boolean;
  hintsSeen?: number;
}

export interface InvocationBody {
  id: string;
  session_id: string;
  stream: boolean;
  input: Record<string, unknown>;
}

export function invocationBody(input: TurnInput, sessionId: string, stream: boolean): InvocationBody {
  let body: Record<string, unknown>;
  if (input.listAdventures) body = { list_adventures: true };
  else if (input.newGame) body = { messages: [], new_game: input.newGame, client_session_id: sessionId };
  else body = { messages: input.message ? [{ role: 'user', content: input.message }] : [] };
  if (input.hintsSeen && !input.listAdventures) body.hints_seen = input.hintsSeen;
  return { id: randomUUID(), session_id: sessionId, stream, input: body };
}

export function filterSSE(buffer: string): { out: string; rest: string } {
  const blocks = buffer.split('\n\n');
  const rest = blocks.pop() ?? '';
  const out = blocks
    .filter((b) => {
      const ev = b.split('\n').find((l) => l.startsWith('event:'));
      return ev !== undefined && FORWARD_EVENTS.has(ev.slice(6).trim());
    })
    .map((b) => `${b}\n\n`)
    .join('');
  return { out, rest };
}

export function normaliseHost(h: string): string {
  const withScheme = h.startsWith('http') ? h : `https://${h}`;
  return withScheme.replace(/\/+$/, '');
}

let cachedDmUrl: string | undefined;

export async function resolveDmUrl(env: Env = process.env, fetchFn: typeof fetch = fetch): Promise<string> {
  if (env.DM_URL) return env.DM_URL.replace(/\/+$/, '');
  if (cachedDmUrl) return cachedDmUrl;
  const host = normaliseHost(env.DATABRICKS_HOST ?? '');
  const basic = Buffer.from(`${env.DATABRICKS_CLIENT_ID}:${env.DATABRICKS_CLIENT_SECRET}`).toString('base64');
  const tok = await fetchFn(`${host}/oidc/v1/token`, {
    method: 'POST',
    headers: { Authorization: `Basic ${basic}`, 'Content-Type': 'application/x-www-form-urlencoded' },
    body: 'grant_type=client_credentials&scope=all-apis',
  });
  if (!tok.ok) throw new HttpError(502, 'Could not authenticate the game app to look up the Dungeon Master');
  const { access_token } = (await tok.json()) as { access_token: string };
  const app = await fetchFn(`${host}/api/2.0/apps/${env.DM_APP_NAME ?? 'agent-bricks-dm'}`, {
    headers: { Authorization: `Bearer ${access_token}` },
  });
  if (!app.ok) throw new HttpError(502, 'Could not find the Dungeon Master app (is agent-bricks-dm deployed?)');
  const { url } = (await app.json()) as { url: string };
  cachedDmUrl = url.replace(/\/+$/, '');
  return cachedDmUrl;
}
