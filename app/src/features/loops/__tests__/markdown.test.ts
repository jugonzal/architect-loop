// app-documents C1: the loop documents' markdown, read into the blocks a concern or loop page draws. The cases are
// the shapes the loop skills write (loop-plan's templates): front matter, headings, bullets with continuation lines,
// tables of decisions and questions, and inline code, bold, strike-through and links.

import { inlineSpans, parseMarkdown } from '../markdown';

describe('parseMarkdown', () => {
  it('drops the front matter, which the Contract card already shows', () => {
    const blocks = parseMarkdown('---\nneeds: [a]\ntouches: [b]\n---\n# Title\n');
    expect(blocks).toEqual([{ kind: 'heading', level: 1, text: 'Title' }]);
  });

  it('keeps a document that only starts with a rule as it is', () => {
    expect(parseMarkdown('---\n\nText')).toEqual([{ kind: 'rule' }, { kind: 'paragraph', text: 'Text' }]);
  });

  it('reads headings and joins a paragraph’s lines', () => {
    expect(parseMarkdown('## Done when\n\nOne line\nand the next.\n\n### Approach\n')).toEqual([
      { kind: 'heading', level: 2, text: 'Done when' },
      { kind: 'paragraph', text: 'One line and the next.' },
      { kind: 'heading', level: 3, text: 'Approach' },
    ]);
  });

  it('reads bullets with their continuation lines, and nested bullets with their depth', () => {
    const text = [
      '- **C1** A claim that runs',
      '  onto a second line.',
      '- **C2** Another.',
      '  - a nested point',
      '1. A numbered one',
    ].join('\n');
    expect(parseMarkdown(text)).toEqual([
      {
        kind: 'list',
        items: [
          { depth: 0, marker: '•', text: '**C1** A claim that runs onto a second line.' },
          { depth: 0, marker: '•', text: '**C2** Another.' },
          { depth: 1, marker: '•', text: 'a nested point' },
          { depth: 0, marker: '1.', text: 'A numbered one' },
        ],
      },
    ]);
  });

  it('reads a table into its header and rows, without the separator, and keeps escaped pipes in a cell', () => {
    const text = [
      '| # | Decision | Decided by, date |',
      '| --- | --- | --- |',
      '| D1 | Use `a \\| b` here. | Juan, 2026-10-20 |',
      '| ~~D2~~ | ~~Old~~ | Juan |',
    ].join('\n');
    expect(parseMarkdown(text)).toEqual([
      {
        kind: 'table',
        header: ['#', 'Decision', 'Decided by, date'],
        rows: [
          ['D1', 'Use `a | b` here.', 'Juan, 2026-10-20'],
          ['~~D2~~', '~~Old~~', 'Juan'],
        ],
      },
    ]);
  });

  it('keeps a fenced code block as it is written', () => {
    expect(parseMarkdown('```sh\nsh up.sh\n  --flag\n```\nAfter')).toEqual([
      { kind: 'code', text: 'sh up.sh\n  --flag' },
      { kind: 'paragraph', text: 'After' },
    ]);
  });

  it('reads a quote as its own block', () => {
    expect(parseMarkdown('> quoted\n> more')).toEqual([{ kind: 'quote', text: 'quoted more' }]);
  });
});

describe('inlineSpans', () => {
  it('splits bold, strike-through, code and links, and leaves the rest as plain text', () => {
    expect(inlineSpans('A **bold** ~~old~~ `code` [link](https://example.com) end')).toEqual([
      { text: 'A ' },
      { text: 'bold', bold: true },
      { text: ' ' },
      { text: 'old', strike: true },
      { text: ' ' },
      { text: 'code', code: true },
      { text: ' ' },
      { text: 'link', href: 'https://example.com' },
      { text: ' end' },
    ]);
  });

  it('reads marks inside bold and strike-through', () => {
    expect(inlineSpans('**`x` and y**')).toEqual([
      { text: 'x', bold: true, code: true },
      { text: ' and y', bold: true },
    ]);
  });

  it('leaves an unclosed mark as the text it is', () => {
    expect(inlineSpans('a ** b ` c')).toEqual([{ text: 'a ** b ` c' }]);
  });

  it('keeps a relative link’s text and its path', () => {
    expect(inlineSpans('[the loop](../README.md)')).toEqual([{ text: 'the loop', href: '../README.md' }]);
  });
});
