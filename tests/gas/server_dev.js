/**
 * Server uji mode Android tanpa Google: menyajikan web/ dengan FIN_MODE='gas'
 * dan menjalankan backend gas/ (tangani) di POST /exec, di atas tiruan Sheet.
 *
 *   node tests/gas/server_dev.js <ekspor.json> [port]
 *   JEDA_MS=1500 node tests/gas/server_dev.js ...   # tiru lambatnya Apps Script
 *
 * <ekspor.json> = keluaran `scripts/migrasi_ke_gsheet.py --ekspor` dari
 * SALINAN data. Password uji: "rahasia-uji". Alamat server di halaman login:
 * http://localhost:<port>/exec
 */
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const { muat } = require('./muat');
const { SpreadsheetPalsu, propertiesPalsu } = require('./sheet_palsu');

const ekspor = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const PORT = Number(process.argv[3] || 8799);
const WEB = path.resolve(__dirname, '..', '..', 'web');

const ctx = muat({ http: () => ({ code: 503, text: 'AI dimatikan di server uji' }) });
ctx.PropertiesService = propertiesPalsu();
const ss = new SpreadsheetPalsu();
ctx.ST = new ctx.StoreSheet(ss);
ctx.api_admin_impor({ data: ekspor.data, seq: ekspor.seq });
ctx.pasang_password('rahasia-uji');

const JEDA = Number(process.env.JEDA_MS || 0);
const HITUNG = { panggilan: 0 };   // GET /hitung -> jumlah panggilan /exec (untuk uji)

const JENIS = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css' };

http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/exec') {
    let isi = '';
    req.on('data', (c) => { isi += c; });
    req.on('end', () => {
      ctx.ST = new ctx.StoreSheet(ss);
      let out;
      try {
        const a = JSON.parse(isi || '{}');
        out = a.batch ? ctx.tanganiRombongan(a) : ctx.tangani(a);
      } catch (e) { out = { status: 500, body: { ok: false, error: 'gagal_server', message: String(e) } }; }
      HITUNG.panggilan += 1;
      // JEDA meniru biaya tetap Apps Script (±1–2 dtk per panggilan).
      setTimeout(() => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(out));
      }, JEDA);
    });
    return;
  }
  if (req.url === '/hitung') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(HITUNG));
  }
  let p = decodeURIComponent(req.url.split('?')[0]);
  if (p === '/') p = '/index.html';
  if (p === '/config.js') {
    res.writeHead(200, { 'Content-Type': 'application/javascript' });
    return res.end("window.FIN_MODE = 'gas';\nwindow.FIN_UI = 'android';\n");
  }
  const f = path.join(WEB, p);
  if (!f.startsWith(WEB) || !fs.existsSync(f) || !fs.statSync(f).isFile()) {
    res.writeHead(404); return res.end('404');
  }
  res.writeHead(200, { 'Content-Type': (JENIS[path.extname(f)] || 'text/plain') + '; charset=utf-8' });
  fs.createReadStream(f).pipe(res);
}).listen(PORT, '127.0.0.1', () => console.log('server uji mode gas: http://localhost:' + PORT));
