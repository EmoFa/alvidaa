#!/usr/bin/env node
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { hash } = require('./native-trial.cjs');
const STOCK_HASH = '046b41aee0242ced3d3fcd9d5e0c0adb68e17ea3bfe14efa13d6225b6050bfad';
function build(stockFile, output) {
  const stock = fs.readFileSync(stockFile);
  assert.equal(hash(stock), STOCK_HASH, 'wrong stock launcher revision');
  const license = fs.readFileSync(path.join(__dirname, 'third-party/free-my-tv/LICENSE'), 'utf8');
  const parts = ['native-platform.js', 'free-my-tv-native.js', 'native-entry.js'];
  const candidate = '/* ALVIDAA_FREE_MY_TV_NATIVE_V1\n' + license + '\n*/\n' + stock + '\n;\n' +
    parts.map(file => fs.readFileSync(path.join(__dirname, file), 'utf8')).join('\n;\n');
  new vm.Script(candidate, { filename: 'native-candidate.js' });
  if (output) {
    const target = path.resolve(output);
    const privateRoot = path.resolve(__dirname, '../../firmware') + path.sep;
    assert.ok(target.startsWith(privateRoot) || target.startsWith('/tmp/'), 'vendor-containing output must stay private');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, candidate, { mode: 0o600 });
    fs.chmodSync(target, 0o600);
  }
  return candidate;
}
if (require.main === module) {
  const [stock, output] = process.argv.slice(2);
  assert.ok(stock && output, 'Usage: build-native.cjs private-stock.js private-output.js');
  const candidate = build(stock, output);
  console.log('Built native candidate: ' + Buffer.byteLength(candidate) + ' bytes; sha256 ' + hash(candidate));
}
module.exports = { build, STOCK_HASH };
