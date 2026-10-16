import { describe, expect, it } from 'vitest';
import { applyEvent, failTurn, newView, startTurn } from './state';

const game = {
  character: { name: 'Brannoc', archetype: 'warrior', hp: 18, max_hp: 18, might: 3, wits: 0, charm: 1, gold: 12, xp: 0, inventory: [] },
  location_id: 'medallion-inn', location_name: 'The Medallion Inn', exits: [], flags: {}, npcs: [], traces_url: null,
};

describe('game view reducer', () => {
  it('runs a full turn', () => {
    let v = startTurn(newView('s1'), 1000, 'I look around');
    expect(v.busy).toBe(true);
    v = applyEvent(v, { event: 'node', data: { node: 'load_state' } }, 1100);
    v = applyEvent(v, { event: 'node', data: { node: 'dm_reason' } }, 1200);
    v = applyEvent(v, { event: 'turn', data: { turn: { narration: 'Smoke curls.', choices: ['a', 'b'], events: [{ type: 'lore', summary: 'Lore: 4' }], game_over: null } } }, 1300);
    v = applyEvent(v, { event: 'game', data: { game } }, 1350);
    v = applyEvent(v, { event: 'run.completed', data: {} }, 1500);
    expect(v.nodes).toEqual(['load_state', 'dm_reason']);
    expect(v.narration).toBe('Smoke curls.');
    expect(v.events[0].type).toBe('lore');
    expect(v.game?.character.name).toBe('Brannoc');
    expect(v.busy).toBe(false);
    expect(v.elapsedMs).toBe(500);
    expect(v.history.slice(-2)).toEqual(['> I look around', 'Smoke curls.']);
  });

  it('a failed stream leaves busy state but keeps the last good game', () => {
    let v = applyEvent(startTurn(newView('s1'), 0), { event: 'game', data: { game } }, 1);
    v = startTurn(v, 10, 'I jump');
    v = failTurn(v, 'The connection to the realm faltered.');
    expect(v.busy).toBe(false);
    expect(v.error).toContain('faltered');
    expect(v.game?.character.name).toBe('Brannoc');
  });

  it('run.failed is treated as a failure', () => {
    const v = applyEvent(startTurn(newView('s1'), 0), { event: 'run.failed', data: { error: 'x' } }, 5);
    expect(v.busy).toBe(false);
    expect(v.error).toBeTruthy();
  });

  it('keeps at most 20 history lines', () => {
    let v = newView('s1');
    for (let i = 0; i < 15; i++) {
      v = startTurn(v, i, `p${i}`);
      v = applyEvent(v, { event: 'turn', data: { turn: { narration: `n${i}`, choices: [], events: [] } } }, i);
    }
    expect(v.history.length).toBe(20);
    expect(v.history.at(-1)).toBe('n14');
  });
});
