import { useEffect, useRef, useState } from 'react';
import { GameScreen } from './game/GameScreen';
import { GuidePanel } from './game/GuidePanel';
import { TitleScreen } from './game/TitleScreen';
import { MusicPlayer } from './game/music';

type Screen = { kind: 'title' } | { kind: 'game'; sessionId: string; newGame?: { name: string; archetype: 'warrior' | 'mage' | 'bard' } };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: 'title' });
  const [track, setTrack] = useState('title');
  const [musicOn, setMusicOn] = useState(false);
  const [guide, setGuide] = useState<{ page?: string } | null>(null);  // transient UI: is the Guide open
  const openGuide = (page?: string) => setGuide({ page });
  const player = useRef<MusicPlayer | null>(null);
  player.current ??= new MusicPlayer((src) => Object.assign(new Audio(src), { preload: 'auto' }));

  useEffect(() => { player.current?.play(track); }, [track]);
  useEffect(() => { player.current?.setEnabled(musicOn); }, [musicOn]);
  useEffect(() => () => player.current?.stop(), []);

  return (
    <>
      <button className="bbtn music-toggle" aria-pressed={musicOn} onClick={() => setMusicOn((on) => !on)}>
        ♪ Music {musicOn ? 'on' : 'off'}
      </button>
      {screen.kind === 'title' ? (
        <TitleScreen onStart={(sessionId, newGame) => setScreen({ kind: 'game', sessionId, newGame })} onTrack={setTrack} onGuide={openGuide} />
      ) : (
        <GameScreen key={screen.sessionId} sessionId={screen.sessionId} newGame={screen.newGame}
                    onQuit={() => setScreen({ kind: 'title' })} onTrack={setTrack} onGuide={openGuide} />
      )}
      {guide && <GuidePanel page={guide.page} onClose={() => setGuide(null)} />}
    </>
  );
}
