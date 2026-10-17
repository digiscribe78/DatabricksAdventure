import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FADE_MS, MusicPlayer, musicUrl, trackFor, type AudioLike } from './music';
import { newView, type GameView } from './state';

const at = (location_id: string, extra: Partial<GameView> = {}): GameView => ({
  ...newView('s'),
  game: {
    character: { name: 'Wren', archetype: 'bard', hp: 14, max_hp: 14, might: 0, wits: 0, charm: 3, gold: 12, xp: 0, inventory: [] },
    location_id, location_name: location_id, exits: [], flags: {}, npcs: [], traces_url: null,
  },
  ...extra,
});

describe('trackFor', () => {
  it('plays the title theme before the first snapshot arrives', () => {
    expect(trackFor(newView('s'))).toBe('title');
  });

  it('plays the theme of the place the player stands', () => {
    expect(trackFor(at('photon-mines'))).toBe('photon-mines');
  });

  it('switches to the battle theme when the last turn had an attack', () => {
    const events = [{ type: 'roll', summary: 'd20' }, { type: 'attack', summary: 'You strike the rat' }];
    expect(trackFor(at('data-swamp', { events }))).toBe('combat');
  });

  it('keeps the current track while the DM is mid-turn, so fights do not flicker', () => {
    expect(trackFor(at('data-swamp', { busy: true }))).toBeNull();
  });

  it('returns to the title theme once the adventure is over', () => {
    expect(trackFor(at('silos-keep', { gameOver: 'victory' }))).toBe('title');
  });
});

describe('musicUrl', () => {
  it('maps a track to its file', () => {
    expect(musicUrl('delta-crossing')).toBe('/music/delta-crossing.mp3');
  });
});

class FakeAudio implements AudioLike {
  volume = 1;
  currentTime = 0;
  duration = 75;
  paused = true;
  src: string;
  constructor(src: string) { this.src = src; }
  play() { this.paused = false; return Promise.resolve(); }
  pause() { this.paused = true; }
}

describe('MusicPlayer', () => {
  let made: FakeAudio[];
  let player: MusicPlayer;

  beforeEach(() => {
    vi.useFakeTimers();
    made = [];
    player = new MusicPlayer((src) => { const a = new FakeAudio(src); made.push(a); return a; }, 0.5);
  });
  afterEach(() => { player.stop(); vi.useRealTimers(); });

  it('makes no sound until it is switched on', () => {
    player.play('title');
    expect(made).toHaveLength(0);
  });

  it('fades the chosen track in once switched on', () => {
    player.play('title');
    player.setEnabled(true);
    expect(made[0].src).toBe('/music/title.mp3');
    expect(made[0].paused).toBe(false);
    vi.advanceTimersByTime(FADE_MS);
    expect(made[0].volume).toBeCloseTo(0.5);
  });

  it('crossfades to a new track and pauses the old one', () => {
    player.setEnabled(true);
    player.play('medallion-inn');
    vi.advanceTimersByTime(FADE_MS);
    player.play('delta-crossing');
    vi.advanceTimersByTime(FADE_MS);
    expect(made[1].src).toBe('/music/delta-crossing.mp3');
    expect(made[1].volume).toBeCloseTo(0.5);
    expect(made[0].paused).toBe(true);
  });

  it('ignores a request for the track already playing', () => {
    player.setEnabled(true);
    player.play('medallion-inn');
    player.play('medallion-inn');
    expect(made).toHaveLength(1);
  });

  it('crossfades a track into its own restart before it ends, covering any fade-out', () => {
    player.setEnabled(true);
    player.play('streaming-falls');
    vi.advanceTimersByTime(FADE_MS);
    made[0].currentTime = made[0].duration - FADE_MS / 1000 + 0.1;
    vi.advanceTimersByTime(250);
    expect(made).toHaveLength(2);
    expect(made[1].src).toBe('/music/streaming-falls.mp3');
  });

  it('fades out and falls silent when switched off', () => {
    player.setEnabled(true);
    player.play('title');
    vi.advanceTimersByTime(FADE_MS);
    player.setEnabled(false);
    vi.advanceTimersByTime(FADE_MS);
    expect(made[0].paused).toBe(true);
  });
});
