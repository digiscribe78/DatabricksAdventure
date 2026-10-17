import { useState } from 'react';
import { EXPLAINERS, GLYPHS, GRAPH } from './explainers';
import type { GameView } from './state';

function Explain({ id, onGuide }: { id: string; onGuide: (page?: string) => void }) {
  const [open, setOpen] = useState(false);
  const e = EXPLAINERS[id];
  if (!e) return null;
  return (
    <span className="explain">
      <button className="q" onClick={() => setOpen(!open)} aria-label={`What is ${e.title}?`}>(?)</button>
      {open && (
        <span className="explain-box">
          <strong>{e.title}.</strong> {e.text} <a href={e.docs} target="_blank" rel="noreferrer">Docs ↗</a>
          {e.guide && <button className="q" onClick={() => onGuide(e.guide)}>More in the Guide ▸</button>}
        </span>
      )}
    </span>
  );
}

export function ScryingGlass({ view, open, onToggle, onGuide }: {
  view: GameView; open: boolean; onToggle: () => void; onGuide: (page?: string) => void;
}) {
  if (!open) {
    return <button className="frame glass-tab" onClick={onToggle}>✦ Scrying Glass ◂</button>;
  }
  const last = view.nodes.at(-1);
  return (
    <aside className="frame bscry">
      <div className="glass-head">
        <span className="t">✦ Scrying Glass ✦</span>
        <button className="q" onClick={onToggle} aria-label="Hide the Scrying Glass">▸</button>
      </div>
      <div className="graph">
        {GRAPH.map((n) => (
          <span key={n} className={`pill ${view.nodes.includes(n) ? 'lit' : ''} ${view.busy && last === n ? 'live' : ''}`}>
            {n}
            <Explain id={n} onGuide={onGuide} />
          </span>
        ))}
      </div>
      <ul className="feed">
        {view.busy && <li className="pending">The DM ponders… ({view.nodes.length} steps so far)</li>}
        {view.events.map((e) => (
          <li key={`${e.type}:${e.summary}`}>
            {GLYPHS[e.type] ?? '•'} {e.summary} <Explain id={e.type} onGuide={onGuide} />
          </li>
        ))}
        {!view.busy && view.events.length === 0 && view.narration && <li>No tools this turn: pure narration.</li>}
      </ul>
      <div className="glass-foot">
        {view.elapsedMs !== undefined && <span>{(view.elapsedMs / 1000).toFixed(1)}s</span>}
        {view.game?.traces_url && (
          <a href={view.game.traces_url} target="_blank" rel="noreferrer">open traces ↗</a>
        )}
      </div>
    </aside>
  );
}
