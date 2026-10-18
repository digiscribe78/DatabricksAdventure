import { describe, expect, it } from 'vitest';
import { MAP_POINTS, mapMarkers } from './worldmap';

const game = {
  location_id: 'delta-crossing',
  exits: [{ id: 'medallion-inn', name: 'The Medallion Inn', open: true }, { id: 'unity-archive', name: 'The Unity Archive', open: true },
          { id: 'data-swamp', name: 'The Data Swamp', open: false }],
} as never;

describe('world map', () => {
  it('pins every location on the painted map', () => {
    expect(Object.keys(MAP_POINTS).sort()).toEqual(['data-swamp', 'delta-crossing', 'medallion-inn', 'photon-mines',
      'silos-keep', 'spark-forge', 'streaming-falls', 'unity-archive']);
    for (const p of Object.values(MAP_POINTS)) expect(p.x > 0 && p.x < 100 && p.y > 0 && p.y < 100).toBe(true);
  });

  it('marks where you are, the roads open from here, the closed ones, and fogs the rest', () => {
    const m = Object.fromEntries(mapMarkers(game).map((x) => [x.id, x.kind]));
    expect(m['delta-crossing']).toBe('here');
    expect(m['medallion-inn']).toBe('open');
    expect(m['unity-archive']).toBe('open');
    expect(m['data-swamp']).toBe('closed');
    expect(m['silos-keep']).toBe('far');
  });

  it('shows nothing until the game state arrives', () => {
    expect(mapMarkers(undefined)).toEqual([]);
  });
});
