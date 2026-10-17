export const TITLE_IMAGE = '/images/title.webp';

export function sceneImage(locationId: string | undefined): string | null {
  return locationId ? `/images/${locationId}.webp` : null;
}
