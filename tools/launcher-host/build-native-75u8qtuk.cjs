#!/usr/bin/env node
/* Build the 75U8QTUK native Home candidate.
 *
 * The vendor bundle is private (gitignored firmware/), so the output is
 * restricted to firmware/ or /tmp/. Nothing vendor-derived is committed.
 * The stock sha256 pins the exact TV revision we fetched and verified.
 */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { hash } = require('./native-trial.cjs');

const STOCK_HASH = '380d337ecbfa08487768b18cb8342630db1c2880c6e6c14811e6f7d1c72f2c8f';
const PARTS = [
  'native-platform-75u8qtuk.js',
  'free-my-tv-native.js',
  'free-my-tv-native-75u8qtuk.js',
  'native-entry.js'
];

function build(stockFile, output) {
  const stock = fs.readFileSync(stockFile);
  assert.equal(hash(stock), STOCK_HASH, 'wrong 75U8QTUK stock launcher revision');
  const license = fs.readFileSync(path.join(__dirname, 'third-party/free-my-tv/LICENSE'), 'utf8');
  const candidate = '/* ALVIDAA_FREE_MY_TV_NATIVE_75U8QTUK_V1\n' + license + '\n*/\n' +
    stock + '\n;\n' +
    PARTS.map(file => fs.readFileSync(path.join(__dirname, file), 'utf8')).join('\n;\n');
  new vm.Script(candidate, { filename: 'native-candidate-75u8qtuk.js' });
  if (output) {
    const target = path.resolve(output);
    const privateRoot = path.resolve(__dirname, '../../firmware') + path.sep;
    assert.ok(target.startsWith(privateRoot) || target.startsWith('/tmp/'),
      'vendor-containing output must stay private');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, candidate, { mode: 0o600 });
    fs.chmodSync(target, 0o600);
  }
  return candidate;
}

if (require.main === module) {
  const [stock, output] = process.argv.slice(2);
  assert.ok(stock && output,
    'Usage: build-native-75u8qtuk.cjs private-stock.js private-output.js');
  const candidate = build(stock, output);
  const buf = Buffer.from(candidate);
  console.log('Built 75U8QTUK native candidate: ' + buf.length + ' bytes; sha256 ' + hash(buf));
}
module.exports = { build, STOCK_HASH, PARTS };
