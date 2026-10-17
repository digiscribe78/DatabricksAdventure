import { endSummary, recapLines } from './ending';
import type { GameView } from './state';

export function EndScreen({ view, onNewTale, onGuide }: { view: GameView; onNewTale: () => void; onGuide: (page?: string) => void }) {
  if (!view.game || !view.gameOver) return null;
  const s = endSummary(view.game, view.gameOver);
  const stats = view.game.stats;
  return (
    <div className="end-screen">
      <h2 className="title8">{s.heading}</h2>
      <p>{s.who} · {s.how}</p>
      <p>Seals: {s.seals.length ? s.seals.map((n) => `${n} ✓`).join('  ') : 'none'}{s.catalog ? ' · Catalog recovered' : ''}</p>
      {stats && (
        <>
          <h3 className="title8 small">What you just saw</h3>
          <ul className="recap">
            {recapLines(stats).map((l) => (
              <li key={l.page}>{l.glyph} {l.text} <button className="q" onClick={() => onGuide(l.page)}>📖</button></li>
            ))}
          </ul>
          {!stats.since_start && <p className="note">Counted from when this save was first played after the update.</p>}
        </>
      )}
      <h3 className="title8 small">What the realm will remember of you</h3>
      {view.game.distilled?.length ? (
        <ul className="recap">{view.game.distilled.map((m) => <li key={m}>· {m}</li>)}</ul>
      ) : <p className="note">The Dreamer will remember this tale tonight.</p>}
      <div className="end-actions">
        <button className="bbtn inline" onClick={onNewTale}>Begin a new tale ▸</button>
        <button className="bbtn inline" onClick={() => onGuide()}>📖 Open the Guide</button>
        {view.game.traces_url && <a href={view.game.traces_url} target="_blank" rel="noreferrer">open traces ↗</a>}
      </div>
    </div>
  );
}
