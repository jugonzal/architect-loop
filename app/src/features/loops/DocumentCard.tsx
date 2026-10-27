// A page's own document, drawn below the derived state (app-documents C1): the file at the main commit the status
// was gathered on, with the path and the commit it was read at. A file that cannot be read says so, and the rest of
// the page, which comes from the status document, is unchanged.

import { ActivityIndicator, Linking, StyleSheet, Text, View } from 'react-native';

import type { StatusDocument } from '../../api/status';
import { useSession } from '../../shell/session';
import { colors, fonts, radius, space, type } from '../../theme';
import { shortSha } from './board';
import { useDocument } from './documents';
import { inlineSpans, parseMarkdown, type Block } from './markdown';
import { Card, Notice, SectionLabel, styles as ui } from './ui';

export function DocumentCard({ doc, path }: { doc: StatusDocument; path: string }) {
  const { fetch, config } = useSession();
  const sha = doc.main.sha;
  const read = useDocument(fetch, config.project, path, sha);
  return (
    <Card testID="document">
      <SectionLabel text="Document" />
      <Text style={ui.mono} testID="document-source" selectable>
        {path} @{shortSha(sha)}
      </Text>
      {read.kind === 'loading' && (
        <View style={styles.waiting} accessibilityLiveRegion="polite">
          <ActivityIndicator color={colors.accent} />
          <Text style={ui.bodyMuted}>Reading the file…</Text>
        </View>
      )}
      {read.kind === 'failed' && (
        <Notice text={`${path} could not be read at @${shortSha(sha)}. ${read.message}`} alert />
      )}
      {read.kind === 'read' && <Markdown text={read.text} />}
    </Card>
  );
}

export function Markdown({ text }: { text: string }) {
  const blocks = parseMarkdown(text);
  let tables = 0;
  return (
    <View style={styles.blocks}>
      {blocks.map((block, i) => {
        const tableIndex = block.kind === 'table' ? tables++ : -1;
        return <BlockView key={i} block={block} tableIndex={tableIndex} />;
      })}
    </View>
  );
}

function BlockView({ block, tableIndex }: { block: Block; tableIndex: number }) {
  switch (block.kind) {
    case 'heading':
      return (
        <Text style={block.level <= 1 ? styles.h1 : block.level === 2 ? styles.h2 : styles.h3} accessibilityRole="header">
          <Inline text={block.text} />
        </Text>
      );
    case 'paragraph':
      return (
        <Text style={ui.body}>
          <Inline text={block.text} />
        </Text>
      );
    case 'quote':
      return (
        <Text style={[ui.bodyMuted, styles.quote]}>
          <Inline text={block.text} />
        </Text>
      );
    case 'list':
      return (
        <View style={ui.tight}>
          {block.items.map((item, i) => (
            <View key={i} style={[styles.item, { paddingLeft: item.depth * space.l }]}>
              <Text style={[ui.body, styles.marker]}>{item.marker}</Text>
              <Text style={[ui.body, ui.grow]}>
                <Inline text={item.text} />
              </Text>
            </View>
          ))}
        </View>
      );
    case 'table':
      // A phone is too narrow for a table's columns, so each row is drawn as its cells under their headers.
      return (
        <View style={ui.tight}>
          {block.rows.map((row, r) => (
            <View key={r} style={styles.row} testID={`table-row-${tableIndex === 0 ? r : `${tableIndex}-${r}`}`}>
              {row.map((cell, c) =>
                cell ? (
                  <View key={c} style={styles.cell}>
                    {block.header[c] ? <Text style={styles.cellLabel}>{block.header[c]}</Text> : null}
                    <Text style={c === 0 ? ui.strong : ui.bodyMuted}>
                      <Inline text={cell} />
                    </Text>
                  </View>
                ) : null,
              )}
            </View>
          ))}
        </View>
      );
    case 'code':
      return (
        <Text style={styles.code} selectable>
          {block.text}
        </Text>
      );
    case 'rule':
      return <View style={styles.rule} />;
  }
}

function Inline({ text }: { text: string }) {
  return (
    <>
      {inlineSpans(text).map((span, i) => {
        const style = [
          span.bold && styles.bold,
          span.strike && styles.strike,
          span.code && styles.inlineCode,
          span.href && styles.link,
        ];
        const href = span.href;
        const web = href && /^https?:\/\//.test(href) ? href : null;
        return (
          <Text
            key={i}
            style={style}
            accessibilityRole={web ? 'link' : undefined}
            onPress={web ? () => void Linking.openURL(web) : undefined}
          >
            {span.text}
          </Text>
        );
      })}
    </>
  );
}

const styles = StyleSheet.create({
  waiting: { flexDirection: 'row', alignItems: 'center', gap: space.s },
  blocks: { gap: space.m },
  h1: { ...type.heading, fontSize: 18, lineHeight: 24, color: colors.ink },
  h2: { ...type.heading, color: colors.ink, paddingTop: space.s },
  h3: { ...type.body, fontFamily: fonts.sansSemiBold, color: colors.inkSecondary },
  quote: { borderLeftWidth: 2, borderLeftColor: colors.borderStrong, paddingLeft: space.m },
  item: { flexDirection: 'row', gap: space.s },
  marker: { color: colors.inkSubtle, minWidth: 14 },
  row: { borderTopWidth: 1, borderTopColor: colors.divider, paddingTop: space.s, gap: space.xs },
  cell: { gap: 2 },
  cellLabel: { ...type.label, color: colors.inkSubtle },
  code: { ...type.mono, color: colors.ink, backgroundColor: colors.inset, borderRadius: radius.button, padding: space.m },
  rule: { height: 1, backgroundColor: colors.divider },
  bold: { fontFamily: fonts.sansSemiBold, color: colors.ink },
  strike: { textDecorationLine: 'line-through', color: colors.inkSubtle },
  inlineCode: { fontFamily: fonts.mono, fontSize: 12, backgroundColor: colors.inset },
  link: { color: colors.accent, textDecorationLine: 'underline' },
});
