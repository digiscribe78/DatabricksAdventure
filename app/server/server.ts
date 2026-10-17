import { createApp, server } from '@databricks/appkit';
import { z } from 'zod';
import { HttpError, filterSSE, invocationBody, resolveDmUrl, userToken } from './dm';

// The only shapes the browser may send: validated before anything reaches the Dungeon Master.
const TurnBody = z.object({
  sessionId: z.string().regex(/^[A-Za-z0-9-]{1,64}$/),
  message: z.string().max(2000).optional(),
  newGame: z.object({ name: z.string().min(1).max(40), archetype: z.enum(['warrior', 'mage', 'bard']) }).optional(),
});
const ListResult = z.object({ output: z.object({ adventures: z.array(z.unknown()) }).partial() }).partial();

interface JsonRequest extends AsyncIterable<Buffer> {
  body?: unknown;
}
interface Reply {
  headersSent: boolean;
  status(code: number): { json(body: unknown): void };
  end(): void;
}

async function readJson(req: JsonRequest): Promise<unknown> {
  if (req.body && typeof req.body === 'object') return req.body;
  const chunks: Buffer[] = [];
  for await (const c of req) chunks.push(c);
  return chunks.length ? (JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown) : {};
}

function fail(res: Reply, e: unknown) {
  const status = e instanceof HttpError ? e.status : e instanceof z.ZodError ? 400 : 500;
  if (!res.headersSent) res.status(status).json({ error: e instanceof Error ? e.message : String(e) });
  else res.end();
}

function dmHeaders(token: string) {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

createApp({
  plugins: [server()],
  onPluginsReady(appkit) {
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
            headers: dmHeaders(token),
            body: JSON.stringify(invocationBody({ listAdventures: true }, crypto.randomUUID(), false)),
          });
          if (!r.ok) throw new HttpError(r.status, await r.text());
          res.json({ adventures: ListResult.parse(await r.json()).output?.adventures ?? [] });
        } catch (e) {
          fail(res, e);
        }
      });

      app.post('/api/turn', async (req, res) => {
        try {
          const body = TurnBody.parse(await readJson(req));
          const token = userToken(req.headers);
          const dm = await resolveDmUrl();
          const upstream = await fetch(`${dm}/api/invocations`, {
            method: 'POST',
            headers: dmHeaders(token),
            body: JSON.stringify(invocationBody({ message: body.message, newGame: body.newGame }, body.sessionId, true)),
          });
          if (!upstream.ok || !upstream.body) throw new HttpError(upstream.status || 502, await upstream.text());
          res.setHeader('Content-Type', 'text/event-stream');
          res.setHeader('Cache-Control', 'no-cache');
          res.flushHeaders();
          const reader = (upstream.body as ReadableStream<Uint8Array>).getReader();
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
