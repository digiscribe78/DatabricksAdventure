import type { GameView } from './state';

/** Reveal the next hint tier (nudge, then clearer). Hints come from game state: no model, no turn. */
export function revealHint(v: GameView): GameView {
  const h = v.game?.hint;
  if (!h || v.hintTier >= 2) return v;
  return {
    ...v,
    hintTier: (v.hintTier + 1) as 1 | 2,
    hintsSeen: v.hintsSeen + 1,
    events: [...v.events, { type: 'hint', summary: `Hint from game state: next beat ${h.beat} at ${h.where}` }],
  };
}
