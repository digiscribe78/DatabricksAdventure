import { createApp, server } from '@databricks/appkit';
import { HttpError, filterSSE, invocationBody, resolveDmUrl, userToken, type TurnInput } from './dm';

async function readJson(req: any): Promise<any> {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c as Buffer);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : {};
}

function fail(res: any, e: unknown) {
  const status = e instanceof HttpError ? e.status : 500;
  if (!res.headersSent) res.status(status).json({ error: e instanceof Error ? e.message : String(e) });
  else res.end();
}

createApp({
  plugins: [server()],
  async onPluginsReady(appkit) {
    appkit.server.extend((app) => {
      app.get('/api/health', (_req, res) => {
        res.json({ ok: true });
      });

      app.get('/api/adventures', async (req, res) => {
        try {
          const token = userToken(req.headers);
          const dm = await resolveDmUrl();
          const r = await fetch(`${dm}/api/invocations`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(invocationBody({ listAdventures: true }, crypto.randomUUID(), false)),
          });
          if (!r.ok) throw new HttpError(r.status, await r.text());
          const data = (await r.json()) as { output?: { adventures?: unknown[] } };
          res.json({ adventures: data.output?.adventures ?? [] });
        } catch (e) {
          fail(res, e);
        }
      });

      app.post('/api/turn', async (req, res) => {
        try {
          const body = await readJson(req);
          const sessionId = String(body.sessionId ?? '');
          if (!/^[A-Za-z0-9-]{1,64}$/.test(sessionId)) throw new HttpError(400, 'sessionId is required');
          const input: TurnInput = { message: body.message, newGame: body.newGame };
          const token = userToken(req.headers);
          const dm = await resolveDmUrl();
          const upstream = await fetch(`${dm}/api/invocations`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
            body: JSON.stringify(invocationBody(input, sessionId, true)),
          });
          if (!upstream.ok || !upstream.body) throw new HttpError(upstream.status || 502, await upstream.text());
          res.setHeader('Content-Type', 'text/event-stream');
          res.setHeader('Cache-Control', 'no-cache');
          res.flushHeaders?.();
          const reader = upstream.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            const { out, rest } = filterSSE(buffer + decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n'));
            buffer = rest;
            if (out) res.write(out);
          }
          const { out } = filterSSE(`${buffer}\n\n`);
          if (out) res.write(out);
          res.end();
        } catch (e) {
          fail(res, e);
        }
      });
    });
  },
}).catch(console.error);
