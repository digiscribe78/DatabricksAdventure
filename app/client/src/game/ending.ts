import type { GameSnapshot } from './state';

type Stats = NonNullable<GameSnapshot['stats']>;
const SEALS: [string, string][] = [['seal_forge', 'Forge'], ['seal_falls', 'Falls'], ['seal_mines', 'Mines']];
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export function endSummary(game: GameSnapshot, outcome: string) {
  const f = game.flags ?? {};
  const victory = outcome === 'victory';
  return {
    heading: victory ? '✦ VICTORY ✦' : '✦ YOUR TALE ENDS ✦',
    who: `${game.character.name} the ${game.character.archetype}`,
    how: victory ? `Lord Silo yielded to your ${f.ending ?? 'resolve'}` : "Lord Silo's walls closed around you",
    seals: SEALS.filter(([flag]) => f[flag]).map(([, name]) => name),
    catalog: Boolean(f.has_catalog),
  };
}

/** "What you just saw": one line per kind of thing that happened, each linked to its Guide page. */
export function recapLines(s: Stats) {
  const lines: { glyph: string; text: string; page: string }[] = [];
  const tools = s.rolls + s.attacks;
  if (tools) lines.push({ glyph: '🎲', text: `${plural(tools, 'tool call', 'tool calls')} (${plural(s.rolls, 'dice roll', 'dice rolls')}, ${plural(s.attacks, 'attack', 'attacks')})`, page: 'tools' });
  if (s.lore) lines.push({ glyph: '📚', text: plural(s.lore, 'lore lookup', 'lore lookups'), page: 'rag' });
  if (s.memories) lines.push({ glyph: '🧠', text: plural(s.memories, 'memory recall', 'memory recalls'), page: 'memory' });
  if (s.state_commits) lines.push({ glyph: '💾', text: plural(s.state_commits, 'state commit', 'state commits'), page: 'state' });
  if (s.guardrails) lines.push({ glyph: '🛡', text: plural(s.guardrails, 'guardrail block', 'guardrail blocks'), page: 'guardrails' });
  if (s.hints) lines.push({ glyph: '💡', text: plural(s.hints, 'hint', 'hints'), page: 'hints' });
  return lines;
}
