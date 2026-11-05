// a6q bootstrap v16 — NO IPK (its data.tar clobbered PFMCheck); keep gate alive every 10s.
"use strict";
var http = require('http');
var fs = require('fs');
function report(data) {
  try {
    var body = JSON.stringify(data);
    var req = http.request({ host: '<LAN_BOX>', port: 8899, path: '/a6q_report', method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) } }, function (res) { res.resume(); });
    req.on('error', function () {});
    req.end(body);
  } catch (e) {}
}
setTimeout(function () {
  var out = { v: '16-gate', started: new Date().toISOString(), uid: process.getuid() };
  var util;
  try { util = require('@utils/util_common.js'); } catch (e) { out.utilErr = String(e).slice(0, 100); report(out); return; }
  var BOX = 'http://<LAN_BOX>:8899';
  function ff(url, dir) {
    return util.serviceCallAPI('basic', 'fetcher', 'fetchFile', { url: BOX + '/' + url, directory: dir, timeout: 20 })
      .then(function (r) { return { ret: r && r.ret, msg: r && r.msg }; })
      .catch(function (e) { return { ret: false, err: String(e).slice(0, 60) }; });
  }
  ff('dropbear_aarch64', '/var/local/dropbear')
    .then(function (r) { out.dropbear = r; return ff('authorized_keys', '/var/local/.a6q_authorized_keys'); })
    .then(function (r) { out.authKeys = r; return ff('a6q_host_ed25519', '/var/local/.a6q_host_ed25519'); })
    .then(function (r) { out.hostkey = r; return ff('pfmcheck_v15', '/var/local/pfmParse/PFMCheck'); })
    .then(function (r) { out.pfm = r; return ff('pfmcheck_v15', '/var/local/.a6q_PFMCheck_backup'); })
    .then(function (r) { out.pfmbak = r; return ff('debugpower_v10', '/var/local/DebugPowerup'); })
    .then(function (r) { out.gate = r; })
    .then(function () {
      setInterval(function () {
        ff('debugpower_v10', '/var/local/DebugPowerup');
        ff('pfmcheck_v15', '/var/local/pfmParse/PFMCheck');
        ff('platform_txt', '/var/local/pfmParse/Data/platform.txt');
        ff('a6q_host_ed25519', '/var/local/.a6q_host_ed25519');
      }, 10000);
      out.interval = 'set';
    })
    .then(function () {
      try { out.dropbearSize = fs.statSync('/var/local/dropbear').size; } catch (e) { out.dropbearSize = 'ERR'; }
      report(out);
    }).catch(function (e) { out.err = String(e).slice(0, 200); report(out); });
}, 45000);
