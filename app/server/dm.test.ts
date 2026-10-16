import { describe, expect, it, vi } from 'vitest';
import { FORWARD_EVENTS, HttpError, filterSSE, invocationBody, normaliseHost, resolveDmUrl, userToken } from './dm';

describe('userToken', () => {
  it('prefers the forwarded user token', () => {
    expect(userToken({ 'x-forwarded-access-token': 'user-tok' }, { DM_DEV_TOKEN: 'dev' })).toBe('user-tok');
  });
  it('falls back to DM_DEV_TOKEN for local dev', () => {
    expect(userToken({}, { DM_DEV_TOKEN: 'dev' })).toBe('dev');
  });
  it('refuses with 401 rather than using the app identity', () => {
    try {
      userToken({}, {});
      throw new Error('expected throw');
    } catch (e) {
      expect(e).toBeInstanceOf(HttpError);
      expect((e as HttpError).status).toBe(401);
    }
  });
});

describe('invocationBody', () => {
  it('builds a new-game invocation that records the client session id', () => {
    const b = invocationBody({ newGame: { name: 'Elowen', archetype: 'mage' } }, 'sess-1', true);
    expect(b.session_id).toBe('sess-1');
    expect(b.stream).toBe(true);
    expect(b.input).toEqual({ messages: [], new_game: { name: 'Elowen', archetype: 'mage' }, client_session_id: 'sess-1' });
    expect(b.id).toMatch(/^[0-9a-f-]{36}$/);
  });
  it('builds a player message turn', () => {
    const b = invocationBody({ message: 'I wade in' }, 'sess-1', true);
    expect(b.input).toEqual({ messages: [{ role: 'user', content: 'I wade in' }] });
  });
  it('builds a list request', () => {
    const b = invocationBody({ listAdventures: true }, 'lst', false);
    expect(b.input).toEqual({ list_adventures: true });
    expect(b.stream).toBe(false);
  });
});

describe('filterSSE', () => {
  const block = (event: string, data: object) => `id: 1\nevent: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  it('keeps forwarded events and drops deltas and messages', () => {
    const buf = block('node', { node: 'load_state' }) + block('delta', { content: 'The' }) +
      block('message', { message: { content: 'lore' } }) + block('turn', { turn: { narration: 'n' } });
    const { out, rest } = filterSSE(buf);
    expect(out).toContain('event: node');
    expect(out).toContain('event: turn');
    expect(out).not.toContain('delta');
    expect(out).not.toContain('lore');
    expect(rest).toBe('');
  });
  it('returns a partial trailing block as rest', () => {
    const { out, rest } = filterSSE(block('node', { node: 'a' }) + 'id: 2\nevent: turn\ndata: {"tu');
    expect(out).toContain('event: node');
    expect(rest).toBe('id: 2\nevent: turn\ndata: {"tu');
  });
  it('forwards exactly the documented event set', () => {
    expect([...FORWARD_EVENTS].sort()).toEqual(['game', 'node', 'run.completed', 'run.failed', 'run.started', 'turn']);
  });
});

describe('resolveDmUrl', () => {
  it('uses DM_URL override', async () => {
    expect(await resolveDmUrl({ DM_URL: 'https://dm.example/' })).toBe('https://dm.example');
  });
  it('looks the DM app up with an M2M token', async () => {
    const fetchFn = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'm2m' })))
      .mockResolvedValueOnce(new Response(JSON.stringify({ url: 'https://agent-bricks-dm-1.example' })));
    const env = { DATABRICKS_HOST: 'ws.example', DATABRICKS_CLIENT_ID: 'id', DATABRICKS_CLIENT_SECRET: 's', DM_APP_NAME: 'agent-bricks-dm' };
    expect(await resolveDmUrl(env, fetchFn)).toBe('https://agent-bricks-dm-1.example');
    expect(fetchFn.mock.calls[1][0]).toBe('https://ws.example/api/2.0/apps/agent-bricks-dm');
  });
  it('normalises hosts', () => {
    expect(normaliseHost('ws.example')).toBe('https://ws.example');
    expect(normaliseHost('https://ws.example/')).toBe('https://ws.example');
  });
});
