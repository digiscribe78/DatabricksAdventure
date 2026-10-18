import { mapMarkers } from './worldmap';
import type { GameView } from './state';

const GLYPH = { here: '★', open: '◆', closed: '✕', far: '·' } as const;
const TITLE = { here: 'You are here', open: 'Open road: click to travel', closed: 'The road is barred for now', far: 'Further afield' } as const;

/** The world map: painted art with live markers for where you are and which roads are open from here. */
export function MapPanel({ view, onTravel, canTravel }: { view: GameView; onTravel: (text: string) => void; canTravel: boolean }) {
  const markers = mapMarkers(view.game);
  return (
    <div className="frame world-map">
      <div className="map-art">
        <img src="/images/world-map.webp" alt="A parchment map of the Kingdom of Sparkia" />
        {markers.map((m) => (
          <button key={m.id} className={`map-marker ${m.kind}`} style={{ left: `${m.x}%`, top: `${m.y}%` }}
                  title={`${m.label}: ${TITLE[m.kind]}`} disabled={!(m.travel && canTravel)}
                  onClick={() => m.travel && onTravel(m.travel)}>
            <span className="pin">{GLYPH[m.kind]}</span>
            {m.kind !== 'far' && <span className="label">{m.label}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
