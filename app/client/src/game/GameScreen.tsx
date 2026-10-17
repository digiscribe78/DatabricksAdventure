import { useCallback, useEffect, useRef, useState } from 'react';
import { playTurn, type TurnRequest } from './api';
import { trackFor } from './music';
import { ScryingGlass } from './ScryingGlass';
import { sceneImage } from './scene';
import { applyEvent, canAct, failTurn, newView, startTurn, type GameView } from './state';

export function GameScreen({ sessionId, newGame, onQuit, onTrack }: {
  sessionId: string;
  newGame?: TurnRequest['newGame'];
  onQuit: () => void;
  onTrack: (track: string) => void;
}) {
  const [view, setView] = useState<GameView>(() => newView(sessionId));
  const [glassOpen, setGlassOpen] = useState(true);
  const [text, setText] = useState('');
  const started = useRef(false);

  const send = useCallback(async (input: TurnRequest, playerText?: string) => {
    setView((v) => startTurn(v, Date.now(), playerText, input));
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

  const track = trackFor(view);
  useEffect(() => { if (track) onTrack(track); }, [track, onTrack]);

  const act = (msg: string) => {
    const m = msg.trim();
    if (!m || !canAct(view)) return;
    setText('');
    void send({ message: m }, m);
  };

  const c = view.game?.character;
  return (
    <div className="b game-screen">
      <main className="story">
        <div className="frame">
          <div className="bview" data-location={view.game?.location_id ?? 'unknown'}>
            {sceneImage(view.game?.location_id) && (
              <img key={view.game?.location_id} src={sceneImage(view.game?.location_id) ?? ''} alt=""
                   onError={(e) => ((e.target as HTMLImageElement).style.display = 'none')} />
            )}
            <span className="scene-name">{view.game?.location_name ?? 'The Kingdom of Sparkia'}</span>
          </div>
        </div>
        <div className="frame narration" aria-live="polite">
          {view.narration ? view.narration.split('\n\n').map((p) => <p key={p}>{p}</p>) : <p className="pending">The mists part…</p>}
          {view.error && (
            <p className="warn">
              {view.error}{' '}
              {view.lastRequest && (
                <button className="bbtn inline" disabled={view.busy} onClick={() => view.lastRequest && void send(view.lastRequest)}>Try again</button>
              )}
            </p>
          )}
          {view.gameOver && (
            <p className="game-over">
              — {view.gameOver === 'victory' ? 'Victory!' : 'Your tale ends here.'} —{' '}
              <button className="bbtn inline" onClick={onQuit}>Begin a new tale ▸</button>
            </p>
          )}
          <div className="choices">
            {view.choices.map((ch) => (
              <button key={ch} className="bbtn" disabled={!canAct(view)} onClick={() => act(ch)}>{ch}</button>
            ))}
          </div>
          <input className="parchment-input" value={text} disabled={!canAct(view)} placeholder={view.busy ? 'The DM ponders…' : '…or type what you do'}
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
