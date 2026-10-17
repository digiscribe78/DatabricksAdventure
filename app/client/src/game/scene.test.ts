import { describe, expect, it } from 'vitest';
import { TITLE_IMAGE, sceneImage } from './scene';

describe('sceneImage', () => {
  it('maps a location to its art and nothing before the snapshot arrives', () => {
    expect(sceneImage('delta-crossing')).toBe('/images/delta-crossing.webp');
    expect(sceneImage(undefined)).toBeNull();
    expect(sceneImage('')).toBeNull();
  });
});

describe('TITLE_IMAGE', () => {
  it('points at the title card art', () => {
    expect(TITLE_IMAGE).toBe('/images/title.webp');
  });
});
