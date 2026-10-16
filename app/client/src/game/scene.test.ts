import { describe, expect, it } from 'vitest';
import { sceneImage } from './scene';

describe('sceneImage', () => {
  it('maps a location to its art and nothing before the snapshot arrives', () => {
    expect(sceneImage('delta-crossing')).toBe('/images/delta-crossing.webp');
    expect(sceneImage(undefined)).toBeNull();
    expect(sceneImage('')).toBeNull();
  });
});
