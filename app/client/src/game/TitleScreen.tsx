import { useEffect, useState } from 'react';
import { listAdventures, type Adventure } from './api';

type Archetype = 'warrior' | 'mage' | 'bard';
const ARCHETYPES: { id: Archetype; label: string; blurb: string }[] = [
  { id: 'warrior', label: 'Warrior', blurb: 'Might +3 · 18 HP · longsword, shield, rope' },
  { id: 'mage', label: 'Mage', blurb: 'Wits +3 · 12 HP · ember wand, lantern, runes' },
  { id: 'bard', label: 'Bard', blurb: 'Charm +3 · 14 HP · rapier, lute, letter of introduction' },
];

export function TitleScreen({ onStart }: { onStart: (sessionId: string, newGame?: { name: string; archetype: Archetype }) => void }) {
  const [name, setName] = useState('');
  const [archetype, setArchetype] = useState<Archetype>('warrior');
  const [saves, setSaves] = useState<Adventure[] | null>(null);
  const [error, setError] = useState<string>();

  useEffect(() => {
    listAdventures().then(setSaves).catch((e: Error) => setError(e.message));
  }, []);

  const begin = () => name.trim() && onStart(crypto.randomUUID(), { name: name.trim().slice(0, 40), archetype });
  const resumable = (saves ?? []).filter((s) => s.client_session_id);

  return (
    <div className="b title-screen">
      <h1 className="title8">The Kingdom of Sparkia</h1>
      <p className="subtitle">A Databricks Adventure</p>
      <div className="frame panel">
        <h2 className="title8 small">New adventure</h2>
        <input className="parchment-input" placeholder="Your name, traveller" value={name} maxLength={40}
               onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && begin()} />
        <div className="archetypes">
          {ARCHETYPES.map((a) => (
            <button key={a.id} className={`bbtn ${archetype === a.id ? 'chosen' : ''}`} onClick={() => setArchetype(a.id)}>
              <strong>{a.label}</strong>
              <span>{a.blurb}</span>
            </button>
          ))}
        </div>
        <button className="bbtn begin" disabled={!name.trim()} onClick={begin}>Begin adventure ▸</button>
      </div>
      <div className="frame panel">
        <h2 className="title8 small">Continue</h2>
        {error && <p className="warn">{error}</p>}
        {saves === null && !error && <p>Consulting the chronicles…</p>}
        {saves !== null && resumable.length === 0 && <p>No saved adventures yet.</p>}
        {resumable.map((s) => (
          <button key={s.session_id} className="bbtn" onClick={() => onStart(s.client_session_id!)}>
            {s.name} the {s.archetype} · {s.location_id.replace(/-/g, ' ')}
          </button>
        ))}
      </div>
    </div>
  );
}
