'use strict';
/*
 * reconcleanup_v1 — remove the probe result file and this source file.
 *
 * Written into /APPS/pkgs/tv.vidaa.jsservice.basic/CHA/functions/fetch/ and
 * invoked at /function/basic/fetch/reconcleanup_v1 after
 * launcher/recon-superwatch.html has read /APPS/.recon_probe_result.json.
 */
const fs = require('fs');

module.exports = async function () {
  const out = { ran: new Date().toISOString() };
  for (const p of ['/APPS/.recon_probe_result.json']) {
    try { fs.unlinkSync(p); out[p] = 'deleted'; }
    catch (e) { out[p] = e.code + ': ' + e.message; }
  }
  try { fs.unlinkSync(__filename); out.selfDeleted = true; }
  catch (e) { out.selfDeleted = e.code + ': ' + e.message; }
  return out;
};
