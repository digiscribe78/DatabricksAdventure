import { describe, expect, it } from 'vitest';
import { parseSSE } from './sse';

describe('parseSSE', () => {
  it('parses complete blocks and keeps a partial tail', () => {
    const { events, rest } = parseSSE('event: node\ndata: {"node":"load_state"}\n\nevent: turn\ndata: {"tu');
    expect(events).toEqual([{ event: 'node', data: { node: 'load_state' } }]);
    expect(rest).toBe('event: turn\ndata: {"tu');
  });
  it('handles several events in one chunk and ignores id lines', () => {
    const { events } = parseSSE('id: 1\nevent: node\ndata: {"node":"a"}\n\nid: 2\nevent: node\ndata: {"node":"b"}\n\n');
    expect(events.map((e) => e.data.node)).toEqual(['a', 'b']);
  });
  it('skips malformed data without throwing', () => {
    const { events } = parseSSE('event: node\ndata: not-json\n\n');
    expect(events).toEqual([]);
  });
});
