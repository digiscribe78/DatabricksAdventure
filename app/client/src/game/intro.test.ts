import { describe, expect, it } from 'vitest';
import { INTRO, UNDER_THE_HOOD } from './intro';

describe('INTRO', () => {
  it('says what this is, the aim, how to play, the quest and the memory note', () => {
    expect(INTRO.map((s) => s.title)).toEqual(['What this is', 'The aim', 'How to play', 'The quest', 'A note on memory']);
    const all = INTRO.map((s) => s.text).join(' ');
    for (const words of ['Dungeon Master', 'Databricks', 'Scrying Glass', '💡 Hint', '📖 Guide', 'Keeper Aldric', 'Lord Silo', 'remembers']) {
      expect(all).toContain(words);
    }
  });

  it('lists the Databricks pieces under the hood', () => {
    expect(UNDER_THE_HOOD).toEqual(['LangGraph on Agent Runtime', 'AI Search', 'Lakebase', 'Agent memory',
      'MLflow tracing and evals', 'AI Gateway guardrails']);
  });
});
