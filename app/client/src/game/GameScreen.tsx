import { useCallback, useEffect, useRef, useState } from 'react';
import { playTurn, type TurnRequest } from './api';
import { ScryingGlass } from './ScryingGlass';
import { applyEvent, failTurn, newView, startTurn, type GameView } from './state';

export function GameScreen({ sessionId, newGame, onQuit }: {
  sessionId: string;
  newGame?: TurnRequest['newGame'];
  onQuit: () => void;
}) {
  const [view, setView] = useState<GameView>(() => newView(sessionId));
  const [glassOpen, setGlassOpen] = useState(true);
  const [text, setText] = useState('');
  const started = useRef(false);

  const send = useCallback(async (input: TurnRequest, playerText?: string) => {
    setView((v) => startTurn(v, Date.now(), playerText));
    try {
      await playTurn(sessionId, input, (e) => setView((v) => applyEvent(v, e, Date.now())));
    } catch (err) {
      setView((v) => failTurn(v, err instanceof Error ? err.message : String(err)));
    }
  }, [sessionId]);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void send(newGame ? { newGame } : { message: '' });
  }, [newGame, send]);

  const act = (msg: string) => {
    const m = msg.trim();
    if (!m || view.busy) return;
    setText('');
    void send({ message: m }, m);
  };

  const c = view.game?.character;
  return (
    <div className="b game-screen">
      <main className="story">
        <div className="frame">
          <div className="bview" data-location={view.game?.location_id ?? 'unknown'}>
            <img src={`/images/${view.game?.location_id}.webp`} alt="" onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
            <span className="scene-name">{view.game?.location_name ?? 'The Kingdom of Sparkia'}</span>
          </div>
        </div>
        <div className="frame narration" aria-live="polite">
          {view.narration ? view.narration.split('\n\n').map((p) => <p key={p}>{p}</p>) : <p className="pending">The mists part…</p>}
          {view.error && (
            <p className="warn">
              {view.error} <button className="bbtn inline" onClick={() => act(text || 'I look around')}>Try again</button>
            </p>
          )}
          {view.gameOver && <p className="game-over">— {view.gameOver === 'victory' ? 'Victory!' : 'Your tale ends here.'} —</p>}
          <div className="choices">
            {view.choices.map((ch) => (
              <button key={ch} className="bbtn" disabled={view.busy} onClick={() => act(ch)}>{ch}</button>
            ))}
          </div>
          <input className="parchment-input" value={text} disabled={view.busy} placeholder={view.busy ? 'The DM ponders…' : '…or type what you do'}
                 onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && act(text)} />
        </div>
        <div className="frame sheet">
          {c ? (
            <>
              <strong>{c.name.toUpperCase()}</strong> · {c.archetype} · HP <span className="hp">{'▮'.repeat(Math.max(0, Math.round((c.hp / c.max_hp) * 9)))}{'▯'.repeat(9 - Math.max(0, Math.round((c.hp / c.max_hp) * 9)))}</span> {c.hp}/{c.max_hp} · M{c.might >= 0 ? '+' : ''}{c.might} W{c.wits >= 0 ? '+' : ''}{c.wits} C{c.charm >= 0 ? '+' : ''}{c.charm} · {c.gold} gp
              <div className="pack">🎒 {c.inventory.join(', ') || 'empty-handed'}</div>
            </>
          ) : 'Reading your character sheet…'}
          <button className="bbtn inline quit" onClick={onQuit}>Leave ▸</button>
        </div>
      </main>
      <ScryingGlass view={view} open={glassOpen} onToggle={() => setGlassOpen(!glassOpen)} />
    </div>
  );
}
