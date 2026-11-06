'use strict';
/*
 * reconprobe_v1 — one-shot in-process probe for the 75U8QTUK root-lane gate.
 *
 * Written into /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/ by
 * launcher/recon-superwatch.html via basic/fetcher fetchFile, then invoked at
 * /function/basic/fetch/reconprobe_v1.
 *
 * Read-only on the TV: stats/connects to the superwatch socket and sends one
 * 4-byte-length + "901:85:901" message (command 85 = directory size). It
 * deletes the two recon markers from findings/05, writes its result to
 * /APPS/.recon_probe_result.json, and unlinks its own source file.
 * launcher/recon-cleanup.js then removes the result file.
 */
const fs = require('fs');
const net = require('net');
const cp = require('child_process');

const MARKERS = [
  '/APPS/.recon_fetcher_marker',
  '/APPS/pkgs/tv.vidaa.jsservice.basic/CHA/.recon_fetcher_marker'
];
const RESULT = '/APPS/.recon_probe_result.json';

function socketTest() {
  return new Promise(function (resolve) {
    let done = false;
    let c = null;
    const chunks = [];
    function fin(extra) {
      if (done) return;
      done = true;
      try { if (c) c.destroy(); } catch (e) {}
      const resp = Buffer.concat(chunks).toString('latin1').slice(0, 300);
      resolve(Object.assign({ resp: resp }, extra || {}));
    }
    try {
      c = net.createConnection('/var/run/superwatch_socket');
    } catch (e) {
      return resolve({ connectThrew: String(e) });
    }
    c.setTimeout(4000);
    c.on('connect', function () {
      try {
        const payload = '901:85:901';
        const b = Buffer.from(payload, 'utf8');
        const h = Buffer.alloc(4);
        h.writeUInt32LE(b.length, 0);
        c.write(Buffer.concat([h, b]));
      } catch (e) { fin({ writeThrew: String(e) }); }
    });
    c.on('data', function (d) { chunks.push(d); });
    c.on('end', function () { fin({ connected: true }); });
    c.on('timeout', function () { fin({ connected: true, timeout: true }); });
    c.on('error', function (e) { fin({ connected: false, err: e.code + ': ' + e.message }); });
  });
}

module.exports = async function () {
  const out = {
    ran: new Date().toISOString(),
    uid: process.getuid ? process.getuid() : null,
    gid: process.getgid ? process.getgid() : null,
    groups: process.getgroups ? process.getgroups() : null,
    arch: process.arch,
    platform: process.platform,
    execPath: process.execPath,
    sourceFile: __filename
  };

  try {
    out.uname = cp.execSync('uname -a', { timeout: 2000 }).toString().trim().slice(0, 300);
  } catch (e) { out.uname = 'ERR: ' + e.message; }

  try {
    const st = fs.statSync('/var/run/superwatch_socket');
    out.socketStat = {
      mode: (st.mode & 0o7777).toString(8),
      uid: st.uid,
      gid: st.gid
    };
  } catch (e) { out.socketStat = 'ERR: ' + e.code; }

  try {
    fs.writeFileSync('/var/local/.recon_write_test', 'ok');
    out.varLocal = { write: true, read: fs.readFileSync('/var/local/.recon_write_test', 'utf8') };
    fs.unlinkSync('/var/local/.recon_write_test');
    out.varLocal.cleanup = true;
  } catch (e) {
    out.varLocal = { error: e.code + ': ' + e.message };
  }

  out.socket = await socketTest();

  out.markers = {};
  for (const m of MARKERS) {
    try { fs.unlinkSync(m); out.markers[m] = 'deleted'; }
    catch (e) { out.markers[m] = e.code + ': ' + e.message; }
  }

  try {
    fs.writeFileSync(RESULT, JSON.stringify(out));
    out.resultFile = RESULT;
  } catch (e) { out.resultFile = 'ERR: ' + e.code; }

  try { fs.unlinkSync(__filename); out.selfDeleted = true; }
  catch (e) { out.selfDeleted = e.code + ': ' + e.message; }

  return out;
};
