import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { EXPLAINERS } from './explainers';
import { GUIDE } from './guide';

describe('GUIDE', () => {
  it('has one page per concept', () => {
    expect(GUIDE.map((p) => p.id)).toEqual(['tools', 'rag', 'state', 'memory', 'structured', 'tracing', 'guardrails', 'evals', 'hints']);
    for (const p of GUIDE) expect(p.saw && p.built && p.tryThis && p.docs.startsWith('https://')).toBeTruthy();
  });

  it('explainers only point at pages that exist', () => {
    const ids = new Set(GUIDE.map((p) => p.id));
    for (const e of Object.values(EXPLAINERS)) if (e.guide) expect(ids.has(e.guide)).toBe(true);
  });

  it("the README's Things to try has every page's try-this", () => {
    const readme = readFileSync(resolve(__dirname, '../../../../README.md'), 'utf8');
    const table = readme.slice(readme.indexOf('## Things to try'));
    for (const p of GUIDE) expect(table, p.id).toContain(p.tryThis);
  });
});

describe('Things to try', () => {
  it('lists every page with a try-this, in Guide order', async () => {
    const { thingsToTry } = await import('./guide');
    expect(thingsToTry().map((t) => t.page)).toEqual(GUIDE.map((p) => p.id));
    expect(thingsToTry()[0]).toEqual({ page: 'tools', glyph: '🎲', tryThis: 'Attack something', look: GUIDE[0].look });
  });
});
