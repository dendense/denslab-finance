/**
 * Utilitas bersama backend Apps Script finance.
 *
 * Semua berkas di folder `gas/` berbagi satu ruang nama global (aturan Apps
 * Script: tidak ada modul). Uji di `tests/gas/` memuat berkas yang sama ke
 * `vm` Node dengan tiruan `Utilities`/`SpreadsheetApp`, jadi kode di sini
 * TIDAK boleh mengandalkan apa pun yang hanya ada di salah satu lingkungan
 * tanpa jalan cadangan.
 *
 * Zona waktu: Asia/Jakarta, sama dengan Mac tempat server Python berjalan.
 * "Hari ini" yang beda zona akan menggeser transaksi tengah malam ke bulan
 * lain — angka bulanan bergeser tanpa error.
 */
var ZONA = 'Asia/Jakarta';

function _bagianWaktu(d) {
  d = d || new Date();
  if (typeof Utilities !== 'undefined' && Utilities.formatDate) {
    var s = Utilities.formatDate(d, ZONA, 'yyyy-MM-dd HH:mm:ss');
    return { tanggal: s.slice(0, 10), jam: s.slice(11) };
  }
  var f = new Intl.DateTimeFormat('en-CA', {
    timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
  }).formatToParts(d);
  var p = {};
  f.forEach(function (x) { p[x.type] = x.value; });
  return { tanggal: p.year + '-' + p.month + '-' + p.day,
           jam: p.hour + ':' + p.minute + ':' + p.second };
}

/** 'YYYY-MM-DD' hari ini (Asia/Jakarta). Uji boleh menimpa `HARI_INI_UJI`. */
function hariIni() {
  if (typeof HARI_INI_UJI !== 'undefined' && HARI_INI_UJI) return HARI_INI_UJI;
  return _bagianWaktu().tanggal;
}

/** 'YYYY-MM-DD HH:MM:SS' — bentuk sama dengan datetime('now','localtime') SQLite. */
function sekarangTeks() {
  var b = _bagianWaktu();
  return b.tanggal + ' ' + b.jam;
}

/** ISO tanpa mikrodetik, seperti datetime.now().replace(microsecond=0).isoformat(). */
function sekarangIso() {
  var b = _bagianWaktu();
  return b.tanggal + 'T' + b.jam;
}

function bulanBerjalan() { return hariIni().slice(0, 7); }

function pad2(n) { return (n < 10 ? '0' : '') + n; }
function pad4(n) { var s = String(n); while (s.length < 4) s = '0' + s; return s; }

function bulanSebelum(month) {
  var y = parseInt(month.slice(0, 4), 10), m = parseInt(month.slice(5, 7), 10) - 1;
  if (m === 0) { m = 12; y -= 1; }
  return pad4(y) + '-' + pad2(m);
}

function bulanSesudah(month) {
  var y = parseInt(month.slice(0, 4), 10), m = parseInt(month.slice(5, 7), 10) + 1;
  if (m === 13) { m = 1; y += 1; }
  return pad4(y) + '-' + pad2(m);
}

function jumlahHari(y, m) { return new Date(Date.UTC(y, m, 0)).getUTCDate(); }

function akhirBulan(month) {
  var y = parseInt(month.slice(0, 4), 10), m = parseInt(month.slice(5, 7), 10);
  return pad4(y) + '-' + pad2(m) + '-' + pad2(jumlahHari(y, m));
}

/** Sama dengan date.fromisoformat untuk bentuk YYYY-MM-DD: format DAN tanggal nyata. */
function tanggalSah(s) {
  var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s));
  if (!m) return false;
  var y = +m[1], bl = +m[2], h = +m[3];
  return bl >= 1 && bl <= 12 && h >= 1 && h <= jumlahHari(y, bl);
}

var NAMA_BULAN = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'];

function namaBulan(month) {
  return NAMA_BULAN[parseInt(month.slice(5, 7), 10) - 1] + ' ' + month.slice(0, 4);
}

/** 'Rp 1.100.000' — sama dengan db.rupiah(). */
function rupiah(n) {
  var v = Number(n);
  if (n === null || n === undefined || n === '' || isNaN(v)) return 'Rp ?';
  v = pyRound(v);
  var neg = v < 0;
  var s = String(Math.abs(v)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return 'Rp ' + (neg ? '-' : '') + s;
}

/** round() Python: setengah ke genap (banker's rounding). */
function pyRound(x) {
  var r = Math.round(x);
  if (Math.abs(x % 1) === 0.5) r = 2 * Math.round(x / 2);
  return r === 0 ? 0 : r;   // buang -0
}

/** ROUND() SQLite: setengah menjauhi nol. */
function sqlRound(x) {
  return x < 0 ? -Math.round(-x) : Math.round(x);
}

/** int(round(float(x))) Python — melempar kalau bukan angka. */
function bulatRupiah(x) {
  if (typeof x === 'boolean' || x === null || x === undefined) throw new Error('bukan angka');
  var v = typeof x === 'number' ? x : Number(String(x).trim());
  if (String(x).trim() === '' || !isFinite(v)) throw new Error('bukan angka');
  return pyRound(v);
}

/** int(x) Python: angka dipotong, teks harus bilangan bulat. */
function pyInt(x) {
  if (typeof x === 'number') {
    if (!isFinite(x)) throw new Error('cannot convert float to integer');
    return Math.trunc(x);
  }
  if (typeof x === 'boolean') return x ? 1 : 0;
  var s = String(x).trim();
  if (!/^[+-]?\d+$/.test(s)) throw new Error("invalid literal for int() with base 10: '" + x + "'");
  return parseInt(s, 10);
}

/** Pembagian lantai Python (`//`). */
function floorDiv(a, b) { return Math.floor(a / b); }

/** Perbandingan teks biner seperti SQLite/Python (bukan localeCompare). */
function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

function benar(x) {
  // Truthiness ala Python untuk nilai dari JSON.
  if (x === null || x === undefined || x === false || x === 0 || x === '') return false;
  if (Array.isArray(x)) return x.length > 0;
  if (typeof x === 'object') return Object.keys(x).length > 0;
  return true;
}

function salin(o) { return JSON.parse(JSON.stringify(o)); }

/** Galat yang pesannya aman ditampilkan (setara ValueError di db.py). */
function GalatNilai(pesan) {
  var e = new Error(pesan);
  e.nilai = true;
  return e;
}
