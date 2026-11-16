/* Jembatan backend — dimuat SEBELUM app.js dan di login.html.
 *
 * Mode 'lokal' (server Python): berkas ini tidak mengubah apa pun selain
 * menyediakan window.FIN untuk alamat halaman.
 *
 * Mode 'gas' (aplikasi Android): setiap fetch('/api/...') dibungkus jadi
 * amplop POST ke Web App Apps Script, lalu balasannya dibuka kembali jadi
 * Response biasa dengan status aslinya (200/401/404). Akibatnya app.js tetap
 * memakai fetch('/api/...') persis seperti ke server Python — tidak ada dua
 * jalur kode untuk satu fitur.
 *
 * Kenapa Content-Type text/plain: itu "simple request" CORS, jadi browser
 * tidak mengirim preflight OPTIONS (Apps Script tidak bisa menjawabnya).
 *
 * Token sesi disimpan di localStorage perangkat. Apps Script tidak bisa
 * memasang cookie, dan sesi harus bertahan walau aplikasi ditutup.
 */
(function () {
  'use strict';
  var MODE = window.FIN_MODE === 'gas' ? 'gas' : 'lokal';

  /* Tampilan Android: dipasang SEDINI mungkin (berkas ini dimuat di <head>)
     supaya tidak ada kedipan tampilan web sebelum bingkai Android muncul. */
  if (window.FIN_UI === 'android') {
    document.documentElement.classList.add('ui-android');
    var css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = '/android.css';
    document.head.appendChild(css);
    if (!document.querySelector('meta[name="theme-color"]')) {
      var meta = document.createElement('meta');
      meta.name = 'theme-color';
      meta.content = '#fbf8ff';
      document.head.appendChild(meta);
    }
  }
  var K_ALAMAT = 'fin_alamat_gas';
  var K_TOKEN = 'fin_token';

  function ambil(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function taruh(k, v) {
    try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* privat */ }
  }

  /* Hanya Web App Apps Script — atau server uji di perangkat itu sendiri
     (tests/gas/server_dev.js). Alamat lain ditolak supaya password tidak
     pernah terkirim ke server yang salah ketik. */
  function alamatSah(u) {
    u = String(u || '').trim();
    return /^https:\/\/script\.google\.com\/macros\/s\/[A-Za-z0-9_-]+\/exec$/.test(u) ||
      /^http:\/\/(localhost|127\.0\.0\.1):\d+\/exec$/.test(u);
  }

  window.FIN = {
    mode: MODE,
    halamanLogin: MODE === 'gas' ? '/login.html' : '/login',
    halamanPanel: MODE === 'gas' ? '/index.html' : '/',
    alamat: function () { return ambil(K_ALAMAT); },
    alamatSah: alamatSah,
    pasangAlamat: function (u) {
      u = String(u || '').trim();
      if (!alamatSah(u)) return false;
      if (u !== ambil(K_ALAMAT)) taruh(K_TOKEN, null);   // server lain = sesi lain
      taruh(K_ALAMAT, u);
      return true;
    },
  };

  if (MODE !== 'gas') return;

  var fetchAsli = window.fetch.bind(window);

  function balas(status, obj) {
    return new Response(JSON.stringify(obj), {
      status: status, headers: { 'Content-Type': 'application/json; charset=utf-8' } });
  }

  /* ── Rombongan ────────────────────────────────────────────────────────────
   * Setiap panggilan Apps Script kena biaya tetap ±1–2 detik, dan refresh()
   * di app.js mengambil 9–10 data BERURUTAN setelah tiap simpan/edit/hapus
   * (terukur: 15–20 detik). Jadi jumlah panggilan yang harus dikurangi.
   *
   * Caranya tanpa daftar URL yang ditulis tangan: berkas ini MENCATAT data
   * apa saja yang diminta tepat setelah sebuah aksi ("pemicu" — mis. PATCH
   * transaksi, atau GET pertama setelah layar sunyi). Lain kali pemicu yang
   * sama terjadi, pemicu + semua data lanjutannya dikirim sebagai SATU
   * rombongan; server menjalankannya berurutan (tulis dulu, baru baca), dan
   * hasilnya disimpan sebentar sampai app.js memintanya satu per satu.
   *
   * Aturan keamanan data:
   *   - Hasil simpanan hanya dipakai ≤15 detik, dan langsung dibuang kalau ada
   *     tulis lain (POST/PATCH/DELETE) — tidak pernah menampilkan angka basi.
   *   - Rombongan gagal (jaringan, server lama) -> jatuh ke panggilan biasa.
   */
  var K_POLA = 'fin_pola_v1';
  var JEDA = 1500;          // ms sunyi sebelum GET dianggap pemicu baru
  var UMUR_SIAP = 15000;    // ms hasil rombongan boleh dipakai
  var TIDAK_DIREKAM = /^\/api\/(auth|ai-status|parse)/;
  var pola = {};
  try { pola = JSON.parse(ambil(K_POLA) || '{}') || {}; } catch (e) { pola = {}; }
  var rekam = null;         // {kunci, M, urls: []}
  var aktivitas = 0;        // waktu mulai/selesai terakhir permintaan /api
  var siap = {};            // url -> {janji, sampai}
  var rombonganMati = false;

  function bulanDari(q) {
    var m = /(?:^|&)month=(\d{4}-\d{2})(?:&|$)/.exec(q || '');
    if (m) return m[1];
    try { return (typeof state !== 'undefined' && state && state.month) || null; } catch (e) { return null; }
  }
  function bulanLalu(M) {
    var y = +M.slice(0, 4), m = +M.slice(5, 7) - 1;
    if (m === 0) { m = 12; y -= 1; }
    return y + '-' + (m < 10 ? '0' : '') + m;
  }
  /* URL -> pola: bulan aktif jadi {M}, bulan sebelumnya {M-1}, id jadi {id}. */
  function cetak(url, M) {
    var t = url.replace(/\/\d+(?=\/|\?|$)/g, '/{id}');
    if (M) t = t.split('month=' + M).join('month={M}').split('month=' + bulanLalu(M)).join('month={M-1}');
    return t;
  }
  function isi(t, M) {
    if (/\{(M|M-1)\}/.test(t) && !M) return null;
    if (t.indexOf('{id}') >= 0) return null;
    return M ? t.split('{M-1}').join(bulanLalu(M)).split('{M}').join(M) : t;
  }
  function simpanPola() {
    var kunci = Object.keys(pola);
    if (kunci.length > 40) delete pola[kunci[0]];
    taruh(K_POLA, JSON.stringify(pola));
  }
  function catat(url) {
    if (!rekam || TIDAK_DIREKAM.test(url)) return;
    var t = cetak(url, rekam.M);
    if (rekam.urls.indexOf(t) < 0 && rekam.urls.length < 15) {
      rekam.urls.push(t);
      pola[rekam.kunci] = rekam.urls.slice();
      simpanPola();
    }
  }

  function kirim(alamat, muatan) {
    return fetchAsli(alamat, {
      method: 'POST', redirect: 'follow', cache: 'no-store',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(muatan),
    }).then(function (r) { return r.text().then(function (t) { return { r: r, t: t }; }); })
      .then(function (x) {
        try { return JSON.parse(x.t); }
        catch (e) {
          // Halaman HTML = biasanya izin Web App bukan "Anyone" atau URL salah.
          return { status: 502, body: { ok: false, error: 'balasan_rusak', message: 'Server Apps Script ' +
            'membalas bukan JSON (HTTP ' + x.r.status + '). Periksa alamat dan izin akses Web App.' } };
        }
      });
  }

  /* Amplop balasan -> Response, termasuk urusan token sesi. */
  function keResponse(a, path, method) {
    aktivitas = Date.now();
    var isiBody = a && a.body !== undefined ? a.body : a;
    if (path === '/api/auth' && method === 'POST' && isiBody && isiBody.token) {
      taruh(K_TOKEN, isiBody.token);
      delete isiBody.token;
    }
    if (path === '/api/auth/keluar' || (a && a.status === 401 && path !== '/api/auth')) {
      taruh(K_TOKEN, null);
      siap = {};
    }
    return balas((a && a.status) || 200, isiBody);
  }

  window.fetch = function (input, init) {
    var url = typeof input === 'string' ? input : (input && input.url) || '';
    var u;
    try { u = new URL(url, location.href); } catch (e) { return fetchAsli(input, init); }
    if (u.origin !== location.origin || u.pathname.indexOf('/api/') !== 0) {
      return fetchAsli(input, init);
    }
    init = init || {};
    var method = String(init.method || 'GET').toUpperCase();
    var body = null;
    if (init.body) { try { body = JSON.parse(init.body); } catch (e) { body = {}; } }

    var alamat = ambil(K_ALAMAT);
    if (!alamat) {
      // 401 membuat app.js membuka halaman login, tempat alamat diisi.
      return Promise.resolve(balas(401, { ok: false, error: 'alamat_kosong',
        message: 'Alamat server belum diatur.' }));
    }
    var path = u.pathname, query = u.search.replace(/^\?/, '');
    var kunciUrl = path + (query ? '?' + query : '');
    var token = ambil(K_TOKEN);
    var sekarang = Date.now();
    var amplop = { method: method, path: path, query: query, body: body, token: token };
    function satu() {
      return kirim(alamat, amplop).then(function (a) { return keResponse(a, path, method); });
    }

    // 1. Sudah tersedia dari rombongan sebelumnya? Boleh dipakai berulang
    //    (refresh() meminta /api/accounts dua kali) — aman, karena tulis apa
    //    pun mengosongkan `siap`, dan umurnya dibatasi UMUR_SIAP.
    if (method === 'GET' && siap[kunciUrl] && siap[kunciUrl].sampai > sekarang) {
      var s = siap[kunciUrl];
      catat(kunciUrl);
      aktivitas = sekarang;
      return s.janji.then(function (a) { return keResponse(a, path, method); }, satu);
    }

    // 2. Tulis = data simpanan bisa basi -> buang. Tulis selalu jadi pemicu.
    if (method !== 'GET') siap = {};
    var pemicu = method !== 'GET' || !rekam || (sekarang - aktivitas) > JEDA;
    aktivitas = sekarang;
    if (!pemicu) {
      catat(kunciUrl);
      return satu();
    }
    if (TIDAK_DIREKAM.test(path)) { rekam = null; return satu(); }

    var M = bulanDari(query);
    var kunci = method + ' ' + cetak(kunciUrl, M);
    rekam = { kunci: kunci, M: M, urls: [] };
    var ikut = rombonganMati ? [] : (pola[kunci] || [])
      .map(function (t) { return isi(t, M); })
      .filter(function (x, i, arr) { return x && x !== kunciUrl && arr.indexOf(x) === i; });
    if (!ikut.length) return satu();

    // 3. Pemicu + data lanjutan dalam SATU panggilan.
    var daftar = [amplop].concat(ikut.map(function (x) {
      var i = x.indexOf('?');
      return { method: 'GET', path: i < 0 ? x : x.slice(0, i), query: i < 0 ? '' : x.slice(i + 1) };
    }));
    var janji = kirim(alamat, { batch: daftar, token: token });
    var hasilKe = function (n) {
      return janji.then(function (r) {
        if (!r || !Array.isArray(r.batch)) {   // server lama tanpa rombongan
          rombonganMati = true;
          throw new Error('rombongan tidak didukung');
        }
        return r.batch[n];
      });
    };
    ikut.forEach(function (x, n) {
      var j = hasilKe(n + 1);
      j.catch(function () { if (siap[x] && siap[x].janji === j) delete siap[x]; });
      siap[x] = { janji: j, sampai: sekarang + UMUR_SIAP };
    });
    return hasilKe(0).then(function (a) { return keResponse(a, path, method); }, function (e) {
      /* Kirim ulang HANYA kalau aman: GET (tidak mengubah apa pun), atau
         server jelas tidak memproses rombongan. Tulis yang putus di tengah
         jalan mungkin SUDAH tersimpan — mengirim ulang bisa mencatat
         transaksi dua kali. Biarkan gagal seperti panggilan biasa. */
      if (method === 'GET' || rombonganMati) return satu();
      throw e;
    });
  };
})();
