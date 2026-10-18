import { useEffect, useState } from 'react';
import { GUIDE, thingsToTry } from './guide';

const TRY = 'try';
const plain = (s: string) => s.replace(/[`*]/g, '');

export function GuidePanel({ page, onClose }: { page?: string; onClose: () => void }) {
  const [id, setId] = useState(page ?? TRY);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);
  const p = GUIDE.find((g) => g.id === id);
  return (
    <div className="guide-overlay" role="dialog" aria-label="Guide">
      <div className="frame guide">
        <div className="guide-head"><span className="title8 small">📖 Guide</span>
          <button className="q" onClick={onClose} aria-label="Close the Guide">×</button></div>
        <div className="guide-body">
          <ul className="guide-list">
            <li><button className={`q ${id === TRY ? 'on' : ''}`} onClick={() => setId(TRY)}>🧭 Things to try</button></li>
            {GUIDE.map((g) => (
              <li key={g.id}><button className={`q ${g.id === id ? 'on' : ''}`} onClick={() => setId(g.id)}>{g.glyph} {g.title}</button></li>
            ))}
          </ul>
          {p ? (
          <article>
              <h3 className="title8 small">{p.glyph} {p.title}</h3>
              <p><strong>What you saw.</strong> {p.saw}</p>
              <p><strong>How it's built here.</strong> {p.built}</p>
              <p><strong>Try this.</strong> {plain(p.tryThis)}, then look at {plain(p.look)}.</p>
              <p><a href={p.docs} target="_blank" rel="noreferrer">Databricks docs ↗</a></p>
            </article>
          ) : (
            <article>
              <h3 className="title8 small">🧭 Things to try</h3>
              <p>Do one of these in the game, then look where it says to see how it worked.</p>
              <ul className="try-list">
                {thingsToTry().map((t) => (
                  <li key={t.page}>
                    {t.glyph} <strong>{plain(t.tryThis)}</strong>, then look at {plain(t.look)}.{' '}
                    <button className="q" onClick={() => setId(t.page)}>More ▸</button>
                  </li>
                ))}
              </ul>
            </article>
          )}
        </div>
      </div>
    </div>
  );
}
