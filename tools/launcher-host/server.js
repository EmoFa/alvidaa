'use strict';
/* alvidaa on-TV launcher host: static file server for /APPS/launcher on
   127.0.0.1:8765 (plus the LAN interface). Run by the re-arm postinst:
   nohup phoenix LD_LIBRARY_PATH=... server.js &
   The page's dynamic endpoints (/ws, /api/*) live on the operator PC; this
   host serves the shell so the TV renders its home offline. */
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = '/APPS/launcher';
const PORT = 8765;
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.json': 'application/json',
  '.woff2': 'font/woff2'
};

function log(m) {
  try { fs.appendFileSync('/tmp/launcher-host.log', new Date().toISOString() + ' ' + m + '\n'); } catch (e) {}
}

const server = http.createServer(function (req, res) {
  let p = decodeURIComponent((req.url || '/').split('?')[0]);
  if (p === '/' || p === '/index.html') p = '/index.html';
  const file = path.join(ROOT, path.normalize(p).replace(/^(\.\.[\/\\])+/, ''));
  if (file.indexOf(ROOT) !== 0) { res.writeHead(403); res.end(); return; }
  fs.readFile(file, function (err, data) {
    if (err) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
      'Content-Length': data.length
    });
    res.end(data);
  });
});

server.listen(PORT, '0.0.0.0', function () {
  log('launcher host listening on ' + PORT);
});
server.on('error', function (e) {
  // EADDRINUSE etc: exit non-zero so the postinst probe reflects reality —
  // a zombie process without a listener is worse than no process.
  log('server error: ' + e + ' — exiting');
  process.exit(1);
});
process.on('uncaughtException', function (e) { log('uncaught: ' + e); process.exit(1); });
