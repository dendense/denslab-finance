/* Kerangka UI Android — HANYA aktif kalau <html> punya kelas `ui-android`
 * (dipasang backend.js dari config.js: FIN_UI = 'android'). Versi web tidak
 * tersentuh: berkas ini langsung berhenti di baris pertama.
 *
 * Prinsip: TIDAK menulis ulang fitur. Semua layar, angka, dan tombol tetap
 * buatan app.js. Berkas ini hanya mengganti BINGKAINYA mengikuti pola Android
 * (Material 3):
 *
 *   - Navigation bar bawah, 5 tujuan (Beranda · Daftar · Analisa · Hutang ·
 *     Akun). Material membatasi 3–5 tujuan; panel punya 6 tab, jadi "Catat"
 *     — aksi terpenting — dipindah ke FAB, bukan tujuan navigasi.
 *   - Top app bar datar: judul layar + aksi. Elemen lama (tombol sensor,
 *     tema, pemilih bulan) DIPINDAH, bukan disalin, supaya listener app.js
 *     tetap menempel.
 *   - Tombol/gesture Back mengikuti riwayat: Catat -> layar sebelumnya,
 *     tab lain -> Beranda, Beranda -> keluar aplikasi.
 *   - Bar bawah & FAB disembunyikan saat keyboard terbuka.
 *   - Tarik ke bawah di puncak layar = segarkan data.
 */
(function () {
  'use strict';
  var root = document.documentElement;
  if (!root.classList.contains('ui-android')) return;
  if (typeof showTab !== 'function') return;

  /* Aplikasi dibuka ulang = mulai dari atas, bukan posisi gulir terakhir
     yang tertinggal di bawah app bar. */
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';

  var $ = function (id) { return document.getElementById(id); };
  var NS = 'http://www.w3.org/2000/svg';

  /* Ikon garis 24px gaya Material Symbols (outlined), digambar sendiri —
     tanpa font ikon dari jaringan, karena aplikasi harus tetap rapi offline. */
  var IKON = {
    home: 'M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1Z',
    daftar: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01',
    analisa: 'M12 3v9l7.8 4.5A9 9 0 1 1 12 3Zm3 0.5A9 9 0 0 1 21 11h-6Z',
    hutang: 'M4 5h16v14H4zM4 9h16M8 3v4M16 3v4M8 13h3M8 16h6',
    akun: 'M3 7a2 2 0 0 1 2-2h13v4M3 7v10a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2Zm14 7h.01',
    tambah: 'M12 5v14M5 12h14',
    kembali: 'M19 12H5M11 6l-6 6 6 6',
  };
  function ikon(nama) {
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('class', 'and-ikon');
    var p = document.createElementNS(NS, 'path');
    p.setAttribute('d', IKON[nama]);
    svg.appendChild(p);
    return svg;
  }
  function el(tag, cls, teks) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (teks) n.textContent = teks;
    return n;
  }

  var JUDUL = { home: 'Beranda', catat: 'Catat transaksi', daftar: 'Transaksi',
    akun: 'Akun', analisa: 'Analisa', hutang: 'Hutang' };
  var TUJUAN = [['home', 'Beranda'], ['daftar', 'Daftar'], ['analisa', 'Analisa'],
    ['hutang', 'Hutang'], ['akun', 'Akun']];
  /* Layar yang angkanya mengikuti bulan terpilih — hanya di sana pemilih
     bulan ditampilkan. Analisa punya pemilih bulannya sendiri. */
  var PAKAI_BULAN = { home: true, daftar: true };

  // ── top app bar ───────────────────────────────────────────────────────────
  var bar = el('header', 'and-bar');
  bar.id = 'and-bar';
  var baris = el('div', 'and-bar-baris');
  var kembali = el('button', 'and-ikon-tombol and-kembali');
  kembali.type = 'button';
  kembali.setAttribute('aria-label', 'Kembali');
  kembali.appendChild(ikon('kembali'));
  kembali.addEventListener('click', function () { history.back(); });
  var judul = el('h1', 'and-judul', 'Beranda');
  var aksi = el('div', 'and-aksi');
  if ($('btn-sensor')) aksi.appendChild($('btn-sensor'));
  baris.appendChild(kembali);
  baris.appendChild(judul);
  baris.appendChild(aksi);
  bar.appendChild(baris);
  var navBulan = document.querySelector('.navbulan');
  if (navBulan) {
    navBulan.classList.add('and-bulan');
    bar.appendChild(navBulan);
  }
  document.body.insertBefore(bar, document.body.firstChild);

  // ── navigation bar bawah ──────────────────────────────────────────────────
  var nav = el('nav', 'and-nav');
  nav.id = 'and-nav';
  nav.setAttribute('aria-label', 'Navigasi utama');
  TUJUAN.forEach(function (t) {
    var b = el('button', 'and-nav-item');
    b.type = 'button';
    b.dataset.tab = t[0];
    var ind = el('span', 'and-nav-indikator');
    ind.appendChild(ikon(t[0]));
    b.appendChild(ind);
    b.appendChild(el('span', 'and-nav-label', t[1]));
    b.addEventListener('click', function () { pindah(t[0]); });
    nav.appendChild(b);
  });
  document.body.appendChild(nav);

  // ── FAB "Catat" ───────────────────────────────────────────────────────────
  var fab = el('button', 'and-fab');
  fab.type = 'button';
  fab.setAttribute('aria-label', 'Catat transaksi');
  fab.appendChild(ikon('tambah'));
  fab.appendChild(el('span', 'and-fab-label', 'Catat'));
  fab.addEventListener('click', function () { pindah('catat'); });
  document.body.appendChild(fab);

  // ── tema pindah ke layar Akun (pengaturan), bukan di bar ─────────────────
  var keluar = $('btn-keluar');
  if ($('btn-tema') && keluar && keluar.parentNode) {
    var setel = el('div', 'and-setelan kartu');
    var label = el('div', 'and-setelan-teks');
    label.appendChild(el('p', 'and-setelan-judul', 'Tema tampilan'));
    label.appendChild(el('p', 'and-setelan-sub', 'Terang, gelap, atau ikut sistem'));
    setel.appendChild(label);
    setel.appendChild($('btn-tema'));
    keluar.parentNode.parentNode.insertBefore(setel, keluar.parentNode);
  }

  // ── navigasi + riwayat (tombol Back Android) ──────────────────────────────
  /* Pola Material: Back dari tujuan tingkat atas kembali ke tujuan awal
     (Beranda); Back dari Beranda keluar aplikasi. Catat ditumpuk di atas
     layar mana pun, jadi Back darinya kembali ke layar asal. */
  var showTabAsli = showTab;
  var dariRiwayat = false;

  function segarkanBingkai(tab) {
    judul.textContent = JUDUL[tab] || '';
    root.dataset.andTab = tab;
    kembali.hidden = tab !== 'catat';
    if (navBulan) navBulan.hidden = !PAKAI_BULAN[tab];
    nav.querySelectorAll('.and-nav-item').forEach(function (b) {
      if (b.dataset.tab === tab) b.setAttribute('aria-current', 'page');
      else b.removeAttribute('aria-current');
    });
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = getComputedStyle(bar).backgroundColor;
  }

  window.showTab = function (name) {
    var sebelum = state.tab;
    var hasil = showTabAsli.apply(this, arguments);
    if (!dariRiwayat && name !== sebelum) {
      var st = { andTab: name };
      if (name === 'catat' || sebelum === 'home') history.pushState(st, '');
      else history.replaceState(st, '');
    }
    segarkanBingkai(name);
    window.scrollTo(0, 0);
    return hasil;
  };
  function pindah(tab) { window.showTab(tab); }

  window.addEventListener('popstate', function (e) {
    var tab = (e.state && e.state.andTab) || 'home';
    dariRiwayat = true;
    try { window.showTab(tab); } finally { dariRiwayat = false; }
  });
  history.replaceState({ andTab: state.tab || 'home' }, '');
  segarkanBingkai(state.tab || 'home');

  // ── bayangan bar saat konten tergulir (elevation on scroll) ──────────────
  window.addEventListener('scroll', function () {
    bar.classList.toggle('terangkat', window.scrollY > 4);
  }, { passive: true });

  // ── keyboard terbuka: sembunyikan bar bawah & FAB ────────────────────────
  if (window.visualViewport) {
    var tinggiPenuh = window.innerHeight;
    window.visualViewport.addEventListener('resize', function () {
      if (window.visualViewport.height > tinggiPenuh) tinggiPenuh = window.visualViewport.height;
      root.classList.toggle('keyboard-buka', window.visualViewport.height < tinggiPenuh * 0.78);
    });
  }

  // ── tarik untuk menyegarkan ──────────────────────────────────────────────
  var penanda = el('div', 'and-tarik');
  penanda.setAttribute('aria-hidden', 'true');
  document.body.appendChild(penanda);
  var awalY = null, jarak = 0, sibuk = false;
  var AMBANG = 72;
  window.addEventListener('touchstart', function (e) {
    if (sibuk || window.scrollY > 0 || state.tab === 'catat' || e.touches.length !== 1) { awalY = null; return; }
    awalY = e.touches[0].clientY;
    jarak = 0;
  }, { passive: true });
  window.addEventListener('touchmove', function (e) {
    if (awalY === null) return;
    jarak = Math.max(0, e.touches[0].clientY - awalY);
    var t = Math.min(jarak, AMBANG * 1.5);
    penanda.style.transform = 'translate(-50%, ' + (t * 0.6) + 'px) rotate(' + (t * 4) + 'deg)';
    penanda.style.opacity = String(Math.min(1, t / AMBANG));
    penanda.classList.toggle('siap', jarak >= AMBANG);
  }, { passive: true });
  window.addEventListener('touchend', function () {
    if (awalY === null) return;
    awalY = null;
    if (jarak >= AMBANG && typeof refresh === 'function') {
      sibuk = true;
      penanda.classList.add('berputar');
      if (navigator.vibrate) navigator.vibrate(8);
      Promise.resolve().then(function () { return refresh(); }).catch(function () {})
        .then(function () {
          sibuk = false;
          penanda.classList.remove('berputar', 'siap');
          penanda.style.opacity = '0';
          penanda.style.transform = '';
          if (state.tab === 'analisa' && typeof renderAnalisa === 'function') renderAnalisa(ANALISA_BULAN);
          if (state.tab === 'hutang' && typeof renderHutang === 'function') renderHutang();
        });
    } else {
      penanda.style.opacity = '0';
      penanda.style.transform = '';
    }
  });
})();
