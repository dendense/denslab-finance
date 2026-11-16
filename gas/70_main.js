/**
 * Titik masuk Web App.
 *
 * Apps Script hanya punya doGet/doPost, tidak bisa membalas status HTTP selain
 * 200, dan tidak bisa memasang cookie. Jadi aplikasi mengirim SEMUA permintaan
 * sebagai POST berisi amplop:
 *
 *   {"method": "GET"|"POST"|"PATCH"|"DELETE", "path": "/api/summary",
 *    "query": "month=2026-11", "body": {...}, "token": "<sesi>"}
 *
 * dan menerima {"status": 200|401|404, "body": {...}}. web/backend.js
 * membuka amplop itu kembali jadi Response biasa, sehingga web/app.js tetap
 * memakai fetch('/api/...') persis seperti ke server Python.
 *
 * Content-Type permintaan `text/plain` disengaja: itu "simple request" CORS,
 * jadi browser tidak mengirim preflight OPTIONS yang tidak bisa dijawab
 * Apps Script.
 */
var PUBLIK_API = ['/api/auth'];

function doGet() {
  return _json({ status: 200, body: { ok: true, layanan: 'finance', pesan: 'API aktif. Pakai POST.' } });
}

function doPost(e) {
  var amplop;
  try { amplop = JSON.parse((e && e.postData && e.postData.contents) || '{}'); }
  catch (err) { return _json({ status: 400, body: { ok: false, error: 'json_rusak', message: 'Body bukan JSON valid.' } }); }
  ST = new StoreSheet(bukaSpreadsheet());
  return _json(amplop.batch ? tanganiRombongan(amplop) : tangani(amplop));
}

/**
 * Rombongan: beberapa amplop dalam SATU panggilan Web App.
 *
 * Kenapa: setiap panggilan Apps Script dikenai biaya tetap ±1–2 detik
 * (terukur 16 Nov 2026), dan refresh() panel mengambil 9–10 data berurutan
 * — 15–20 detik setelah tiap edit. Dalam rombongan, biaya tetap dibayar
 * sekali dan tiap tab Sheet dibaca sekali (ST dipakai bersama).
 *
 * Amplop dijalankan BERURUTAN dengan ST yang sama: tulis di depan (mis.
 * PATCH transaksi) sudah terlihat oleh baca di belakangnya, sama seperti
 * kalau dikirim satu per satu.
 */
var BATAS_ROMBONGAN = 25;

function tanganiRombongan(r) {
  var daftar = Array.isArray(r.batch) ? r.batch.slice(0, BATAS_ROMBONGAN) : [];
  return { status: 200, batch: daftar.map(function (a) {
    if (a && !a.token) a.token = r.token;
    try { return tangani(a || {}); }
    catch (e) {
      return { status: 200, body: { ok: false, error: 'gagal_server', message: String(e && e.message) } };
    }
  }) };
}

function _json(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function _parseQuery(q) {
  var p = {};
  String(q || '').split('&').forEach(function (bag) {
    if (!bag) return;
    var i = bag.indexOf('=');
    var k = decodeURIComponent((i < 0 ? bag : bag.slice(0, i)).replace(/\+/g, ' '));
    var v = i < 0 ? '' : decodeURIComponent(bag.slice(i + 1).replace(/\+/g, ' '));
    if (v === '') return;            // parse_qs membuang nilai kosong
    (p[k] = p[k] || []).push(v);
  });
  return p;
}

/** Jalankan fungsi tulis di bawah kunci skrip: dua HP menyimpan bersamaan
 *  tidak boleh menghasilkan id kembar atau baris tertimpa. */
function _dikunci(fn) {
  if (typeof LockService === 'undefined') return fn();
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try { return fn(); } finally { lock.releaseLock(); }
}

function _aman(fn) {
  try { return fn(); }
  catch (e) {
    console.error(e && e.stack ? e.stack : e);
    return { ok: false, error: 'gagal_server', message: 'Server gagal memproses permintaan (' +
      (e.name || 'Error') + ': ' + e.message + '). Lihat log eksekusi Apps Script.' };
  }
}

function tangani(a) {
  var method = String(a.method || 'GET').toUpperCase();
  var path = String(a.path || '');
  var params = _parseQuery(a.query);
  var body = a.body && typeof a.body === 'object' ? a.body : {};
  var ok = function (b) { return { status: 200, body: b }; };

  if (path.indexOf('/api/admin/') === 0) return _dikunci(function () { return api_admin(path, body); });

  if (path === '/api/auth' && method === 'GET') return ok(api_auth_status());
  if (path === '/api/auth' && method === 'POST') {
    return _dikunci(function () { return api_auth_login(body); });
  }
  if (PUBLIK_API.indexOf(path) < 0 && !sesi_sah(a.token)) {
    return { status: 401, body: { ok: false, error: 'belum_login', message: 'Sesi tidak berlaku. Masuk dulu.' } };
  }

  if (method === 'GET') {
    var rute = {
      '/api/summary': api_summary, '/api/transactions': api_transactions,
      '/api/categories': api_categories, '/api/accounts': api_accounts,
      '/api/trend': api_trend, '/api/spending-by-category': api_categories_spending,
      '/api/suggestions': api_suggestions, '/api/analysis': api_analysis,
      '/api/savings': api_savings, '/api/debts': api_debts, '/api/months': api_months,
      '/api/ai-status': api_ai_status, '/api/auth/status': api_auth_status_lengkap,
    };
    if (rute[path]) return ok(_aman(function () { return rute[path](params); }));
    return { status: 404, body: { error: 'tidak_ditemukan' } };
  }

  var tulis = function (fn) { return ok(_dikunci(function () { return _aman(fn); })); };
  var m;
  if (method === 'POST') {
    if (path === '/api/parse') return ok(_aman(function () { return api_parse(body); }));
    if (path === '/api/save') return tulis(function () { return api_save(body); });
    if (path === '/api/debts/batalkan') return tulis(function () { return api_debts_batalkan(body); });
    if (path === '/api/accounts') return tulis(function () { return api_account_create(body); });
    if (path === '/api/analysis') return tulis(function () { return api_analysis_create(body); });
    if (path === '/api/savings') return tulis(function () { return api_savings_set(body); });
    if (path === '/api/auth/keluar') {
      return ok(_dikunci(function () { akhiri_sesi(a.token); return { ok: true, keluar: true }; }));
    }
  } else if (method === 'PATCH') {
    if ((m = /^\/api\/accounts\/(\d+)$/.exec(path))) {
      return tulis(function () { return api_account_patch(parseInt(m[1], 10), body); });
    }
    if ((m = /^\/api\/transactions\/(\d+)$/.exec(path))) {
      return tulis(function () { return api_transaction_patch(parseInt(m[1], 10), body); });
    }
  } else if (method === 'DELETE') {
    if ((m = /^\/api\/transactions\/(\d+)$/.exec(path))) {
      return tulis(function () { return api_transaction_delete(parseInt(m[1], 10)); });
    }
    if ((m = /^\/api\/analysis\/(\d{4}-\d{2})$/.exec(path))) {
      return tulis(function () { return api_analysis_delete(m[1]); });
    }
    if (path === '/api/savings') return tulis(function () { return api_savings_delete(); });
  }
  return { status: 404, body: { ok: false, error: 'tidak_ditemukan' } };
}
