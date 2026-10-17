import { describe, expect, it } from 'vitest';
import { inlineParts } from './format';

describe('inlineParts', () => {
  it('turns the DM\'s **bold** into bold runs', () => {
    expect(inlineParts('You stand at the **Delta Crossing** as night falls.')).toEqual([
      { text: 'You stand at the ', bold: false },
      { text: 'Delta Crossing', bold: true },
      { text: ' as night falls.', bold: false },
    ]);
  });

  it('leaves plain text and stray asterisks alone', () => {
    expect(inlineParts('No markup here.')).toEqual([{ text: 'No markup here.', bold: false }]);
    expect(inlineParts('A lone * star and **unclosed')).toEqual([{ text: 'A lone * star and **unclosed', bold: false }]);
  });
});

describe('inlineParts italics', () => {
  it('turns *italic* into italic runs, alongside bold', () => {
    expect(inlineParts('They lead *under* the **Archive**.')).toEqual([
      { text: 'They lead ', bold: false },
      { text: 'under', bold: false, italic: true },
      { text: ' the ', bold: false },
      { text: 'Archive', bold: true },
      { text: '.', bold: false },
    ]);
  });
});
