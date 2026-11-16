/**
 * Pemasangan, impor dari SQLite, dan backup.
 *
 * Alur pertama kali (lihat docs/ANDROID-GSHEET.md):
 *   1. Jalankan `siapkan()` sekali dari editor Apps Script. Ia membuat tab,
 *      mengisi 11 kategori bawaan, membuat ADMIN_TOKEN, dan memasang
 *      backup mingguan. Token dicetak di log eksekusi.
 *   2. Deploy sebagai Web App.
 *   3. Di Mac: `python3 scripts/migrasi_ke_gsheet.py --url <URL> --token <ADMIN_TOKEN>`
 *      memindahkan isi finance.db + jadwal hutang, dan memasang password.
 *
 * Endpoint /api/admin/* hanya menerima ADMIN_TOKEN. Token itu tidak pernah
 * disimpan di aplikasi Android.
 */
var KATEGORI_BAWAAN = [
  ['Makan', 'out', 10], ['Transport', 'out', 20], ['Belanja', 'out', 30], ['Hiburan', 'out', 40],
  ['Tagihan', 'out', 50], ['Kesehatan', 'out', 60], ['Pendidikan', 'out', 70], ['Lainnya', 'out', 80],
  ['Gaji', 'in', 10], ['Bonus', 'in', 20], ['Lainnya', 'in', 30]];

var URUTAN_TABEL = ['accounts', 'categories', 'transactions', 'analyses', 'savings_goals',
  'jadwal_hutang', 'hutang_lunas', 'terhapus', 'sesi'];

function isiKategoriBawaan() {
  var ada = {};
  ST.baca('categories').forEach(function (c) { ada[c.name + '|' + c.direction] = true; });
  var baru = KATEGORI_BAWAAN.filter(function (k) { return !ada[k[0] + '|' + k[1]]; })
    .map(function (k) { return { name: k[0], direction: k[1], is_system: 1, sort_order: k[2] }; });
  if (baru.length) ST.tambah('categories', baru);
  return baru.length;
}

/** Jalankan SEKALI dari editor Apps Script. Aman diulang. */
function siapkan() {
  ST = new StoreSheet(bukaSpreadsheet());
  URUTAN_TABEL.forEach(function (t) { ST.baca(t); });   // membuat tab yang belum ada
  var n = isiKategoriBawaan();
  var props = PropertiesService.getScriptProperties();
  var token = props.getProperty('ADMIN_TOKEN');
  if (!token) {
    token = _acak();
    props.setProperty('ADMIN_TOKEN', token);
  }
  var pemicu = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === 'backupMingguan';
  });
  if (!pemicu) {
    ScriptApp.newTrigger('backupMingguan').timeBased().onWeekDay(ScriptApp.WeekDay.MONDAY)
      .atHour(3).create();
  }
  var ss = bukaSpreadsheet();
  var lembar1 = ss.getSheetByName('Sheet1') || ss.getSheetByName('Lembar1');
  if (lembar1 && ss.getSheets().length > 1 && lembar1.getLastRow() === 0) ss.deleteSheet(lembar1);
  console.log('Siap. Kategori bawaan ditambahkan: ' + n);
  console.log('ADMIN_TOKEN (simpan, dipakai skrip migrasi): ' + token);
  console.log('Belum ada KENARI_API_KEY? Isi di Project Settings > Script Properties.');
  return token;
}

/** Salinan penuh spreadsheet tiap Senin 03:00. Riwayat versi Sheets tetap ada di luar ini. */
function backupMingguan() {
  var ss = bukaSpreadsheet();
  ss.copy(ss.getName() + ' — backup ' + hariIni());
}

function api_admin(path, body) {
  var token = PropertiesService.getScriptProperties().getProperty('ADMIN_TOKEN');
  if (!token || !body.admin_token || !_samaPersis(String(body.admin_token), token)) {
    return { status: 401, body: { ok: false, error: 'admin_ditolak', message: 'ADMIN_TOKEN salah atau belum dibuat (jalankan siapkan()).' } };
  }
  if (path === '/api/admin/password') {
    try { pasang_password(body.password); }
    catch (e) { return { status: 200, body: { ok: false, error: 'password_tidak_sah', message: e.message } }; }
    return { status: 200, body: { ok: true, dipasang: true } };
  }
  if (path === '/api/admin/status') {
    var hitung = {};
    URUTAN_TABEL.forEach(function (t) { if (t !== 'sesi') hitung[t] = ST.baca(t).length; });
    return { status: 200, body: { ok: true, jumlah: hitung, sudah_ada_password: sudah_ada_password() } };
  }
  if (path === '/api/admin/impor') return { status: 200, body: api_admin_impor(body) };
  return { status: 404, body: { ok: false, error: 'tidak_ditemukan' } };
}

/**
 * Ganti isi tabel dengan data dari SQLite. Menolak kalau tab `transactions`
 * sudah berisi, kecuali `timpa: true` — impor ulang yang tidak sengaja akan
 * menghapus transaksi yang dicatat dari HP sejak impor pertama.
 */
function api_admin_impor(body) {
  var data = body.data || {};
  if (ST.baca('transactions').length && !body.timpa) {
    return { ok: false, error: 'sudah_berisi', message: 'Tab transactions sudah berisi ' +
      ST.baca('transactions').length + ' baris. Kirim timpa=true kalau memang mau menimpa.' };
  }
  var hasil = {};
  URUTAN_TABEL.forEach(function (t) {
    if (t === 'sesi' || !(t in data)) return;
    var cols = SKEMA[t].kolom.map(function (k) { return k[0]; });
    var rows = (data[t] || []).map(function (r) {
      var o = {};
      cols.forEach(function (c) { o[c] = r[c] === undefined ? null : r[c]; });
      return o;
    });
    ST.gantiSemua(t, rows);
    hasil[t] = rows.length;
  });
  var seq = body.seq || {};
  Object.keys(seq).forEach(function (t) {
    if (SKEMA[t] && SKEMA[t].id) ST._tulisSeq(t, Number(seq[t]) || 0);
  });
  isiKategoriBawaan();
  return { ok: true, diimpor: hasil };
}
