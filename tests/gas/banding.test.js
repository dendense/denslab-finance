/**
 * Backend Apps Script vs server Python: balasan HARUS sama.
 *
 *   python3 tests/gas/golden.py <salinan-data> <golden.json>
 *   GOLDEN=<golden.json> node --test tests/gas/*.test.js
 *
 * Kasus diputar ulang berurutan ke `tangani()` (router 70_main.js), dua kali:
 *   1. StoreMemori — logika murni
 *   2. StoreSheet di atas tiruan Google Sheet yang meniru konversi otomatis
 *      Sheets (teks -> angka/tanggal/rumus), diisi lewat endpoint impor admin
 *      — jalur yang sama dengan migrasi sungguhan.
 *
 * Yang sengaja tidak dibandingkan: stempel waktu (beda detik antar dua
 * proses), latensi, dan dua teks yang memang berubah (lokasi jejak hapus &
 * sumber jadwal hutang).
 */
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const { muat } = require('./muat');
const { SpreadsheetPalsu, propertiesPalsu } = require('./sheet_palsu');

const BERKAS = process.env.GOLDEN;
const ABAIKAN = new Set(['created_at', 'dibuat_pada', 'ditandai_pada', 'lunas_pada',
  'dihapus_pada', 'tx_terakhir', 'latensi_ms', 'pemulihan', 'sumber', 'narasi_basi']);

function normal(x) {
  if (Array.isArray(x)) return x.map(normal);
  if (x && typeof x === 'object') {
    const o = {};
    Object.keys(x).sort().forEach((k) => { o[k] = ABAIKAN.has(k) ? '<diabaikan>' : normal(x[k]); });
    return o;
  }
  return x === '' ? null : x;
}

function siapkanCtx(g) {
  const ai = g.ai_palsu;
  return muat({
    hariIni: g.hari_ini,
    http: (url, body) => {
      if (body.max_tokens === 5) return { code: 200, text: ai.status };
      if (body.messages[0].content.indexOf('Kamu parser') === 0) {
        return { code: 200, text: ai.parser[body.messages[1].content] };
      }
      return { code: 200, text: ai.analisa };
    },
  });
}

function putarUlang(g, ctx, storeBaru) {
  ctx.ST = storeBaru();
  ctx.pasang_password('rahasia-uji');
  const masuk = ctx.tangani({ method: 'POST', path: '/api/auth', body: { password: 'rahasia-uji' } });
  assert.strictEqual(masuk.status, 200);
  const token = masuk.body.token;
  const tolak = ctx.tangani({ method: 'GET', path: '/api/summary', token: 'salah' });
  assert.strictEqual(tolak.status, 401);

  const beda = [];
  g.kasus.forEach((k, i) => {
    ctx.ST = storeBaru();   // store baru per permintaan, seperti doPost
    const r = ctx.tangani({ method: k.method, path: k.path, query: k.query, body: k.body, token });
    const js = normal(JSON.parse(JSON.stringify(r.body)));
    try {
      assert.strictEqual(r.status, k.status, 'status');
      assert.deepStrictEqual(js, normal(k.hasil));
    } catch (e) {
      beda.push('#' + i + ' ' + k.method + ' ' + k.path + (k.query ? '?' + k.query : '') +
        ' ' + JSON.stringify(k.body || '') + '\n' + e.message.split('\n').slice(0, 40).join('\n'));
    }
  });
  if (beda.length) {
    assert.fail(beda.length + '/' + g.kasus.length + ' kasus berbeda:\n\n' + beda.slice(0, 6).join('\n\n'));
  }
}

const lewati = !BERKAS && 'set GOLDEN=<golden.json>';

test('StoreMemori: backend Apps Script = server Python', { skip: lewati }, () => {
  const g = JSON.parse(fs.readFileSync(BERKAS, 'utf8'));
  const ctx = siapkanCtx(g);
  const data = JSON.parse(JSON.stringify(g.ekspor.data));
  const seq = Object.assign({}, g.ekspor.seq);
  putarUlang(g, ctx, () => { const s = new ctx.StoreMemori(data); s.seq = seq; return s; });
});

test('Rombongan: kasus dikirim berkelompok (tulis lalu baca) tetap = server Python', { skip: lewati }, () => {
  const g = JSON.parse(fs.readFileSync(BERKAS, 'utf8'));
  const ctx = siapkanCtx(g);
  ctx.PropertiesService = propertiesPalsu();
  const ss = new SpreadsheetPalsu();
  ctx.ST = new ctx.StoreSheet(ss);
  ctx.api_admin_impor({ data: g.ekspor.data, seq: g.ekspor.seq });
  ctx.pasang_password('rahasia-uji');
  const token = ctx.tangani({ method: 'POST', path: '/api/auth', body: { password: 'rahasia-uji' } }).body.token;

  // Kelompok 7 kasus berturut-turut per rombongan; satu StoreSheet per
  // rombongan (seperti satu doPost). Tulis di depan harus terlihat oleh baca
  // di belakangnya dalam rombongan yang sama.
  const beda = [];
  for (let i = 0; i < g.kasus.length; i += 7) {
    const kelompok = g.kasus.slice(i, i + 7);
    ctx.ST = new ctx.StoreSheet(ss);
    const r = ctx.tanganiRombongan({ token, batch: kelompok.map((k) => ({
      method: k.method, path: k.path, query: k.query, body: k.body })) });
    kelompok.forEach((k, j) => {
      const h = r.batch[j];
      try {
        assert.strictEqual(h.status, k.status, 'status');
        assert.deepStrictEqual(normal(JSON.parse(JSON.stringify(h.body))), normal(k.hasil));
      } catch (e) {
        beda.push('#' + (i + j) + ' ' + k.method + ' ' + k.path + '\n' + e.message.split('\n').slice(0, 20).join('\n'));
      }
    });
  }
  if (beda.length) assert.fail(beda.length + ' kasus berbeda dalam rombongan:\n\n' + beda.slice(0, 4).join('\n\n'));
  // Batas ukuran rombongan dihormati.
  ctx.ST = new ctx.StoreSheet(ss);
  const besar = ctx.tanganiRombongan({ token, batch: Array(40).fill({ method: 'GET', path: '/api/categories' }) });
  assert.strictEqual(besar.batch.length, ctx.BATAS_ROMBONGAN);
});

test('StoreSheet (tiruan Sheets): impor + semua kasus = server Python', { skip: lewati }, () => {
  const g = JSON.parse(fs.readFileSync(BERKAS, 'utf8'));
  const ctx = siapkanCtx(g);
  ctx.PropertiesService = propertiesPalsu();
  const ss = new SpreadsheetPalsu();
  ctx.ST = new ctx.StoreSheet(ss);
  const imp = ctx.api_admin_impor({ data: g.ekspor.data, seq: g.ekspor.seq });
  assert.ok(imp.ok, JSON.stringify(imp));
  // Impor kedua tanpa `timpa` harus ditolak: transaksi dari HP tidak boleh hilang.
  ctx.ST = new ctx.StoreSheet(ss);
  assert.strictEqual(ctx.api_admin_impor({ data: g.ekspor.data }).error, 'sudah_berisi');
  // Tidak ada sel yang terbaca sebagai rumus atau berubah jadi tanggal/angka diam-diam.
  Object.values(ss.lembar).forEach((sh) => sh.grid.forEach((row) => row.forEach((v) => {
    assert.notStrictEqual(v, '#RUMUS', 'sel jadi rumus di tab ' + sh.nama);
    assert.ok(!(v instanceof Date), 'sel jadi Date di tab ' + sh.nama);
  })));
  putarUlang(g, ctx, () => new ctx.StoreSheet(ss));
});
