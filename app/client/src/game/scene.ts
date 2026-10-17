export function sceneImage(locationId: string | undefined): string | null {
  return locationId ? `/images/${locationId}.webp` : null;
}
