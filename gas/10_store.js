/**
 * Penyimpanan — satu tab Google Sheet per tabel SQLite lama.
 *
 * Baris 1 tiap tab = nama kolom. Kolom dibaca BERDASARKAN NAMA header, bukan
 * posisi, supaya menyisipkan/menggeser kolom di Sheet tidak membuat angka
 * tertukar diam-diam.
 *
 * Teks selalu ditulis dengan awalan apostrof ('). Tanpa itu Sheets mengubah
 * "2026-11-05" jadi tanggal, "0812..." jadi angka, dan catatan berawalan "="
 * jadi RUMUS. Apostrof tidak ikut terbaca kembali oleh getValues().
 *
 * Id: SQLite AUTOINCREMENT tidak pernah memakai ulang id yang sudah dihapus.
 * Itu ditiru dengan penghitung `SEQ_<tabel>` di Script Properties — kalau
 * memakai max(id)+1, transaksi baru bisa mewarisi id transaksi yang baru
 * dihapus, dan jejak di tab `terhapus`/`hutang_lunas` menunjuk ke baris yang
 * salah.
 */
var SKEMA = {
  accounts: { id: true, kolom: [['id', 'int'], ['name', 'text'], ['kind', 'text'],
    ['opening_balance', 'int'], ['is_active', 'int'], ['created_at', 'text']] },
  categories: { id: true, kolom: [['id', 'int'], ['name', 'text'], ['direction', 'text'],
    ['is_system', 'int'], ['sort_order', 'int']] },
  transactions: { id: true, kolom: [['id', 'int'], ['occurred_on', 'text'],
    ['direction', 'text'], ['amount', 'int'], ['account_id', 'int'],
    ['to_account_id', 'int'], ['category_id', 'int'], ['note', 'text'],
    ['flow_type', 'text'], ['source', 'text'], ['created_at', 'text']] },
  analyses: { id: true, kolom: [['id', 'int'], ['month', 'text'], ['dibuat_pada', 'text'],
    ['tx_terakhir', 'text'], ['narasi', 'text'], ['snapshot', 'text'],
    ['model', 'text'], ['catatan', 'text']] },
  savings_goals: { id: true, kolom: [['id', 'int'], ['name', 'text'],
    ['target_amount', 'int'], ['account_id', 'int'], ['target_date', 'text'],
    ['is_archived', 'int'], ['created_at', 'text']] },
  sesi: { id: false, kolom: [['token_hash', 'text'], ['dibuat_pada', 'num'],
    ['terakhir', 'num']] },
  jadwal_hutang: { id: false, kolom: [['nama_utang', 'text'], ['nomor', 'int'],
    ['nominal', 'int'], ['jatuh_tempo', 'text'], ['jatuh_tempo_teks', 'text']] },
  hutang_lunas: { id: false, kolom: [['nama_utang', 'text'], ['jatuh_tempo', 'text'],
    ['nomor', 'int'], ['nominal', 'int'], ['ditandai_pada', 'text'],
    ['transaksi_id', 'int'], ['transaksi_nominal', 'int'], ['transaksi_tanggal', 'text']] },
  terhapus: { id: false, kolom: [['dihapus_pada', 'text'], ['transaksi', 'text']] },
};

function _tipeKolom(tabel) {
  var t = {};
  SKEMA[tabel].kolom.forEach(function (k) { t[k[0]] = k[1]; });
  return t;
}

/** Nilai sel -> nilai JS. Sel kosong = null (Sheet tidak membedakan '' dan NULL). */
function _dariSel(v, tipe) {
  if (v === '' || v === null || v === undefined) return null;
  if (tipe === 'int' || tipe === 'num') {
    var n = Number(v);
    if (isNaN(n)) return null;
    return tipe === 'int' ? Math.trunc(n) : n;
  }
  if (v instanceof Date || Object.prototype.toString.call(v) === '[object Date]') {
    // Sel yang terlanjur jadi tanggal (diketik manual tanpa apostrof).
    var b = _bagianWaktu(v);
    return b.jam === '00:00:00' ? b.tanggal : b.tanggal + ' ' + b.jam;
  }
  return String(v);
}

function _keSel(v, tipe) {
  if (v === null || v === undefined) return '';
  if (tipe === 'int' || tipe === 'num') return Number(v);
  var s = String(v);
  return s === '' ? '' : "'" + s;
}

// ─────────────────────────────────────────────────────────────────────────────
// Implementasi dasar: semua logika tulis ada di sini, lapisan fisik
// (Sheet / memori) hanya menyediakan _muat, _tulisSemua, _tambahBaris.
// ─────────────────────────────────────────────────────────────────────────────
function StoreDasar() { this._cache = {}; }

StoreDasar.prototype.baca = function (tabel) {
  if (!this._cache[tabel]) this._cache[tabel] = this._muat(tabel);
  return this._cache[tabel];
};

StoreDasar.prototype._idBerikut = function (tabel) {
  var maks = 0;
  this.baca(tabel).forEach(function (r) { if (r.id > maks) maks = r.id; });
  var seq = Math.max(maks, this._bacaSeq(tabel));
  return seq + 1;
};

/** Tambah beberapa baris sekaligus. Mengembalikan id baru (tabel ber-id). */
StoreDasar.prototype.tambah = function (tabel, objs) {
  var ids = [];
  if (SKEMA[tabel].id) {
    var berikut = this._idBerikut(tabel);
    objs.forEach(function (o) { o.id = berikut++; ids.push(o.id); });
    this._tulisSeq(tabel, berikut - 1);
  }
  this._tambahBaris(tabel, objs);
  var c = this.baca(tabel);
  objs.forEach(function (o) { c.push(salin(o)); });
  return ids;
};

StoreDasar.prototype.ubah = function (tabel, id, obj) {
  var rows = this.baca(tabel);
  var i = rows.findIndex(function (r) { return r.id === id; });
  if (i < 0) throw new Error('baris ' + tabel + ' id ' + id + ' tidak ada');
  rows[i] = salin(obj);
  this._tulisBaris(tabel, i, rows[i]);
};

/** Ganti seluruh isi tabel (dipakai untuk hapus/arsip/rewrite). */
StoreDasar.prototype.gantiSemua = function (tabel, rows) {
  this._cache[tabel] = rows.map(salin);
  this._tulisSemua(tabel, this._cache[tabel]);
};

StoreDasar.prototype.hapusDimana = function (tabel, fn) {
  var rows = this.baca(tabel);
  var sisa = rows.filter(function (r) { return !fn(r); });
  var n = rows.length - sisa.length;
  if (n > 0) this.gantiSemua(tabel, sisa);
  return n;
};

// ── Memori (uji Node) ───────────────────────────────────────────────────────
function StoreMemori(data) {
  StoreDasar.call(this);
  this.data = data || {};
  this.seq = {};
}
StoreMemori.prototype = Object.create(StoreDasar.prototype);
StoreMemori.prototype._muat = function (t) { return salin(this.data[t] || []); };
StoreMemori.prototype._tambahBaris = function (t, objs) {
  this.data[t] = (this.data[t] || []).concat(salin(objs));
};
StoreMemori.prototype._tulisBaris = function (t, i, o) { this.data[t][i] = salin(o); };
StoreMemori.prototype._tulisSemua = function (t, rows) { this.data[t] = salin(rows); };
StoreMemori.prototype._bacaSeq = function (t) { return this.seq[t] || 0; };
StoreMemori.prototype._tulisSeq = function (t, n) { this.seq[t] = n; };

// ── Google Sheet ────────────────────────────────────────────────────────────
function StoreSheet(ss) {
  StoreDasar.call(this);
  this.ss = ss;
  this.props = PropertiesService.getScriptProperties();
}
StoreSheet.prototype = Object.create(StoreDasar.prototype);

StoreSheet.prototype._sheet = function (tabel) {
  var sh = this.ss.getSheetByName(tabel);
  if (!sh) {
    sh = this.ss.insertSheet(tabel);
    var nama = SKEMA[tabel].kolom.map(function (k) { return k[0]; });
    sh.getRange(1, 1, 1, nama.length).setValues([nama]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
};

/** Peta nama kolom -> indeks (0-based) dari header yang ADA di Sheet. */
StoreSheet.prototype._header = function (tabel) {
  var sh = this._sheet(tabel);
  var lebar = Math.max(sh.getLastColumn(), 1);
  var h = sh.getRange(1, 1, 1, lebar).getValues()[0].map(String);
  var kurang = SKEMA[tabel].kolom.map(function (k) { return k[0]; })
    .filter(function (n) { return h.indexOf(n) < 0; });
  if (kurang.length) {
    // Kolom baru di skema: tambahkan di kanan, data lama tidak tersentuh.
    sh.getRange(1, h.length + 1, 1, kurang.length).setValues([kurang]);
    h = h.concat(kurang);
  }
  return h;
};

StoreSheet.prototype._muat = function (tabel) {
  var sh = this._sheet(tabel);
  var h = this._header(tabel);
  var tipe = _tipeKolom(tabel);
  var n = sh.getLastRow() - 1;
  if (n <= 0) return [];
  var nilai = sh.getRange(2, 1, n, h.length).getValues();
  var hasil = [];
  nilai.forEach(function (baris) {
    if (baris.every(function (v) { return v === '' || v === null; })) return;
    var o = {};
    SKEMA[tabel].kolom.forEach(function (k) {
      o[k[0]] = _dariSel(baris[h.indexOf(k[0])], tipe[k[0]]);
    });
    hasil.push(o);
  });
  return hasil;
};

StoreSheet.prototype._keBaris = function (tabel, h, o) {
  var tipe = _tipeKolom(tabel);
  return h.map(function (nama) {
    return tipe[nama] ? _keSel(o[nama], tipe[nama]) : '';
  });
};

StoreSheet.prototype._tambahBaris = function (tabel, objs) {
  if (!objs.length) return;
  var sh = this._sheet(tabel);
  var h = this._header(tabel);
  var self = this;
  var data = objs.map(function (o) { return self._keBaris(tabel, h, o); });
  sh.getRange(sh.getLastRow() + 1, 1, data.length, h.length).setValues(data);
};

StoreSheet.prototype._tulisBaris = function (tabel, i, o) {
  // Baris di cache = urutan baris data di Sheet (baris kosong dilewati saat
  // muat), jadi cari baris fisik lewat kunci id, bukan indeks.
  var sh = this._sheet(tabel);
  var h = this._header(tabel);
  var kol = h.indexOf('id');
  var n = sh.getLastRow() - 1;
  var ids = sh.getRange(2, kol + 1, n, 1).getValues();
  for (var r = 0; r < ids.length; r++) {
    if (Number(ids[r][0]) === o.id) {
      sh.getRange(r + 2, 1, 1, h.length).setValues([this._keBaris(tabel, h, o)]);
      return;
    }
  }
  throw new Error('baris ' + tabel + ' id ' + o.id + ' tidak ditemukan di Sheet');
};

StoreSheet.prototype._tulisSemua = function (tabel, rows) {
  var sh = this._sheet(tabel);
  var h = this._header(tabel);
  var lama = sh.getLastRow() - 1;
  var self = this;
  var data = rows.map(function (o) { return self._keBaris(tabel, h, o); });
  if (data.length) sh.getRange(2, 1, data.length, h.length).setValues(data);
  if (lama > data.length) {
    sh.getRange(data.length + 2, 1, lama - data.length, h.length).clearContent();
  }
};

StoreSheet.prototype._bacaSeq = function (t) {
  return Number(this.props.getProperty('SEQ_' + t) || 0);
};
StoreSheet.prototype._tulisSeq = function (t, n) {
  this.props.setProperty('SEQ_' + t, String(n));
};

/** Spreadsheet yang dipakai: SPREADSHEET_ID di Script Properties, atau induk skrip. */
function bukaSpreadsheet() {
  var id = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  return id ? SpreadsheetApp.openById(id) : SpreadsheetApp.getActiveSpreadsheet();
}
