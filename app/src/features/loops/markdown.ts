// The markdown of a loop document, read into the blocks a concern or loop page draws (app-documents C1). It reads
// the shapes the loop skills write and nothing more: front matter, headings, paragraphs, bullets with continuation
// lines, tables, fenced code, quotes and rules, and inline bold, strike-through, code and links. Anything else stays
// as the text it is, so a page never hides what the file says.

export type ListItem = { readonly depth: number; readonly marker: string; readonly text: string };

export type Block =
  | { readonly kind: 'heading'; readonly level: number; readonly text: string }
  | { readonly kind: 'paragraph'; readonly text: string }
  | { readonly kind: 'list'; readonly items: readonly ListItem[] }
  | { readonly kind: 'table'; readonly header: readonly string[]; readonly rows: readonly (readonly string[])[] }
  | { readonly kind: 'code'; readonly text: string }
  | { readonly kind: 'quote'; readonly text: string }
  | { readonly kind: 'rule' };

export type Span = {
  readonly text: string;
  readonly bold?: true;
  readonly strike?: true;
  readonly code?: true;
  readonly href?: string;
};

const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const BULLET = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;
const FENCE = /^\s*```/;

/** The front matter's lines, when the file opens with a --- block that a --- line closes. */
function frontMatterEnd(lines: readonly string[]): number {
  if (lines[0]?.trim() !== '---') return 0;
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i]!.trim();
    if (line === '---') return i + 1;
    // Front matter is key: value lines and their list items; a blank line or prose means it was a rule.
    if (!/^([\w-]+:|\s*-\s)/.test(lines[i]!)) return 0;
  }
  return 0;
}

/** A table row's cells, with `\|` kept as a pipe inside a cell. */
function cells(line: string): string[] {
  const inner = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return inner.split(/(?<!\\)\|/).map((cell) => cell.trim().replace(/\\\|/g, '|'));
}

function startsBlock(line: string): boolean {
  return HEADING.test(line) || BULLET.test(line) || TABLE_ROW.test(line) || FENCE.test(line) || /^\s*>/.test(line) || RULE.test(line);
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n?/g, '\n').split('\n');
  const blocks: Block[] = [];
  let i = frontMatterEnd(lines);
  while (i < lines.length) {
    const line = lines[i]!;
    if (!line.trim()) {
      i++;
      continue;
    }
    if (FENCE.test(line)) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !FENCE.test(lines[i]!)) body.push(lines[i++]!);
      i++; // the closing fence
      blocks.push({ kind: 'code', text: body.join('\n') });
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ kind: 'heading', level: heading[1]!.length, text: heading[2]! });
      i++;
      continue;
    }
    if (RULE.test(line)) {
      blocks.push({ kind: 'rule' });
      i++;
      continue;
    }
    if (TABLE_ROW.test(line)) {
      const rows: string[][] = [];
      while (i < lines.length && TABLE_ROW.test(lines[i]!)) {
        if (!TABLE_RULE.test(lines[i]!)) rows.push(cells(lines[i]!));
        i++;
      }
      blocks.push({ kind: 'table', header: rows[0] ?? [], rows: rows.slice(1) });
      continue;
    }
    if (BULLET.test(line)) {
      const items: { depth: number; marker: string; parts: string[] }[] = [];
      while (i < lines.length) {
        const current = lines[i]!;
        const bullet = BULLET.exec(current);
        if (bullet) {
          const marker = /^\d/.test(bullet[2]!) ? bullet[2]!.replace(')', '.') : '•';
          items.push({ depth: Math.floor(bullet[1]!.replace(/\t/g, '  ').length / 2), marker, parts: [bullet[3]!] });
        } else if (current.trim() && /^\s/.test(current) && items.length) {
          items[items.length - 1]!.parts.push(current.trim());
        } else {
          break;
        }
        i++;
      }
      blocks.push({
        kind: 'list',
        items: items.map(({ depth, marker, parts }) => ({ depth, marker, text: parts.join(' ') })),
      });
      continue;
    }
    if (/^\s*>/.test(line)) {
      const parts: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i]!)) parts.push(lines[i++]!.replace(/^\s*>\s?/, '').trim());
      blocks.push({ kind: 'quote', text: parts.join(' ') });
      continue;
    }
    const parts: string[] = [];
    while (i < lines.length && lines[i]!.trim() && !(parts.length && startsBlock(lines[i]!))) parts.push(lines[i++]!.trim());
    blocks.push({ kind: 'paragraph', text: parts.join(' ') });
  }
  return blocks;
}

type Marks = Omit<Span, 'text'>;

// Each mark, the text that opens it, and the one that closes it. Code is read first, so nothing inside it is a mark.
const PAIRS = [
  { open: '`', close: '`', mark: 'code' },
  { open: '**', close: '**', mark: 'bold' },
  { open: '~~', close: '~~', mark: 'strike' },
] as const;

const LINK = /^\[([^\]]+)\]\(([^)\s]+)\)/;

function push(out: Span[], text: string, marks: Marks) {
  if (!text) return;
  const last = out[out.length - 1];
  if (last && JSON.stringify({ ...last, text: '' }) === JSON.stringify({ ...marks, text: '' })) {
    out[out.length - 1] = { ...last, text: last.text + text };
  } else {
    out.push({ text, ...marks });
  }
}

function spansInto(out: Span[], text: string, marks: Marks) {
  let plain = '';
  let i = 0;
  while (i < text.length) {
    const rest = text.slice(i);
    const link = marks.code ? null : LINK.exec(rest);
    if (link) {
      push(out, plain, marks);
      plain = '';
      spansInto(out, link[1]!, { ...marks, href: link[2]! });
      i += link[0].length;
      continue;
    }
    const pair = marks.code ? undefined : PAIRS.find((p) => rest.startsWith(p.open));
    const end = pair ? text.indexOf(pair.close, i + pair.open.length) : -1;
    if (pair && end > i + pair.open.length) {
      push(out, plain, marks);
      plain = '';
      const inner = text.slice(i + pair.open.length, end);
      if (pair.mark === 'code') push(out, inner, { ...marks, code: true });
      else spansInto(out, inner, { ...marks, [pair.mark]: true });
      i = end + pair.close.length;
      continue;
    }
    plain += text[i];
    i++;
  }
  push(out, plain, marks);
}

/** A line's text as spans of plain, bold, struck-through, code and linked text. */
export function inlineSpans(text: string): Span[] {
  const out: Span[] = [];
  spansInto(out, text, {});
  return out;
}
