import { useEffect, useState } from 'react';
import { GUIDE } from './guide';

export function GuidePanel({ page, onClose }: { page?: string; onClose: () => void }) {
  const [id, setId] = useState(page ?? GUIDE[0].id);
  useEffect(() => {
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onClose]);
  const p = GUIDE.find((g) => g.id === id) ?? GUIDE[0];
  return (
    <div className="guide-overlay" role="dialog" aria-label="Guide">
      <div className="frame guide">
        <div className="guide-head"><span className="title8 small">📖 Guide</span>
          <button className="q" onClick={onClose} aria-label="Close the Guide">×</button></div>
        <div className="guide-body">
          <ul className="guide-list">
            {GUIDE.map((g) => (
              <li key={g.id}><button className={`q ${g.id === id ? 'on' : ''}`} onClick={() => setId(g.id)}>{g.glyph} {g.title}</button></li>
            ))}
          </ul>
          <article>
            <h3 className="title8 small">{p.glyph} {p.title}</h3>
            <p><strong>What you saw.</strong> {p.saw}</p>
            <p><strong>How it's built here.</strong> {p.built}</p>
            <p><strong>Try this.</strong> {p.tryThis.replace(/`/g, '')}, then look at {p.look.replace(/[`*]/g, '')}.</p>
            <p><a href={p.docs} target="_blank" rel="noreferrer">Databricks docs ↗</a></p>
          </article>
        </div>
      </div>
    </div>
  );
}
