import type { GameSnapshot } from './state';

/** Where each place sits on public/images/world-map.webp, in percent of its width and height. */
export const MAP_POINTS: Record<string, { x: number; y: number; label: string }> = {
  'medallion-inn': { x: 22, y: 48, label: 'Lakehouse Village' },
  'delta-crossing': { x: 46, y: 64, label: 'Delta Crossing' },
  'unity-archive': { x: 51, y: 36, label: 'Unity Archive' },
  'spark-forge': { x: 28, y: 15, label: 'Spark Forge' },
  'streaming-falls': { x: 51, y: 12, label: 'Streaming Falls' },
  'photon-mines': { x: 75, y: 23, label: 'Photon Mines' },
  'data-swamp': { x: 74, y: 79, label: 'Data Swamp' },
  'silos-keep': { x: 92, y: 56, label: "Silo's Keep" },
};

export type MarkerKind = 'here' | 'open' | 'closed' | 'far';
export interface Marker { id: string; label: string; x: number; y: number; kind: MarkerKind; travel?: string }

/** The map's markers from the game snapshot: you are here, the roads open from here, the barred ones, the rest fogged. */
export function mapMarkers(game: GameSnapshot | undefined): Marker[] {
  if (!game) return [];
  const exits = new Map(game.exits.map((e) => [e.id, e]));
  return Object.entries(MAP_POINTS).map(([id, p]) => {
    const exit = exits.get(id);
    const kind: MarkerKind = id === game.location_id ? 'here' : exit ? (exit.open === false ? 'closed' : 'open') : 'far';
    return { id, ...p, kind, travel: kind === 'open' ? `I travel to ${exit!.name}.` : undefined };
  });
}
