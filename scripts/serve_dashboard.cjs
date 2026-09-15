#!/usr/bin/env node
// Hepsiburada dashboard statik sunucusu: http://127.0.0.1:4318
const http = require('http');
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', 'dashboard');
const PORT = Number(process.env.DASHBOARD_PORT || 4318);
const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript' };
http.createServer((req, res) => {
  const name = (req.url === '/' ? '/index.html' : req.url.split('?')[0]).replace(/\.\./g, '');
  const file = path.join(ROOT, name);
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404); res.end('yok'); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    res.end(data);
  });
}).listen(PORT, '127.0.0.1', () => console.log(`DASHBOARD_SERVE http://127.0.0.1:${PORT}`));
