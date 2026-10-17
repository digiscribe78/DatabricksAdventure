import { describe, expect, it } from 'vitest';
import { revealHint } from './hints';
import { newView, startTurn, type GameView } from './state';

const hint = { beat: 'spoke_with_aldric', where: 'The Unity Archive', nudge: 'The doors…', clearer: 'Call out…' };
const withHint = (): GameView => ({ ...newView('s'), game: { hint } as never });

describe('revealHint', () => {
  it('shows the nudge, then the clearer hint, and logs each in the Glass', () => {
    const one = revealHint(withHint());
    expect(one.hintTier).toBe(1);
    expect(one.events.at(-1)).toEqual({ type: 'hint', summary: 'Hint from game state: next beat spoke_with_aldric at The Unity Archive' });
    const two = revealHint(one);
    expect(two.events.at(-1)?.summary).toBe('Clearer hint from game state: next beat spoke_with_aldric at The Unity Archive');
    expect(two.hintTier).toBe(2);
    expect(two.hintsSeen).toBe(2);
    expect(revealHint(two).hintTier).toBe(2);  // no third tier
  });

  it('does nothing without a hint', () => {
    expect(revealHint(newView('s')).hintTier).toBe(0);
  });

  it('a new turn closes the hint and the count is sent then reset', () => {
    const shown = revealHint(withHint());
    const next = startTurn(shown, 0, 'go');
    expect(next.hintTier).toBe(0);
    expect(next.hintsSeen).toBe(0);
  });
});
