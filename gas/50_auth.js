/**
 * Port src/auth.py — password + sesi, untuk Web App yang TERBUKA di internet.
 *
 * Bedanya dengan versi Mac:
 *   - Tidak ada cookie (Web App Apps Script tidak bisa memasang cookie ke
 *     aplikasi). Token dikirim di badan permintaan; aplikasi menyimpannya di
 *     localStorage.
 *   - Tidak ada boot UUID. Sesi berakhir setelah 30 hari atau saat keluar.
 *   - Password TIDAK bisa dipasang lewat halaman login. Di Mac, "pemasang
 *     pertama menang" aman karena server hanya mendengar 127.0.0.1; di
 *     internet itu berarti siapa pun yang menemukan URL lebih dulu bisa
 *     mengunci Deny keluar. Password dipasang lewat endpoint admin yang butuh
 *     ADMIN_TOKEN (lihat scripts/migrasi_ke_gsheet.py).
 *   - Salah password berulang dikunci sementara (10x / 15 menit).
 *
 * Hash: SHA-256 bergaram, diulang ITERASI kali. PBKDF2 200.000 iterasi versi
 * Mac terlalu lambat untuk Apps Script (tiap panggilan Utilities mahal).
 */
var BATAS_UMUR_DETIK = 30 * 24 * 60 * 60;
var PANJANG_MIN_PASSWORD = 6;
var ITERASI = 3000;
var BATAS_GAGAL = 10;
var JENDELA_GAGAL_DETIK = 15 * 60;

function _sha256Hex(s) {
  if (typeof SHA256_UJI !== 'undefined' && SHA256_UJI) return SHA256_UJI(s);
  var b = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, s, Utilities.Charset.UTF_8);
  return b.map(function (x) { return ((x + 256) % 256).toString(16); })
    .map(function (h) { return h.length === 1 ? '0' + h : h; }).join('');
}

function _acak() {
  if (typeof ACAK_UJI !== 'undefined' && ACAK_UJI) return ACAK_UJI();
  return (Utilities.getUuid() + Utilities.getUuid()).replace(/-/g, '');
}

function _cache() {
  return typeof CacheService !== 'undefined' ? CacheService.getScriptCache() : null;
}

function _setProp(nama, nilai) {
  if (typeof KONFIG_UJI !== 'undefined' && KONFIG_UJI) { KONFIG_UJI[nama] = nilai; return; }
  PropertiesService.getScriptProperties().setProperty(nama, nilai);
}

function _hashPassword(password, salt, iterasi) {
  var h = _sha256Hex(salt + ':' + password);
  for (var i = 0; i < iterasi; i++) h = _sha256Hex(h + salt);
  return h;
}

function _samaPersis(a, b) {
  if (a.length !== b.length) return false;
  var beda = 0;
  for (var i = 0; i < a.length; i++) beda |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return beda === 0;
}

function _kredensial() {
  var s = _prop('KREDENSIAL');
  if (!s) return null;
  try { return JSON.parse(s); } catch (e) { return null; }
}

function sudah_ada_password() { return !!_kredensial(); }

function pasang_password(password) {
  if (!password || String(password).length < PANJANG_MIN_PASSWORD) {
    throw GalatNilai('password minimal ' + PANJANG_MIN_PASSWORD + ' karakter');
  }
  var salt = _acak().slice(0, 32);
  _setProp('KREDENSIAL', JSON.stringify({ algo: 'sha256_ulang', iterasi: ITERASI, salt: salt,
    hash: _hashPassword(String(password), salt, ITERASI) }));
  akhiri_semua_sesi();
}

function cek_password(password) {
  var k = _kredensial();
  if (!k || !password) return false;
  return _samaPersis(_hashPassword(String(password), k.salt, k.iterasi), k.hash);
}

// ── pembatas tebakan ────────────────────────────────────────────────────────
function _gagalTerlalu() {
  var c = _cache();
  return c ? Number(c.get('login_gagal') || 0) >= BATAS_GAGAL : false;
}
function _catatGagal() {
  var c = _cache();
  if (c) c.put('login_gagal', String(Number(c.get('login_gagal') || 0) + 1), JENDELA_GAGAL_DETIK);
}

// ── sesi ────────────────────────────────────────────────────────────────────
function _hashToken(t) { return _sha256Hex(String(t || '')); }
function _detik() { return Date.now() / 1000; }

function buat_sesi() {
  var token = _acak();
  _bersihkanSesi();
  ST.tambah('sesi', [{ token_hash: _hashToken(token), dibuat_pada: _detik(), terakhir: _detik() }]);
  return token;
}

function sesi_sah(token) {
  if (!token) return false;
  var kunci = _hashToken(token);
  var c = _cache();
  if (c && c.get('sesi_' + kunci)) return true;
  var baris = ST.baca('sesi').filter(function (s) { return s.token_hash === kunci; })[0];
  if (!baris) return false;
  if (_detik() - Number(baris.dibuat_pada) > BATAS_UMUR_DETIK) {
    ST.hapusDimana('sesi', function (s) { return s.token_hash === kunci; });
    return false;
  }
  if (c) c.put('sesi_' + kunci, '1', 600);   // 10 menit; keluar menghapusnya
  return true;
}

function akhiri_sesi(token) {
  if (!token) return false;
  var kunci = _hashToken(token);
  var c = _cache();
  if (c) c.remove('sesi_' + kunci);
  return ST.hapusDimana('sesi', function (s) { return s.token_hash === kunci; }) > 0;
}

function akhiri_semua_sesi() {
  var c = _cache();
  if (c) ST.baca('sesi').forEach(function (s) { c.remove('sesi_' + s.token_hash); });
  return ST.hapusDimana('sesi', function () { return true; });
}

function jumlah_sesi() { _bersihkanSesi(); return ST.baca('sesi').length; }

function _bersihkanSesi() {
  var batas = _detik() - BATAS_UMUR_DETIK;
  ST.hapusDimana('sesi', function (s) { return Number(s.dibuat_pada) < batas; });
}

// ── endpoint auth ───────────────────────────────────────────────────────────
function api_auth_status() {
  return { sudah_ada_password: sudah_ada_password(), panjang_min_password: PANJANG_MIN_PASSWORD };
}

function api_auth_status_lengkap() {
  return { sudah_ada_password: sudah_ada_password(), jumlah_sesi: jumlah_sesi(),
    umur_sesi_jam: BATAS_UMUR_DETIK / 3600,
    catatan: 'Sesi bertahan walau app ditutup — berakhir saat kamu keluar atau setelah ' +
      (BATAS_UMUR_DETIK / 86400) + ' hari.',
    python_di_bawah_rekomendasi: false };
}

/** Login. Mengembalikan {status, body}; token ikut di body kalau berhasil. */
function api_auth_login(body) {
  if (!sudah_ada_password()) {
    return { status: 401, body: { ok: false, error: 'password_belum_dipasang',
      message: 'Password belum dipasang di server. Pasang dulu lewat ' +
        'scripts/migrasi_ke_gsheet.py --password (butuh ADMIN_TOKEN).' } };
  }
  if (_gagalTerlalu()) {
    return { status: 401, body: { ok: false, error: 'terlalu_banyak_gagal',
      message: 'Terlalu banyak percobaan gagal. Tunggu 15 menit lalu coba lagi.' } };
  }
  if (!cek_password(body.password || '')) {
    _catatGagal();
    return { status: 401, body: { ok: false, error: 'password_salah', message: 'Password salah.' } };
  }
  return { status: 200, body: { ok: true, masuk: true, token: buat_sesi() } };
}
