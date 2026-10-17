import { describe, expect, it } from 'vitest';
import { endSummary, recapLines } from './ending';

const game = {
  character: { name: 'Tess', archetype: 'warrior' },
  flags: { seal_forge: 'yes', seal_falls: 'yes', seal_mines: 'yes', has_catalog: 'yes', ending: 'wits' },
} as never;

describe('endSummary', () => {
  it('summarises a victory from the final flags', () => {
    expect(endSummary(game, 'victory')).toEqual({
      heading: '✦ VICTORY ✦', who: 'Tess the warrior', how: 'Lord Silo yielded to your wits',
      seals: ['Forge', 'Falls', 'Mines'], catalog: true,
    });
  });
  it('summarises a defeat', () => {
    const s = endSummary({ character: { name: 'Ash', archetype: 'mage' }, flags: {} } as never, 'defeat');
    expect(s.heading).toBe('✦ YOUR TALE ENDS ✦');
    expect(s.how).toBe("Lord Silo's walls closed around you");
    expect(s.seals).toEqual([]);
  });
});

describe('recapLines', () => {
  it('lists only what happened, each pointing at its Guide page', () => {
    const lines = recapLines({ rolls: 3, attacks: 2, lore: 9, memories: 0, state_commits: 4, guardrails: 1, hints: 1, turns: 20, since_start: true });
    expect(lines.map((l) => l.page)).toEqual(['tools', 'rag', 'state', 'guardrails', 'hints']);
    expect(lines[0]).toEqual({ glyph: '🎲', text: '5 tool calls (3 dice rolls, 2 attacks)', page: 'tools' });
    expect(lines[1].text).toBe('9 lore lookups');
  });
});
