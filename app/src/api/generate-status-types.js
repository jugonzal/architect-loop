#!/usr/bin/env node
// Generates src/api/status.gen.ts, the app's types for the status document, from the schema the loop-status
// script writes against (command-center/D15). The schema is the source of truth: change it, run
// `npm run generate:status`, and commit both in the same change. `npm run check:status`, and the test beside
// this file, fail when the committed types no longer match the schema.
//
// Plain Node (CommonJS), so it runs without a TypeScript toolchain. Metro never bundles it: nothing in the app
// imports it.
'use strict';

const fs = require('fs');
const path = require('path');
const { compile } = require('json-schema-to-typescript');

const SCHEMA = path.resolve(__dirname, '../../../plugin/skills/loop-status/scripts/status.schema.json');
const OUTPUT = path.resolve(__dirname, 'status.gen.ts');

const BANNER = [
  '/* eslint-disable */',
  '// Generated from plugin/skills/loop-status/scripts/status.schema.json by src/api/generate-status-types.js.',
  '// Do not edit by hand: change the schema, then run `npm run generate:status` (command-center/D15).',
].join('\n');

async function generate() {
  const schema = JSON.parse(fs.readFileSync(SCHEMA, 'utf8'));
  return compile(schema, 'StatusDocument', {
    bannerComment: BANNER,
    additionalProperties: false,
    strictIndexSignatures: true,
    unreachableDefinitions: true,
    format: true,
    style: { singleQuote: true, printWidth: 120 },
  });
}

async function main(argv) {
  const generated = await generate();
  if (argv.includes('--check')) {
    const committed = fs.existsSync(OUTPUT) ? fs.readFileSync(OUTPUT, 'utf8') : '';
    if (committed !== generated) {
      process.stderr.write('src/api/status.gen.ts does not match the schema: run `npm run generate:status`\n');
      return 1;
    }
    process.stdout.write('src/api/status.gen.ts matches the schema\n');
    return 0;
  }
  fs.writeFileSync(OUTPUT, generated);
  process.stdout.write('wrote src/api/status.gen.ts\n');
  return 0;
}

module.exports = { generate, SCHEMA, OUTPUT };

if (require.main === module) {
  main(process.argv.slice(2)).then(
    (code) => process.exit(code),
    (error) => {
      process.stderr.write(String(error && error.stack ? error.stack : error) + '\n');
      process.exit(1);
    },
  );
}
