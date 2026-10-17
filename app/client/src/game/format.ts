export interface InlinePart {
  text: string;
  bold: boolean;
  italic?: true;
}

// **bold** or *italic*: the markdown the DM uses for names, places and stress.
const EMPHASIS = /\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*/g;

/** Split a paragraph of the DM's narration into plain, bold and italic runs. */
export function inlineParts(text: string): InlinePart[] {
  const parts: InlinePart[] = [];
  let at = 0;
  for (const m of text.matchAll(EMPHASIS)) {
    if (m.index > at) parts.push({ text: text.slice(at, m.index), bold: false });
    parts.push(m[1] !== undefined ? { text: m[1], bold: true } : { text: m[2], bold: false, italic: true });
    at = m.index + m[0].length;
  }
  if (at < text.length) parts.push({ text: text.slice(at), bold: false });
  return parts;
}
