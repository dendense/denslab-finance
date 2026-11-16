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
    var amplop = { method: method, path: u.pathname, query: u.search.replace(/^\?/, ''),
      body: body, token: ambil(K_TOKEN) };

    return fetchAsli(alamat, {
      method: 'POST', redirect: 'follow', cache: 'no-store',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(amplop),
    }).then(function (r) { return r.text().then(function (t) { return { r: r, t: t }; }); })
      .then(function (x) {
        var a;
        try { a = JSON.parse(x.t); }
        catch (e) {
          // Halaman HTML = biasanya izin Web App bukan "Anyone" atau URL salah.
          return balas(502, { ok: false, error: 'balasan_rusak', message: 'Server Apps Script ' +
            'membalas bukan JSON (HTTP ' + x.r.status + '). Periksa alamat dan izin akses Web App.' });
        }
        var isi = a && a.body !== undefined ? a.body : a;
        if (u.pathname === '/api/auth' && method === 'POST' && isi && isi.token) {
          taruh(K_TOKEN, isi.token);
          delete isi.token;
        }
        if (u.pathname === '/api/auth/keluar' || (a && a.status === 401 && u.pathname !== '/api/auth')) {
          taruh(K_TOKEN, null);
        }
        return balas((a && a.status) || 200, isi);
      });
  };
})();
