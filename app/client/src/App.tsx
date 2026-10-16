import { useState } from 'react';
import { GameScreen } from './game/GameScreen';
import { TitleScreen } from './game/TitleScreen';

type Screen = { kind: 'title' } | { kind: 'game'; sessionId: string; newGame?: { name: string; archetype: 'warrior' | 'mage' | 'bard' } };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: 'title' });
  return screen.kind === 'title' ? (
    <TitleScreen onStart={(sessionId, newGame) => setScreen({ kind: 'game', sessionId, newGame })} />
  ) : (
    <GameScreen key={screen.sessionId} sessionId={screen.sessionId} newGame={screen.newGame} onQuit={() => setScreen({ kind: 'title' })} />
  );
}
