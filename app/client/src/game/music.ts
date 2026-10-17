import type { GameView } from './state';

/** Crossfade length, both between tracks and when a track loops into itself. */
export const FADE_MS = 2000;
const STEP_MS = 50;
const WATCH_MS = 250;

const PLACES = new Set([
  'medallion-inn', 'delta-crossing', 'unity-archive', 'spark-forge',
  'streaming-falls', 'photon-mines', 'data-swamp', 'silos-keep',
]);

/** Which track suits this moment, or null to keep whatever is playing (mid-turn). */
export function trackFor(v: GameView): string | null {
  if (v.busy) return null;
  if (v.gameOver || !v.game) return 'title';
  if (v.events.some((e) => e.type === 'attack')) return 'combat';
  return PLACES.has(v.game.location_id) ? v.game.location_id : 'title';
}

export const musicUrl = (track: string) => `/music/${track}.mp3`;

/** The slice of HTMLAudioElement the player needs, so tests can stand in for it. */
export interface AudioLike {
  volume: number;
  currentTime: number;
  readonly duration: number;
  readonly paused: boolean;
  play(): Promise<void>;
  pause(): void;
}

/**
 * Two-deck music player: each change of track (or a track reaching its end)
 * crossfades a fresh deck in over the old one, so tracks that fade out still loop
 * seamlessly. Silent until enabled, because browsers only allow sound after a click.
 */
export class MusicPlayer {
  private enabled = false;
  private wanted: string | null = null;
  private current: { track: string; audio: AudioLike } | null = null;
  private ramps = new Map<AudioLike, ReturnType<typeof setInterval>>();
  private watch?: ReturnType<typeof setInterval>;

  private make: (src: string) => AudioLike;
  private maxVolume: number;

  constructor(make: (src: string) => AudioLike, maxVolume = 0.5) {
    this.make = make;
    this.maxVolume = maxVolume;
  }

  play(track: string) {
    this.wanted = track;
    if (this.enabled && this.current?.track !== track) this.switchTo(track);
  }

  setEnabled(on: boolean) {
    this.enabled = on;
    if (on && this.wanted && !this.current) this.switchTo(this.wanted);
    if (!on && this.current) {
      this.fade(this.current.audio, 0, true);
      this.current = null;
    }
  }

  stop() {
    this.ramps.forEach((t, a) => { clearInterval(t); a.pause(); });
    this.ramps.clear();
    this.current?.audio.pause();
    this.current = null;
    if (this.watch) clearInterval(this.watch);
    this.watch = undefined;
  }

  private switchTo(track: string) {
    if (this.current) this.fade(this.current.audio, 0, true);
    const audio = this.make(musicUrl(track));
    audio.volume = 0;
    audio.play().catch(() => undefined); // a missing file or a blocked autoplay just stays silent
    this.current = { track, audio };
    this.fade(audio, this.maxVolume, false);
    this.watch ??= setInterval(() => this.loopIfEnding(), WATCH_MS);
  }

  private loopIfEnding() {
    const c = this.current;
    if (!c || !Number.isFinite(c.audio.duration)) return;
    if (c.audio.currentTime >= c.audio.duration - FADE_MS / 1000) this.switchTo(c.track);
  }

  private fade(audio: AudioLike, to: number, pauseAtEnd: boolean) {
    const running = this.ramps.get(audio);
    if (running) clearInterval(running);
    const from = audio.volume;
    const steps = FADE_MS / STEP_MS;
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      audio.volume = i >= steps ? to : from + ((to - from) * i) / steps;
      if (i >= steps) {
        clearInterval(t);
        this.ramps.delete(audio);
        if (pauseAtEnd) audio.pause();
      }
    }, STEP_MS);
    this.ramps.set(audio, t);
  }
}
