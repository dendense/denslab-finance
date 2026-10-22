/* finance — logika panel. Mobile-first.
 *
 * ATURAN BESI (CONTRACT.md): UI tidak pernah menghitung angka keuangan.
 * Semua angka datang dari /api/summary, /api/transactions, /api/parse, /api/save.
 * Satu-satunya aritmetika di berkas ini adalah untuk GEOMETRI GRAFIK dan untuk
 * menjumlahkan baris yang SUDAH dikirim server (subtotal kelompok harian di
 * layar Daftar) — tidak ada saldo, total, atau tren yang dihitung ulang di sini.
 */
'use strict';

const API = '/api';

/* ── Sifat transaksi — label & warna, satu sumber kebenaran ─────────────── */
const FLOW = {
  expense:      { label: 'Pengeluaran',  color: 'var(--expense)',    sign: 'out' },
  income:       { label: 'Pemasukan',    color: 'var(--income)',     sign: 'in'  },
  receivable:   { label: 'Talangan',     color: 'var(--receivable)', sign: 'out' },
  debt_payment: { label: 'Bayar utang',  color: 'var(--debt)',       sign: 'out' },
  transfer:     { label: 'Pindah akun',  color: 'var(--transfer)',   sign: 'flat' },
};

/* flow_type -> direction yang sah. Cermin dari FLOW_DIRECTION di db.py.
   Dipakai supaya chip koreksi tidak pernah mengirim pasangan yang ditolak. */
const FLOW_TO_DIRECTION = {
  expense: 'out', receivable: 'out', debt_payment: 'out',
  transfer: 'transfer', income: 'in',
};

/* Urutan chip sebagai keputusan manusia, bukan urutan nilai. */
const FLOW_ORDER = ['expense', 'income', 'receivable', 'debt_payment', 'transfer'];

const DIRECTION_LABEL = { in: 'masuk', out: 'keluar', transfer: 'pindah' };
const ACCOUNT_KIND_LABEL = {
  bank: 'Bank', cash: 'Tunai', savings: 'Tabungan', investment: 'Investasi',
};
const MONTH_SHORT = ['Jan','Feb','Mar','Apr','Mei','Jun','Jul','Agu','Sep','Okt','Nov','Des'];
const MONTH_LONG = ['Januari','Februari','Maret','April','Mei','Juni','Juli',
                    'Agustus','September','Oktober','November','Desember'];

/* ── Format (CONTRACT.md §7) ──────────────────────────────────────────────
 *
 * Mode sensor: semua nominal di halaman ini DISAMARKAN di satu titik, di
 * fungsi ini — bukan per elemen. Alasannya: ada 22 tempat memakai rupiah(),
 * dan menambal satu per satu gampang terlewat saat ada tampilan baru.
 *
 * Batas yang harus jujur diketahui: ini HANYA menyembunyikan tampilan.
 * Angka aslinya tetap ada di DOM, tetap terkirim server, dan bisa dilihat
 * lewat inspect element / view-source. Sensor ini berguna untuk mencegah
 * orang di sebelahmu melihat nominal (pundak, screenshot, presentasi),
 * BUKAN untuk melindungi data dari orang yang punya akses ke browser.
 */
let SENSOR = false;
const SAMAR = '••••••';

function saklarSensor(nyala) {
  SENSOR = !!nyala;
}

/* Samarkan angka di dalam teks bebas (catatan transaksi, tooltip).
   Catatan seperti "Topup e-toll via BRI 301250" dan
   "Transfer BI-Fast ke 098765432109876" memuat nominal dan nomor rekening —
   saat sensor menyala, keduanya tidak boleh tetap terbaca di tooltip.
   Angka 4 digit ke atas disamarkan; tahun (4 digit diawali 19/20) dan jam
   dibiarkan supaya kalimatnya masih bisa dipahami. */
function samarkanAngka(teks) {
  if (!SENSOR || !teks) return teks;
  return String(teks).replace(/\b\d{4,}\b/g, (m) => {
    if (/^(19|20)\d{2}$/.test(m)) return m;      /* tahun: 2026 */
    return SAMAR;
  });
}

function rupiah(n) {
  if (SENSOR) return SAMAR;
  if (n === null || n === undefined || Number.isNaN(Number(n))) return 'Rp ?';
  const neg = Number(n) < 0;
  const s = Math.abs(Math.round(Number(n))).toLocaleString('id-ID');
  return (neg ? '−Rp ' : 'Rp ') + s.replace(/\u00a0/g, '.');
}
function rupiahShort(n) {
  if (SENSOR) return SAMAR;
  const v = Number(n) || 0;
  const a = Math.abs(v);
  if (a >= 1e9) return 'Rp ' + (v / 1e9).toFixed(1).replace('.', ',') + ' M';
  if (a >= 1e6) return 'Rp ' + (v / 1e6).toFixed(1).replace('.', ',') + ' jt';
  if (a >= 1e3) return 'Rp ' + Math.round(v / 1e3) + ' rb';
  return rupiah(v);
}
function parseISO(iso) {
  const [y, m, d] = String(iso).slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}
function todayISO() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
       + '-' + String(d.getDate()).padStart(2, '0');
}
function dayKey(iso) { return String(iso).slice(0, 10); }
function dayLabel(iso) {
  const t = todayISO();
  const yest = (() => { const d = new Date(); d.setDate(d.getDate() - 1); 
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0'); })();
  const k = dayKey(iso);
  if (k === t) return 'Hari ini';
  if (k === yest) return 'Kemarin';
  const d = parseISO(k);
  return d.getDate() + ' ' + MONTH_SHORT[d.getMonth()] + ' ' + d.getFullYear();
}
function dateLabel(iso) {
  const d = parseISO(iso);
  return d.getDate() + ' ' + MONTH_SHORT[d.getMonth()] + ' ' + d.getFullYear();
}
function monthLabel(ym) {
  const [y, m] = String(ym).split('-').map(Number);
  return MONTH_LONG[(m || 1) - 1] + ' ' + y;
}
function timeLabel(ts) {
  const m = String(ts || '').match(/(\d{2}):(\d{2})/);
  return m ? m[1] + ':' + m[2] : '';
}

/* Catatan untuk DITAMPILKAN: sensor nominal dulu (kalau menyala), lalu
   rapikan kapitalisasinya. Dipakai di SEMUA tempat yang menampilkan catatan
   ke Deny, supaya tidak ada layar yang tampil berbeda dari layar lain.

   Sensor DULU, baru kapitalisasi: `samarkanAngka()` mengganti digit dengan
   '•', dan itu tidak mengubah huruf sama sekali — jadi urutannya tidak
   berpengaruh pada hasil. Tapi menulisnya dalam urutan ini membuat niatnya
   jelas: yang dilihat Deny adalah angka yang sudah disembunyikan, lalu
   dirapikan hurufnya. */
function catatanTampil(note, cadangan) {
  const teks = note || cadangan || '';
  return rapikanJudul(SENSOR ? samarkanAngka(teks) : teks);
}

/* ── Kapitalisasi judul transaksi (permintaan Deny, 3 Okt) ───────────────
   "judul setiap transaksi dibuat capitalize case walaupun dalam pengetikan
   kita hanya tulis lowercase"

   DIPAKAI HANYA SAAT MENAMPILKAN. Data di database TIDAK diubah — dan itu
   keputusan yang disengaja, bukan kelalaian:
     1. Catatan asli tetap apa adanya. Kalau suatu saat aturan ini diubah atau
        dibatalkan, tidak ada data yang perlu dikembalikan.
     2. Pencarian di sisi server tetap memakai teks yang kamu tulis. Kalau UI
        menulis ulang teksnya ke database, "parkir" yang kamu cari bisa jadi
        sudah tersimpan sebagai "Parkir" dan pencarian jadi tidak konsisten.

   ATURANNYA — sebuah kata dirapikan HANYA kalau kata itu seluruhnya huruf
   kecil. Begitu ada satu huruf kapital di mana pun, kata itu dilewati utuh.
   Aturan ini yang melindungi merek & akronim di catatan Deny, yang sudah
   diuji terhadap 25 catatan sungguhan: SirayAI, QRIS, GoPaylater, SPinjam,
   BRIVA, BI-Fast, TWP TNI AU, Kaget30GB28Hari, MDB, Azko — semuanya utuh,
   nol dari 12 rusak.

   Yang SENGAJA tidak dilakukan: mengubah huruf di TENGAH kata. Jadi
   'e-toll' tetap 'e-toll' (lihat PERTAHANKAN), dan 'parkir' jadi 'Parkir'.

   Kata sambung & kata depan (ke, di, via, dan, ...) tetap huruf kecil kalau
   bukan kata pertama — itu konvensi judul, dan tanpa aturan ini hasilnya
   "Pembayaran BRIVA Ke TWP TNI AU" yang terasa salah saat dibaca.
*/
const KECIL_SELALU = new Set([
  // Indonesia
  'ke', 'di', 'dari', 'dan', 'atau', 'yang', 'untuk', 'pada', 'dengan',
  'oleh', 'itu', 'ini', 'serta', 'juga', 'agar', 'supaya', 'karena',
  'kalau', 'jika', 'sampai', 'tapi', 'tetapi', 'sebagai',
  // Inggris (dipakai di catatannya: via, per, of, to, for, the, ...)
  'via', 'per', 'of', 'to', 'for', 'the', 'a', 'an', 'at', 'in', 'on',
  'by', 'with', 'and', 'or', 'from',
]);

/* Kata yang penulisan resminya huruf kecil semua dan HARUS dibiarkan.
   Ditulis eksplisit — bukan disimpulkan kode — supaya kalau nanti ada merek
   lain, jelas ke mana menambahkannya. */
const PERTAHANKAN = new Set(['e-toll']);

function rapikanJudul(teks) {
  if (!teks) return teks;

  /* Pisah pada spasi TAPI simpan pemisahnya, supaya spasi berlipat dan
     baris baru tidak hilang saat disatukan kembali. */
  const bagian = String(teks).split(/(\s+)/);
  let posisiKata = 0;

  return bagian.map((b) => {
    if (!b.trim()) return b;                 /* spasi / baris baru */
    const pertama = posisiKata === 0;
    posisiKata += 1;

    if (PERTAHANKAN.has(b.toLowerCase())) return b;
    if (/[A-Z]/.test(b)) return b;           /* sudah ada kapital -> utuh */
    if (!/[a-z]/.test(b)) return b;          /* angka / tanda baca -> utuh */
    if (!pertama && KECIL_SELALU.has(b.toLowerCase())) return b.toLowerCase();

    /* Hanya huruf PERTAMA yang dikapitalkan. Tanda hubung dan garis miring
       tidak dianggap pemisah kata, jadi satu kata tetap satu kata. */
    return b[0].toUpperCase() + b.slice(1);
  }).join('');
}

/* ── Keterangan "kapan dicatat" untuk baris di halaman Daftar ────────────
   Permintaan Deny (3 Okt): halaman Daftar belum punya keterangan jam,
   padahal `created_at` sudah dikirim API.

   Mengembalikan {teks, judul} — atau null kalau keterangannya TIDAK BOLEH
   ditampilkan. null dipakai di tiga keadaan berbeda, dan ketiganya disengaja:

   1. `created_at` kosong/tidak berbentuk tanggal.
      Baris lama bisa tidak punya jam. Menampilkan "NaN" atau karangan sendiri
      lebih buruk daripada tidak menampilkan apa pun.

   2. `source == 'statement'` (transaksi impor rekening koran).
      Terukur di database Deny: 15 baris impor punya `created_at` yang SAMA
      PERSIS — 2026-10-03 07:46:26 — karena ditulis satu skrip dalam satu
      detik. Menampilkan "07:46 dicatat" di limabelas baris membuat Deny
      mengira dia mencatatnya berbarengan; yang sebenarnya terjadi adalah
      skripnya berjalan sekali. Jadi yang disebut ASALNYA, bukan jamnya.
      (Rencana ini sudah disetujui monica.)

   3. Belum ada `created_at` (baris yang dibuat sebelum kolomnya ada).

   Kenapa tanda "·" dipakai untuk memisah tanggal dan jam: `dateLabel()`
   sudah dipakai di barisnya sendiri, dan tanpa pemisah "3 Okt 2026 23:36"
   terbaca seperti satu tanggal panjang. */
function keteranganDicatat(t) {
  if (!t) return null;

  const sumber = String(t.source || 'manual');

  /* Impor statement: jamnya tidak bermakna, sebut asalnya. */
  if (sumber === 'statement') {
    return {
      teks: 'impor rekening koran',
      judul: 'Baris ini masuk dari impor rekening koran, bukan dicatat satu '
        + 'per satu. Jam impornya sama untuk semua baris, jadi tidak '
        + 'ditampilkan.',
    };
  }

  const jam = timeLabel(t.created_at);
  if (!jam) return null;   /* tidak ada jam yang bisa dipercaya */

  const tglCatat = String(t.created_at).slice(0, 10);
  const tglKejadian = String(t.occurred_on).slice(0, 10);

  /* Kalau dicatat di hari yang sama dengan kejadiannya, tanggalnya sudah ada
     di baris itu — cukup jamnya saja. Kalau BEDA, tanggalnya wajib disebut:
     menulis "3 Okt 23:36" untuk kejadian 2 Okt itu berbohong. */
  if (tglCatat === tglKejadian) {
    return {
      teks: '· ' + jam + ' dicatat',
      judul: 'Dicatat ' + dateLabel(tglCatat) + ' pukul ' + jam,
    };
  }
  return {
    teks: '· dicatat ' + dateLabel(tglCatat) + ' ' + jam,
    judul: 'Kejadiannya ' + dateLabel(tglKejadian) + ', dicatat '
      + dateLabel(tglCatat) + ' pukul ' + jam,
  };
}
function addMonths(ym, delta) {
  const [y, m] = String(ym).split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}

/* ── DOM ────────────────────────────────────────────────────────────────── */
/* Akun default untuk transaksi baru.
   PENTING: parser sering mengembalikan account_hint null, dan _resolve_account di
   db.py jatuh ke akun bernama 'Tunai' (saldo 0) — bukan akun yang benar-benar
   dipakai. Jadi UI harus mengirim akun secara eksplisit, tidak menyerahkan
   default ke tebakan server. Pilih akun dengan saldo terbesar; itu akun kerja
   Deny (BRI), dan semua data nyata memang di sana. */
function defaultAccountName() {
  const active = state.accounts.filter((a) => a.is_active);
  if (!active.length) return null;
  const top = active.slice().sort((a, b) => b.balance - a.balance)[0];
  return top.name;
}
/* Cocokkan tebakan parser ke akun yang benar-benar ada; kalau tidak ketemu
   atau kosong, pakai akun default. */
function resolveHint(hint) {
  const h = String(hint || '').trim().toLowerCase();
  if (h) {
    const hit = state.accounts.find((a) => a.name.toLowerCase() === h)
      || state.accounts.find((a) => a.name.toLowerCase().includes(h));
    if (hit) return hit.name;
  }
  return defaultAccountName();
}

/* Nama akun -> id, untuk dikirim ke /api/save dan PATCH /api/transactions/<id>.
   state.accounts diisi dari /api/accounts (punya id) — BUKAN dari
   summary.accounts, yang tidak punya id maupun is_active.

   Mengembalikan null kalau tidak ketemu. Pemanggil yang memutuskan apa yang
   ditampilkan, bukan diam-diam memakai akun lain: /api/save sekarang gagal
   keras kalau akun keliru, jadi menebak hanya memindahkan kegagalan. */
function akunIdDari(nama) {
  const n = String(nama || '').trim().toLowerCase();
  const aktif = (state.accounts || []).filter((a) => a.is_active);
  if (!aktif.length) return null;
  if (n) {
    const hit = aktif.find((a) => a.name.toLowerCase() === n)
      || aktif.find((a) => a.name.toLowerCase().includes(n));
    if (hit) return hit.id;
  }
  const top = aktif.slice().sort((a, b) => (b.balance || 0) - (a.balance || 0))[0];
  return top ? top.id : null;
}

const $ = (id) => document.getElementById(id);
function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined && text !== null) n.textContent = text;
  return n;
}

/* Ikon SVG inline. `currentColor` dipakai di stroke supaya warnanya mengikuti
   teks tombol — jadi terang/gelap beres sendiri tanpa aturan CSS tambahan.
   aria-hidden: ikon tidak boleh dibacakan; yang dibacakan aria-label tombol. */
const IKON_SVG = {
  /* pensil */
  edit: ['M12 20h9', 'M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'],
  /* tempat sampah: tutup, badan, dua garis isi */
  hapus: ['M3 6h18', 'M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2',
          'M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6',
          'M10 11v6', 'M14 11v6'],
  /* chevron ke bawah: menandai lipatan yang bisa dibuka. Diputar lewat CSS
     saat terbuka, jadi cukup satu ikon untuk dua keadaan. */
  lipat: ['m6 9 6 6 6-6'],
  /* segitiga peringatan (triangle-alert): penanda jatuh tempo dekat/terlambat.
     Dipakai BERSAMA teks, bukan menggantikan — supaya warning tidak
     mengandalkan warna saja (buta warna). */
  peringatan: ['m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z',
               'M12 9v4', 'M12 17h.01'],
};
function ikon(nama) {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '1.8');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('width', '20');
  svg.setAttribute('height', '20');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  (IKON_SVG[nama] || []).forEach((d) => {
    const path = document.createElementNS(NS, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  });
  return svg;
}
function toast(msg, kind) {
  const host = $('toast-host');
  host.textContent = '';
  const t = el('div', 'toast' + (kind === 'error' ? ' toast--error' : ''), msg);
  t.setAttribute('role', 'status');
  host.appendChild(t);
  setTimeout(() => { if (t.parentNode) t.parentNode.removeChild(t); }, 4200);
}

/* Tandai tombol sedang bekerja. Teks aslinya disimpan supaya bisa dipulihkan
   apa adanya kalau request gagal — jangan mengarang label baru. */
function setBusy(btn, busy) {
  if (!btn) return;
  if (busy) {
    btn.dataset.label = btn.textContent;
    btn.setAttribute('aria-busy', 'true');
    btn.disabled = true;
  } else {
    btn.removeAttribute('aria-busy');
    if (btn.dataset.label) { btn.textContent = btn.dataset.label; delete btn.dataset.label; }
    btn.disabled = false;
  }
}

/* ── HTTP ─────────────────────────────────────────────────────────────────
 *
 * SATU pembungkus untuk semua permintaan. Aturan monica: 401 -> arahkan ke
 * /login, titik. Jangan coba lagi, jangan tampilkan pesan error, jangan
 * biarkan isi layar lama terlihat.
 *
 * Kenapa di sini dan bukan di tiap pemanggil: ada 11 tempat memanggil fetch
 * di berkas ini. Menambah pemeriksaan 401 di 11 tempat berarti 11 kesempatan
 * lupa — dan yang terlupa tidak akan kelihatan sampai sesinya mati, yang
 * justru keadaan paling sulit ditelusuri. Lewat pembungkus ini, pemanggil
 * baru otomatis ikut terlindungi tanpa perlu tahu apa-apa.
 *
 * Kenapa penting, bukan sekadar rapi: sesi hidup di memori server. Restart
 * server (atau diam 12 jam) mematikan sesi saat Deny sedang memakai panel.
 * Tanpa penanganan ini dia melihat panel dengan angka lama, mengira datanya
 * masih hidup, lalu setiap kali menekan Simpan gagal.
 */
let SEDANG_KE_LOGIN = false;

function keLogin(reason) {
  /* Penjaga sekali-jalan: satu muat halaman bisa memicu beberapa fetch
     sekaligus (Beranda memanggil summary, accounts, savings). Tanpa ini,
     `location.replace` dipanggil berulang dan browser bisa membatalkan
     pengalihan yang sedang berjalan. */
  if (SEDANG_KE_LOGIN) return;
  SEDANG_KE_LOGIN = true;
  try { sessionStorage.setItem('sesi_mati', reason || 'sesi berakhir'); } catch (e) { /* mode privat */ }
  window.location.replace('/login');
}

/* Bungkus fetch: kembalikan Response seperti biasa, TAPI kalau statusnya 401
   langsung alihkan dan hentikan pemrosesan dengan melempar. Pelemparan itu
   disengaja — 401 BUKAN kondisi yang boleh dilanjutkan. */
async function fetchSesi(url, opt) {
  const r = await fetch(url, opt);
  if (r.status === 401) {
    keLogin('sesi berakhir');
    throw new Error('sesi_berakhir');
  }
  return r;
}

async function apiGet(path) {
  const r = await fetchSesi(API + path, { headers: { 'Accept': 'application/json' } });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}
async function apiPost(path, body) {
  const r = await fetchSesi(API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const text = await r.text();
  let data;
  try { data = JSON.parse(text); }
  catch (e) { return { ok: false, error: 'balasan_rusak',
    message: 'Server membalas bukan JSON (HTTP ' + r.status + ').' }; }
  return data;
}

/* ── State ──────────────────────────────────────────────────────────────── */
const state = {
  month: null,        /* 'YYYY-MM' dari server pada load pertama */
  summary: null,
  accounts: [],
  categories: [],     /* diisi dari /api/categories di refresh() — JANGAN biarkan kosong */
  tx: [],
  parsedAny: false,
  tab: 'home',
};

/* ══ BERANDA ═════════════════════════════════════════════════════════════ */

/* Tampilkan angka dengan gerak pendek menuju nilai akhir.
   Nilai akhir TIDAK PERNAH dihitung di sini — selalu angka yang dikirim server.
   Kalau sistem minta kurangi gerak, angka langsung ditulis tanpa animasi. */
function gerakAngka(el, ke) {
  const turun = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Nilai akhir ditulis LEBIH DULU, sebelum animasi apa pun.
     Alasannya: requestAnimationFrame tidak berjalan di tab yang tidak terlihat
     (di-throttle browser), jadi kalau penulisan akhir digantungkan pada frame
     terakhir, angka bisa macet di nilai lama. Dengan urutan ini, layar selalu
     berisi angka API yang benar walau animasinya tidak pernah jalan. */
  const dari = el.__angka;
  el.__angka = ke;
  el.textContent = rupiah(ke);

  if (turun || dari === undefined || dari === ke) return;

  /* Animasi hanya "menimpa" angka akhir tadi selama ~260 ms, lalu berhenti
     tepat di nilai akhir. */
  if (el.__raf) { cancelAnimationFrame(el.__raf); el.__raf = null; }
  const ms = 260;
  const t0 = performance.now();
  const langkah = (t) => {
    const p = Math.min(1, (t - t0) / ms);
    if (p >= 1) {
      el.__raf = null;
      el.textContent = rupiah(ke);
      return;
    }
    const nilai = Math.round(dari + (ke - dari) * (1 - Math.pow(1 - p, 3)));
    el.textContent = rupiah(nilai);
    el.__raf = requestAnimationFrame(langkah);
  };
  el.__raf = requestAnimationFrame(langkah);
}

function renderHero(s) {
  gerakAngka($('hero-value'), s.net_worth.total);
  const bd = $('hero-breakdown');
  const parts = [];
  if (s.net_worth.liquid) parts.push(['Likuid', rupiah(s.net_worth.liquid)]);
  if (s.net_worth.non_liquid) parts.push(['Tidak likuid', rupiah(s.net_worth.non_liquid)]);
  parts.push(['Akun aktif', String(s.net_worth.account_count)]);
  bd.textContent = '';
  parts.forEach(([k, v]) => {
    const w = el('span', null, k + ' ');
    const b = el('b', null, v);
    w.appendChild(b);
    bd.appendChild(w);
  });
  bd.hidden = false;

  /* Uang di akun nonaktif. Monica memperbaiki v_net_worth supaya `total`
     TETAP menghitung akun nonaktif (sebelumnya bug: menonaktifkan akun
     menghapus saldonya dari kekayaan). Karena itu saldo akun nonaktif ada
     di dalam `total` tapi TIDAK muncul di daftar akun mana pun — tanpa baris
     ini Deny melihat kekayaan yang tidak bisa dijelaskan asalnya.

     Hanya kalau > 0: kalau selalu tampil dengan 0, orang mengira ada uang
     nyangkut padahal tidak ada (pesan monica). */
  const nonaktif = Number(s.net_worth.balance_inactive) || 0;
  const barisLama = $('hero-nonaktif');
  if (barisLama) barisLama.remove();
  if (nonaktif > 0) {
    const p = el('p', 'mt-3 rounded-lg px-3 py-2 text-[13px] leading-snug '
      + 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200');
    p.id = 'hero-nonaktif';
    p.appendChild(el('b', null, rupiah(nonaktif)));
    p.appendChild(document.createTextNode(
      ' ada di akun yang dinonaktifkan. Uang itu tetap dihitung dalam total di '
      + 'atas, tapi tidak muncul di daftar akun. Aktifkan akunnya di layar Akun '
      + 'kalau uang itu masih dipakai.'));
    bd.parentElement.appendChild(p);
  }
}

function renderStats(s) {
  const f = s.flow;
  $('stat-in').textContent = rupiah(f.total_in);
  $('stat-expense').textContent = rupiah(f.total_out);

  /* pengeluaran: sebutkan apa yang BUKAN konsumsi, supaya tidak menyesatkan */
  const others = [];
  if (f.receivable_out) others.push('talangan ' + rupiah(f.receivable_out));
  if (f.debt_payment_out) others.push('bayar utang ' + rupiah(f.debt_payment_out));
  $('stat-in-sub').textContent = s.ada_data
    ? s.tx_count + ' transaksi tercatat'
    : 'belum ada transaksi';
  $('stat-expense-sub').textContent = others.length
    ? 'sudah termasuk talangan & bayar utang: ' + others.join(' · ')
    : 'konsumsi saja.';

  /* selisih — pakai net_real (perubahan kekayaan sebenarnya) */
  const card = $('delta-card');
  const v = f.net_real;
  card.classList.toggle('delta--up', v > 0);
  card.classList.toggle('delta--down', v < 0);
  $('delta-value').textContent = rupiah(v);
  $('delta-sub').textContent = 'Perubahan kekayaan sebenarnya: pemasukan dikurangi '
    + 'pengeluaran, talangan, dan pelunasan utang. Selisih arus kas apa adanya '
    + rupiah(f.net) + '.';
}

function renderRecent(items, gagal) {
  const host = $('recent-host');
  host.textContent = '';
  /* Sama seperti renderDaftar: "gagal memuat" bukan "belum ada transaksi".
     Tanpa pembedaan ini, kegagalan endpoint transaksi tampil sebagai daftar
     kosong tanpa penjelasan — dan Deny mengira catatannya hilang. */
  if (gagal) {
    host.appendChild(el('p', 'm-0 rounded-xl border border-dashed '
      + 'border-gray-300 px-4 py-3 text-sm text-gray-500 dark:text-gray-400',
      'Tidak bisa memuat transaksi terakhir. Datamu tidak terpengaruh — '
      + 'muat ulang halaman.'));
    return;
  }
  const list = el('ul', 'm-0 list-none p-0');
  items.slice(0, 6).forEach((t) => list.appendChild(txRow(t, true)));
  host.appendChild(list);
}

/* ══ Grafik tren 6 bulan ═════════════════════════════════════════════════
 * Semua angka dari /api/summary per bulan. Bulan tanpa data (ada_data:false)
 * TIDAK digambar sebagai nol — garisnya diputus dan titiknya kosong.
 */
async function loadTrend(curMonth) {
  /* SATU request menggantikan ENAM. Sebelumnya fungsi ini memanggil
     /api/summary enam kali berurutan (satu per bulan) — di HP dengan sinyal
     lemah itu terasa, dan enam respons yang harus cocok satu sama lain.

     /api/trend sudah ada sejak lama dan tidak kupakai sampai sekarang.

     Yang TIDAK berubah: bentuk keluaran fungsi ini. drawChart() tetap menerima
     {month, state, net_real, expense_real, total_in} seperti sebelumnya, jadi
     gambarannya tidak perlu disentuh sama sekali — dan itu disengaja, karena
     grafiknya sudah teruji.

     Bulan kosong: /api/trend mengirim `ada_data: false` dan total_in = null.
     Itu dipetakan ke state 'kosong' seperti sebelumnya, BUKAN ke 0 — bulan
     tanpa transaksi tidak boleh digambar sebagai batang bernilai nol.

     Diverifikasi lebih dulu dengan pembanding angka (/tmp/banding-tren.py):
     empat field — total_in, total_out, net_real, expense_real — dibandingkan
     per bulan terhadap sumber lama, dan hasilnya identik di keenam bulan.
     Dijalankan SEBELUM perubahan, dan dijalankan LAGI sesudahnya. */
  const bulan = [];
  for (let i = 5; i >= 0; i--) bulan.push(addMonths(curMonth, -i));

  let d;
  try {
    d = await apiGet('/trend?months=6');
  } catch (e) {
    /* Kalau endpointnya tidak bisa dihubungi, tandai SEMUA bulan sebagai
       'error' — bukan 'kosong'. Bedanya penting: 'kosong' berarti "tidak ada
       transaksi", dan itu klaim tentang data Deny yang tidak boleh dibuat
       kalau yang sebenarnya terjadi adalah koneksi gagal. */
    return bulan.map((m) => ({ month: m, state: 'error' }));
  }

  const perBulan = {};
  (d.items || []).forEach((x) => { perBulan[x.month] = x; });

  return bulan.map((m) => {
    const x = perBulan[m];
    /* Bulan yang tidak disebut endpoint sama sekali: perlakukan sebagai
       kosong, sama seperti /api/summary yang dulu mengembalikan ada_data:false.
       Tapi kalau endpointnya menjawab `ada_data:false`, itu juga 'kosong'. */
    if (!x || !x.ada_data) return { month: m, state: 'kosong' };
    return {
      month: m, state: 'ada',
      net_real: x.net_real,
      expense_real: x.expense_real,
      total_in: x.total_in,
      /* Cacah transaksi ikut diteruskan sejak F-2. Sebelumnya dibuang di sini,
         padahal /api/trend sudah mengirimnya sejak lama — dan tanpa cacah,
         grafik tidak bisa membedakan "bulan tipis" dari "bulan bolong".
         Angkanya dari SERVER, tidak dihitung ulang. */
      tx_count: x.tx_count,
    };
  });
}

function drawChart(series) {
  const host = $('chart-host');
  host.textContent = '';

  const known = series.filter((p) => p.state === 'ada');
  const note = $('chart-note');
  const legend = $('chart-legend');
  legend.textContent = '';

  if (!known.length) {
    /* Bedakan "tidak ada data" dari "gagal membaca". Sebelumnya keduanya
       menghasilkan kalimat yang sama — "Belum ada data 6 bulan terakhir,
       catat transaksi dulu" — dan itu MENYALAHKAN Deny untuk kegagalan
       koneksi. Kalau /api/trend tidak bisa dihubungi padahal dia punya 25
       transaksi, pesan itu membuatnya mengira datanya kosong dan dia akan
       mencatat ulang transaksi yang sudah ada.

       Kegagalan adalah kegagalan; ia tidak boleh menyamar jadi keadaan data. */
    const gagal = series.filter((p) => p.state === 'error').length;
    if (gagal === series.length) {
      note.textContent = 'Grafik tidak bisa dibaca: keenam bulan terakhir '
        + 'gagal diambil dari server. Ini bukan berarti datanya kosong.';
      const e = el('div', 'rounded-xl border border-dashed border-gray-300 px-4 py-5 text-center '
        + 'dark:border-gray-700');
      e.appendChild(el('p', 'm-0 mb-1 text-base font-semibold',
        'Tidak bisa memuat grafik tren'));
      e.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400',
        'Server tidak menjawab /api/trend. Datamu tidak terpengaruh — '
        + 'muat ulang halaman, atau periksa apakah servernya masih jalan.'));
      host.appendChild(e);
      host.setAttribute('aria-label', 'Grafik tren gagal dimuat');
      return;
    }

    note.textContent = 'Belum ada satu bulan pun dengan transaksi tercatat dalam '
      + '6 bulan terakhir. Tidak ada yang bisa digambar — dan tidak digambar '
      + 'sebagai nol.';
    const e = el('div', 'rounded-xl border border-dashed border-gray-300 px-4 py-5 text-center');
    e.appendChild(el('p', 'm-0 mb-1 text-base font-semibold', 'Belum ada data 6 bulan terakhir'));
    e.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400',
      'Catat transaksi dulu; grafik muncul setelah ada minimal satu bulan berisi data.'));
    host.appendChild(e);
    host.setAttribute('aria-label', 'Grafik tren kosong: belum ada data');
    return;
  }

  const kosong = series.filter((p) => p.state !== 'ada').length;
  note.textContent = known.length + ' dari 6 bulan punya data'
    + (kosong ? '; ' + kosong + ' bulan tanpa data digambar sebagai slot kosong, bukan nol' : '')
    + '. Batang = uang yang benar-benar masuk dan keluar pada bulan itu.';

  /* Geometri saja — bukan angka keuangan. Dua batang per bulan:
     pemasukan (total_in) dan pengeluaran sungguhan (expense_real).
     total_out sengaja TIDAK dipakai: di Oktober 2.100.000 vs 284.000, dan
     menampilkannya sebagai "pengeluaran" akan menyesatkan (CONTRACT.md §2). */
  /* viewBox 720x200: rasio 3.6, cocok dengan bentuk kartu di jendela lebar
     (lebar ~700 px, tinggi wajar ~195 px). viewBox 320x168 sebelumnya terlalu
     ramping untuk kartu selebar itu, sehingga SVG selalu diregangkan atau
     dipotong dan batangnya berubah bentuk. */
  const W = 720, H = 200, TOP = 16, BOT = 34, L = 10, R = 10;
  const n = series.length;
  const innerW = W - L - R;
  const innerH = H - TOP - BOT;
  const slot = innerW / n;
  const batangW = Math.min(26, slot * 0.26);
  const jeda = 4;               /* jarak antara batang masuk & keluar */

  /* Skala: nilai terbesar di antara pemasukan & pengeluaran semua bulan. */
  const semuaNilai = [];
  known.forEach((p) => { semuaNilai.push(p.total_in, p.expense_real); });

  /* ── Garis rata-rata pengeluaran (F-2) ────────────────────────────────
     Menjawab "bulan ini di atas atau di bawah kebiasaan?".

     🔴 YANG DIHITUNG DI SINI HANYA POSISI GARIS, bukan angka keuangan yang
     ditampilkan. Alasannya sama dengan panjang batang: panjang batang juga
     rasio terhadap nilai terbesar, dan itu sudah diterima. Yang TIDAK saya
     lakukan: mencetak nominal rata-ratanya. Angka itu tidak dikirim endpoint
     mana pun, jadi menampilkannya berarti UI mengarang angka keuangan —
     dilarang aturan 1 HANDOFF-YUKI.md. Garisnya diberi keterangan sebagai
     teks di legenda, tanpa nominal.

     Hanya digambar kalau ada ≥2 bulan berdata: dengan satu bulan, rata-ratanya
     SAMA dengan bulan itu, dan garisnya cuma menimpa puncak batangnya sendiri
     — garis yang tidak memberi tahu apa pun. */
  const rata = known.length >= 2
    ? known.reduce((j, p) => j + Number(p.expense_real || 0), 0) / known.length
    : null;
  /* momo memperingatkan: kalau garis rata-rata ditambahkan, skala harus
     dihitung ulang termasuk nilainya, kalau tidak garisnya keluar viewBox.
     Secara matematis rata-rata ≤ nilai terbesar, jadi ini tidak akan
     mengubah vmax — tapi ditulis eksplisit supaya tidak bergantung pada
     kebetulan itu. */
  if (rata !== null) semuaNilai.push(rata);
  const vmax = Math.max(1, ...semuaNilai);

  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  /* Rasio dipertahankan (bukan 'none'): dengan 'none' SVG selebar kartu
     diregangkan 4.27x sementara viewBox-nya 1.9, sehingga batangnya gepeng.
     Label bulan sudah dipindah ke HTML di bawah SVG, jadi teks tidak ikut
     miring — itu alasan 'none' dipakai sebelumnya. */
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svg.setAttribute('class', 'tren-svg');
  svg.setAttribute('role', 'presentation');

  const mk = (tag, attrs) => {
    const e = document.createElementNS(NS, tag);
    Object.keys(attrs).forEach((k) => e.setAttribute(k, attrs[k]));
    return e;
  };
  const naik = (v) => (innerH * v) / vmax;
  /* Lebar nyata tempat SVG akan digambar, untuk mengubah "6px di layar" jadi
     satuan viewBox. host sudah ada di DOM; kalau belum terukur, pakai W. */
  const lebarSvgNyata = () => {
    const w = host.getBoundingClientRect().width;
    return w > 40 ? w : W;
  };

  /* garis bantu mendatar (3 tingkat) supaya tinggi batang bisa dibaca */
  for (let g = 1; g <= 3; g++) {
    const y = TOP + innerH - (innerH * g) / 3;
    svg.appendChild(mk('line', {
      x1: L, y1: y, x2: W - R, y2: y,
      stroke: 'currentColor', 'stroke-width': 0.5, opacity: 0.12,
    }));
  }
  /* garis dasar */
  svg.appendChild(mk('line', {
    x1: L, y1: TOP + innerH, x2: W - R, y2: TOP + innerH,
    stroke: 'currentColor', 'stroke-width': 1, opacity: 0.25,
  }));

  /* ── Pola pembeda batang pengeluaran (F-2) ────────────────────────────
     Alasan: dua batang dalam satu slot sebelumnya hanya dibedakan oleh
     WARNA (hijau vs merah). Itu gagal syarat "terbaca tanpa warna" —
     dan momo menunjuk ini sebagai kekurangan chart tren (§4.5). Posisi
     sudah membantu (masuk selalu kiri, keluar selalu kanan), tapi posisi
     tidak menolong kalau hanya satu batang yang terlihat di bulan itu.

     Solusinya pola GARIS MIRING pada batang pengeluaran. Garisnya
     `currentColor` (warna teks kartu), bukan warna baru — jadi ia bekerja
     di terang maupun gelap tanpa token tambahan, dan dasar batangnya tetap
     `--color-expense` sehingga kontras batang-terhadap-kartu tidak berubah.

     Jaraknya dihitung dalam SATUAN LAYAR lalu dikonversi ke satuan viewBox,
     sama seperti minH: pola tetap 6px di layar pada lebar apa pun. Angka
     tetap 6 unit akan jadi 2,4px di 360px — terlalu rapat, batangnya
     terlihat abu-abu, bukan berpola. */
  const skalaSvg = lebarSvgNyata() / W;
  const jarakPola = 6 / skalaSvg;
  const tebalPola = Math.max(0.6, 1 / skalaSvg);
  const defs = mk('defs', {});
  const pola = mk('pattern', {
    id: 'tren-pola-keluar', patternUnits: 'userSpaceOnUse',
    width: jarakPola, height: jarakPola,
  });
  pola.appendChild(mk('rect', {
    x: 0, y: 0, width: jarakPola, height: jarakPola,
    fill: 'var(--color-expense)',
  }));
  pola.appendChild(mk('line', {
    x1: 0, y1: jarakPola, x2: jarakPola, y2: 0,
    stroke: 'currentColor', 'stroke-width': tebalPola, opacity: 0.55,
  }));
  defs.appendChild(pola);
  svg.appendChild(defs);

  /* ── Garis rata-rata pengeluaran (F-2) ────────────────────────────────
     Digambar SEBELUM batang supaya batang tetap di atasnya. Putus-putus,
     `currentColor` — sengaja lebih redup daripada batang supaya tidak
     terbaca sebagai data.

     Opacity 0,55 BUKAN pilihan estetika: 0,45 diukur dan GAGAL — 2,93:1
     terhadap kartu putih, di bawah ambang WCAG 1.4.11 (non-teks 3:1).
     Pada 0,55 terukur 3,96:1 (terang) / 5,61:1 (gelap). Kalau diturunkan
     lagi demi "halus", garisnya berhenti memenuhi syarat. */
  if (rata !== null) {
    const yRata = TOP + innerH - naik(rata);
    svg.appendChild(mk('line', {
      x1: L, y1: yRata, x2: W - R, y2: yRata,
      stroke: 'currentColor', 'stroke-width': 1.5,
      'stroke-dasharray': '6 4', opacity: 0.55,
    }));
  }

  series.forEach((p, i) => {
    const tengah = L + slot * i + slot / 2;
    if (p.state === 'ada') {
      const hMasuk = naik(p.total_in);
      const hKeluar = naik(p.expense_real);
      /* Tinggi minimum 4px: nilai kecil (mis. pengeluaran 301rb terhadap
         pemasukan 8jt) hanya 3.7% tinggi, dan 2px di layar sempit praktis
         tidak terlihat — orang lalu menyimpulkan "tidak ada pengeluaran".
         Angka persisnya tetap ditulis di ringkasan di bawah grafik, jadi
         bentuk minimum ini tidak menyembunyikan besaran yang sebenarnya. */
      /* Minimum ~6px DI LAYAR, bukan angka tetap dalam satuan SVG.
         Skala grafik di layar sempit ~0.44 px/unit (316px lebar untuk 720
         unit), jadi minH=4 unit cuma 1.8px — masih tidak terlihat. */
      const minH = Math.max(6, 6 / (lebarSvgNyata() / W));
      /* batang pemasukan (kiri), hijau */
      svg.appendChild(mk('rect', {
        x: tengah - jeda / 2 - batangW, y: TOP + innerH - Math.max(minH, hMasuk),
        width: batangW, height: Math.max(minH, hMasuk), rx: 2,
        fill: 'var(--color-income)',
      }));
      /* batang pengeluaran sungguhan (kanan), merah + pola garis miring */
      svg.appendChild(mk('rect', {
        x: tengah + jeda / 2, y: TOP + innerH - Math.max(minH, hKeluar),
        width: batangW, height: Math.max(minH, hKeluar), rx: 2,
        fill: 'url(#tren-pola-keluar)',
      }));
    } else {
      /* slot kosong: kotak bergaris putus, tanda "belum dicatat" — bukan nol */
      svg.appendChild(mk('rect', {
        x: tengah - (batangW + jeda / 2), y: TOP + innerH - 8,
        width: batangW * 2 + jeda, height: 8, rx: 2,
        fill: 'none', stroke: 'currentColor', 'stroke-width': 1,
        'stroke-dasharray': '2 2', opacity: 0.35,
      }));
    }
  });

  host.appendChild(svg);

  /* label bulan DI BAWAH svg, bukan di dalamnya: teks di dalam SVG yang
     diregangkan (preserveAspectRatio none) jadi miring dan tidak terbaca. */
  const barisLabel = el('div', 'mt-1 flex');
  series.forEach((p) => {
    const m = Number(p.month.split('-')[1]);
    /* Satu kolom per bulan. Angka cacah ikut di kolom yang sama supaya
       sejajar dengan batangnya, bukan mengambang di tempat lain. */
    const kolom = el('div', 'flex-1 min-w-0 text-center');
    const namaBulan = el('span', 'block text-[11px] '
      + (p.state === 'ada' ? 'font-semibold text-gray-600 dark:text-gray-300'
                           : 'text-gray-500 dark:text-gray-400'),
      MONTH_SHORT[m - 1]);
    /* `title` dipertahankan dari versi sebelumnya: bulan tanpa data tetap
       bisa dijelaskan saat disinggahi kursor. Sempat hilang saat cacah
       transaksi ditambahkan, dan itu regresi — dikembalikan di sini. */
    if (p.state !== 'ada') namaBulan.title = 'Belum ada data';
    kolom.appendChild(namaBulan);

    /* ── Cacah transaksi (F-2) ─────────────────────────────────────────
       momo §4.4(d): nomor `tx_count` kecil di bawah label bulan, "supaya
       Deny tahu kalau datanya bolong". Itu kebutuhan nyata — dua bulan
       dengan tinggi batang sama bisa berarti 3 transaksi atau 40.

       Kenapa HANYA ANGKANYA, tanpa kata "transaksi": diukur, bukan dikira.
       Lebar satu kolom pada 360px = 47,7px. "120 transaksi" pada 10px =
       63,8px (meluber), "120 trx" = 33,3px (muat, tapi "trx" adalah
       singkatan yang belum pernah dipakai panel ini — konvensi baru).
       Angka telanjang "120" = 11,3px: selalu muat sampai 4 digit.
       Satuannya dijelaskan sekali di legenda, dan `aria-label` di bawah
       tetap menyebut "transaksi" lengkap per bulan — jadi pembaca layar
       tidak pernah mendengar angka tanpa satuan. */
    if (p.state === 'ada') {
      const n = Number(p.tx_count) || 0;
      const cacah = el('span', 'block text-[10px] text-gray-500 dark:text-gray-400', String(n));
      /* `font-variant-numeric` lewat inline style, bukan kelas `tabular-nums`:
         kelas itu tidak ada di tailwind.css hasil build. Angka rata lebar
         supaya kolom 6 bulan tidak bergoyang saat cacahnya beda digit. */
      cacah.style.fontVariantNumeric = 'tabular-nums';
      kolom.appendChild(cacah);
    }
    barisLabel.appendChild(kolom);
  });
  host.appendChild(barisLabel);

  /* Ringkasan tekstual — angka penting tidak disembunyikan di balik grafik. */
  const rows = series.slice().reverse().map((p) => {
    const lbl = MONTH_SHORT[Number(p.month.split('-')[1]) - 1] + ' ' + p.month.slice(0, 4);
    if (p.state === 'ada') {
      return lbl + ': masuk ' + rupiah(p.total_in) + ', konsumsi ' + rupiah(p.expense_real)
        + ', ' + (Number(p.tx_count) || 0) + ' transaksi';
    }
    if (p.state === 'error') return lbl + ': gagal dibaca';
    return lbl + ': belum ada data';
  });
  host.setAttribute('aria-label', 'Tren 6 bulan. ' + rows.join('. '));

  /* Legenda */
  const item = (warna, teks, putus) => {
    const w = el('span', 'inline-flex items-center gap-1.5');
    const k = el('i', 'inline-block h-2.5 w-2.5 rounded-sm');
    if (putus) {
      k.style.border = '1.5px dashed currentColor';
      k.style.opacity = '0.45';
    } else {
      k.style.background = warna;
    }
    w.appendChild(k);
    w.appendChild(document.createTextNode(teks));
    return w;
  };
  /* Penanda garis rata-rata: GARIS MENDATAR putus-putus, bukan kotak.
     Kalau kupakai kotak bergaris putus lagi, ia akan kembar dengan penanda
     "bulan belum dicatat" dan legenda jadi tidak bisa dibedakan — persis
     kesalahan yang F-2 ini sedang perbaiki. Bentuknya sengaja mengikuti
     bentuk aslinya di grafik (garis mendatar). */
  const itemGaris = (teks) => {
    const w = el('span', 'inline-flex items-center gap-1.5');
    /* `w-4` tidak ada di build Tailwind — lebar penanda ditulis inline. */
    const k = el('i', 'inline-block shrink-0');
    k.style.width = '16px';
    k.style.borderTop = '1.5px dashed currentColor';
    k.style.opacity = '0.55';
    w.appendChild(k);
    w.appendChild(document.createTextNode(teks));
    return w;
  };

  legend.appendChild(item('var(--color-income)', 'pemasukan'));
  legend.appendChild(item('var(--color-expense)', 'konsumsi'));
  legend.appendChild(item(null, 'bulan belum dicatat', true));
  /* Keterangan garis rata-rata HANYA kalau garisnya benar-benar digambar.
     Kalau tidak, legenda akan menjelaskan sesuatu yang tidak ada di grafik. */
  if (rata !== null) {
    legend.appendChild(itemGaris('rata-rata konsumsi ' + known.length + ' bulan'));
  }
  /* Satuan untuk angka kecil di bawah label bulan — dijelaskan SEKALI di
     sini, bukan diulang di setiap kolom (di 360px tidak muat). */
  legend.appendChild(el('span', 'inline-flex items-center gap-1.5',
    'angka kecil = jumlah transaksi bulan itu'));
}

/* ══ Pengeluaran per kategori — batang horizontal ═══════════════════════
 * Menjawab satu pertanyaan: "bulan ini uangku habis ke mana?".
 *
 * Sumbernya /api/spending-by-category (CONTRACT.md §2). SQL-nya sudah
 * menyaring flow_type='expense', jadi talangan project dan pelunasan utang
 * TIDAK ikut — itu bukan konsumsi, dan kalau dicampur kategori "Tagihan"
 * akan terlihat raksasa padahal isinya pelunasan pinjaman.
 *
 * TIGA keadaan dibedakan tegas, sama seperti drawChart():
 *   'ada'   -> ada minimal satu kategori dengan total > 0
 *   'kosong'-> server menjawab, tapi tidak ada pengeluaran bulan itu
 *   'gagal' -> endpointnya tidak bisa dihubungi
 * Kegagalan TIDAK boleh menyamar jadi "belum ada pengeluaran": kalimat itu
 * klaim tentang data Deny, dan tidak boleh dibuat kalau yang terjadi
 * sebenarnya koneksi putus (UI-MOBILE.md, bagian "Kegagalan tidak boleh
 * menyamar jadi keadaan data").
 *
 * UI TIDAK menjumlahkan apa pun di sini. Rancangan momo (KAJIAN-BKLIT-UI
 * §4.4) meminta 7 kategori teratas + satu batang "Lainnya (N kategori)"
 * hasil penjumlahan ekor. Penjumlahan itu DILAKUKAN DI UI, dan itu
 * melanggar aturan pertama HANDOFF-YUKI.md: "UI tidak menghitung angka
 * keuangan. Semua angka dari API." Karena itu di sini SEMUA kategori yang
 * dikirim server digambar apa adanya, tanpa digabung dan tanpa diurut ulang
 * (server sudah ORDER BY total DESC). Kalau daftarnya suatu saat terlalu
 * panjang, penggabungan ekornya harus di server — itu perubahan API, dan
 * itu keputusan monica, bukan tambalan di UI. Selisih ini dilaporkan di
 * laporan F-1.
 *
 * Satu-satunya aritmetika di sini adalah GEOMETRI: panjang batang =
 * total / total terbesar. Tidak ada angka keuangan yang dihitung ulang.
 *
 * AKSESIBILITAS — dan ini hasil pengukuran, bukan dugaan:
 * Versi pertama saya menaruh role="img" + aria-label di host, meniru
 * `#chart-host`. Saya ukur pohon aksesibilitasnya lewat CDP
 * (`Accessibility.getPartialAXTree` + `DOM.describeNode`) dan hasilnya:
 * role="img" di Chrome TIDAK memangkas anak-anaknya. Teks per kategori
 * tetap muncul sebagai node terpisah di dalam subtree, jadi pembaca layar
 * membacakan sepuluh kategori DUA KALI — sekali dari aria-label, sekali
 * dari teks di dalamnya. Untuk #chart-host itu tidak terasa karena isinya
 * murni SVG tanpa teks; di sini isinya teks.
 * Perbaikannya: teksnya sendiri yang jadi isi aksesibel (nama kategori,
 * jumlah transaksi, nominal — sudah terbaca berurutan di dalam <li>), dan
 * batangnya ditandai aria-hidden. Nol pengulangan, nol aria-label tambahan.
 * Aturan kartu F-1 "nilai yang hanya bisa dibaca lewat hover = gagal" tetap
 * terpenuhi karena nominalnya memang teks, bukan tooltip.
 */
async function renderKategori() {
  const host = $('kategori-host');
  if (!host) return;
  host.textContent = '';
  const note = $('kategori-note');
  const bulan = state.month || null;

  let d;
  try {
    d = await apiGet('/spending-by-category'
      + (bulan ? '?month=' + encodeURIComponent(bulan) + '&direction=out' : '?direction=out'));
  } catch (e) {
    note.textContent = 'Rincian kategori tidak bisa dibaca dari server. '
      + 'Ini BUKAN berarti konsumsimu kosong.';
    const kotak = el('div', 'rounded-xl border border-dashed border-gray-300 px-4 py-5 '
      + 'text-center dark:border-gray-700');
    kotak.appendChild(el('p', 'm-0 mb-1 text-base font-semibold',
      'Tidak bisa memuat rincian kategori'));
    kotak.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400',
      'Server tidak menjawab /api/spending-by-category. Datamu tidak '
      + 'terpengaruh — muat ulang halaman, atau periksa apakah servernya '
      + 'masih jalan.'));
    host.appendChild(kotak);
    return;
  }

  const semua = (d.items || []).filter((r) => Number(r.total) > 0);
  const namaBulan = monthLabel(d.month || bulan || '');

  /* ── Keadaan kosong: kalimat yang menjelaskan, bukan batang nol ──────── */
  if (!semua.length) {
    note.textContent = 'Tidak ada konsumsi tercatat di ' + namaBulan + '. '
      + 'Tidak digambar sebagai batang nol — nol dan "tidak ada data" dua hal '
      + 'berbeda.';
    const kotak = el('div', 'rounded-xl border border-dashed border-gray-300 px-4 py-5 '
      + 'text-center dark:border-gray-700');
    kotak.appendChild(el('p', 'm-0 mb-1 text-base font-semibold',
      'Belum ada konsumsi di ' + namaBulan));
    kotak.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400',
      'Yang dihitung di sini hanya transaksi bersifat "Pengeluaran". Talangan '
      + 'dan pelunasan utang sengaja tidak ikut — keduanya bukan konsumsi.'));
    host.appendChild(kotak);
    return;
  }

  /* Geometri: panjang batang relatif terhadap kategori TERBESAR. Nilai
     terbesar selalu jadi batang penuh — itu yang membuat panjangnya bisa
     dibandingkan. Angka persisnya tetap dicetak sebagai teks di tiap baris. */
  const terbesar = Math.max(...semua.map((r) => Number(r.total)));
  const totalKategori = semua.length;

  /* Catatan TIDAK menjumlahkan apa pun. Versi pertamanya menulis "N kategori,
     M transaksi" dengan M = jumlah `tx_count` — dan itu UI yang menjumlahkan
     sendiri, persis yang dilarang HANDOFF-YUKI.md aturan 1. Yang tersisa di
     sini cuma panjang daftar (bukan penjumlahan nilai) dan nama kategori
     terbesar, yang diambil apa adanya dari server (server sudah ORDER BY
     total DESC). */
  note.textContent = totalKategori + ' kategori, urut dari terbesar. '
    + 'Panjang batang = porsi terhadap kategori terbesar (' + semua[0].category
    + '), bukan terhadap total. Angka persisnya tercetak di tiap baris. '
    + 'Talangan dan pelunasan utang tidak dihitung.';

  const NS = 'http://www.w3.org/2000/svg';
  const daftar = el('ul', 'kat-daftar');

  semua.forEach((r) => {
    const nilai = Number(r.total);
    const persen = terbesar > 0 ? (nilai / terbesar) * 100 : 0;
    const jumlahTx = Number(r.tx_count) || 0;

    const li = el('li', 'kat-baris');

    /* Nama + jumlah transaksi di kiri, nominal di kanan. Nominal DICETAK,
       tidak disembunyikan di tooltip: nilai yang hanya bisa dibaca lewat
       hover = gagal (kartu F-1 + UI-MOBILE.md "Yang harus dihindari"). */
    const kepala = el('div', 'kat-kepala');
    const kiri = el('div', 'kat-kiri');
    kiri.appendChild(el('span', 'kat-nama', r.category));
    kiri.appendChild(el('span', 'kat-jumlah',
      jumlahTx + ' transaksi'));
    kepala.appendChild(kiri);
    kepala.appendChild(el('span', 'kat-nilai', rupiah(nilai)));
    li.appendChild(kepala);

    /* Batangnya inline SVG, sama seperti grafik tren — nol library, nol
       dependensi. viewBox 100x10 dengan preserveAspectRatio="none": SVG
       meregang mengikuti lebar kartu tanpa perlu dihitung ulang saat jendela
       diubah ukurannya. SEMUA teks ada di HTML di atas batang, bukan di
       dalam SVG — teks di dalam SVG yang diregangkan jadi gepeng.

       aria-hidden: batangnya hiasan. Panjangnya sudah dinyatakan ulang
       sebagai angka di baris yang sama, jadi tidak ada informasi yang hilang
       saat pembaca layar melewatinya. */
    const lacak = el('div', 'kat-lacak');
    lacak.setAttribute('aria-hidden', 'true');
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', '0 0 100 10');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('class', 'kat-svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    const rect = document.createElementNS(NS, 'rect');
    rect.setAttribute('x', '0');
    rect.setAttribute('y', '0');
    rect.setAttribute('width', String(persen));
    rect.setAttribute('height', '10');
    rect.setAttribute('class', 'kat-isi');
    svg.appendChild(rect);
    lacak.appendChild(svg);
    li.appendChild(lacak);

    daftar.appendChild(li);
  });

  host.appendChild(daftar);
}

/* ══ Baris transaksi — lencana per flow_type ═════════════════════════════ */
function flowBadge(ft) {
  const meta = FLOW[ft] || { label: ft || 'tidak diketahui', color: 'var(--fg-faint)' };
  /* Tanpa titik warna: latar + warna teks lencana sudah membedakan sifatnya,
     dan titik itu memakan 11px yang di kolom sempit lebih berguna untuk nama. */
  return el('span', 'lencana lencana-' + (FLOW[ft] ? ft : 'transfer'), meta.label);
}
function txRow(t, compact) {
  const li = el('li', 'baris');
  const main = el('div', 'min-w-0 flex-1');

  /* Catatan transaksi adalah teks bebas dari database dan SERING memuat
     nominal serta nomor rekening ("Topup e-toll via BRI 301250",
     "Transfer BI-Fast ke 098765432109876"). Saat sensor menyala, angka di
     dalamnya ikut disamarkan — kalau tidak, nominal tetap terbaca di layar
     walau kolom nominalnya sudah bertitik-titik. */
  const teksCatatan = catatanTampil(t.note, '(tanpa catatan)');
  const note = el('p', 'baris-nama m-0 mb-1 font-medium', teksCatatan);
  /* Kalau nama dipotong di kolom sempit, teks lengkapnya tetap harus bisa
     dibaca — title untuk tetikus, aria-label untuk pembaca layar.
     PENTING: catatan transaksi sering memuat nominal ("Topup e-toll 301250")
     dan nomor rekening. Saat sensor menyala, keduanya harus ikut disamarkan —
     tanpa ini tooltip jadi jalan bocor nominal yang sudah disembunyikan. */
  if (t.note) {
    const teks = catatanTampil(t.note);
    note.title = teks;
    note.setAttribute('aria-label', teks);
  }
  main.appendChild(note);

  /* Meta satu baris. Yang paling panjang (nama) dipotong elipsis, sisanya
     tetap utuh — supaya tinggi baris rata, tidak ada yang membungkus 2–3 baris
     seperti sebelumnya (94px vs 138px hanya karena catatan panjang). */
  const meta = el('div', 'baris-meta');
  meta.appendChild(flowBadge(t.flow_type));
  if (t.category_name) {
    meta.appendChild(el('span', 'baris-pisah', '·'));
    meta.appendChild(el('span', 'shrink-0', t.category_name));
  }
  const acc = t.account_name + (t.to_account_name ? ' → ' + t.to_account_name : '');
  meta.appendChild(el('span', 'baris-pisah', '·'));
  meta.appendChild(el('span', 'shrink-0', acc));
  main.appendChild(meta);

  /* Tanggal di barisnya SENDIRI, bukan dijejalkan ke baris meta. Di kolom
     sempit, memaksa tanggal sebaris membuat nama akun terpotong ("BR…").

     SEJAK 3 Okt: jam dicatat duduk di SEBELAH tanggal (permintaan Deny),
     bukan di baris bawahnya. Yang dijaga tetap sama seperti alasan di atas —
     keduanya harus muat di satu baris tanpa memotong apa pun. Karena itu
     wadahnya `flex-wrap`, BUKAN satu baris yang dipaksa: kalau tanggal + jam
     tidak muat di lebar yang tersedia, jamnya turun sendiri ke bawah
     tanggalnya. Itu lebih baik daripada meluber keluar kartu atau terpotong
     elipsis, dan tanpa `flex-wrap` salah satu dari keduanya pasti terjadi di
     layar 360px dengan catatan panjang. */
  const barisWaktu = el('div', 'flex flex-wrap items-baseline gap-x-2');
  barisWaktu.appendChild(el('span', 'baris-tanggal',
    compact ? dayLabel(t.occurred_on) : dateLabel(t.occurred_on)));

  /* ── Keterangan WAKTU DICATAT (permintaan Deny, 3 Okt) ────────────────
     Halaman Daftar tidak punya keterangan jam, padahal `created_at` sudah
     dikirim API dan sudah dipakai di kartu Beranda. Akibatnya dua transaksi
     di tanggal sama tidak bisa dibedakan mana yang dicatat lebih dulu.

     DUA hal yang membuat ini mudah salah, dan keduanya sudah diukur:

     1. `source == 'statement'` TIDAK boleh menampilkan jam. Ke-15 transaksi
        impor punya `created_at` yang SAMA PERSIS (2026-10-03 07:46:26) karena
        dibuat oleh satu skrip dalam satu detik. Menampilkan "07:46 dicatat" di
        limabelas baris membuat Deny mengira dia mencatatnya berbarengan —
        padahal itu jam skrip, bukan waktu kejadian. Yang benar: sebut ASALNYA.
        (Rencana ini sudah disetujui monica.)

     2. Tanggal dan jam dipisah dengan "·", dan hanya tanggalnya yang
        disalin dari `created_at` kalau `occurred_on` berbeda. Transaksi bisa
        dicatat BESOK untuk kejadian HARI INI (mis. belanja malam baru
        dicatat pagi), dan menulis "3 Okt 23:36" padahal kejadiannya 2 Okt
        itu berbohong. jadi:
          occurred_on == created_at  ->  "3 Okt 2026 · 23:36 dicatat"
          berbeda                    ->  "2 Okt 2026 · dicatat 3 Okt 23:36"
     Yang tidak ada dibuat sendiri di UI: `created_at` bisa kosong di baris
     lama; kalau kosong, keterangannya dihilangkan — lebih baik tidak ada
     keterangan daripada keterangan yang salah. */
  if (!compact) {
    const waktu = keteranganDicatat(t);
    if (waktu) {
      const w = el('span', 'baris-waktu', waktu.teks);
      if (waktu.judul) w.title = waktu.judul;
      barisWaktu.appendChild(w);
    }
  }
  main.appendChild(barisWaktu);
  li.appendChild(main);

  const sum = el('div', 'shrink-0 text-right');
  const sign = (FLOW[t.flow_type] || {}).sign || 'flat';
  const cls = sign === 'in' ? 'in' : sign === 'out' ? 'out' : 'flat';
  const prefix = sign === 'in' ? '+' : sign === 'out' ? '−' : '';
  const warna = cls === 'in' ? 'text-(--color-income)'
    : cls === 'out' ? 'text-(--color-expense)' : 'text-gray-500 dark:text-gray-400';
  sum.appendChild(el('div', 'angka-baris ' + warna, prefix + rupiah(t.amount)));
  if (compact) {
    sum.appendChild(el('span', 'mt-0.5 block text-[11px] font-medium text-gray-500 dark:text-gray-400', timeLabel(t.created_at) + ' dicatat'));
  }
  li.appendChild(sum);

  /* Tombol Edit — hanya di halaman Daftar (compact=false). Di panel "transaksi
     terakhir" di Beranda tidak dipasang: di sana orang sedang membaca
     ringkasan, bukan memperbaiki data, dan tombolnya akan menambah derau. */
  if (!compact) {
    const ubah = el('button', 'tombol tombol-hantu tombol-ikon shrink-0');
    ubah.type = 'button';
    ubah.appendChild(ikon('edit'));
    /* Ikon saja berarti tidak ada teks yang bisa dibaca. Tiga penggantinya,
       dan ketiganya perlu — bukan pilihan salah satu:
         aria-label : pembaca layar, dan nama yang dipakai tes
         title      : tooltip saat kursor diam di desktop
       Tanpa sensor, nama transaksi dipakai apa adanya. DENGAN sensor menyala,
       catatannya mengandung nominal — jadi harus disamarkan di sini juga,
       kalau tidak tooltipnya jadi jalan bocor. */
    const labelEdit = 'Edit transaksi '
      + catatanTampil(t.note, 'tanpa catatan');
    ubah.setAttribute('aria-label', labelEdit);
    ubah.title = labelEdit;
    ubah.addEventListener('click', () => formEditTransaksi(li, t));
    li.appendChild(ubah);

    /* Tombol Hapus — hanya di halaman Daftar, sama seperti Edit.
       Hapusnya KERAS (monica menyimpan salinannya ke terhapus.log
       sebelum barisnya dibuang), jadi konfirmasinya dua langkah dan
       menyebut catatan + nominal supaya tidak salah baris. */
    const hapus = el('button', 'tombol tombol-hantu tombol-ikon tombol-bahaya shrink-0');
    hapus.type = 'button';
    hapus.appendChild(ikon('hapus'));
    const labelHapus = 'Hapus transaksi '
      + catatanTampil(t.note, 'tanpa catatan');
    hapus.setAttribute('aria-label', labelHapus);
    hapus.title = labelHapus;
    hapus.addEventListener('click', () => formHapusTransaksi(li, t));

    /* Kedua tombol dibungkus satu wadah. Di layar sempit wadahnya turun ke
       baris bawah (lihat .baris-tombol di src.css) supaya nama transaksi
       dapat lebar penuh, bukan tersisa ~99px. */
    const wadahTombol = el('div', 'baris-tombol');
    wadahTombol.appendChild(ubah);
    wadahTombol.appendChild(hapus);
    li.appendChild(wadahTombol);
  }
  return li;
}

/* ══ Hapus transaksi — konfirmasi dua langkah ════════════════════════════
   Langkah 1: baris berubah jadi pertanyaan konfirmasi. Tidak ada request
   dikirim sebelum Deny menekan "Ya, hapus".
   Langkah 2: DELETE dikirim, lalu daftar dimuat ulang. */
function formHapusTransaksi(li, t) {
  const asli = li.cloneNode(true);
  li.textContent = '';
  li.className = 'baris flex-col items-stretch gap-3';

  li.appendChild(el('p', 'm-0 text-sm font-semibold text-(--color-expense)',
    'Hapus transaksi ini?'));

  /* Nama + nominal disebut, dan untuk transfer akun tujuannya juga —
     supaya Deny tahu baris mana yang sedang dia buang. */
  const rincian = el('p', 'm-0 text-xs leading-snug text-gray-600 dark:text-gray-300');
  const teks = catatanTampil(t.note, 'tanpa catatan');
  const akun = (t.account_name || '?')
    + (t.to_account_name ? ' → ' + t.to_account_name : '');
  rincian.textContent = teks + ' · ' + rupiah(t.amount) + ' · '
    + dateLabel(t.occurred_on) + ' · ' + akun;
  li.appendChild(rincian);

  li.appendChild(el('p', 'm-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Transaksinya dihapus dari daftar dan dari semua angka. Salinannya disimpan '
    + 'di terhapus.log, tapi mengembalikannya tidak bisa lewat panel ini.'));

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const barisTombol = el('div', 'flex gap-2');
  const ya = el('button', 'tombol tombol-utama flex-1', 'Ya, hapus');
  ya.type = 'button';
  /* Tombol hapus dibedakan warnanya supaya tidak tertukar dengan Batal
     saat tangan sedang cepat. */
  ya.style.cssText = 'background:var(--color-expense);color:#fff;';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { formTutup(li, asli, t); });

  ya.addEventListener('click', async () => {
    ya.disabled = true;
    ya.setAttribute('aria-busy', 'true');
    ya.textContent = 'Menghapus…';
    try {
      const r = await fetchSesi(API + '/transactions/' + t.id, { method: 'DELETE' });
      const j = await r.json().catch(() => null);
      if (!j) {
        pesan.textContent = 'Server membalas bukan JSON (HTTP ' + r.status + ').';
        pesan.hidden = false; formPulihkan(ya, 'Ya, hapus'); return;
      }
      if (!j.ok) {
        pesan.textContent = j.message || j.error || 'Gagal menghapus transaksi.';
        pesan.hidden = false; formPulihkan(ya, 'Ya, hapus'); return;
      }
      toast('Transaksi dihapus');
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false; formPulihkan(ya, 'Ya, hapus');
    }
  });

  [pesan, barisTombol].forEach((n) => li.appendChild(n));
  barisTombol.appendChild(ya);
  barisTombol.appendChild(batal);
  batal.focus();
}

/* ══ Edit transaksi ══════════════════════════════════════════════════════
   Menggantikan baris dengan form. Yang bisa diubah: tanggal, nominal,
   sifat (flow_type), kategori, akun, catatan. Arah TIDAK dikirim — server
   menurunkannya dari flow_type (keputusan monica).

   Backend `PATCH /api/transactions/<id>` belum ada saat ini. Kalau server
   menjawab 404, form menampilkan pesan bahwa endpointnya belum tersedia,
   bukan gagal tanpa penjelasan. */
function formEditTransaksi(li, t) {
  const asli = li.cloneNode(true);
  li.textContent = '';
  li.className = 'baris flex-col items-stretch gap-3';

  const judul = el('p', 'm-0 text-sm font-semibold', 'Ubah transaksi');
  li.appendChild(judul);

  /* Nominal & catatan asli ditampilkan supaya Deny tahu persis baris mana
     yang sedang diubah — nama transaksi bisa mirip satu sama lain.
     Catatannya dirapikan seperti di daftar: kalimat ini milik layar, bukan
     milik kolom input, jadi hurufnya harus sama dengan yang dilihat Deny
     di baris daftar. Kolom inputnya sendiri tetap berisi teks ASLI. */
  const asal = el('p', 'm-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Sebelumnya: ' + catatanTampil(t.note, 'tanpa catatan')
    + ' · ' + rupiah(t.amount) + ' · ' + dateLabel(t.occurred_on)
    + ' · ' + (t.account_name || '?'));
  li.appendChild(asal);

  const bidang = (idTeks, teksLabel, jenis, nilai) => {
    const l = el('label', 'text-xs font-medium', teksLabel);
    l.setAttribute('for', idTeks);
    const i = el('input', 'min-h-tap w-full rounded-lg border border-gray-300 px-3 py-2 '
      + 'text-[15px] dark:border-gray-700 dark:bg-gray-900');
    i.id = idTeks;
    i.type = jenis;
    if (nilai !== undefined) i.value = nilai;
    return [l, i];
  };

  /* Nominal: number dengan inputMode numeric supaya papan angka muncul di HP. */
  const [lNom, iNom] = bidang('edit-nom-' + t.id, 'Nominal (Rp)', 'number', t.amount);
  iNom.min = '1';
  iNom.step = '1';
  iNom.inputMode = 'numeric';

  const [lTgl, iTgl] = bidang('edit-tgl-' + t.id, 'Tanggal', 'date', t.occurred_on);

  /* Sifat transaksi sebagai chip — sama seperti kartu draft, karena ini pilihan
     yang sama dan orang sudah mengenalinya. */
  const lSifat = el('label', 'text-xs font-medium', 'Sifat transaksi');
  const rowSifat = el('div', 'flex flex-wrap gap-2');
  let flowPilih = t.flow_type;
  Object.keys(FLOW).forEach((f) => {
    const b = el('button', 'chip', FLOW[f].label);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(f === flowPilih));
    b.addEventListener('click', () => {
      flowPilih = f;
      Array.from(rowSifat.children).forEach((c) =>
        c.setAttribute('aria-pressed', String(c === b)));
      syncSifat();
    });
    rowSifat.appendChild(b);
  });

  /* Kategori: chip juga, dan ikut arah flow_type yang dipilih. */
  const lKat = el('label', 'text-xs font-medium', 'Kategori');
  const rowKat = el('div', 'flex flex-wrap gap-2');
  let katPilih = t.category_name || null;
  const arahDari = (f) => (f === 'income' ? 'in' : f === 'transfer' ? null : 'out');
  function gambarKategori() {
    rowKat.textContent = '';
    const arah = arahDari(flowPilih);
    if (arah === null) {
      katPilih = null;
      rowKat.appendChild(el('span', 'text-xs text-gray-500 dark:text-gray-400',
        'Pindah akun tidak memakai kategori.'));
      return;
    }
    const cocok = (state.categories || []).filter((c) => c.direction === arah);
    if (!cocok.length) {
      /* Kalau kategori tidak bisa dimuat, jangan hapus nilai lama diam-diam —
         kirim apa adanya dan biarkan server yang memutuskan. */
      rowKat.appendChild(el('span', 'text-xs text-gray-500 dark:text-gray-400',
        katPilih ? ('Kategori sekarang: ' + katPilih) : 'Tidak ada pilihan kategori.'));
      return;
    }
    /* Kategori lama mungkin tidak ada di daftar arah baru (mis. dari Makan
       ke Pemasukan). Jangan paksa kosong tanpa memberi tahu. */
    const ada = cocok.some((c) => c.name === katPilih);
    if (katPilih && !ada) {
      rowKat.appendChild(el('span', 'w-full text-xs text-(--color-expense)',
        'Kategori "' + katPilih + '" tidak ada untuk sifat ini. Pilih yang lain '
        + 'atau biarkan kosong.'));
      katPilih = null;
    }
    cocok.forEach((c) => {
      const b = el('button', 'chip', c.name);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(c.name === katPilih));
      b.addEventListener('click', () => {
        katPilih = c.name;
        Array.from(rowKat.children).forEach((x) =>
          x.setAttribute('aria-pressed', String(x === b)));
      });
      rowKat.appendChild(b);
    });
  }

  /* Akun sebagai chip. Nilainya DIKIRIM SEBAGAI account_id, bukan nama —
     /api/save sudah membuktikan bahwa mengirim nama saja rapuh. */
  const lAkun = el('label', 'text-xs font-medium', 'Akun');
  const rowAkun = el('div', 'flex flex-wrap gap-2');
  const akunAktif = (state.accounts || []).filter((a) => a.is_active);
  let akunPilih = null;
  akunAktif.forEach((a) => {
    const ini = a.name === t.account_name;
    if (ini) akunPilih = a.id;
    const b = el('button', 'chip', a.name);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(ini));
    b.addEventListener('click', () => {
      akunPilih = a.id;
      Array.from(rowAkun.children).forEach((x) =>
        x.setAttribute('aria-pressed', String(x === b)));
    });
    rowAkun.appendChild(b);
  });
  if (!akunAktif.length) {
    rowAkun.appendChild(el('span', 'text-xs text-gray-500 dark:text-gray-400',
      'Daftar akun tidak bisa dimuat.'));
  }

  const [lCat, iCat] = bidang('edit-catatan-' + t.id, 'Catatan', 'text', t.note || '');
  iCat.maxLength = 120;

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  /* Alasan tombol Simpan mati saat sifat = Pindah akun. Teks di layar, bukan
     hanya `title` — lihat syncSifat(). */
  const alasanTransfer = el('p', 'teks-peringatan');
  alasanTransfer.hidden = true;
  alasanTransfer.setAttribute('role', 'status');

  const barisTombol = el('div', 'flex gap-2');
  const simpan = el('button', 'tombol tombol-utama flex-1', 'Simpan perubahan');
  simpan.type = 'button';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { formTutup(li, asli, t); });

  /* Simpan dinonaktifkan kalau tidak ada yang berubah — supaya tidak ada
     request yang tidak perlu, dan supaya Deny tahu tidak ada yang dikirim. */
  function syncTombol() {
    const nom = Math.round(Number(iNom.value || 0));
    const berubah = nom !== t.amount
      || iTgl.value !== t.occurred_on
      || flowPilih !== t.flow_type
      || katPilih !== (t.category_name || null)
      || (akunPilih && akunPilih !== akunIdDari(t.account_name))
      || iCat.value.trim() !== (t.note || '');
    simpan.disabled = !berubah || !(nom > 0);
  }
  [iNom, iTgl, iCat].forEach((i) => i.addEventListener('input', syncTombol));
  [iNom, iTgl, iCat].forEach((i) => i.addEventListener('change', syncTombol));
  rowSifat.addEventListener('click', syncTombol);
  rowKat.addEventListener('click', syncTombol);
  rowAkun.addEventListener('click', syncTombol);

  function syncSifat() {
    gambarKategori();
    syncTombol();
    /* transfer butuh akun tujuan, dan layar ini tidak punya pemilihnya —
       katakan apa adanya alih-alih mengirim data setengah jadi. Pemilih
       tujuan ada di layar Catat (kartu draft), jadi arahkan ke sana.
       Pesannya TAMPIL di layar, bukan hanya di `title`: title tidak muncul
       di layar sentuh, dan tombol mati tanpa alasan terbaca seperti bug. */
    if (flowPilih === 'transfer') {
      simpan.disabled = true;
      simpan.title = 'Pindah akun butuh akun tujuan, dan layar Ubah tidak punya '
        + 'pemilihnya. Batalkan, lalu catat ulang lewat layar Catat.';
      alasanTransfer.textContent = simpan.title;
      alasanTransfer.hidden = false;
    } else {
      simpan.title = '';
      alasanTransfer.hidden = true;
      syncTombol();
    }
  }

  simpan.addEventListener('click', async () => {
    pesan.hidden = true;
    const nom = Math.round(Number(iNom.value || 0));
    if (!(nom > 0)) {
      pesan.textContent = 'Nominal harus lebih dari 0.';
      pesan.hidden = false; iNom.focus(); return;
    }
    if (!iTgl.value) {
      pesan.textContent = 'Tanggal tidak boleh kosong.';
      pesan.hidden = false; iTgl.focus(); return;
    }
    if (!akunPilih) {
      pesan.textContent = 'Pilih akun dulu.';
      pesan.hidden = false; return;
    }

    /* Hanya field yang BERUBAH yang dikirim. Mengirim semuanya berarti UI
       menulis ulang kolom yang tidak disentuh Deny — dan kalau ada kolom yang
       ternyata tidak boleh diubah, requestnya gagal tanpa alasan yang jelas. */
    const kirim = {};
    if (nom !== t.amount) kirim.amount = nom;
    if (iTgl.value !== t.occurred_on) kirim.occurred_on = iTgl.value;
    if (flowPilih !== t.flow_type) kirim.flow_type = flowPilih;
    if (katPilih !== (t.category_name || null)) kirim.category = katPilih;
    if (akunPilih !== akunIdDari(t.account_name)) kirim.account_id = akunPilih;
    if (iCat.value.trim() !== (t.note || '')) kirim.note = iCat.value.trim() || null;

    /* direction SENGAJA tidak pernah dikirim — lihat catatan di atas fungsi. */
    simpan.disabled = true;
    simpan.setAttribute('aria-busy', 'true');
    simpan.textContent = 'Menyimpan…';
    try {
      const r = await fetchSesi(API + '/transactions/' + t.id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(kirim),
      });
      const j = await r.json().catch(() => null);
      if (!j) {
        pesan.textContent = 'Server membalas bukan JSON (HTTP ' + r.status + ').';
        pesan.hidden = false; formPulihkan(simpan, 'Simpan perubahan'); return;
      }
      /* 404 pada PATCH transaksi = endpointnya belum ada di server, bukan
         "transaksi tidak ditemukan". Membedakan keduanya penting: yang satu
         tidak akan berhasil walau dicoba berkali-kali, yang satu lagi perlu
         dicek datanya. Tanpa pembedaan ini Deny menekan Simpan berulang kali
         tanpa tahu kenapa tidak pernah berhasil. */
      if (r.status === 404 && (j.error === 'tidak_ditemukan')) {
        pesan.textContent = 'Server belum punya endpoint untuk mengubah '
          + 'transaksi (PATCH /api/transactions/' + t.id + '). Perubahan tidak '
          + 'tersimpan. Endpoint ini sedang diminta ke monica — sampai ada, '
          + 'perbaikan lewat layar Catat atau tanya monica.';
        pesan.hidden = false;
        /* Tombol TIDAK diaktifkan kembali: tidak ada gunanya menekan lagi. */
        simpan.textContent = 'Tidak tersedia';
        return;
      }
      if (!j.ok) {
        pesan.textContent = j.message || j.error || 'Gagal menyimpan perubahan.';
        pesan.hidden = false; formPulihkan(simpan, 'Simpan perubahan'); return;
      }
      toast('Perubahan tersimpan');
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false; formPulihkan(simpan, 'Simpan perubahan');
    }
  });

  [judul, asal, lNom, iNom, lTgl, iTgl, lSifat, rowSifat, lKat, rowKat,
   lAkun, rowAkun, lCat, iCat, alasanTransfer, pesan, barisTombol].forEach((n) => li.appendChild(n));
  barisTombol.appendChild(simpan);
  barisTombol.appendChild(batal);

  syncSifat();
  iNom.focus();
  iNom.select();
}

/* Kembalikan tombol ke keadaan bisa ditekan setelah gagal. `disabled` diset
   di awal supaya tidak ada klik ganda, tapi tanpa pemulihan ini tombolnya
   tinggal "Menyimpan…" selamanya dan Deny tidak bisa mengulang. */
function formPulihkan(tombol, teksAsli) {
  tombol.disabled = false;
  tombol.removeAttribute('aria-busy');
  tombol.textContent = teksAsli;
}

/* Tutup form edit: ganti baris form kembali jadi baris transaksi biasa.
   Pendengar tombol Edit dipasang ulang — tanpa itu, baris yang sudah
   dibatalkan tidak bisa diedit lagi. */
function formTutup(liForm, liAsli, t) {
  const baru = liAsli.cloneNode(true);
  liForm.replaceWith(baru);
  /* Pencarian tombol lewat aria-label, BUKAN textContent. Sejak tombolnya
     ikon, textContent-nya kosong — dan pencarian berbasis teks akan diam-diam
     tidak memasang pendengar, sehingga baris tidak bisa diedit lagi setelah
     dibatalkan. Ini pernah terjadi dan sulit terlihat. */
  const btnEdit = Array.from(baru.querySelectorAll('button'))
    .find((b) => (b.getAttribute('aria-label') || '').startsWith('Edit transaksi'));
  if (btnEdit) btnEdit.addEventListener('click', () => formEditTransaksi(baru, t));
  const btnHapus = Array.from(baru.querySelectorAll('button'))
    .find((b) => (b.getAttribute('aria-label') || '').startsWith('Hapus transaksi'));
  if (btnHapus) btnHapus.addEventListener('click', () => formHapusTransaksi(baru, t));
}

/* ══ Daftar: dikelompokkan per hari, header lengket, lipat per tanggal ══ */

/* Status buka/tutup tiap tanggal, DIINGAT selama halaman belum dimuat ulang.
   Tanpa ini, setiap renderDaftar() mengembalikan semua tanggal ke keadaan
   awal — dan menekan Ubah/Hapus pada baris di tanggal lain akan membuka
   lipatannya sendiri, sehingga hasil editnya terlihat seperti "semua tanggal
   tiba-tiba terbuka". Nilai: true = dibuka paksa oleh pengguna, false =
   ditutup paksa. Tanggal yang tidak ada di sini memakai bawaan (lihat
   tanggalTerbukaBawaan()). Dibersihkan saat ganti bulan. */
let LIPAT_TANGGAL = {};

/* Ambang jumlah transaksi sebelum tanggal selain hari ini ikut tertutup
   otomatis. Kalau bulan ini cuma sedikit baris, menutupnya malah menambah
   klik tanpa menghemat gulir apa pun. */
const AMBANG_LIPAT = 8;

/* Hari ini, sebagai tanggal kalender setempat (YYYY-MM-DD). */
function hariIniISO() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
    + '-' + String(d.getDate()).padStart(2, '0');
}

/* Apakah kelompok tanggal ini terbuka secara BAWAAN?

   ATURAN (diminta Deny, 3 Okt): yang dibiarkan terbuka hanya HARI INI.
   Tanggal lain — termasuk kemarin — tertutup. TAPI hanya kalau bulan ini
   memang ramai, yaitu lebih dari AMBANG_LIPAT transaksi. Kalau bulan ini
   cuma 5 baris, semuanya dibiarkan terbuka: menutup daftar sependek itu
   hanya menambah klik tanpa menghemat gulir, dan halamannya memang belum
   panjang.

   Kenapa ambangnya dihitung per BULAN, bukan per tanggal (keputusan Deny):
   yang membuat halaman panjang adalah jumlah baris total, bukan panjang satu
   kelompok. Bulan dengan 60 baris yang tersebar di 15 tanggal itu yang bikin
   gulir panjang; satu tanggal ramai di bulan yang cuma 12 baris tidak.

   Dibandingkan sebagai TANGGAL KALENDER, bukan selisih jam: panelnya dipakai
   jam 23:50 dan jam 00:10, dan transaksi hari ini tidak boleh berubah jadi
   "bukan hari ini" hanya karena tengah malam lewat. */
function tanggalTerbukaBawaan(iso, jumlahBulanIni) {
  if (jumlahBulanIni <= AMBANG_LIPAT) return true;   /* bulan sepi: biarkan */
  return dayKey(iso) === hariIniISO();
}

/* Apakah kelompok tanggal ini sedang terbuka? Pilihan pengguna
   (LIPAT_TANGGAL) menang atas bawaan — kalau tidak, menekan tombolnya tidak
   berpengaruh pada renderDaftar() berikutnya. */
function tanggalTerbuka(iso, jumlahBulanIni) {
  const k = dayKey(iso);
  if (Object.prototype.hasOwnProperty.call(LIPAT_TANGGAL, k)) {
    return LIPAT_TANGGAL[k];
  }
  return tanggalTerbukaBawaan(k, jumlahBulanIni);
}
function renderDaftar(items, gagal) {
  const host = $('daftar-host');
  host.textContent = '';
  /* `gagal` dipisah dari "kosong": kalau endpoint transaksi tidak menjawab,
     daftar ini kosong karena kegagalan — bukan karena Deny belum mencatat.
     Menulis "belum ada data" di situ menyalahkannya untuk masalah koneksi. */
  $('daftar-count').textContent = gagal
    ? 'Tidak bisa memuat'
    : (items.length ? items.length + ' transaksi · ' + monthLabel(state.month) : '');

  if (gagal) {
    const e = el('div', 'rounded-xl border border-dashed border-gray-300 px-5 py-6 text-center');
    e.appendChild(el('p', 'm-0 mb-1 text-base font-semibold', 'Tidak bisa memuat transaksi'));
    e.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400',
      'Server tidak menjawab daftar transaksi. Datamu tidak terpengaruh — '
      + 'muat ulang halaman, atau periksa apakah servernya masih jalan.'));
    host.appendChild(e);
    return;
  }

  if (!items.length) {
    const e = el('div', 'rounded-xl border border-dashed border-gray-300 px-5 py-6 text-center');
    e.appendChild(el('p', 'm-0 mb-1 text-base font-semibold', 'Belum ada data bulan ini'));
    e.appendChild(el('p', 'm-0 text-sm text-gray-500 dark:text-gray-400', 'Tidak ada transaksi tercatat di '
      + monthLabel(state.month) + '. Ini bukan berarti pengeluarannya nol.'));
    host.appendChild(e);
    return;
  }

  const groups = [];
  const byKey = {};
  items.forEach((t) => {
    const k = dayKey(t.occurred_on);
    if (!byKey[k]) { byKey[k] = []; groups.push(k); }
    byKey[k].push(t);
  });

  /* Ambang "bulan ramai" dihitung dari SELURUH bulan, bukan dari jumlah yang
     sedang tampil: memakai panjang daftar bukan pilihan yang benar begitu ada
     penyaring, karena daftar tersaring yang pendek akan membuka semua tanggal
     padahal bulannya ramai. */
  const jumlahBulan = items.length;

  /* Kalau hari ini belum ada transaksi, katakan di ATAS daftar — bukan
     menghilangkan tanggal lampau. Deny minta yang lampau tetap ada di
     bawahnya, dan itu memang masuk akal: justru saat hari ini kosong, orang
     paling ingin melihat hari-hari sebelumnya. */
  const adaHariIni = groups.some((k) => k === hariIniISO());
  if (!adaHariIni) {
    const kosong = el('div', 'mb-4 rounded-xl border border-dashed '
      + 'border-gray-300 px-5 py-4 dark:border-gray-700');
    kosong.appendChild(el('p', 'm-0 text-sm font-semibold text-gray-600 '
      + 'dark:text-gray-300', 'Belum ada transaksi hari ini'));
    kosong.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug '
      + 'text-gray-500 dark:text-gray-400',
      'Transaksi sebelumnya ada di bawah. Ini bukan berarti hari ini '
      + 'pengeluarannya nol.'));
    host.appendChild(kosong);
  }

  groups.forEach((k) => {
    const g = el('div', 'mb-4');
    const terbuka = tanggalTerbuka(k, jumlahBulan);

    /* Subtotal baris yang SUDAH dikirim server — bukan angka keuangan baru.
       Dihitung SEBELUM head dibuat karena angkanya ikut tampil saat tertutup:
       orang perlu tahu ada apa di dalam lipatan sebelum memutuskan mengklik. */
    const outOnly = byKey[k].filter((t) => t.direction === 'out')
      .reduce((a, t) => a + t.amount, 0);
    const inOnly = byKey[k].filter((t) => t.direction === 'in')
      .reduce((a, t) => a + t.amount, 0);
    const bits = [];
    if (inOnly) bits.push('+' + rupiah(inOnly));
    if (outOnly) bits.push('−' + rupiah(outOnly));

    /* Seluruh header jadi tombol, bukan cuma ikon 20px di ujungnya: di HP
       menyasar ikon sekecil itu menyiksa, dan seluruh baris header memang
       sudah terasa seperti bagian yang bisa dibuka. */
    const head = el('button', 'txgroup-head w-full text-left');
    head.type = 'button';
    head.setAttribute('aria-expanded', terbuka ? 'true' : 'false');
    head.setAttribute('aria-controls', 'grup-' + k);

    const kiri = el('span', 'flex min-w-0 items-center gap-1.5');
    const chev = el('span', 'chevron-lipat shrink-0');
    chev.appendChild(ikon('lipat'));
    kiri.appendChild(chev);
    kiri.appendChild(el('span', null, dayLabel(k)));
    head.appendChild(kiri);

    const kanan = el('span', 'flex shrink-0 items-center gap-2');
    kanan.appendChild(el('span', 'angka font-medium normal-case tracking-normal',
      bits.join('  ') || '—'));
    head.appendChild(kanan);
    g.appendChild(head);

    /* Jumlah transaksi hanya tampil saat TERTUTUP — saat terbuka, barisnya
       sudah terlihat dan hitungannya jadi pengulangan.
       Elemennya dibuat SEKALI di sini lalu cuma di-toggle `hidden`; versi
       sebelumnya menghapus & membuat ulang, dan itu bikin angkanya hilang
       karena pencarian elemennya tidak menemukan apa pun untuk dibuang. */
    const hitung = el('span', 'normal-case tracking-normal font-normal');
    hitung.textContent = '· ' + byKey[k].length;
    hitung.hidden = terbuka;
    kanan.appendChild(hitung);

    const list = el('ul', 'm-0 list-none p-0 kartu kartu-rapat');
    list.id = 'grup-' + k;
    byKey[k].forEach((t) => list.appendChild(txRow(t, false)));
    list.hidden = !terbuka;
    g.appendChild(list);

    head.addEventListener('click', () => {
      const sekarangTerbuka = !list.hidden;   /* keadaan nyata di layar */
      const jadi = !sekarangTerbuka;
      LIPAT_TANGGAL[dayKey(k)] = jadi;
      list.hidden = !jadi;
      hitung.hidden = jadi;
      head.setAttribute('aria-expanded', jadi ? 'true' : 'false');
    });

    host.appendChild(g);
  });

  const note = el('p', 'mt-4 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Subtotal per hari dijumlahkan dari baris yang tampil di layar ini saja — '
    + 'angka resmi tetap dari /api/summary.');
  host.appendChild(note);
}

/* ══ Akun ════════════════════════════════════════════════════════════════
   Sumber daftar akun: GET /api/accounts, bukan summary.accounts.
   Alasannya: endpoint akun mengirim `id` dan `is_active`, yang dibutuhkan
   tombol Ubah. summary.accounts tidak punya id. */
async function renderAkun(s) {
  $('akun-total').textContent = rupiah(s.net_worth.total);
  const bd = $('akun-breakdown');
  bd.textContent = '';
  [['Likuid', rupiah(s.net_worth.liquid)],
   ['Tidak likuid', rupiah(s.net_worth.non_liquid)],
   ['Jumlah akun', String(s.net_worth.account_count)]].forEach(([k, v]) => {
    const w = el('span', null, k + ' ');
    w.appendChild(el('b', null, v));
    bd.appendChild(w);
  });
  bd.hidden = false;

  /* Sama seperti di Beranda: hanya tampil kalau ada. Di panel Akun ini lebih
     penting lagi — orang yang baru menonaktifkan akun akan mencari uangnya
     di daftar di bawah dan tidak menemukannya. */
  const nonaktifAkun = Number(s.net_worth.balance_inactive) || 0;
  const sisaBaris = $('akun-nonaktif');
  if (sisaBaris) sisaBaris.remove();
  if (nonaktifAkun > 0) {
    const p = el('p', 'mt-3 rounded-lg px-3 py-2 text-[13px] leading-snug '
      + 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200');
    p.id = 'akun-nonaktif';
    p.appendChild(el('b', null, rupiah(nonaktifAkun)));
    p.appendChild(document.createTextNode(
      ' ada di akun nonaktif — tidak muncul di daftar di bawah, tapi tetap '
      + 'terhitung dalam total. Gunakan tombol Ubah pada akun itu untuk '
      + 'mengaktifkannya kembali.'));
    bd.parentElement.appendChild(p);
  }

  const host = $('akun-host');
  host.textContent = '';

  let daftar;
  try {
    const r = await fetchSesi('/api/accounts?all=1', { cache: 'no-store' });
    const j = await r.json();
    daftar = (j.items || []).filter((a) => a.is_active);
  } catch (e) {
    /* Kalau endpoint akun mati, jangan tampilkan panel kosong tanpa alasan —
       katakan apa yang terjadi dan apa yang bisa dilakukan. */
    host.className = 'flex flex-col gap-5';
    host.appendChild(el('p', 'kartu text-sm leading-snug',
      'Tidak bisa memuat daftar akun dari /api/accounts. Nominal di atas tetap '
      + 'dari /api/summary, tapi daftar akun tidak bisa ditampilkan.'));
    return;
  }

  const daily = daftar.filter((a) => a.kind !== 'savings' && a.kind !== 'investment');
  const saved = daftar.filter((a) => a.kind === 'savings' || a.kind === 'investment');

  /* Jarak antar kelompok diatur induknya lewat gap-6 (di index.html).
     Jangan pasang margin di sini — dua sumber jarak membuat hasilnya tidak
     konsisten (44 px vs 24 px). */
  host.className = 'flex flex-col gap-5';

  const block = (title, list) => {
    if (!list.length) return;
    const wrap = el('div');
    wrap.appendChild(el('p', 'eyebrow mb-2', title));
    const card = el('div', 'kartu kartu-rapat');
    const ul = el('ul', 'm-0 list-none p-0');
    list.forEach((a) => {
      const li = el('li', 'baris');
      const main = el('div', 'min-w-0 flex-1');
      main.appendChild(el('p', 'baris-nama m-0 mb-1 font-medium', a.name));
      const meta = el('div', 'baris-meta');
      meta.appendChild(el('span', null, ACCOUNT_KIND_LABEL[a.kind] || a.kind));
      main.appendChild(meta);
      li.appendChild(main);
      li.appendChild(el('div', 'shrink-0 text-right angka-baris '
        + (a.balance > 0 ? 'text-(--color-income)' : 'text-gray-500 dark:text-gray-400'),
        rupiah(a.balance)));

      /* Tombol Ubah: satu per baris, ukuran 44x44 (UI-MOBILE.md), pakai teks
         bukan ikon saja supaya jelas maksudnya tanpa menebak. */
      const ubah = el('button', 'tombol tombol-hantu tombol-kecil shrink-0', 'Ubah');
      ubah.type = 'button';
      ubah.setAttribute('aria-label', 'Ubah nama akun ' + a.name);
      ubah.addEventListener('click', () => formUbahAkun(li, a));
      li.appendChild(ubah);
      ul.appendChild(li);
    });
    card.appendChild(ul);
    wrap.appendChild(card);
    host.appendChild(wrap);
  };
  block('Akun harian', daily);
  block('Tabungan & investasi', saved);

  /* Tombol tambah akun. Ditaruh di luar kartu supaya tidak terlihat seperti
     salah satu akun di dalam daftar. */
  const tambah = el('button', 'tombol tombol-utama', 'Tambah akun');
  tambah.type = 'button';
  tambah.id = 'btn-tambah-akun';
  tambah.addEventListener('click', () => {
    const wadah = el('div');
    tambah.replaceWith(wadah);
    formTambahAkun(wadah);
  });
  host.appendChild(tambah);
}

/* ── Form ubah nama akun (inline di baris akun) ──────────────────────────
   Hanya nama yang bisa diubah. `kind` dan `opening_balance` SENGAJA tidak
   disediakan: /api/accounts PATCH menolaknya dengan error `field_terkunci`,
   karena keduanya mengubah angka v_net_worth tanpa satu pun transaksi. */
function formUbahAkun(li, akun) {
  const asli = li.innerHTML;
  li.textContent = '';
  li.className = 'baris flex-col items-stretch gap-2';

  const label = el('label', 'text-xs font-medium', 'Nama akun');
  label.setAttribute('for', 'akun-nama-' + akun.id);
  const input = el('input', 'min-h-tap w-full rounded-lg border border-gray-300 px-3 py-2 text-[15px] dark:border-gray-700 dark:bg-gray-900');
  input.id = 'akun-nama-' + akun.id;
  input.type = 'text';
  input.value = akun.name;
  input.maxLength = 40;

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const barisTombol = el('div', 'flex gap-2');
  const simpan = el('button', 'tombol tombol-utama flex-1', 'Simpan nama');
  simpan.type = 'button';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';

  const tutup = () => {
    const li2 = el('li', 'baris');
    li2.innerHTML = asli;
    li.replaceWith(li2);
    /* Pasang ulang pendengar tombol Ubah pada baris yang baru. */
    const btn = li2.querySelector('button');
    if (btn) btn.addEventListener('click', () => formUbahAkun(li2, akun));
  };
  batal.addEventListener('click', tutup);

  simpan.addEventListener('click', async () => {
    const nama = input.value.trim();
    if (!nama) {
      pesan.textContent = 'Nama tidak boleh kosong.';
      pesan.hidden = false;
      input.focus();
      return;
    }
    if (nama === akun.name) { tutup(); return; }

    simpan.disabled = true;
    simpan.setAttribute('aria-busy', 'true');
    /* Nama tombol berubah jadi ikon spinner saat menunggu — harus
       dikembalikan kalau gagal, kalau tidak tombolnya tinggal spinner. */
    const teksAsli = simpan.textContent;
    simpan.textContent = 'Menyimpan…';
    try {
      const r = await fetchSesi('/api/accounts/' + akun.id, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        /* kind & opening_balance tidak dikirim — server menolaknya, dan
           mengirimnya berarti aku mencoba mengubah angka yang bukan hakku. */
        body: JSON.stringify({ name: nama }),
      });
      const j = await r.json();
      if (!j.ok) {
        pesan.textContent = j.message || 'Gagal mengubah nama akun.';
        pesan.hidden = false;
        simpan.disabled = false;
        simpan.removeAttribute('aria-busy');
        simpan.textContent = teksAsli;
        return;
      }
      toast('Nama akun diubah jadi ' + j.name);
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false;
      simpan.disabled = false;
      simpan.removeAttribute('aria-busy');
      simpan.textContent = teksAsli;
    }
  });

  [label, input, pesan, barisTombol].forEach((n) => li.appendChild(n));
  barisTombol.appendChild(simpan);
  barisTombol.appendChild(batal);
  input.focus();
  input.select();
}

/* ── Form tambah akun ────────────────────────────────────────────────────
   Saldo awal HANYA ada di form ini. Setelah akun dibuat, angkanya terkunci
   (monica: mengubahnya menggeser semua saldo lama, termasuk bulan yang
   laporannya sudah ditunjukkan). Jadi kalau salah mengisi saldo awal, jalan
   keluarnya bukan edit — tapi nonaktifkan akun itu dan buat yang baru. */
function formTambahAkun(wadah) {
  wadah.textContent = '';
  const wrap = el('div');
  wrap.appendChild(el('p', 'eyebrow mb-2', 'Akun baru'));
  /* Padding 16px, BUKAN `kartu-rapat`. `kartu-rapat` artinya padding: 0 —
     dipakai untuk kartu yang isinya daftar (tiap baris sudah punya padding
     sendiri). Di form, tidak ada baris yang punya padding, jadi label dan
     input menempel ke tepi kartu: isinya mulai 1px dari border. Terukur
     sebelum perbaikan: padding 0px, anak pertama di kiri 1px.
     Form lain di panel ini (Edit/Hapus/Ubah) memakai kelas `baris` yang
     punya padding 14px 16px — form ini sekarang sejajar dengannya. */
  const card = el('div', 'kartu p-4 flex flex-col gap-3');

  const bidang = (idTeks, teksLabel, jenis, nilai) => {
    const l = el('label', 'text-xs font-medium', teksLabel);
    l.setAttribute('for', idTeks);
    const i = el('input', 'min-h-tap w-full rounded-lg border border-gray-300 px-3 py-2 text-[15px] dark:border-gray-700 dark:bg-gray-900');
    i.id = idTeks;
    i.type = jenis;
    if (nilai !== undefined) i.value = nilai;
    return [l, i];
  };

  const [lNama, iNama] = bidang('akun-baru-nama', 'Nama akun', 'text', '');
  iNama.maxLength = 40;
  iNama.placeholder = 'cth: Mandiri';
  const [lJenis, iJenis] = bidang('akun-baru-jenis', 'Jenis', 'text', 'bank');
  const [lSaldo, iSaldo] = bidang('akun-baru-saldo', 'Saldo awal (Rp)', 'number', '0');
  iSaldo.min = '0';
  iSaldo.step = '1';
  iSaldo.inputMode = 'numeric';

  const petunjuk = el('p', 'm-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Jenis yang dikenal: bank · cash · ewallet · savings · investment. '
    + 'Saldo awal hanya bisa diisi sekarang — setelah akun dibuat, angkanya '
    + 'terkunci karena mengubahnya akan menggeser semua saldo lama.');

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const barisTombol = el('div', 'flex gap-2');
  const simpan = el('button', 'tombol tombol-utama flex-1', 'Tambah akun');
  simpan.type = 'button';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { wrap.replaceWith(tombolTambahBaru()); });

  simpan.addEventListener('click', async () => {
    pesan.hidden = true;
    const nama = iNama.value.trim();
    const jenis = iJenis.value.trim().toLowerCase();
    if (!nama) {
      pesan.textContent = 'Nama akun tidak boleh kosong.';
      pesan.hidden = false; iNama.focus(); return;
    }
    const saldo = Math.round(Number(iSaldo.value || 0));
    if (!Number.isFinite(saldo) || saldo < 0) {
      pesan.textContent = 'Saldo awal harus angka bulat 0 atau lebih.';
      pesan.hidden = false; iSaldo.focus(); return;
    }
    simpan.disabled = true;
    simpan.setAttribute('aria-busy', 'true');
    simpan.textContent = 'Menyimpan…';
    try {
      const r = await fetchSesi('/api/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nama, kind: jenis, opening_balance: saldo }),
      });
      const j = await r.json();
      if (!j.ok) {
        pesan.textContent = j.message || 'Gagal menambah akun.';
        pesan.hidden = false;
        simpan.disabled = false;
        simpan.removeAttribute('aria-busy');
        simpan.textContent = 'Tambah akun';
        return;
      }
      toast('Akun ' + j.name + ' ditambahkan');
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false;
      simpan.disabled = false;
      simpan.removeAttribute('aria-busy');
      simpan.textContent = 'Tambah akun';
    }
  });

  [lNama, iNama, lJenis, iJenis, lSaldo, iSaldo, petunjuk, pesan, barisTombol]
    .forEach((n) => card.appendChild(n));
  barisTombol.appendChild(simpan);
  barisTombol.appendChild(batal);
  wrap.appendChild(card);
  wadah.appendChild(wrap);
  iNama.focus();
}

function tombolTambahBaru() {
  const b = el('button', 'tombol tombol-utama', 'Tambah akun');
  b.type = 'button';
  b.addEventListener('click', () => {
    const w = el('div');
    b.replaceWith(w);
    formTambahAkun(w);
  });
  return b;
}

/* ══ Target tabungan (di bawah panel transaksi terakhir) ═════════════════
   Permintaan Deny. Menggantikan panel "saldo akun tabungan" yang lebih dulu
   di sini — lihat surat monica "persetujuan-tabungan" §1 (pilihan 3).

   Sumber: GET /api/savings. Angka TIDAK dihitung di UI; bahkan `persen` dan
   `status` datang dari server supaya aturannya cuma ada di satu tempat.
*/
let TARGET_ADA = false;   /* dipakai tombol untuk memutuskan buang vs arsipkan */

async function renderTargetTabungan() {
  const host = $('target-host');
  if (!host) return;
  host.textContent = '';
  host.className = 'kartu mt-3';

  let d;
  try {
    const r = await fetchSesi('/api/savings', { cache: 'no-store' });
    d = await r.json();
  } catch (e) {
    host.appendChild(el('p', 'm-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Tidak bisa memuat target tabungan dari /api/savings.'));
    return;
  }

  TARGET_ADA = !!d.ada_target;

  /* ── Keadaan kosong: ajakan, BUKAN angka nol ──────────────────────────
     "Rp 0 dari Rp 0" atau bar 0% terbaca seperti kerusakan, bukan keadaan
     awal (aturan monica §4). */
  if (!d.ada_target) {
    host.appendChild(el('p', 'm-0 text-sm font-semibold', 'Belum ada target'));
    host.appendChild(el('p', 'mt-1 mb-3 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Pasang target untuk mulai memantau. Progres dihitung dari saldo akun '
      + 'tabungan, jadi tabungannya perlu diisi lewat transaksi pindah akun.'));

    const bisa = (d.akun_bisa_dipakai || []);
    if (!bisa.length) {
      /* Tanpa akun berjenis savings/investment, target tidak bisa dipasang
         sama sekali — katakan apa yang harus dilakukan dulu daripada
         menampilkan tombol yang pasti gagal. */
      host.appendChild(el('p', 'm-0 text-[13px] leading-snug text-(--color-expense)',
        'Belum ada akun tabungan. Buat dulu akun berjenis "savings" di layar Akun.'));
      return;
    }
    const btn = el('button', 'tombol tombol-utama', 'Pasang target');
    btn.type = 'button';
    btn.addEventListener('click', () => formTargetTabungan(host, d.akun_bisa_dipakai, null));
    host.appendChild(btn);
    return;
  }

  /* ── Ada target ─────────────────────────────────────────────────────── */
  const t = d.target;

  /* Nama + tombol ubah. `persen` bisa > 100 dan TIDAK di-cap (aturan 3b):
     kelebihan itu informasi, bukan error. */
  const kepala = el('div', 'flex items-start justify-between gap-3');
  kepala.appendChild(el('p', 'm-0 text-sm font-semibold', t.name));

  const aksi = el('div', 'flex shrink-0 gap-1');
  const btnUbah = el('button', 'tombol tombol-hantu tombol-ikon');
  btnUbah.type = 'button';
  btnUbah.setAttribute('aria-label', 'Ubah target tabungan ' + t.name);
  btnUbah.title = 'Ubah target';
  btnUbah.appendChild(ikon('edit'));
  btnUbah.addEventListener('click', () => formTargetTabungan(host, d.akun_bisa_dipakai, t));
  aksi.appendChild(btnUbah);

  const btnArsip = el('button', 'tombol tombol-hantu tombol-ikon tombol-bahaya');
  btnArsip.type = 'button';
  btnArsip.setAttribute('aria-label', 'Arsipkan target tabungan ' + t.name);
  btnArsip.title = 'Arsipkan target';
  btnArsip.appendChild(ikon('hapus'));
  btnArsip.addEventListener('click', () => formArsipTarget(host, t));
  aksi.appendChild(btnArsip);
  kepala.appendChild(aksi);
  host.appendChild(kepala);

  /* Angka: terkumpul dari target, total dari target — langsung dari server. */
  const angka = el('p', 'mt-2 mb-0');
  angka.appendChild(el('span', 'angka-stat text-(--color-income)', rupiah(t.terkumpul)));
  /* Spasi eksplisit: teks yang ditempel langsung setelah <span> kehilangan
     spasi di HTML ("Rp 0dari Rp 14.500.000"). Ditulis sebagai teks dengan
     spasi di depan, bukan diserahkan pada jarak visual. */
  angka.appendChild(el('span', 'ml-2 text-[13px] text-gray-500 dark:text-gray-400',
    ' dari ' + rupiah(t.target_amount)));
  host.appendChild(angka);

  /* Bar progres. Lebarnya dari `persen` server, TAPI dibatasi 100 supaya
     tidak meluber keluar kotak — angkanya tetap ditulis apa adanya di
     sebelahnya, jadi tidak ada dua bacaan berbeda (jawabanku ke monica). */
  const persen = Number(t.persen) || 0;
  const lebar = Math.max(0, Math.min(100, persen));
  const bar = el('div', 'mt-3 h-2 w-full rounded-full bg-gray-200 dark:bg-gray-800');
  /* Position dipasang INLINE, bukan lewat kelas `relative`/`absolute`:
     keduanya TIDAK ADA di web/tailwind.css hasil build (diperiksa dengan
     pencarian literal di berkas build, bukan ditebak). Menambahkannya
     berarti menjalankan `npm run css` — dilarang kartu ini.
     `overflow-hidden` juga DILEPAS dari sini: penanda skala 50% menonjol
     keluar bar, dan `overflow-hidden` akan memotongnya. Yang butuh
     pemotongan adalah isinya saja (sudut membulat), dan itu dipasang di
     elemen isi. */
  bar.style.position = 'relative';
  bar.setAttribute('role', 'progressbar');
  bar.setAttribute('aria-valuemin', '0');
  bar.setAttribute('aria-valuemax', '100');
  bar.setAttribute('aria-label', 'Progres target tabungan');

  /* ── Kenapa `aria-valuenow` memakai `lebar`, bukan `persen` (F-2) ─────
     Sebelumnya di sini `aria-valuenow` = `persen`, yang bisa > 100 (target
     terlampaui — dan itu memang tidak di-cap, kelebihan itu informasi).
     Tapi `aria-valuemax` = 100, jadi saat persen 140 atributnya berbunyi
     "140 dari maksimum 100" — nilai di luar rentangnya sendiri. Itu ARIA
     tidak sah, dan pembaca layar boleh mengabaikan seluruh progressbar-nya
     karena itu; satu bug kecil bisa menghapus seluruh informasi bar.

     Perbaikan: `aria-valuenow` = `lebar` (0–100, selalu di dalam rentang),
     dan angka sebenarnya pindah ke `aria-valuetext` sebagai kalimat. Jadi
     tidak ada informasi yang hilang — justru lebih: pembaca layar kini
     mendengar nominalnya, bukan cuma angka persen telanjang. */
  bar.setAttribute('aria-valuenow', String(Math.round(lebar)));
  /* Status dari SERVER (aturan 3b), bukan dihitung dari persen. Dipakai di
     kalimat `aria-valuetext` di bawah, jadi harus dihitung lebih dulu. */
  const labelStatus = t.status === 'tercapai' ? 'Tercapai'
    : t.status === 'belum_mulai' ? 'Belum mulai' : 'Berjalan';
  /* Kalimat lengkap, urutan: terkumpul, target, persen asli, status.
     `persen` ASLI (bukan `lebar`) — "140 persen" itu fakta, dan menyensor
     jadi "100" justru menyembunyikan bahwa targetnya sudah lewat. */
  bar.setAttribute('aria-valuetext',
    'Terkumpul ' + rupiah(t.terkumpul) + ' dari ' + rupiah(t.target_amount)
    + ', ' + persen + ' persen, ' + labelStatus.toLowerCase() + '.');

  const isi = el('div', 'h-full rounded-full transition-[width] duration-300');
  isi.style.width = lebar + '%';
  /* Tercapai -> hijau; belum mulai -> abu (jangan terlihat seperti gagal). */
  isi.style.background = t.status === 'tercapai' ? 'var(--color-income)'
    : t.status === 'belum_mulai' ? 'var(--color-transfer)' : 'var(--color-income)';
  bar.appendChild(isi);

  /* ── Penanda skala 50% (F-2) ─────────────────────────────────────────
     Tanpa acuan di tengah, bar 8px sulit dinilai "sudah separuh atau belum"
     tanpa mengukur dengan mata.

     🔴 PENANDA INI DIPINDAH KE LUAR BAR, dan itu hasil pengukuran, bukan
     selera. Percobaan pertama menaruhnya DI DALAM bar (garis 1px
     `currentColor` opacity 0,5). Diukur: penanda itu harus kontras ≥3:1
     terhadap ISI bar (hijau `#067647`) dan terhadap TRACK (`#e5e7eb`) —
     dua latar yang luminansinya berjauhan. Rentangnya kosong, persis
     masalah yang F-1 sudah buktikan pada track-vs-batang: tidak ada satu
     warna yang lulus keduanya. Menambah token warna baru dilarang kartu.

     Solusi: penanda digambar sebagai goresan yang MENONJOL keluar dari bar
     (atas & bawah), jadi latarnya adalah KARTU, bukan isi bar atau track.
     Dengan begitu ia cuma perlu lulus sekali terhadap satu latar, dan itu
     bisa diukur: `currentColor` opacity 0,55 → 3,96:1 (terang) / 5,61:1
     (gelap), sama dengan garis rata-rata di grafik tren.

     `aria-hidden="true"`: ini hiasan skala, bukan data. Angkanya sudah
     dibawa teks "52% dari target" dan `aria-valuetext`; membiarkannya
     terbaca hanya menambah node kosong di pohon aksesibilitas. */
  const penanda = el('div', '');
  penanda.style.position = 'absolute';
  penanda.style.left = '50%';
  penanda.style.top = '-3px';
  penanda.style.bottom = '-3px';
  penanda.style.width = '1px';
  penanda.style.background = 'currentColor';
  penanda.style.opacity = '0.55';
  penanda.setAttribute('aria-hidden', 'true');
  bar.appendChild(penanda);

  host.appendChild(bar);

  const barisPersen = el('div', 'mt-1 flex items-baseline justify-between gap-3');
  barisPersen.appendChild(el('span', 'text-[13px] font-semibold', persen + '% dari target'));
  barisPersen.appendChild(el('span', 'text-[12px] text-gray-500 dark:text-gray-400', labelStatus));
  host.appendChild(barisPersen);

  /* ── Sisa / kelebihan ────────────────────────────────────────────────
     `sisa` bisa NEGATIF kalau tabungan melebihi target. Ditulis "Lebih X",
     bukan "kurang Rp -X" — angka negatif di kalimat "kurang" mudah salah
     dibaca (kutulis ke monica, dia setuju). */
  const sisa = Number(t.sisa) || 0;
  if (sisa > 0) {
    host.appendChild(el('p', 'mt-3 mb-0 text-[13px]',
      'Kurang ' + rupiah(sisa) + (t.target_date ? ' · tenggat ' + dateLabel(t.target_date) : '')));
  } else if (sisa < 0) {
    const p = el('p', 'mt-3 mb-0 text-[13px] font-medium text-(--color-income)');
    p.appendChild(document.createTextNode('Lebih ' + rupiah(Math.abs(sisa))));
    p.appendChild(document.createTextNode(' dari target'));
    host.appendChild(p);
  } else {
    host.appendChild(el('p', 'mt-3 mb-0 text-[13px] font-medium text-(--color-income)',
      'Tepat di target'));
  }

  /* ── Perkiraan ───────────────────────────────────────────────────────
     Aturan 3a: null JANGAN jadi "0 bulan". Kalau rata-rata belum ada,
     tulis kalimatnya — "perkiraan 0 bulan lagi" akan terbaca "target sudah
     tercapai", dan itu menyesatkan.

     Tiga keadaan, dan yang ketiga mudah salah: kalau target SUDAH terlampaui,
     `perkiraan_bulan_lagi` juga null (server: `sisa > 0` jadi syarat). Jadi
     null TIDAK selalu berarti "belum cukup data" — bisa juga "sudah selesai".
     Menulis "belum cukup untuk memperkirakan" di situ akan salah: yang
     sebenarnya terjadi justru targetnya sudah lewat. */
  const rata = t.rata_setoran_bulanan;
  const perkiraan = t.perkiraan_bulan_lagi;
  const sudahLewat = Number(t.sisa) <= 0;

  if (rata === null || rata === undefined) {
    host.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Belum ada setoran, jadi belum bisa diperkirakan berapa lama lagi.'));
  } else if (perkiraan === null || perkiraan === undefined) {
    host.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      sudahLewat
        ? 'Rata-rata ' + rupiah(rata) + '/bulan. Tidak ada yang perlu diperkirakan — '
          + 'targetnya sudah terlampaui.'
        : 'Rata-rata ' + rupiah(rata) + '/bulan — belum cukup untuk memperkirakan '
          + 'kapan tercapai.'));
  } else if (perkiraan > 0) {
    host.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Rata-rata ' + rupiah(rata) + '/bulan · sekitar ' + perkiraan
      + ' bulan lagi kalau konsisten.'));
  } else {
    host.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Rata-rata ' + rupiah(rata) + '/bulan. Target sudah tercapai.'));
  }

  /* ── Aturan 3c: sebut bedanya kalau riwayat setoran ≠ terkumpul ──────
     Kalau pernah menarik, "total menabung" dari riwayat akan lebih besar
     dari `terkumpul`. Itu benar — tapi tanpa penjelasan terlihat seperti
     salah hitung. */
  const setoran = (t.riwayat_setoran || []).reduce((j, x) => j + (Number(x.total) || 0), 0);
  const tarikan = (t.riwayat_penarikan || []).reduce((j, x) => j + (Number(x.total) || 0), 0);
  if (setoran > 0 && setoran !== Number(t.terkumpul)) {
    host.appendChild(el('p', 'mt-2 mb-0 text-[12px] leading-snug text-gray-500 dark:text-gray-400',
      'Pernah disetor ' + rupiah(setoran) + (tarikan > 0 ? ' dan ditarik ' + rupiah(tarikan) : '')
      + '. Yang dihitung di atas adalah saldo akun sekarang, bukan total setoran.'));
  }

  /* ── Aturan 3d: `catatan` wajib tampil ───────────────────────────────── */
  if (d.catatan) {
    host.appendChild(el('p', 'mt-3 mb-0 border-t border-gray-100 pt-2 text-[12px] '
      + 'leading-snug text-gray-500 dark:border-gray-800 dark:text-gray-400', d.catatan));
  }
}

/* ── Form pasang / ubah target ───────────────────────────────────────────
   `target` null = pasang baru; ada isinya = ubah (server mengarsipkan yang
   lama otomatis, jadi UI tidak perlu menghapus dulu). */
function formTargetTabungan(host, akunBisa, target) {
  host.textContent = '';

  const bidang = (idTeks, teksLabel, jenis, nilai) => {
    const l = el('label', 'text-xs font-medium', teksLabel);
    l.setAttribute('for', idTeks);
    const i = el('input', 'min-h-tap w-full rounded-lg border border-gray-300 px-3 py-2 '
      + 'text-[15px] dark:border-gray-700 dark:bg-gray-900');
    i.id = idTeks;
    i.type = jenis;
    if (nilai !== undefined && nilai !== null) i.value = nilai;
    return [l, i];
  };

  const [lNama, iNama] = bidang('target-nama', 'Nama target', 'text', target ? target.name : '');
  iNama.maxLength = 40;
  iNama.placeholder = 'cth: Dana Darurat';

  const [lJml, iJml] = bidang('target-jumlah', 'Jumlah target total (Rp)', 'number',
    target ? target.target_amount : '');
  iJml.min = '1';
  iJml.step = '1';
  iJml.inputMode = 'numeric';

  /* Akun: chip seperti di form lain — pilihan yang sama, bentuk yang sama. */
  const lAkun = el('label', 'text-xs font-medium', 'Akun tabungan');
  const rowAkun = el('div', 'flex flex-wrap gap-2');
  const akunAktif = (akunBisa || []);
  let akunPilih = target ? target.account_id : (akunAktif[0] ? akunAktif[0].id : null);
  akunAktif.forEach((a) => {
    const b = el('button', 'chip', a.name);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(a.id === akunPilih));
    b.addEventListener('click', () => {
      akunPilih = a.id;
      Array.from(rowAkun.children).forEach((x) =>
        x.setAttribute('aria-pressed', String(x === b)));
    });
    rowAkun.appendChild(b);
  });

  const petunjuk = el('p', 'm-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Ini target TOTAL — satu angka yang mau dikumpulkan, bukan sisihan per bulan. '
    + 'Progres dihitung dari saldo akun yang dipilih, jadi menabung di akun lain '
    + 'tidak menggeser progresnya.');

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const barisTombol = el('div', 'flex gap-2');
  const simpan = el('button', 'tombol tombol-utama flex-1', target ? 'Simpan target' : 'Pasang target');
  simpan.type = 'button';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { renderTargetTabungan(); });

  simpan.addEventListener('click', async () => {
    pesan.hidden = true;
    const nama = iNama.value.trim();
    const jumlah = Math.round(Number(iJml.value || 0));
    if (!nama) { pesan.textContent = 'Nama target tidak boleh kosong.'; pesan.hidden = false; iNama.focus(); return; }
    if (!(jumlah > 0)) { pesan.textContent = 'Target harus lebih besar dari nol.'; pesan.hidden = false; iJml.focus(); return; }
    if (!akunPilih) { pesan.textContent = 'Pilih akun tabungan dulu.'; pesan.hidden = false; return; }

    formPulihkan(simpan, target ? 'Simpan target' : 'Pasang target');
    simpan.disabled = true;
    simpan.setAttribute('aria-busy', 'true');
    simpan.textContent = 'Menyimpan…';
    try {
      const r = await fetchSesi('/api/savings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: nama, target_amount: jumlah, account_id: akunPilih }),
      });
      const j = await r.json().catch(() => null);
      if (!j) { pesan.textContent = 'Server membalas bukan JSON (HTTP ' + r.status + ').'; pesan.hidden = false; formPulihkan(simpan, target ? 'Simpan target' : 'Pasang target'); return; }
      if (!j.ok) { pesan.textContent = j.message || j.error || 'Gagal menyimpan target.'; pesan.hidden = false; formPulihkan(simpan, target ? 'Simpan target' : 'Pasang target'); return; }
      toast(j.target && j.target.name ? 'Target ' + j.target.name + ' disimpan' : 'Target disimpan');
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false; formPulihkan(simpan, target ? 'Simpan target' : 'Pasang target');
    }
  });

  host.className = 'kartu mt-3 flex flex-col gap-3';
  [lNama, iNama, lJml, iJml, lAkun, rowAkun, petunjuk, pesan, barisTombol]
    .forEach((n) => host.appendChild(n));
  barisTombol.appendChild(simpan);
  barisTombol.appendChild(batal);
  iNama.focus();
}

/* ── Arsipkan target: konfirmasi dua langkah ─────────────────────────────
   Arsipkan, BUKAN hapus — datanya tetap ada di database, panel berhenti
   menampilkannya. Kamu bisa memasang target baru kapan saja. */
function formArsipTarget(host, target) {
  host.textContent = '';
  host.className = 'kartu mt-3 flex flex-col gap-3';

  host.appendChild(el('p', 'm-0 text-sm font-semibold text-(--color-expense)',
    'Arsipkan target ini?'));
  const rincian = el('p', 'm-0 text-xs leading-snug text-gray-600 dark:text-gray-300');
  rincian.textContent = target.name + ' · ' + rupiah(target.target_amount)
    + ' · akun ' + target.account_name;
  host.appendChild(rincian);
  host.appendChild(el('p', 'm-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Targetnya berhenti ditampilkan, tapi datanya tetap tersimpan. Tabungannya '
    + 'sendiri tidak terpengaruh — uangnya tetap di akun ' + target.account_name + '.'));

  const pesan = el('p', 'm-0 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const barisTombol = el('div', 'flex gap-2');
  const ya = el('button', 'tombol tombol-utama flex-1', 'Ya, arsipkan');
  ya.type = 'button';
  ya.style.cssText = 'background:var(--color-expense);color:#fff;';
  const batal = el('button', 'tombol tombol-hantu flex-1', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { renderTargetTabungan(); });

  ya.addEventListener('click', async () => {
    ya.disabled = true;
    ya.setAttribute('aria-busy', 'true');
    ya.textContent = 'Mengarsipkan…';
    try {
      const r = await fetchSesi('/api/savings', { method: 'DELETE' });
      const j = await r.json().catch(() => null);
      if (!j || !j.ok) {
        pesan.textContent = (j && (j.message || j.error)) || 'Gagal mengarsipkan target.';
        pesan.hidden = false; formPulihkan(ya, 'Ya, arsipkan'); return;
      }
      toast('Target diarsipkan');
      await refresh();
    } catch (e) {
      pesan.textContent = 'Server tidak menjawab. Coba lagi.';
      pesan.hidden = false; formPulihkan(ya, 'Ya, arsipkan');
    }
  });

  [pesan, barisTombol].forEach((n) => host.appendChild(n));
  barisTombol.appendChild(ya);
  barisTombol.appendChild(batal);
  batal.focus();
}

/* ══ CHAT: parse → konfirmasi → simpan (DUA langkah, tidak digabung) ═════ */

function chatBubble(text, kind) {
  const b = el('div', 'gelembung gelembung-' + (kind || 'bot'), text);
  $('chatlog').appendChild(b);
  scrollChat();
  return b;
}
function scrollChat() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function flowChips(current, onChange) {
  const row = el('div', 'flex flex-wrap gap-2');
  FLOW_ORDER.forEach((ft) => {
    const b = el('button', 'chip chip-flow', FLOW[ft].label);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(ft === current));
    b.addEventListener('click', () => {
      Array.from(row.children).forEach((c) =>
        c.setAttribute('aria-pressed', String(c === b)));
      onChange(ft);
    });
    row.appendChild(b);
  });
  return row;
}

/* Alasan pertama yang menghalangi simpan, atau null.
   Transfer tanpa akun tujuan PASTI ditolak server ("akun tujuan tidak
   disebutkan"), dan tujuan yang sama dengan asal juga ("transfer ke akun yang
   sama tidak masuk akal"). Lebih jujur menonaktifkan tombolnya di sini
   daripada membiarkan Deny menekan Simpan lalu menunggu galat. */
function alasanTolakSimpan(items) {
  for (const it of items) {
    if (it.flow_type !== 'transfer') continue;
    if (!it.to_account_hint) {
      return 'Pindah akun butuh akun tujuan — pilih di kartu draft sebelum menyimpan.';
    }
    if (it.to_account_hint === it.account_hint) {
      return 'Akun tujuan tidak boleh sama dengan akun asal.';
    }
  }
  return null;
}

/* Kartu draft untuk satu transaksi hasil /api/parse.
   mengembalikan { node, get } — get() mengembalikan payload siap /api/save.
   `onChange` dipanggil setiap kali pilihan di kartu berubah, supaya pemanggil
   bisa menghitung ulang keadaan tombol Simpan. */
function draftCard(d, index, total, onChange) {
  /* Nama akun TUJUAN dari parser, dicocokkan ke akun aktif seperti akun asal.
     `account_hint` = akun ASAL, `to_account_hint` = akun TUJUAN (CONTRACT.md).
     Kalau tidak ada yang cocok, tebakan parser DIPERTAHANKAN apa adanya:
     server yang menolak dengan pesan berperan ("akun tujuan 'X' tidak
     ditemukan"), dan pesan itu ditampilkan tanpa diterjemahkan di klien. */
  const hintTujuan = (() => {
    const h = String(d.to_account_hint || '').trim().toLowerCase();
    if (!h) return null;
    const hit = state.accounts.find((a) => a.is_active && a.name.toLowerCase() === h)
      || state.accounts.find((a) => a.is_active && a.name.toLowerCase().includes(h));
    return hit ? hit.name : d.to_account_hint;
  })();

  const item = {
    occurred_on: d.occurred_on || todayISO(),
    direction: d.direction || 'out',
    flow_type: d.flow_type || 'expense',
    amount: d.amount,
    note: d.note || '',
    category: d.category || null,
    account_hint: resolveHint(d.account_hint),
    to_account_hint: hintTujuan,
    assumed_date: !!d.assumed_date,
  };

  const wrap = el('div', 'draft-item');
  const head = el('div', 'draft-kepala');
  head.appendChild(el('span', null, total > 1 ? 'Draft ' + (index + 1)
    + ' dari ' + total : 'Draft transaksi'));
  head.appendChild(el('span', 'draft-acc', 'akun ' + (item.account_hint || 'tidak pasti')));
  wrap.appendChild(head);

  const body = el('div', 'draft-item');

  /* jumlah */
  body.appendChild(el('p', 'angka-draft', rupiah(item.amount)));
  if (item.note) body.appendChild(el('p', 'mb-3 text-sm text-gray-500 dark:text-gray-400 break-words', item.note));

  /* Sifat transaksi — chip koreksi (bagian D handoff) */
  const fflow = el('div', 'draft-bidang');
  fflow.appendChild(el('label', null, 'Sifat transaksi'));
  const chipRow = flowChips(item.flow_type, (ft) => {
    item.flow_type = ft;
    item.direction = FLOW_TO_DIRECTION[ft];
    /* transfer tidak punya kategori di db.py */
    fflow.querySelector('.flowwarn').hidden = (ft !== 'transfer');
    /* chip akun tujuan hanya relevan untuk transfer */
    ftujuan.hidden = (ft !== 'transfer');
    if (onChange) onChange();
  });
  fflow.appendChild(chipRow);
  const warn = el('p', 'teks-peringatan flowwarn',
    'Pindah akun: kategori tidak dipakai, dan akun tujuan wajib dipilih.');
  warn.hidden = item.flow_type !== 'transfer';
  fflow.appendChild(warn);
  body.appendChild(fflow);

  /* akun — chip, bukan dropdown. Parser sering menebak salah atau kosong,
     jadi Deny harus bisa mengoreksi akun di layar ini juga. */
  const facc = el('div', 'draft-bidang');
  facc.appendChild(el('label', null, 'Akun'));
  const arow = el('div', 'flex flex-wrap gap-2');
  state.accounts.filter((a) => a.is_active).forEach((a) => {
    const b = el('button', 'chip', a.name);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(a.name === item.account_hint));
    b.addEventListener('click', () => {
      item.account_hint = a.name;
      Array.from(arow.children).forEach((c) => c.setAttribute('aria-pressed',
        String(c === b)));
      const lbl = wrap.querySelector('.draft-acc');
      if (lbl) lbl.textContent = 'akun ' + a.name;
      /* akun tujuan tidak boleh sama dengan asal — daftarnya digambar ulang */
      gambarTujuan();
      if (onChange) onChange();
    });
    arow.appendChild(b);
  });
  facc.appendChild(arow);
  /* Monica menghapus perilaku "diam-diam pakai akun default": /api/save kini
     gagal keras kalau akun tidak cocok, bukan menyimpan ke akun lain. Jadi
     pesannya harus jujur — tebakannya memang diganti, dan Deny perlu
     memastikan pilihannya benar karena simpan akan gagal kalau keliru. */
  if (d.account_hint && !state.accounts.some((a) =>
        a.name.toLowerCase() === String(d.account_hint).toLowerCase())) {
    facc.appendChild(el('p', 'teks-peringatan',
      'Parser menebak akun "' + d.account_hint + '", akun itu tidak ada. '
      + 'Dipakai ' + (item.account_hint || 'akun terbesar')
      + ' — periksa dulu, karena simpan gagal kalau akunnya keliru.'));
  }
  body.appendChild(facc);

  /* Akun TUJUAN — hanya untuk transfer. Daftarnya akun aktif yang sama
     dengan chip asal, dan akun yang sedang jadi asal DINONAKTIFKAN: server
     menolak "transfer ke akun yang sama tidak masuk akal", jadi pilihannya
     tidak ditawarkan sejak awal. Yang dikirim tetap NAMA (to_account_hint),
     bukan id — server yang mencocokkan, klien tidak menebak. */
  const ftujuan = el('div', 'draft-bidang');
  ftujuan.appendChild(el('label', null, 'Akun tujuan'));
  const trow = el('div', 'flex flex-wrap gap-2');
  const tcatatan = el('p', 'teks-peringatan');
  tcatatan.hidden = true;
  /* Alasan chip-asal dinonaktifkan ditulis di layar, bukan hanya di `title`:
     `title` tidak muncul di layar sentuh dan tidak dibacakan andal, jadi
     tanpa baris ini Deny hanya melihat chip yang tidak bereaksi. */
  const tasal = el('p', 'm-0 basis-full text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Akun asal tidak bisa dipilih sebagai akun tujuan.');
  tasal.hidden = true;

  function gambarTujuan() {
    trow.textContent = '';
    const aktif = state.accounts.filter((a) => a.is_active);
    if (!aktif.length) {
      trow.appendChild(el('span', 'text-xs text-gray-500 dark:text-gray-400',
        'Daftar akun tidak bisa dimuat.'));
      return;
    }
    aktif.forEach((a) => {
      const b = el('button', 'chip', a.name);
      b.type = 'button';
      b.disabled = (a.name === item.account_hint);
      if (b.disabled) b.title = 'Sudah dipakai sebagai akun asal.';
      b.setAttribute('aria-pressed', String(a.name === item.to_account_hint));
      b.addEventListener('click', () => {
        item.to_account_hint = a.name;
        Array.from(trow.children).forEach((c) => c.setAttribute('aria-pressed',
          String(c === b)));
        tcatatan.hidden = true;
        if (onChange) onChange();
      });
      trow.appendChild(b);
    });
    /* Tujuan dari parser yang tidak ada di daftar: jangan dihapus diam-diam.
       Katakan apa adanya dan biarkan server menolak dengan pesan berperannya
       ("akun tujuan 'X' tidak ditemukan") — itu yang ditampilkan ke Deny. */
    if (item.to_account_hint
        && !aktif.some((a) => a.name === item.to_account_hint)) {
      tcatatan.textContent = 'Akun tujuan dari parser: "' + item.to_account_hint
        + '" — tidak ada di daftar akun aktif. Pilih salah satu di atas, atau '
        + 'simpan dan biarkan server menolaknya dengan pesan aslinya.';
      tcatatan.hidden = false;
    }
    tasal.hidden = !aktif.some((a) => a.name === item.account_hint);
  }
  gambarTujuan();
  ftujuan.appendChild(trow);
  ftujuan.appendChild(tasal);
  ftujuan.appendChild(tcatatan);
  ftujuan.hidden = item.flow_type !== 'transfer';
  body.appendChild(ftujuan);

  /* kategori sebagai chip */
  const fcat = el('div', 'draft-bidang');
  fcat.appendChild(el('label', null, 'Kategori'));
  if (state.categories.length) {
    const crow = el('div', 'flex flex-wrap gap-2');
    const pick = (name, btn) => {
      item.category = name;
      Array.from(crow.children).forEach((c) =>
        c.setAttribute('aria-pressed', String(c === btn)));
    };
    state.categories
      .filter((c) => c.direction === item.direction)
      .forEach((c) => {
        const b = el('button', 'chip', c.name);
        b.type = 'button';
        b.setAttribute('aria-pressed', String(c.name === item.category));
        b.addEventListener('click', () => pick(c.name, b));
        crow.appendChild(b);
      });
    fcat.appendChild(crow);
  } else {
    const ro = el('input', null);
    ro.type = 'text';
    ro.value = item.category || '';
    ro.placeholder = 'kategori';
    ro.style.cssText = 'font:inherit;font-size:15px;padding:10px 12px;'
      + 'border:1px solid var(--line-strong);border-radius:8px;max-width:200px;'
      + 'min-height:44px;width:100%';
    ro.addEventListener('input', () => { item.category = ro.value || null; });
    fcat.appendChild(ro);
    fcat.appendChild(el('p', 'teks-peringatan',
      'Tebakan parser. Server pakai kategori ini kalau ada; kalau tidak dikenal, '
      + 'jatuh ke "Lainnya" — bukan gagal.'));
  }
  body.appendChild(fcat);

  /* tanggal — selalu bisa diubah */
  const fdate = el('div', 'draft-bidang');
  const dl = el('label', null, 'Tanggal');
  dl.setAttribute('for', 'd-' + index);
  fdate.appendChild(dl);
  const di = el('input', 'min-h-tap w-full max-w-55 rounded-lg border border-gray-300 px-3 py-2 text-[15px] dark:border-gray-700 dark:bg-gray-900');
  di.type = 'date';
  di.id = 'd-' + index;
  di.value = dayKey(item.occurred_on);
  di.addEventListener('change', () => {
    item.occurred_on = di.value || todayISO();
    item.assumed_date = false;
    assume.hidden = true;
  });
  fdate.appendChild(di);
  body.appendChild(fdate);

  /* penanda tanggal dianggap — jangan disembunyikan */
  const assume = el('div', 'peringatan');
  assume.appendChild(el('span', 'inline-block h-1.5 w-1.5 rounded-full bg-current'));
  assume.appendChild(el('span', null,
    'Tanggal dianggap hari ini — belum disebut di kalimatmu. Ubah kalau salah.'));
  assume.hidden = !item.assumed_date;
  body.appendChild(assume);

  wrap.appendChild(body);
  return { node: wrap, get: () => item };
}

function renderDraft(draft) {
  const list = draft.transactions || [];
  /* Buang kartu draft yang belum disimpan dari percakapan sebelumnya.
     Dua kartu sekaligus = Deny bisa menyimpan draft basi tanpa sadar. */
  document.querySelectorAll('#chatlog .draft').forEach((n) => n.remove());

  const box = el('div', 'draft');
  const head = el('div', 'draft-kepala');
  head.appendChild(el('span', null,
    list.length > 1 ? list.length + ' draft menunggu dicek' : 'Draft menunggu dicek'));
  box.appendChild(head);

  /* kalau lebih dari satu: daftar yang dicek satu-satu, bukan digabung */
  const cards = list.map((d, i) => draftCard(d, i, list.length, syncSimpan));
  cards.forEach((c) => box.appendChild(c.node));

  const foot = el('div', 'draft-item');
  const row = el('div', 'flex gap-3 mt-4');
  row.style.marginTop = '0';
  const save = el('button', 'tombol tombol-utama', list.length > 1
    ? 'Simpan ' + list.length + ' transaksi' : 'Simpan');
  save.type = 'button';

  /* Tombol Simpan mengikuti keadaan kartu, bukan cuma jumlah kartu: transfer
     tanpa tujuan (atau tujuan = asal) akan ditolak server, jadi tombolnya
     dimatikan dan alasannya ditulis di bawah — bukan dibiarkan ditekan lalu
     gagal. Dipanggil ulang oleh tiap chip lewat `onChange`. */
  function syncSimpan() {
    const alasan = alasanTolakSimpan(cards.map((c) => c.get()));
    save.disabled = !!alasan;
    save.title = alasan || '';
    alasanSimpan.textContent = alasan || '';
    alasanSimpan.hidden = !alasan;
  }
  const alasanSimpan = el('p', 'teks-peringatan');
  alasanSimpan.hidden = true;
  alasanSimpan.setAttribute('role', 'status');
  const drop = el('button', 'tombol tombol-hantu', 'Batal');
  drop.type = 'button';
  drop.addEventListener('click', () => {
    box.remove();
    chatBubble('Draft dibuang. Tidak ada yang tersimpan.', 'bot');
  });
  save.addEventListener('click', async () => {
    const items = cards.map((c) => c.get());
    /* buang field yang bukan milik /api/save supaya kontraknya bersih */
    const payload = items.map((it) => {
      const o = {
        occurred_on: it.occurred_on,
        direction: it.direction,
        flow_type: it.flow_type,
        amount: Math.round(Number(it.amount)),   /* integer, bukan string */
      };
      if (it.note) o.note = it.note;
      if (it.category) o.category = it.category;
      if (it.account_hint) o.account_hint = it.account_hint;
      /* Akun tujuan HANYA untuk transfer. Kalau draft transfer diubah jadi
         Pengeluaran, pilihan tujuan lama masih tersimpan di kartu — mengirimnya
         membuat server menolak ("flow_type 'expense' tidak boleh punya akun
         tujuan") padahal Deny tidak menyentuh apa pun soal tujuan. */
      if (it.flow_type === 'transfer' && it.to_account_hint) {
        o.to_account_hint = it.to_account_hint;
      }
      return o;
    });

    setBusy(save, true);
    drop.disabled = true;
    const res = await apiPost('/save', { transactions: payload });
    if (!res.ok) {
      setBusy(save, false);
      drop.disabled = false;
      const b = chatBubble('Gagal menyimpan: ' + (res.message || res.error
        || 'sebab tidak diketahui'), 'error');
      if (res.error === 'gagal_simpan') {
        b.appendChild(el('p', 'teks-peringatan',
          'Tidak ada yang tersimpan — server menyimpan semua-atau-tidak-sama-sekali.'));
      }
      const fix = el('button', 'tombol tombol-hantu tombol-kecil', 'Isi manual');
      fix.type = 'button';
      fix.style.marginTop = '12px';
      fix.addEventListener('click', () => { box.remove(); openManual(); });
      b.appendChild(fix);
      return;
    }
    box.remove();
    chatBubble('Tersimpan: ' + res.count + ' transaksi.', 'bot');
    const lunasDraft = res.hutang_lunas || [];
    toast('Tersimpan · ' + res.count + ' transaksi'
      + (lunasDraft.length
        ? ' · Cicilan ' + lunasDraft[0].nama_utang + ' ditandai lunas' : ''));
    hutangLunasBaru(lunasDraft);
    state.parsedAny = true;
    await refresh();
  });
  row.appendChild(save);
  row.appendChild(drop);
  foot.appendChild(row);
  foot.appendChild(alasanSimpan);
  box.appendChild(foot);

  syncSimpan();
  $('chatlog').appendChild(box);
  scrollChat();
}

/* Input manual — jalur yang tidak boleh diblokir kalau provider bermasalah */
function openManual() {
  /* satu kartu manual saja, jangan bertumpuk dengan draft lain */
  document.querySelectorAll('#chatlog .draft').forEach((n) => n.remove());

  const box = el('div', 'draft');
  const head = el('div', 'draft-kepala');
  head.appendChild(el('span', null, 'Isi manual'));
  box.appendChild(head);

  const body = el('div', 'draft-item');
  const item = {
    occurred_on: todayISO(), direction: 'out', flow_type: 'expense',
    amount: null, note: '', category: null,
    account_hint: defaultAccountName(),
  };
  /* Label akun ditulis SETELAH `item` ada. Sebelumnya baris ini di atas
     deklarasi `item`, jadi membuka "Isi manual" melempar ReferenceError
     ("Cannot access 'item' before initialization") dan kartunya tidak pernah
     tampil — jalur cadangan saat provider AI mati, mati juga. */
  head.appendChild(el('span', 'draft-acc', 'akun ' + (item.account_hint || 'tidak pasti')));

  /* akun: chip, bukan dropdown */
  const facc = el('div', 'draft-bidang');
  facc.appendChild(el('label', null, 'Akun'));
  const arow = el('div', 'flex flex-wrap gap-2');
  state.accounts.filter((a) => a.is_active).forEach((a) => {
    const b = el('button', 'chip', a.name);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(a.name === item.account_hint));
    b.addEventListener('click', () => {
      item.account_hint = a.name;
      Array.from(arow.children).forEach((c) => c.setAttribute('aria-pressed',
        String(c === b)));
    });
    arow.appendChild(b);
  });
  facc.appendChild(arow);
  body.appendChild(facc);

  /* arah */
  const fdir = el('div', 'draft-bidang');
  fdir.appendChild(el('label', null, 'Arah'));
  const drow = el('div', 'flex flex-wrap gap-2');
  [['out', 'Keluar'], ['in', 'Masuk']].forEach(([v, lbl]) => {
    const b = el('button', 'chip', lbl);
    b.type = 'button';
    b.setAttribute('aria-pressed', String(v === item.direction));
    b.addEventListener('click', () => {
      item.direction = v;
      item.flow_type = v === 'in' ? 'income' : 'expense';
      Array.from(drow.children).forEach((c) => c.setAttribute('aria-pressed',
        String(c === b)));
      sync();
    });
    drow.appendChild(b);
  });
  fdir.appendChild(drow);
  body.appendChild(fdir);

  /* jumlah */
  const famt = el('div', 'draft-bidang');
  const al = el('label', null, 'Jumlah (rupiah)');
  famt.appendChild(al);
  const ai = el('input');
  ai.type = 'text';
  ai.inputMode = 'numeric';
  ai.autocomplete = 'off';
  ai.placeholder = 'cth: 45000';
  ai.style.cssText = 'font:inherit;font-size:20px;padding:10px 12px;min-height:44px;'
    + 'border:1px solid var(--line-strong);border-radius:8px;width:100%;max-width:220px;'
    + 'font-variant-numeric:tabular-nums';
  ai.addEventListener('input', () => {
    const digits = ai.value.replace(/[^\d]/g, '');
    item.amount = digits ? parseInt(digits, 10) : null;
    ai.value = digits;
    sync();
  });
  famt.appendChild(ai);
  body.appendChild(famt);

  /* sifat */
  const fflow = el('div', 'draft-bidang');
  fflow.appendChild(el('label', null, 'Sifat transaksi'));
  const frow = flowChips(item.flow_type, (ft) => {
    item.flow_type = ft;
    item.direction = FLOW_TO_DIRECTION[ft];
    Array.from(drow.children).forEach((c) => c.setAttribute('aria-pressed',
      String(c.textContent.toLowerCase().startsWith(ft === 'income' ? 'masuk' : 'keluar'))));
    sync();
  });
  fflow.appendChild(frow);
  body.appendChild(fflow);

  /* catatan */
  const fnote = el('div', 'draft-bidang');
  const nl = el('label', null, 'Catatan (opsional)');
  fnote.appendChild(nl);
  const ni = el('input');
  ni.type = 'text';
  ni.placeholder = 'cth: makan malam';
  ni.style.cssText = 'font:inherit;font-size:15px;padding:10px 12px;min-height:44px;'
    + 'border:1px solid var(--line-strong);border-radius:8px;width:100%';
  ni.addEventListener('input', () => { item.note = ni.value; });
  fnote.appendChild(ni);
  body.appendChild(fnote);

  /* tanggal */
  const fdate = el('div', 'draft-bidang');
  const dl = el('label', null, 'Tanggal');
  fdate.appendChild(dl);
  const di = el('input', 'min-h-tap w-full max-w-55 rounded-lg border border-gray-300 px-3 py-2 text-[15px] dark:border-gray-700 dark:bg-gray-900');
  di.type = 'date';
  di.value = item.occurred_on;
  di.addEventListener('change', () => { item.occurred_on = di.value || todayISO(); });
  fdate.appendChild(di);
  body.appendChild(fdate);

  const foot = el('div', 'draft-item');
  const row = el('div', 'flex gap-3 mt-4');
  row.style.marginTop = '0';
  const save = el('button', 'tombol tombol-utama', 'Simpan');
  save.type = 'button';
  save.disabled = true;
  const alasanManual = el('p', 'teks-peringatan');
  alasanManual.hidden = true;
  alasanManual.setAttribute('role', 'status');
  const cancel = el('button', 'tombol tombol-hantu', 'Batal');
  cancel.type = 'button';
  cancel.addEventListener('click', () => box.remove());
  save.addEventListener('click', async () => {
    setBusy(save, true);
    const res = await apiPost('/save', {
      transactions: [{
        occurred_on: item.occurred_on, direction: item.direction,
        flow_type: item.flow_type, amount: item.amount,
        note: item.note || null, category: item.category || null,
      }],
    });
    if (!res.ok) {
      setBusy(save, false);
      sync();
      chatBubble('Gagal menyimpan: ' + (res.message || res.error), 'error');
      return;
    }
    box.remove();
    chatBubble('Tersimpan: ' + res.count + ' transaksi.', 'bot');
    const lunasManual = res.hutang_lunas || [];
    toast('Tersimpan'
      + (lunasManual.length
        ? ' · Cicilan ' + lunasManual[0].nama_utang + ' ditandai lunas' : ''));
    hutangLunasBaru(lunasManual);
    state.parsedAny = true;
    await refresh();
  });
  row.appendChild(save);
  row.appendChild(cancel);
  foot.appendChild(row);
  foot.appendChild(alasanManual);
  box.appendChild(foot);

  function sync() {
    if (item.flow_type === 'transfer') {
      save.disabled = true;
      save.title = 'Pindah akun butuh akun tujuan — isi lewat layar Catat (kartu draft).';
      alasanManual.textContent = save.title;
      alasanManual.hidden = false;
    } else {
      save.title = '';
      alasanManual.hidden = true;
      save.disabled = !(item.amount > 0);
    }
  }

  box.appendChild(body);
  $('chatlog').appendChild(box);
  scrollChat();
  ai.focus();
}

async function sendChat(text) {
  chatBubble(text, 'user');
  const send = $('btn-send');
  const icon = $('btn-send-icon');
  send.disabled = true;
  send.setAttribute('aria-busy', 'true');
  const old = icon.textContent;
  icon.textContent = '';
  const sp = el('span', 'spinner');
  sp.setAttribute('aria-hidden', 'true');
  icon.appendChild(sp);

  const res = await apiPost('/parse', { text: text });

  send.disabled = false;
  send.removeAttribute('aria-busy');
  icon.textContent = old;

  if (!res.ok) {
    /* Dua elemen terpisah, BUKAN appendChild ke gelembung teks: `chatBubble`
       mengisi textContent, jadi tombol yang di-append ke sana menempel
       langsung ke kalimatnya ("...environmentIsi manual"). Terukur di layar
       sebelum diperbaiki. Wadah pembungkus menjaga keduanya tetap berjarak. */
    const wadah = el('div', 'gelembung gelembung-error flex flex-col items-start');
    wadah.appendChild(el('p', 'm-0', res.message || res.error
      || 'sebab tidak diketahui'));
    const btn = el('button', 'tombol tombol-hantu tombol-kecil mt-3', 'Isi manual');
    btn.type = 'button';
    btn.addEventListener('click', () => openManual());
    wadah.appendChild(btn);
    $('chatlog').appendChild(wadah);
    scrollChat();
    return;
  }
  const d = res.draft || {};
  const list = d.transactions || [];

  /* bukan transaksi: balasan chat biasa, bukan kartu */
  if (!list.length) {
    chatBubble(d.question || 'Aku belum menangkap transaksi dari kalimat itu.');
    return;
  }
  renderDraft(d);
  if (d.question) chatBubble(d.question);
}

/* ══ Hutang — jadwal cicilan per utang (GET /api/debts) ══════════════════
   Sumber: LIST-HUTANG.md, dibaca server secara READ-ONLY. Halaman ini TIDAK
   menyentuh DB dan TIDAK menghitung angka keuangan apa pun — total per utang,
   jumlah cicilan, total semua, dan "cicilan berikutnya" semuanya sudah
   dihitung server (CONTRACT.md: UI tidak pernah menghitung angka keuangan).

   Kenapa ada: berkas LIST-HUTANG.md tidak punya penanda "sudah dibayar",
   jadi halaman ini menampilkan JADWAL (nominal + jatuh tempo), bukan progres
   cicilan. "Cicilan berikutnya" = yang pertama belum lewat tanggalnya,
   BUKAN "yang belum dibayar". Itu keterbatasan sumber, dan UI mengatakannya
   apa adanya. */
function hutangBaris(r) {
  /* Satu baris cicilan: nomor + jatuh tempo di kiri, nominal di kanan.
     Memakai .baris + .baris-nama + .angka-baris yang sudah ada.

     Cicilan yang sudah LUNAS (r.lunas) tetap DITAMPILKAN, tapi DICORET
     (strikethrough) dan diberi lencana "LUNAS" — bukan dihapus (keputusan
     Deny). Teks dicoret tetap wajib terbaca, jadi warnanya memakai pasangan
     aksesibel yang sudah dipakai di panel ini: text-gray-500 di mode terang
     (4,84:1 di atas putih) dan dark:text-gray-400 di mode gelap (6,82:1 di
     atas gray-900). Keduanya >=4,5:1 (WCAG AA) — tidak mengulang kasus F-3.
     Garis coret dipasang lewat inline style supaya nol ubah tailwind.css.
     Jarak baris ditambah lewat utility `py-4` (14->16px) yang HANYA
     dipasang di baris cicilan hutang, supaya tab Daftar (yang memakai
     .baris yang sama) tidak ikut berubah. */
  const li = el('li', 'baris py-4');
  const kiri = el('div', 'min-w-0 flex-1');
  const nama = el('p', 'baris-nama m-0 mb-2 font-medium',
    r.nomor + '. ' + r.jatuh_tempo_teks);
  if (r.lunas) nama.classList.add('text-gray-500', 'dark:text-gray-400');
  kiri.appendChild(nama);
  if (r.lunas) {
    const barisLencana = el('div', 'flex flex-wrap items-center gap-3');
    barisLencana.appendChild(el('span', 'lencana lencana-income', 'LUNAS'));
    if (r.lunas_pada) {
      barisLencana.appendChild(el('span',
        'text-[11px] text-gray-500 dark:text-gray-400',
        'ditandai ' + String(r.lunas_pada).slice(0, 10)));
    }
    kiri.appendChild(barisLencana);
  }
  li.appendChild(kiri);
  const nominal = el('div', 'shrink-0 text-right angka-baris', rupiah(r.nominal));
  if (r.lunas) nominal.classList.add('text-gray-500', 'dark:text-gray-400');
  li.appendChild(nominal);
  if (r.lunas) {
    /* coret: garis lewat teks, tapi teksnya sendiri tetap berwarna aksesibel */
    [nama, nominal].forEach((n) => { n.style.textDecoration = 'line-through'; });
  }
  return li;
}

/* Penghitung `id` unik untuk `<ul>` rincian lipatan di tab Hutang. Dipakai
   oleh aria-controls -> id. Bertambah tiap render; `id` hanya perlu unik di
   DOM saat itu (renderHutang membuang node lama sebelum menggambar ulang). */
let urutLipatHutang = 0;
/* Durasi animasi lipatan Hutang (ms). HARUS sinkron dengan .lipat-hutang-isi
   di web/src.css. Dipakai sebagai fallback timer — bukan mengandalkan
   transitionend, yang bisa tak terpicu kalau elemen berubah cepat. */
const DURASI_LIPAT = 240;

/* ── Peringatan jatuh tempo per kartu (permintaan Deny) ─────────────────────
   "setiap list hutang yang tanggalnya sudah mendekati H-2, munculkan tulisan
   warning bahwa itu tanggal terdekat jatuh tempo" + keputusan Deny: sisa ≤2
   hari (termasuk hari ini) DAN yang sudah lewat ikut ditandai.

   Mengapa TIDAK memakai `u.cicilan_berikutnya`: server hanya mengambil
   `jatuh_tempo >= hari_ini` (src/server.py:819-821), jadi cicilan yang SUDAH
   LEWAT tidak pernah muncul di sana — padahal Deny minta yang lewat ditandai.
   Kalau semua cicilan sudah lewat, `cicilan_berikutnya` bahkan null. Karena itu
   kita hitung sendiri dari `u.baris[]`.

   Fungsi MURNI (tanpa DOM, tanpa jam sistem kalau `today` diisi) supaya kasus
   batas bisa diuji tanpa menunggu tanggal nyata: `today` = 'YYYY-MM-DD'.
   Aturan:
     - ambil cicilan BELUM LUNAS (`r.lunas === false`) dengan `jatuh_tempo`
       PALING AWAL (bandingkan tanggal saja, format ISO -> perbandingan string);
     - tidak ada baris belum-lunas (semua lunas) -> null (NOL warning);
     - tanggal < hari ini -> {jenis:'terlambat', hari:N} (gaya tegas);
     - selisih 0/1/2 hari  -> {jenis:'dekat', hari:N} (warning biasa);
     - selisih > 2 hari    -> null (tidak muncul).
   Perhitungan selisih memakai `parseISO` (waktu LOKAL) — BUKAN
   `new Date('2026-10-13')` polos yang diinterpretasi UTC (bisa geser 1 hari di
   WIB). Dibulatkan karena selisih dua tengah-malam lokal bisa 23/25 jam saat
   pergantian DST. */
function hutangWarning(u, today) {
  const hariIni = today || todayISO();
  const baris = (u && u.baris) ? u.baris : [];
  let palingAwal = null;
  for (let i = 0; i < baris.length; i++) {
    const r = baris[i];
    if (r.lunas) continue;                       /* cicilan lunas tidak dihitung */
    const k = String(r.jatuh_tempo).slice(0, 10); /* tanggal saja, buang jam */
    if (palingAwal === null || k < palingAwal) palingAwal = k;
  }
  if (palingAwal === null) return null;          /* semua lunas -> nol warning */

  const tHari = parseISO(hariIni).getTime();
  const tJatuh = parseISO(palingAwal).getTime();
  const selisih = Math.round((tJatuh - tHari) / 86400000);

  if (selisih < 0) {
    return { jenis: 'terlambat', hari: -selisih, tanggal: palingAwal,
             teks: 'Terlambat ' + (-selisih) + ' hari' };
  }
  if (selisih === 0) {
    return { jenis: 'dekat', hari: 0, tanggal: palingAwal,
             teks: 'Jatuh tempo hari ini' };
  }
  if (selisih === 1) {
    return { jenis: 'dekat', hari: 1, tanggal: palingAwal,
             teks: 'Jatuh tempo besok' };
  }
  if (selisih === 2) {
    return { jenis: 'dekat', hari: 2, tanggal: palingAwal,
             teks: 'Jatuh tempo 2 hari lagi' };
  }
  return null;                                   /* >2 hari -> tidak ada warning */
}

/* Tampilan warning: pil berisi IKON segitiga + TEKS (bukan warna saja —
   aman untuk buta warna). Kelas .hutang-peringatan* ada di web/src.css. */
function hutangWarningEl(w) {
  const pil = el('p', 'hutang-peringatan mt-3 mb-0 '
    + (w.jenis === 'terlambat' ? 'hutang-peringatan-terlambat'
                               : 'hutang-peringatan-dekat'));
  const ik = el('span', 'hutang-peringatan-ikon');
  ik.setAttribute('aria-hidden', 'true');
  ik.appendChild(ikon('peringatan'));
  pil.appendChild(ik);
  pil.appendChild(el('span', null, w.teks + ' · ' + dateLabel(w.tanggal)));
  return pil;
}

function hutangKartu(u) {
  /* py-6 menambah padding vertikal (20->24px) HANYA di kartu hutang;
     `.kartu` sendiri tidak diubah supaya tab lain tidak ikut. */
  const kartu = el('div', 'kartu py-6');
  kartu.appendChild(el('p', 'm-0 text-sm font-semibold', u.nama));

  /* Baris ringkas: jumlah cicilan + TOTAL SISA per utang (angka dari server).
     `total_sisa` = total - yang sudah lunas. Kalau server versi lama belum
     mengirimnya (field tak ada), jatuh ke `total` supaya tidak menampilkan
     NaN — tapi tidak menghitung sendiri. */
  const sisa = (typeof u.total_sisa === 'number') ? u.total_sisa : u.total;
  const ringkas = el('p', 'mt-2 mb-0 text-[13px] text-gray-500 dark:text-gray-400',
    u.jumlah_cicilan + ' cicilan · sisa ' + rupiah(sisa));
  kartu.appendChild(ringkas);

  /* Berapa cicilan yang sudah lunas dari total (angka dari server). */
  if (u.jumlah_lunas > 0) {
    kartu.appendChild(el('p', 'mt-2 mb-0 text-[13px] text-(--color-income)',
      u.jumlah_lunas + ' dari ' + u.jumlah_cicilan + ' cicilan lunas'));
  }

  /* Cicilan berikutnya. Kalau null -> kalimat, BUKAN angka 0. */
  const next = el('p', 'mt-3 mb-0 text-[13px] leading-snug');
  if (u.cicilan_berikutnya) {
    next.appendChild(el('span', 'text-gray-500 dark:text-gray-400', 'Cicilan berikutnya: '));
    next.appendChild(el('span', 'font-semibold', rupiah(u.cicilan_berikutnya.nominal)));
    next.appendChild(el('span', 'text-gray-500 dark:text-gray-400',
      ' · ' + u.cicilan_berikutnya.jatuh_tempo_teks));
  } else {
    next.appendChild(el('span', 'text-gray-500 dark:text-gray-400',
      'Semua cicilan sudah lewat tanggal.'));
  }
  kartu.appendChild(next);

  /* Peringatan jatuh tempo ≤2 hari / terlambat — DI LUAR lipatan, jadi
     terlihat tanpa membuka rincian (permintaan Deny). Nol warning kalau tidak
     ada cicilan belum-lunas dalam rentang itu. */
  const warn = hutangWarning(u);
  if (warn) kartu.appendChild(hutangWarningEl(warn));

  /* Detail semua cicilan, dilipat default tertutup. Tetap memakai kelas
     bersama .txgroup-head + .chevron-lipat (konsisten dengan lipatan di layar
     Daftar), TAPI ditambah modifier KHUSUS HUTANG `.lipat-hutang` +
     `.lipat-hutang-isi` supaya animasi/hover hanya berlaku di tab Hutang —
     kelas bersama tidak disentuh (tab Daftar tetap apa adanya). */
  /* ARIA disclosure yang benar: tombol `aria-expanded` (sudah ada) +
     `aria-controls` -> `id` pada `<ul>` rincian. Chevron sudah `aria-hidden`
     (dari ikon()). Ini BUKAN listbox — tak ada daftar opsi / nilai terpilih,
     jadi role="listbox"/"option" salah semantik di sini dan TIDAK dipakai.
     Modifier `.lipat-hutang` khusus instance Hutang; kelas bersama
     `.txgroup-head`/`.chevron-lipat` (juga dipakai tab Daftar) tidak disentuh. */
  const idRincian = 'rincian-hutang-' + (++urutLipatHutang);
  const head = el('button', 'txgroup-head lipat-hutang mt-4');
  head.type = 'button';
  head.setAttribute('aria-expanded', 'false');
  head.setAttribute('aria-controls', idRincian);
  const kiri = el('span', 'flex min-w-0 items-center gap-1.5');
  const chev = el('span', 'chevron-lipat shrink-0');
  chev.appendChild(ikon('lipat'));
  kiri.appendChild(chev);
  kiri.appendChild(el('span', 'normal-case tracking-normal font-normal',
    'Rincian ' + u.jumlah_cicilan + ' cicilan'));
  head.appendChild(kiri);
  kartu.appendChild(head);

  const list = el('ul', 'lipat-hutang-isi m-0 list-none p-0 kartu kartu-rapat');
  list.id = idRincian;
  list.hidden = true;
  u.baris.forEach((r) => list.appendChild(hutangBaris(r)));
  kartu.appendChild(list);

  /* Buka-tutup beranimasi: tinggi (max-height 0 -> tinggi isi terukur) +
     opasitas; panah diputar 180° oleh aturan bersama
     `.txgroup-head[aria-expanded='true'] .chevron-lipat` (sudah ada).
     Timer DURASI_LIPAT = jaring aman supaya `hidden` tetap dipasang walau
     `transitionend` tak terpicu (tab tak terlihat / gerak dikurangi). Saat
     `prefers-reduced-motion: reduce`, CSS mematikan transisi → lipatan tetap
     berfungsi, hanya tanpa gerak. */
  let timerLipat = null;
  head.addEventListener('click', () => {
    const akanBuka = list.hidden;
    if (timerLipat) { clearTimeout(timerLipat); timerLipat = null; }
    if (akanBuka) {
      list.hidden = false;
      /* Paksa reflow: elemen baru keluar dari `hidden` (display:none). Tanpa
         pembacaan layout ini, browser bisa melewatkan transisi (dari keadaan
         display:none tak ada nilai awal untuk dianimasikan). */
      void list.offsetHeight;
      /* scrollHeight = tinggi isi penuh walau sedang terpotong max-height:0 */
      list.style.maxHeight = list.scrollHeight + 'px';
      list.classList.add('lipat-hutang-buka');
    } else {
      list.style.maxHeight = '0px';
      list.classList.remove('lipat-hutang-buka');
      timerLipat = setTimeout(() => {
        list.hidden = true;
        timerLipat = null;
      }, DURASI_LIPAT);
    }
    head.setAttribute('aria-expanded', akanBuka ? 'true' : 'false');
  });
  return kartu;
}

async function renderHutang() {
  const host = $('hutang-host');
  const ringkas = $('hutang-ringkas');
  if (!host) return;
  host.textContent = '';
  if (ringkas) ringkas.textContent = '';

  let d;
  try {
    d = await apiGet('/debts');
  } catch (e) {
    /* Endpoint tidak menjawab (mis. server versi lama -> 404, atau koneksi
       mati). Katakan dengan jelas; jangan biarkan halaman kosong. */
    const kotak = el('div', 'kartu');
    kotak.appendChild(el('p', 'm-0 mb-1 text-sm font-semibold',
      'Tidak bisa memuat jadwal hutang'));
    kotak.appendChild(el('p', 'm-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Server tidak menjawab /api/debts. Kalau server belum dijalankan ulang '
      + 'setelah endpoint ini ditambahkan, itu penyebabnya. Datamu tidak '
      + 'terpengaruh — tidak ada berkas yang diubah.'));
    host.appendChild(kotak);
    return;
  }

  /* Server membalas ok:false saat berkas hilang atau formatnya berubah.
     Tampilkan pesannya apa adanya — bukan tabel kosong tanpa keterangan. */
  if (!d || d.ok === false) {
    const kotak = el('div', 'kartu');
    kotak.appendChild(el('p', 'm-0 mb-1 text-sm font-semibold',
      'Jadwal hutang tidak bisa ditampilkan'));
    kotak.appendChild(el('p', 'm-0 text-[13px] leading-snug text-(--color-expense)',
      (d && d.message) || 'Server tidak memberi keterangan.'));
    host.appendChild(kotak);
    return;
  }

  /* Kartu ringkasan: total SISA + jumlah utang + berapa cicilan lunas.
     Semua angka dari server (`total_sisa_semua`, `total_lunas_semua`).
     `total_sisa_semua` belum ada di server versi lama -> jatuh ke
     `total_semua` supaya tidak menampilkan NaN. */
  if (ringkas) {
    const totalSisa = (typeof d.total_sisa_semua === 'number')
      ? d.total_sisa_semua : d.total_semua;
    const totalLunas = (typeof d.total_lunas_semua === 'number')
      ? d.total_lunas_semua : 0;
    const k = el('div', 'kartu py-6');
    k.appendChild(el('p', 'eyebrow m-0', 'Total sisa cicilan'));
    k.appendChild(el('p', 'angka-besar mt-1 mb-0', rupiah(totalSisa)));
    k.appendChild(el('p', 'mt-2 mb-0 text-[13px] text-gray-500 dark:text-gray-400',
      d.jumlah_utang + ' utang · diukur ' + d.hari_ini));

    /* Jumlah cicilan lunas dari total. Dihitung dari `utang[]` (angka server),
       bukan dari daftar transaksi — UI tidak menghitung angka keuangan. */
    if (totalLunas > 0) {
      let jmlLunas = 0, jmlCicilan = 0;
      (d.utang || []).forEach((u) => {
        jmlLunas += (u.jumlah_lunas || 0);
        jmlCicilan += (u.jumlah_cicilan || 0);
      });
      k.appendChild(el('p', 'mt-2 mb-0 text-[13px] font-medium text-(--color-income)',
        jmlLunas + ' dari ' + jmlCicilan + ' cicilan lunas · '
        + rupiah(totalLunas) + ' sudah dibayar'));
    }

    /* Entri "yatim": ditandai lunas tapi tak ada lagi di jadwal (mis. Deny
       menyunting LIST-HUTANG.md). Dilaporkan apa adanya; tidak dihitung. */
    if (d.yatim && d.yatim.length) {
      k.appendChild(el('p', 'mt-3 mb-0 text-[11px] text-(--color-debt)',
        d.yatim.length + ' penandaan lunas tidak lagi ada di jadwal (diabaikan).'));
    }

    k.appendChild(el('p', 'mt-3 mb-0 text-[11px] text-gray-500 dark:text-gray-400',
      'Sumber: ' + d.sumber + ' (baca saja). Sisa = total jadwal dikurangi '
      + 'cicilan yang sudah ditandai lunas.'));
    ringkas.appendChild(k);
  }

  (d.utang || []).forEach((u) => host.appendChild(hutangKartu(u)));
}

/* Banner "Cicilan X ditandai lunas" + tombol Batalkan.
   Muncul setelah transaksi disimpan (dipanggil dari renderDraft/openManual
   saat balasan /api/save memuat `hutang_lunas`). Tombol Batalkan memanggil
   POST /api/debts/batalkan, lalu menyegarkan tab Hutang.

   Kenapa banner, bukan toast: toast() auto-hilang 4,2 detik dan tak bisa
   memuat tombol. Banner ini tetap ada sampai dibatalkan/ditutup supaya Deny
   punya kesempatan membatalkan. */
function hutangLunasBaru(daftar) {
  if (!daftar || !daftar.length) return;
  /* Host global (di luar tab) supaya banner terlihat dari tab Catat MAUPUN
     Hutang. Jatuh ke #hutang-ringkas kalau host global tak ada (harness). */
  const host = $('hutang-lunas-host') || $('hutang-ringkas');
  if (!host) return;   /* tak ada host -> jangan melempar */

  daftar.forEach((h) => {
    const kotak = el('div', 'kartu');
    kotak.setAttribute('role', 'status');
    kotak.appendChild(el('p', 'm-0 text-sm font-semibold',
      'Cicilan ' + h.nama_utang + ' ditandai lunas'));

    const rinci = el('p', 'mt-1 mb-0 text-[13px] text-gray-500 dark:text-gray-400',
      'Cicilan ke-' + h.nomor + ' · ' + rupiah(h.nominal));
    kotak.appendChild(rinci);

    const row = el('div', 'mt-3 flex flex-wrap gap-3');
    const batal = el('button', 'tombol tombol-hantu tombol-kecil', 'Batalkan');
    batal.type = 'button';
    batal.addEventListener('click', async () => {
      setBusy(batal, true);
      let res;
      try {
        res = await apiPost('/debts/batalkan',
          { nama_utang: h.nama_utang, jatuh_tempo: h.jatuh_tempo });
      } catch (e) {
        if (String(e && e.message) === 'sesi_berakhir') return;
        res = { ok: false, message: 'Server tidak menjawab.' };
      }
      if (!res || res.ok === false) {
        setBusy(batal, false);
        toast((res && (res.message || res.error)) || 'Gagal membatalkan',
          'error');
        return;
      }
      kotak.remove();
      toast('Dibatalkan: ' + h.nama_utang + ' · cicilan ke-' + h.nomor);
      /* Segarkan tab Hutang supaya baris tercoret & total sisa kembali. */
      renderHutang().catch(() => {});
    });
    row.appendChild(batal);

    const tutup = el('button', 'tombol tombol-hantu tombol-kecil', 'Tutup');
    tutup.type = 'button';
    tutup.addEventListener('click', () => kotak.remove());
    row.appendChild(tutup);

    kotak.appendChild(row);
    host.appendChild(kotak);
  });
}

/* ══ Navigasi (navbar atas) ═══════════════════════════════════════════════
   Satu set tombol saja. Dulu ada bottom bar terpisah; sekarang tidak. */
function showTab(name) {
  const sebelumnya = state.tab;
  state.tab = name;

  ['home', 'catat', 'daftar', 'akun', 'analisa', 'hutang'].forEach((n) => {
    const v = $('view-' + n);
    if (!v) return;
    const tampil = (n === name);
    v.hidden = !tampil;
    /* Pasang ulang animasi masuk supaya terlihat setiap kali tab berganti,
       bukan hanya saat pertama dimuat. */
    if (tampil && sebelumnya !== name) {
      v.style.animation = 'none';
      void v.offsetWidth;          /* paksa browser menghitung ulang */
      v.style.animation = '';
    }
  });
  /* Analisa dimuat saat tabnya dibuka, bukan saat panel dimuat: datanya
     berat kalau kosong, dan Deny hampir selalu memakai tab lain dulu. */
  if (name === 'analisa' && sebelumnya !== 'analisa') {
    renderAnalisa(ANALISA_BULAN).catch((e) => {
      if (String(e && e.message) !== 'sesi_berakhir') {
        const host = $('analisa-host');
        if (host) {
          host.textContent = '';
          host.appendChild(el('p', 'kartu text-sm leading-snug',
            'Tidak bisa memuat analisa. Coba muat ulang halaman.'));
        }
      }
    });
  }
  /* Hutang juga dimuat saat tabnya dibuka, bukan saat panel dimuat — pola yang
     sama dengan Analisa. Kalau gagal (mis. server versi lama yang belum punya
     /api/debts, atau sesi berakhir), halamannya menampilkan keterangan yang
     jelas; TIDAK dibiarkan kosong tanpa penjelasan. */
  if (name === 'hutang' && sebelumnya !== 'hutang') {
    renderHutang().catch((e) => {
      if (String(e && e.message) !== 'sesi_berakhir') {
        const host = $('hutang-host');
        if (host) {
          host.textContent = '';
          host.appendChild(el('p', 'kartu text-sm leading-snug',
            'Tidak bisa memuat jadwal hutang. Coba muat ulang halaman.'));
        }
      }
    });
  }
  document.querySelectorAll('.navtab').forEach((t) => {
    if (t.dataset.tab === name) t.setAttribute('aria-current', 'page');
    else t.removeAttribute('aria-current');
  });
  if (name === 'catat') {
    /* Panel cek AI diisi saat tab Catat dibuka — pola yang sama dengan
       halaman Analisa: tidak perlu diperiksa kalau tabnya belum dilihat. */
    periksaStatusAI(false);
    setTimeout(() => $('chat-input').focus({ preventScroll: true }), 60);
  }
  /* Tab yang sama ditekan lagi: jangan lompat ke atas, Deny mungkin sedang
     membaca posisi tertentu. */
  if (sebelumnya !== name) {
    const turun = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, behavior: turun ? 'auto' : 'smooth' });
  }
}

async function refresh() {
  let s;
  try {
    s = await apiGet('/summary' + (state.month ? '?month=' + state.month : ''));
  } catch (e) {
    toast('Gagal membaca /api/summary — server mati?', 'error');
    return;
  }
  state.month = s.month;
  state.summary = s;
  /* state.accounts WAJIB dari /api/accounts, bukan s.accounts (summary).
     summary.accounts TIDAK punya is_active, sehingga filter(is_active) di
     akunIdDari/resolveHint/defaultAccountName menghasilkan daftar KOSONG —
     dan akibatnya tidak ada akun yang bisa dipilih saat menyimpan.
     Diambil di sini supaya semua pemakainya (draft chat, isi manual, chip
     akun) melihat sumber yang sama. Kalau endpoint akun mati, daftarnya
     kosong dan pemakainya menampilkan pesan jujur, bukan menebak. */
  try {
    const ra = await fetchSesi('/api/accounts?all=1', { cache: 'no-store' });
    const ja = await ra.json();
    state.accounts = ja.items || [];
  } catch (e) {
    state.accounts = [];
  }
  /* state.categories WAJIB dari /api/categories, bukan ditebak.
     Sejak panel ini dibuat, `state.categories` diisi `[]` dan TIDAK PERNAH
     diisi ulang — padahal /api/categories sudah ada dan mengembalikan 11
     kategori. Akibatnya chip kategori tidak pernah tampil di layar Catat
     (jatuh ke kolom teks bebas, sehingga salah ketik lolos ke /api/save),
     dan pemilih kategori di form edit hanya menulis "Tidak ada pilihan
     kategori". Diambil di sini — sebelum renderDaftar() di bawah — supaya
     semua pemakainya melihat daftar yang sama.
     Kalau endpointnya mati, daftarnya kosong dan pemakainya menampilkan
     pesan jujur; TIDAK diisi tebakan. */
  try {
    const rc = await fetchSesi('/api/categories', { cache: 'no-store' });
    const jc = await rc.json();
    state.categories = jc.items || [];
  } catch (e) {
    state.categories = [];
  }
  $('month-label').textContent = monthLabel(s.month);

  renderHero(s);
  renderStats(s);
  /* renderAkun async (mengambil /api/accounts). Kesalahannya ditangkap di
     dalam renderAkun sendiri, jadi tidak perlu .catch() di sini — tapi kalau
     lupa menulisnya sebagai async, panel Akun akan kosong tanpa pesan. */
  await renderAkun(s);
  /* Kartu target tabungan (GET /api/savings). Menggantikan panel saldo
     tabungan yang dulu di sini — lihat surat monica "persetujuan-tabungan". */
  await renderTargetTabungan();
  /* Panel sisa bulan lalu di atas grafik tren. Dipanggil setelah `state`
     terisi supaya perbandingan "sekarang" langsung tersedia. */
  await renderSisaBulanLalu();

  const emptyBox = $('home-empty');
  const hasData = s.ada_data;
  /* ada_data:false -> kalimat, bukan angka 0 */
  if (!hasData) {
    emptyBox.hidden = false;
    $('home-empty-body').textContent =
      'Tidak ada transaksi tercatat di ' + monthLabel(s.month)
      + '. Angka di atas masih kekayaan hari ini, bukan angka bulan ini — '
      + 'dan pengeluaran bulan ini bukan nol, hanya belum dicatat.';
    $('stat-in').textContent = '—';
    $('stat-expense').textContent = '—';
    $('delta-value').textContent = '—';
  } else {
    emptyBox.hidden = true;
  }

  /* Kegagalan BUKAN keadaan data.
     Sebelumnya `catch` mengosongkan state.tx lalu panel menulis "Belum ada
     data" — kalau endpoint transaksi yang gagal, Deny melihat kalimat yang
     menyalahkan dirinya sendiri padahal dia punya 25 transaksi.
     Pola yang sama dengan grafik tren (lihat loadTrend): "kosong" dan
     "gagal dibaca" harus jadi dua keadaan yang berbeda. */
  let gagalTx = false;
  try {
    const tx = await apiGet('/transactions?month=' + s.month + '&limit=400');
    state.tx = tx.items || [];
  } catch (e) {
    state.tx = [];
    gagalTx = true;
  }
  renderRecent(state.tx, gagalTx);
  renderDaftar(state.tx, gagalTx);
  $('daftar-count').textContent = gagalTx
    ? `Tidak bisa memuat · ${monthLabel(s.month)}`
    : (hasData
       ? `${state.tx.length} transaksi · ${monthLabel(s.month)}`
       : `Belum ada data · ${monthLabel(s.month)}`);

  drawChart(await loadTrend(s.month));
  /* Kartu pengeluaran per kategori — bulan yang sedang dilihat panel.
     Ditaruh setelah grafik tren: tren menjawab "bagaimana keadaanku
     sepanjang waktu", kategori menjawab "apa yang harus kuubah". */
  await renderKategori();
}

/* ══ Panel cek jaringan AI (halaman Catat) ═════════════════════════════════
   Menjawab satu pertanyaan: apakah catat pintar bisa dipakai sekarang?

   TIGA ATURAN yang membentuk bentuk panel ini:

   1. EMPAT keadaan, bukan tiga. "Belum diperiksa" TIDAK boleh hijau — itu
      klaim sehat tanpa dasar, persis pola yang berkali-kali jadi bug di repo
      ini (kegagalan menyamar jadi keadaan normal).
   2. TIDAK ADA kolom URL/API key di sini, dan jangan ditambahkan. Kunci di UI
      = kunci di browser = kunci ikut ke cadangan DB & mungkin ke repo publik.
      Kunci hidup di env.sh di luar repo. Keputusan ini sudah ditolak sekali;
      alasannya lengkap di requests/CATATAN-BELUM-SELESAI.md §5b.
   3. Panel ini TIDAK memanggil model untuk sekadar cek lalu lintas. Setiap
      panggilan membakar kuota Deny. Status dibaca dari endpoint ringan
      /api/ai-status yang disediakan server — SUDAH ADA sejak monica
      menambahkannya (commit df19e56, didokumentasikan di CONTRACT.md §17).
      404 hanya muncul kalau server-nya versi lama; panel lalu jujur berkata
      "belum bisa diperiksa" — itu jalur cadangan, bukan keadaan normal.
*/
const AI_HOST = () => $('ai-host');

function renderStatusAI(w) {
  const host = AI_HOST();
  if (!host) return;
  host.textContent = '';

  /* `w` = { keadaan, judul, pesan, endpoint, model, latensi_ms }
     keadaan: 'ok' | 'lambat' | 'gagal' | 'belum'

     Kelasnya (.ai-panel/.ai-ok/…) ada di src.css, BUKAN ditulis sebagai
     kelas Tailwind lepas di sini: `bg-(--color-…-bg)` yang ditulis dari JS
     tidak menghasilkan CSS (diukur — lihat catatan di src.css). */
  /* Keadaan yang tidak dikenal jatuh ke 'belum', BUKAN ke 'ok'. Kalau server
     suatu hari mengirim keadaan baru yang belum dikenal UI ini, panelnya
     menampilkan "belum tahu" — bukan berpura-pura sehat. Kelas .ai-belum
     selalu ada, jadi tampilannya juga tidak rusak tanpa gaya. */
  const DIKENAL = ['ok', 'lambat', 'gagal', 'belum'];
  const kode = DIKENAL.indexOf(w.keadaan) > -1 ? w.keadaan : 'belum';

  const kartu = el('div', 'ai-panel ai-' + kode);

  /* Baris pertama: titik warna + judul + tombol periksa ulang.
     Keadaannya ditulis sebagai TEKS juga, bukan hanya warna — kalau hanya
     warna, panel ini tidak terbaca oleh yang buta warna. */
  const baris = el('div', 'flex items-center gap-2');
  const titik = el('span', 'ai-titik ai-judul-' + kode);
  titik.setAttribute('aria-hidden', 'true');
  baris.appendChild(titik);
  baris.appendChild(el('span', 'flex-1 ai-judul ai-judul-' + kode, w.judul));

  const btn = el('button', 'tombol tombol-hantu tombol-kecil shrink-0', 'Periksa');
  btn.type = 'button';
  btn.addEventListener('click', () => periksaStatusAI(true));
  baris.appendChild(btn);
  kartu.appendChild(baris);

  if (w.pesan) {
    kartu.appendChild(el('p', 'ai-pesan ai-judul-' + kode, w.pesan));
  }

  /* Rincian teknis — kecil dan redup: berguna saat ada masalah, tidak
     mengganggu saat semuanya normal. */
  const rinci = [];
  if (w.endpoint) rinci.push('Endpoint: ' + w.endpoint);
  if (w.model) rinci.push('Model: ' + w.model);
  if (typeof w.latensi_ms === 'number') rinci.push('Balas dalam ' + w.latensi_ms + ' ms');
  if (rinci.length) {
    const p = el('p', 'ai-rinci');
    rinci.forEach((r, i) => {
      if (i) p.appendChild(document.createTextNode(' · '));
      p.appendChild(document.createTextNode(r));
    });
    kartu.appendChild(p);
  }

  host.appendChild(kartu);
}

let SEDANG_CEK_AI = false;
async function periksaStatusAI(manual) {
  const host = AI_HOST();
  if (!host || SEDANG_CEK_AI) return;

  /* Keadaan awal saat diperiksa: 'belum' — BUKAN hijau. Panel tidak boleh
     terlihat sehat hanya karena pemeriksaan belum selesai. */
  if (manual) {
    SEDANG_CEK_AI = true;
    try {
      const r = await fetchSesi(API + '/ai-status', { cache: 'no-store' });
      if (r.status === 404) {
        /* Endpoint belum ada di server. Katakan apa adanya — jangan
           memakai /api/parse sebagai pengganti, itu membakar kuota Deny
           setiap kali halaman dimuat. */
        renderStatusAI({ keadaan: 'belum',
          judul: 'Belum bisa diperiksa',
          pesan: 'Server belum punya endpoint /api/ai-status, jadi panel ini '
               + 'belum tahu keadaan AI-nya. Ini bukan berarti AI-nya mati. '
               + 'Catat pintar tetap dicoba saat kamu mengirim kalimat.' });
        return;
      }
      const j = await r.json();
      const d = j || {};
      /* Server yang menentukan keadaannya; UI hanya menampilkan. Sama seperti
         aturan angka: UI tidak menghitung, UI tidak menebak.

         `judul` diambil dari `keadaan` yang DIKIRIM SERVER, bukan dari `d.ok`.
         Salahnya kalau memakai `d.ok`: keadaan "lambat" juga ber-ok=true, jadi
         panelnya menulis "AI siap dipakai" padahal pesannya sendiri bilang
         "menjawab tapi lambat" — judul dan isi bertentangan (terukur di
         layar). Server sudah mengirim `keadaan`; pakai itu. */
      const kode = d.keadaan || (d.ok ? 'ok' : 'gagal');
      const JUDUL = {
        ok: 'AI siap dipakai',
        lambat: 'AI menjawab lambat',
        gagal: 'AI tidak bisa dipakai',
        belum: 'Belum bisa diperiksa',
      };
      renderStatusAI({
        keadaan: kode,
        judul: d.judul || JUDUL[kode] || JUDUL.gagal,
        pesan: d.pesan || '',
        endpoint: d.endpoint || null,
        model: d.model || null,
        latensi_ms: typeof d.latensi_ms === 'number' ? d.latensi_ms : null,
      });
      /* Simpan hasil pemeriksaan di sesi ini. Dua sebab:
         (a) penanda 'aiDiperiksa' supaya tidak memanggil model lagi saat
             Deny berpindah-pindah tab (keputusan Deny 5 Okt);
         (b) hasilnya sendiri, supaya panel TIDAK lupa dan menampilkan
             "belum diperiksa" padahal baru saja diperiksa — itu membingungkan
             dan membuat Deny memeriksa ulang tanpa perlu (makin banyak kuota
             terpakai, kebalikan dari maksudnya).
         Kalau tanggalnya beda hari, hasil lama diabaikan. */
      try {
        sessionStorage.setItem('aiDiperiksa', '1');
        sessionStorage.setItem('aiHasil', JSON.stringify({
          tgl: new Date().toDateString(),
          w: { keadaan: kode, judul: d.judul || JUDUL[kode] || JUDUL.gagal,
               pesan: d.pesan || '', endpoint: d.endpoint || null,
               model: d.model || null,
               latensi_ms: typeof d.latensi_ms === 'number' ? d.latensi_ms : null }
        }));
      } catch (e) {}
    } catch (e) {
      renderStatusAI({ keadaan: 'gagal',
        judul: 'Server tidak menjawab',
        pesan: 'Panel tidak bisa membaca status AI karena server finance-nya '
             + 'sendiri tidak menjawab. Coba lagi sebentar lagi.' });
    } finally {
      SEDANG_CEK_AI = false;
    }
    return;
  }

  /* ── Pemeriksaan OTOMATIS: sekali per sesi browser ─────────────────────
     Keputusan Deny (5 Okt): sekali per sesi, bukan setiap tab Catat dibuka.
     Setiap panggilan mengirim satu pesan "ok" ke model dan MEMBAKAR KUOTA
     Deny (monica §5), jadi berpindah-pindah tab tidak boleh memanggil ulang.

     sessionStorage, bukan localStorage: tanda ini harus hilang saat tab
     ditutup / browser ditutup, supaya sesi berikutnya memeriksa lagi. Itu
     pola yang sama dengan "Sesi berakhir" di login.

     Keadaan awal SEBELUM diperiksa: 'belum' — BUKAN hijau. */
  let sudah;
  try { sudah = sessionStorage.getItem('aiDiperiksa') === '1'; } catch (e) { sudah = false; }

  if (sudah) {
    /* Sudah diperiksa di sesi ini. Tampilkan HASILNYA lagi — bukan "belum",
       karena panel yang lupa hasil yang baru saja didapat akan membuat Deny
       memeriksa ulang tanpa perlu (justru menambah pemakaian kuota).
       Kalau hasilnya tidak terbaca atau beda hari, baru tampilkan "belum". */
    let hasil = null;
    try {
      const mentah = sessionStorage.getItem('aiHasil');
      if (mentah) {
        const h = JSON.parse(mentah);
        if (h && h.tgl === new Date().toDateString() && h.w) hasil = h.w;
      }
    } catch (e) { hasil = null; }

    if (hasil) {
      renderStatusAI(hasil);
      return;
    }

    renderStatusAI({ keadaan: 'belum',
      judul: 'Belum diperiksa di sesi ini',
      pesan: 'Panel ini memeriksa sekali per sesi supaya tidak memakai kuota '
           + 'terus-menerus. Tekan "Periksa" kalau mau tahu keadaannya '
           + 'sekarang. Catat pintar tetap dicoba saat kamu mengirim kalimat.' });
    return;
  }

  periksaStatusAI(true);
}

/* ══ Tema: Terang · Gelap · Ikut sistem ═══════════════════════════════════
   Tailwind membaca varian `dark:` dari class `.gelap` di <html>. Script kecil
   di <head> sudah memasang class itu sebelum halaman digambar; fungsi di sini
   yang menangani perubahan setelah panel hidup.
   Pilihan disimpan di localStorage supaya bertahan antar sesi. */
const TEMA = ['sistem', 'terang', 'gelap'];
const TEMA_IKON = { sistem: '◐', terang: '☀', gelap: '☾' };
const TEMA_LABEL = { sistem: 'Ikut sistem', terang: 'Terang', gelap: 'Gelap' };

function temaTerpasang() {
  const pilih = document.documentElement.dataset.tema || 'sistem';
  const sistemGelap = window.matchMedia('(prefers-color-scheme: dark)').matches;
  return pilih === 'gelap' || (pilih === 'sistem' && sistemGelap) ? 'gelap' : 'terang';
}

function pasangTema(pilih) {
  document.documentElement.dataset.tema = pilih;
  document.documentElement.classList.toggle('gelap',
    pilih === 'gelap'
    || (pilih === 'sistem' && window.matchMedia('(prefers-color-scheme: dark)').matches));
  try { localStorage.setItem('tema', pilih); } catch (e) {}
  gambarTombolTema();
}

function gambarTombolTema() {
  const pilih = document.documentElement.dataset.tema || 'sistem';
  const ikon = $('tema-ikon');
  const status = $('tema-status');
  if (ikon) ikon.textContent = TEMA_IKON[pilih] || '◐';
  if (status) {
    status.textContent = 'Tema: ' + (TEMA_LABEL[pilih] || pilih)
      + (pilih === 'sistem' ? ' (sedang ' + temaTerpasang() + ')' : '');
  }
  const btn = $('btn-tema');
  if (btn) btn.setAttribute('aria-label',
    'Tema ' + (TEMA_LABEL[pilih] || pilih) + '. Tekan untuk ganti.');
}

/* ══ Sensor nominal ═══════════════════════════════════════════════════════
   Menyembunyikan semua nominal di layar (kekayaan, statistik, daftar, akun,
   grafik). Penyamaran terjadi di rupiah()/rupiahShort(), jadi tidak ada
   tampilan yang bisa terlewat.
   TIDAK disimpan ke localStorage: setiap reload, nominal terlihat lagi. */
function gambarTombolSensor() {
  const btn = $('btn-sensor');
  const ikon = $('sensor-ikon');
  const status = $('sensor-status');
  if (!btn) return;
  btn.setAttribute('aria-pressed', String(SENSOR));
  btn.setAttribute('aria-label', SENSOR
    ? 'Tampilkan nominal uang' : 'Sembunyikan nominal uang');
  if (ikon) ikon.textContent = SENSOR ? '🙈' : '👁';
  if (status) {
    status.textContent = SENSOR ? 'Nominal disembunyikan.' : 'Nominal terlihat.';
  }
}

/* ══ Sisa bulan lalu (di atas grafik tren) ══════════════════════════════
   Permintaan Deny: panel di atas grafik tren berisi "sisa pada bulan
   sebelumnya", dengan placeholder kalau belum ada data.

   Angkanya = saldo di AKHIR bulan lalu (`angka.net_worth_akhir`), dibangun
   monica di `db.saldo_per_tanggal()`.

   Yang PENTING dan mudah salah: `net_worth_akhir` bernilai `null` dalam DUA
   keadaan berbeda, dan keduanya butuh kalimat yang berbeda:
     1. bulan belum selesai        -> "belum selesai, jadi belum ada angka akhir bulan"
     2. bulan selesai tapi kosong  -> "belum ada data bulan itu"
   Menampilkan satu pesan untuk keduanya akan menyesatkan di salah satunya.

   Dan `null` TIDAK pernah kutulis sebagai Rp 0 — nol dan "tidak ada data"
   adalah dua hal berbeda; itu aturan yang sama dengan `ada_data: false`.
*/
let BULAN_LALU = null;   /* bulan yang ditanyakan panel ini, untuk refresh */

async function renderSisaBulanLalu() {
  const host = $('lalu-host');
  if (!host) return;
  host.textContent = '';

  /* Bulan lalu = bulan sebelum bulan yang sedang dilihat panel
     (`state.month`), supaya panelnya ikut saat Deny menekan ‹ ›.
     Kalau state.month belum ada (muat pertama), TANYA ke server dulu —
     bukan menebak dari jam perangkat: bulan berjalan itu pengetahuan server. */
  let bulanLalu;
  if (state.month) {
    bulanLalu = addMonths(state.month, -1);
  } else {
    try {
      const sm = await apiGet('/summary');
      bulanLalu = addMonths(sm.month, -1);
    } catch (e) {
      return;   /* refresh() akan memanggil ulang setelah state terisi */
    }
  }
  BULAN_LALU = bulanLalu;

  let d;
  try {
    d = await apiGet('/analysis?month=' + encodeURIComponent(bulanLalu));
  } catch (e) {
    /* Kalau endpointnya tidak bisa dihubungi, itu BUKAN "belum ada data" —
       dan menampilkan placeholder akan menyembunyikan masalah sebenarnya. */
    host.appendChild(el('p', 'm-0 text-[13px] leading-snug text-gray-500 dark:text-gray-400',
      'Tidak bisa memuat data ' + monthLabel(bulanLalu) + ' dari /api/analysis.'));
    return;
  }

  const a = d.angka;
  const akhir = a.net_worth_akhir;

  /* ── Placeholder: belum ada angka akhir bulan ─────────────────────────
     Dua sebab, dua kalimat (lihat catatan di atas). */
  if (akhir === null || akhir === undefined) {
    const kotak = el('div', 'rounded-lg border border-dashed border-gray-300 px-4 py-3 '
      + 'dark:border-gray-700');
    kotak.appendChild(el('p', 'm-0 text-sm font-semibold text-gray-600 dark:text-gray-300',
      'Belum ada data bulan lalu'));
    kotak.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug '
      + 'text-gray-500 dark:text-gray-400',
      d.boleh_dianalisa === false
        ? 'Bulan ' + d.nama_bulan + ' belum selesai, jadi belum ada angka akhir bulan '
          + 'untuk dibandingkan. Angkanya masih bisa berubah.'
        : 'Tidak ada transaksi tercatat di ' + d.nama_bulan + ', jadi saldo akhir '
          + 'bulan itu sama dengan bulan sebelumnya — tidak ada yang bisa ditampilkan '
          + 'sebagai angka tersendiri.'));
    host.appendChild(kotak);
    return;
  }

  /* ── Ada angka: saldo akhir bulan lalu ────────────────────────────────
     Ditampilkan bersama "sekarang" supaya panelnya menjawab pertanyaan yang
     sebenarnya: apakah uangnya bertambah atau berkurang? Satu angka saja
     tidak memberi tahu apa-apa. */
  host.appendChild(el('p', 'm-0 text-[13px] text-gray-500 dark:text-gray-400',
    'Saldo akhir ' + d.nama_bulan + ' (' + dateLabel(a.per_tanggal) + ')'));
  host.appendChild(el('p', 'angka-stat mt-0.5 mb-0', rupiah(akhir)));

  const sekarang = (state.summary && state.summary.net_worth)
    ? state.summary.net_worth.total : null;
  if (sekarang !== null && sekarang !== undefined) {
    const beda = sekarang - akhir;
    const baris = el('p', 'mt-2 mb-0 text-[13px] leading-snug');
    if (beda > 0) {
      baris.appendChild(el('span', 'font-medium text-(--color-income)',
        '▲ ' + rupiah(beda)));
      baris.appendChild(document.createTextNode(' lebih tinggi dari sekarang'));
    } else if (beda < 0) {
      baris.appendChild(el('span', 'font-medium text-(--color-expense)',
        '▼ ' + rupiah(Math.abs(beda))));
      baris.appendChild(document.createTextNode(' lebih rendah dari sekarang'));
    } else {
      baris.appendChild(el('span', 'text-gray-500 dark:text-gray-400',
        'Sama dengan saldo sekarang'));
    }
    host.appendChild(baris);

    /* Kalau uangnya berkurang, sebutkan bahwa pengeluaran sungguhan dan
       pelunasan utang tidak sama artinya — supaya turunnya tidak otomatis
       terbaca sebagai "boros". */
    host.appendChild(el('p', 'mt-1 mb-0 text-[11px] leading-snug '
      + 'text-gray-500 dark:text-gray-400',
      'Selisih ini dari saldo, bukan dari pengeluaran — pelunasan utang dan '
      + 'talangan ikut mengubah saldo tanpa berarti konsumsi.'));
  }
}

/* ══ Analisa Bulanan ═════════════════════════════════════════════════════
 * Analisa untuk bulan yang SUDAH SELESAI. Sumber: /api/analysis.
 *
 * Kenapa halaman ini ada dan kenapa bentuknya begini: lihat surat monica
 * "analisa-bulanan". Empat aturan yang paling mudah dilanggar sudah ditandai
 * di komentar masing-masing bagian.
 */
let ANALISA_BULAN = null;   /* bulan yang sedang dilihat di layar Analisa */

async function renderAnalisa(bulanDipilih) {
  const host = $('analisa-host');
  const sel = $('analisa-bulan');
  if (!host || !sel) return;

  /* ── Pemilih bulan ────────────────────────────────────────────────────
     Daftar dari /api/months: HANYA bulan yang punya transaksi. Bulan tanpa
     transaksi tidak punya apa pun untuk ditampilkan, jadi menaruhnya di
     pemilih hanya membuat Deny menekan bulan yang pasti menjawab
     "belum ada data". */
  let daftar = [];
  let bulanBerjalan = null;
  try {
    const rm = await apiGet('/months');
    daftar = rm.bulan || [];
    bulanBerjalan = rm.bulan_berjalan;

    if (!bulanDipilih) {
      /* Default: bulan TERBARU yang sudah selesai (bisa dianalisa). Kalau
         tidak ada, pakai yang terbaru apa pun — lebih baik menampilkan
         bulan berjalan dengan tombol mati daripada layar kosong. */
      const bisa = daftar.filter((b) => b.boleh_dianalisa);
      bulanDipilih = (bisa.length ? bisa[bisa.length - 1] : daftar[daftar.length - 1]);
      bulanDipilih = bulanDipilih ? bulanDipilih.month : null;
    }

    sel.textContent = '';
    if (!daftar.length) {
      const o = el('option', null, 'Belum ada bulan');
      o.value = '';
      sel.appendChild(o);
      sel.disabled = true;
    } else {
      sel.disabled = false;
      daftar.forEach((b) => {
        const o = el('option', null, b.nama_bulan
          + (b.ada_analisa ? ' · sudah dianalisa' : ''));
        o.value = b.month;
        if (b.month === bulanDipilih) o.selected = true;
        sel.appendChild(o);
      });
    }
  } catch (e) {
    host.textContent = '';
    host.appendChild(el('p', 'kartu text-sm leading-snug',
      'Tidak bisa memuat daftar bulan dari /api/months. Coba muat ulang.'));
    return;
  }

  if (!bulanDipilih) {
    host.textContent = '';
    host.appendChild(el('p', 'kartu text-sm leading-snug',
      'Belum ada bulan dengan transaksi, jadi belum ada yang bisa dianalisa. '
      + 'Catat transaksi dulu di layar Catat.'));
    $('analisa-penanda').textContent = '';
    return;
  }

  ANALISA_BULAN = bulanDipilih;

  let d;
  try {
    d = await apiGet('/analysis?month=' + encodeURIComponent(bulanDipilih));
  } catch (e) {
    host.textContent = '';
    host.appendChild(el('p', 'kartu text-sm leading-snug',
      'Tidak bisa memuat analisa ' + bulanDipilih + ' dari /api/analysis.'));
    return;
  }

  host.textContent = '';
  const a = d.angka;

  /* Penanda di sebelah pemilih: bulan bernama + status analisanya. */
  const bInfo = daftar.find((b) => b.month === bulanDipilih);
  $('analisa-penanda').textContent = bInfo && bInfo.ada_analisa
    ? 'sudah dianalisa' : 'belum dianalisa';

  /* ── Bulan tanpa data ─────────────────────────────────────────────────
     Aturan 3f: kalimat, BUKAN deretan nol. Nol dan "tidak ada data" adalah
     dua hal berbeda — menampilkan nol membuat Deny mengira pengeluarannya
     nol. */
  if (!a.ada_data) {
    const k = el('div', 'rounded-xl border border-dashed border-gray-300 px-5 py-6 '
      + 'text-center dark:border-gray-700');
    k.appendChild(el('p', 'm-0 text-base font-semibold', 'Belum ada data bulan ini'));
    k.appendChild(el('p', 'mt-1 mb-0 text-sm text-gray-500 dark:text-gray-400',
      'Tidak ada transaksi tercatat di ' + d.nama_bulan
      + '. Ini bukan berarti pengeluarannya nol.'));
    host.appendChild(k);
    return;
  }

  /* ── Kartu utama: BISA DITABUNG ───────────────────────────────────────
     ATURAN 3a — pakai `sisa_bebas`, BUKAN `sisa_kas`. Ini yang paling mudah
     salah dan salahnya berbahaya: `sisa_kas` mengurangi pelunasan utang dan
     talangan, yang uangnya memang sudah tidak ada tapi bukan konsumsi. */
  const km = el('div', 'kartu');
  km.appendChild(el('p', 'eyebrow', 'Bisa ditabung ' + d.nama_bulan));
  km.appendChild(el('p', 'angka-besar mt-1 text-(--color-income)', rupiah(a.sisa_bebas)));
  km.appendChild(el('p', 'mt-2 mb-0 text-xs leading-snug text-gray-500 dark:text-gray-400',
    'Dihitung dari uang masuk dikurangi pengeluaran sungguhan. Pelunasan utang '
    + 'dan talangan tidak ikut dikurangi — itu bukan konsumsi, tapi uangnya juga '
    + 'sudah tidak ada.'));

  /* ATURAN 2 — peringatan kelengkapan DI ATAS angka sisa.
     Monica: angkanya tetap ditampilkan, yang perlu dilakukan adalah
     menyatakan dasarnya, bukan menghapus angkanya. Ditaruh di atas supaya
     terbaca SEBELUM Deny mempercayai angkanya.

     Peringatan ini yang mencegah "sisa bebas Rp 7,6 juta" dari 3 hari data
     terlihat seperti uang yang benar-benar bisa ditabung. */
  if (d.kelengkapan && d.kelengkapan.peringatan) {
    const kartuPerhatian = el('div', 'kartu border-amber-300 bg-amber-50 '
      + 'dark:border-amber-700 dark:bg-amber-900/25');
    kartuPerhatian.appendChild(el('p', 'm-0 text-[13px] font-semibold text-amber-900 '
      + 'dark:text-amber-100', 'Data belum lengkap'));
    kartuPerhatian.appendChild(el('p', 'mt-1 mb-0 text-[13px] leading-snug '
      + 'text-amber-800 dark:text-amber-200', d.kelengkapan.peringatan));
    host.appendChild(kartuPerhatian);
  }
  host.appendChild(km);

  /* ── Ringkasan arus ───────────────────────────────────────────────────
     `sisa_kas` boleh ditampilkan, tapi diberi label JELAS ("sisa arus kas")
     dan TIDAK di sebelah angka tabungan tanpa penjelasan (aturan 3a). */
  const kr = el('div', 'kartu');
  kr.appendChild(el('p', 'eyebrow mb-3', 'Ringkasan arus'));
  const baris = [
    ['Uang masuk', rupiah(a.masuk), 'text-(--color-income)'],
    ['Pengeluaran sungguhan', rupiah(a.konsumsi), 'text-(--color-expense)'],
    ['Pelunasan utang', rupiah(a.pelunasan_utang), 'text-(--color-debt)'],
    ['Talangan (piutang)', rupiah(a.talangan_piutang), 'text-(--color-receivable)'],
    ['Sisa arus kas', rupiah(a.sisa_kas), ''],
  ];
  const ul = el('ul', 'm-0 list-none p-0 flex flex-col gap-2');
  baris.forEach(([k, v, warna]) => {
    const li = el('li', 'flex items-baseline justify-between gap-3 text-sm');
    li.appendChild(el('span', 'text-gray-600 dark:text-gray-300', k));
    li.appendChild(el('span', 'shrink-0 angka-baris ' + warna, v));
    ul.appendChild(li);
  });
  kr.appendChild(ul);
  /* Bedanya disebut eksplisit: ini angka yang paling mudah disalahartikan. */
  if (a.sisa_kas !== a.sisa_bebas) {
    kr.appendChild(el('p', 'mt-3 mb-0 border-t border-gray-100 pt-3 text-xs '
      + 'leading-snug text-gray-500 dark:border-gray-800 dark:text-gray-400',
      'Sisa arus kas (' + rupiah(a.sisa_kas) + ') berbeda dari "bisa ditabung" ('
      + rupiah(a.sisa_bebas) + ') sebesar ' + rupiah(a.sisa_bebas - a.sisa_kas)
      + ' — selisihnya pelunasan utang dan talangan.'));
  }
  host.appendChild(kr);

  /* ── Kategori: perubahan vs bulan lalu ────────────────────────────────
     Dari `angka.kategori` (bukan dari `saran`): ini keadaannya, bukan
     sarannya. `perubahan_persen` bisa null kalau tidak ada pembanding. */
  if ((a.kategori || []).length) {
    const kk = el('div', 'kartu');
    kk.appendChild(el('p', 'eyebrow mb-3', 'Pengeluaran per kategori'));
    const ul2 = el('ul', 'm-0 list-none p-0 flex flex-col gap-3');
    a.kategori.forEach((c) => {
      const li = el('li', 'flex items-baseline justify-between gap-3 text-sm');
      const kiri = el('div', 'min-w-0');
      kiri.appendChild(el('span', 'font-medium', c.category));
      if (c.wajib) {
        kiri.appendChild(el('span', 'ml-2 rounded px-1.5 py-0.5 text-[10px] '
          + 'font-semibold uppercase tracking-wide bg-gray-100 text-gray-600 '
          + 'dark:bg-gray-800 dark:text-gray-300', 'wajib'));
      }
      if (c.total_bulan_lalu !== null && c.total_bulan_lalu !== undefined
          && c.perubahan_persen !== null && c.perubahan_persen !== undefined) {
        /* Panah + persen apa adanya dari server. Tidak kuhitung ulang. */
        const naik = c.perubahan_persen > 0;
        kiri.appendChild(el('span', 'ml-2 text-[11px] '
          + (naik ? 'text-(--color-expense)' : 'text-(--color-income)'),
          (naik ? '▲ ' : '▼ ') + Math.abs(c.perubahan_persen) + '% dari bulan lalu'));
      } else if (c.total_bulan_lalu === null || c.total_bulan_lalu === undefined) {
        kiri.appendChild(el('span', 'ml-2 text-[11px] text-gray-500 dark:text-gray-400',
          'belum ada pembanding'));
      }
      li.appendChild(kiri);
      li.appendChild(el('span', 'shrink-0 angka-baris', rupiah(c.total)));
      ul2.appendChild(li);
    });
    kk.appendChild(ul2);
    if (!a.kategori_lalu_ada) {
      kk.appendChild(el('p', 'mt-3 mb-0 border-t border-gray-100 pt-3 text-xs '
        + 'leading-snug text-gray-500 dark:border-gray-800 dark:text-gray-400',
        'Bulan sebelumnya belum punya data, jadi belum ada perbandingan naik/turun.'));
    }
    host.appendChild(kk);
  }

  /* ── Narasi ───────────────────────────────────────────────────────────
     Keputusan Deny: narasi dibuat SEKALI lalu tersimpan. Kalau transaksi
     dikoreksi setelahnya, angkanya ikut benar (dihitung ulang) tapi
     kalimatnya tidak — itu `narasi_basi`. Peringatannya DI ATAS narasi
     supaya terbaca sebelum Deny mempercayai kalimatnya (monica §4). */
  const kn = el('div', 'kartu');
  kn.appendChild(el('p', 'eyebrow mb-3', 'Narasi'));

  if (d.narasi_basi) {
    const p = el('div', 'mb-3 rounded-lg bg-amber-50 px-3 py-2 text-[12px] '
      + 'leading-snug text-amber-800 dark:bg-amber-900/25 dark:text-amber-200');
    p.textContent = 'Narasi ini dibuat sebelum ada perubahan data. Angka di '
      + 'atas sudah yang terbaru, tapi kalimatnya belum.';
    kn.appendChild(p);
  }

  if (d.ada_analisa && d.narasi) {
    kn.appendChild(el('p', 'm-0 text-sm leading-relaxed', d.narasi.ringkasan || ''));

    /* per_kategori dijamin terisi lengkap oleh monica (aturan 3d). Kalau
       `kategori_diganti` berisi nama, artinya kalimat itu dari hitungan,
       bukan dari AI — ditandai kecil supaya transparan (opsional). */
    const diganti = d.narasi.kategori_diganti || [];
    const perKat = d.narasi.per_kategori || {};
    const nama = Object.keys(perKat);
    if (nama.length) {
      const ul3 = el('ul', 'mt-3 mb-0 list-none p-0 flex flex-col gap-2 '
        + 'border-t border-gray-100 pt-3 dark:border-gray-800');
      nama.forEach((k) => {
        const li = el('li', 'text-[13px] leading-snug');
        li.appendChild(el('span', 'font-medium', k + ': '));
        li.appendChild(document.createTextNode(perKat[k]));
        if (diganti.indexOf(k) > -1) {
          li.appendChild(el('span', 'ml-1 text-[11px] text-gray-500 dark:text-gray-400',
            '(dari data)'));
        }
        ul3.appendChild(li);
      });
      kn.appendChild(ul3);
    }
    if (d.narasi.penutup) {
      kn.appendChild(el('p', 'mt-3 mb-0 text-[13px] leading-snug text-gray-600 '
        + 'dark:text-gray-300', d.narasi.penutup));
    }
    if (d.dibuat_pada) {
      kn.appendChild(el('p', 'mt-3 mb-0 text-[11px] text-gray-500 dark:text-gray-400',
        'Dibuat ' + d.dibuat_pada + (d.model ? ' · ' + d.model : '')));
    }
  } else {
    kn.appendChild(el('p', 'm-0 text-sm leading-snug text-gray-500 dark:text-gray-400',
      'Belum ada narasi untuk ' + d.nama_bulan + '. Angka di atas tetap benar — '
      + 'narasi cuma penjelasan tambahan.'));
  }

  /* Tombol: "Buat analisa" yang belum ada, atau "Buat ulang" yang sudah ada.
     ATURAN 4 — mati kalau `boleh_dianalisa: false`, dan ALASANNYA ditulis:
     mematikan tombol tanpa penjelasan membuat Deny mengira ada yang rusak. */
  const barisTombol = el('div', 'mt-4 flex flex-wrap items-center gap-2');
  const boleh = !!d.boleh_dianalisa;
  const bBuat = el('button', 'tombol ' + (d.ada_analisa ? 'tombol-hantu' : 'tombol-utama'),
    d.ada_analisa ? 'Buat ulang narasi' : 'Buat analisa');
  bBuat.type = 'button';
  bBuat.disabled = !boleh;
  if (!boleh) {
    bBuat.title = 'Bulan ' + d.nama_bulan + ' belum selesai — angkanya masih bisa berubah.';
  }
  bBuat.addEventListener('click', () => buatAnalisa(d));
  barisTombol.appendChild(bBuat);

  /* Hapus narasi (angkanya tetap ada) — hanya kalau memang ada narasi. */
  if (d.ada_analisa) {
    const bHapus = el('button', 'tombol tombol-hantu', 'Hapus narasi');
    bHapus.type = 'button';
    bHapus.addEventListener('click', () => hapusNarasi(d));
    barisTombol.appendChild(bHapus);
  }
  kn.appendChild(barisTombol);

  if (!boleh) {
    kn.appendChild(el('p', 'mt-2 mb-0 text-xs leading-snug text-gray-500 '
      + 'dark:text-gray-400',
      'Bulan ' + d.nama_bulan + ' belum selesai, jadi belum bisa dianalisa — '
      + 'angkanya masih bisa berubah. Analisa dibuat untuk bulan yang sudah lewat.'));
  }

  host.appendChild(kn);

  /* ── Saran hemat ──────────────────────────────────────────────────────
     ATURAN 3b & 3c: `potensi_hemat: null` ditampilkan TANPA angka (jangan
     tulis "Rp 0"), dan `asumsi` WAJIB tampil — angka hemat tanpa penjelasan
     tidak bisa dipercaya (UI-MOBILE.md). Kalau ruang kurang, perkecil;
     jangan dihapus. */
  const saran = (d.saran && d.saran.kategori) || [];
  if (saran.length) {
    const ks = el('div', 'kartu');
    ks.appendChild(el('p', 'eyebrow mb-3', 'Yang bisa ditekan'));

    if (d.saran.total_potensi_hemat !== null && d.saran.total_potensi_hemat !== undefined) {
      ks.appendChild(el('p', 'mb-3 text-sm', 'Total yang bisa dihemat: '
        + rupiah(d.saran.total_potensi_hemat)));
    }

    const ul4 = el('ul', 'm-0 list-none p-0 flex flex-col gap-3');
    saran.forEach((x) => {
      const li = el('li', 'border-t border-gray-100 pt-3 first:border-t-0 first:pt-0 '
        + 'dark:border-gray-800');
      const kepala = el('div', 'flex items-baseline justify-between gap-3');
      const kiri = el('div', 'min-w-0');
      kiri.appendChild(el('span', 'text-sm font-medium', x.kategori));
      if (x.wajib) {
        kiri.appendChild(el('span', 'ml-2 rounded px-1.5 py-0.5 text-[10px] font-semibold '
          + 'uppercase tracking-wide bg-gray-100 text-gray-600 dark:bg-gray-800 '
          + 'dark:text-gray-300', 'wajib'));
      }
      kepala.appendChild(kiri);
      /* Angka hemat: HANYA kalau ada. Kalau null, tidak ada angka sama sekali. */
      if (x.potensi_hemat !== null && x.potensi_hemat !== undefined) {
        kepala.appendChild(el('span', 'shrink-0 angka-baris text-(--color-income)',
          rupiah(x.potensi_hemat)));
      }
      li.appendChild(kepala);
      li.appendChild(el('p', 'mt-1 mb-0 text-xs leading-snug text-gray-500 '
        + 'dark:text-gray-400', x.asumsi || ''));
      ul4.appendChild(li);
    });
    ks.appendChild(ul4);

    if (d.saran.catatan) {
      ks.appendChild(el('p', 'mt-3 mb-0 border-t border-gray-100 pt-3 text-[11px] '
        + 'leading-snug text-gray-500 dark:border-gray-800 dark:text-gray-400',
        d.saran.catatan));
    }
    host.appendChild(ks);
  }

  /* ── Kelengkapan: angkanya, bukan cuma kalimatnya ──────────────────────
     Peringatan sudah di atas; di sini dasarnya, supaya bisa diperiksa. */
  if (d.kelengkapan) {
    const kl = el('p', 'text-xs leading-relaxed text-gray-500 dark:text-gray-400');
    kl.textContent = 'Data ' + d.nama_bulan + ': ' + d.kelengkapan.hari_tercatat
      + ' dari ' + d.kelengkapan.jumlah_hari_bulan + ' hari tercatat, '
      + d.kelengkapan.tx_count + ' transaksi. Dianggap lengkap kalau mencapai '
      + d.kelengkapan.ambang_hari + ' hari.';
    host.appendChild(kl);
  }
}

/* Buat / segarkan narasi. Keputusan Deny: MANUAL — tidak ada yang muncul
   sendiri, Deny yang menekan. */
async function buatAnalisa(d) {
  const host = $('analisa-host');
  const tombol = Array.from(host.querySelectorAll('button'))
    .find((b) => /Buat (analisa|ulang narasi)/.test(b.textContent));
  const teksAsli = tombol ? tombol.textContent : '';
  if (tombol) { tombol.disabled = true; tombol.setAttribute('aria-busy', 'true'); tombol.textContent = 'Membuat…'; }

  try {
    const r = await fetchSesi(API + '/analysis', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ month: d.month }),
    });
    const j = await r.json().catch(() => null);
    if (!j) {
      toast('Server membalas bukan JSON (HTTP ' + r.status + ')', 'error');
      if (tombol) formPulihkan(tombol, teksAsli);
      return;
    }
    /* Pakai `message` dari server apa adanya — dia yang tahu alasannya
       (bulan belum selesai, tidak ada data, dan seterusnya). */
    if (!j.ok) {
      toast(j.message || j.error || 'Gagal membuat analisa', 'error');
      if (tombol) formPulihkan(tombol, teksAsli);
      return;
    }
    toast('Narasi dibuat');
    await renderAnalisa(d.month);
  } catch (e) {
    if (String(e && e.message) !== 'sesi_berakhir') {
      toast('Server tidak menjawab', 'error');
      if (tombol) formPulihkan(tombol, teksAsli);
    }
  }
}

/* Hapus NARASI saja. Angkanya tetap ada karena selalu dihitung ulang.
   Ini berguna kalau narasinya terasa tidak berguna dan mau dibuat ulang. */
function hapusNarasi(d) {
  const host = $('analisa-host');
  const kn = Array.from(host.querySelectorAll('.kartu'))
    .find((k) => k.querySelector('.eyebrow') && k.querySelector('.eyebrow').textContent === 'Narasi');
  if (!kn) return;
  const barisLama = kn.querySelector('.mt-4');
  const wadah = el('div', 'mt-4 rounded-lg border border-(--color-expense) px-3 py-3');

  wadah.appendChild(el('p', 'm-0 text-sm font-semibold text-(--color-expense)',
    'Hapus narasi ' + d.nama_bulan + '?'));
  wadah.appendChild(el('p', 'mt-1 mb-0 text-xs leading-snug text-gray-600 dark:text-gray-300',
    'Hanya kalimatnya yang dihapus. Angka di halaman ini tetap ada karena '
    + 'selalu dihitung ulang dari transaksi.'));

  const pesan = el('p', 'm-0 mt-2 text-xs text-(--color-expense)');
  pesan.hidden = true;
  pesan.setAttribute('role', 'alert');

  const baris = el('div', 'mt-3 flex gap-2');
  const ya = el('button', 'tombol', 'Ya, hapus narasi');
  ya.type = 'button';
  ya.style.cssText = 'background:var(--color-expense);color:#fff;';
  const batal = el('button', 'tombol tombol-hantu', 'Batal');
  batal.type = 'button';
  batal.addEventListener('click', () => { wadah.replaceWith(barisLama); });

  ya.addEventListener('click', async () => {
    ya.disabled = true;
    ya.setAttribute('aria-busy', 'true');
    ya.textContent = 'Menghapus…';
    try {
      const r = await fetchSesi(API + '/analysis/' + encodeURIComponent(d.month),
        { method: 'DELETE' });
      const j = await r.json().catch(() => null);
      if (!j || !j.ok) {
        pesan.textContent = (j && (j.message || j.error)) || 'Gagal menghapus narasi.';
        pesan.hidden = false; formPulihkan(ya, 'Ya, hapus narasi'); return;
      }
      toast('Narasi dihapus');
      await renderAnalisa(d.month);
    } catch (e) {
      if (String(e && e.message) !== 'sesi_berakhir') {
        pesan.textContent = 'Server tidak menjawab. Coba lagi.';
        pesan.hidden = false; formPulihkan(ya, 'Ya, hapus narasi');
      }
    }
  });

  [pesan, baris].forEach((n) => wadah.appendChild(n));
  baris.appendChild(ya);
  baris.appendChild(batal);
  barisLama.replaceWith(wadah);
  batal.focus();
}

/* ══ Keluar ══════════════════════════════════════════════════════════════
   POST /api/auth/keluar mencabut token di server dan menghapus cookie, lalu
   kita arahkan ke /login. Tanpa konfirmasi — keluar tidak merusak apa pun
   (monica §5); yang berbahaya hapus transaksi, bukan keluar.

   TIDAK lewat fetchSesi: endpoint ini justru dipanggil saat sesi masih sah,
   dan kalau balasannya 401 (sesi sudah mati duluan) kita tetap mau ke /login
   — bukan masalah. Yang penting jangan sampai tombol ini diam tanpa reaksi
   kalau server tidak menjawab. */
async function keluar() {
  const btn = $('btn-keluar');
  if (btn) { btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.textContent = 'Keluar…'; }
  try {
    await fetch('/api/auth/keluar', { method: 'POST' });
  } catch (e) {
    /* Server tidak menjawab: tetap alihkan ke /login. Cookie mungkin masih
       ada, tapi /login akan meminta password lagi dan itu hasil yang benar
       dari sudut Deny — dibanding menahan dia di panel yang sudah dia
       minta kunci. */
  }
  window.location.replace('/login');
}

/* ══ Ikat ════════════════════════════════════════════════════════════════ */
function wire() {
  document.querySelectorAll('.navtab').forEach((t) => {
    t.addEventListener('click', () => showTab(t.dataset.tab));
  });
  /* Pemilih bulan di layar Analisa. */
  const selAnalisa = $('analisa-bulan');
  if (selAnalisa) {
    selAnalisa.addEventListener('change', () => {
      ANALISA_BULAN = selAnalisa.value || null;
      renderAnalisa(ANALISA_BULAN);
    });
  }

  $('btn-prev-month').addEventListener('click', async () => {
    state.month = addMonths(state.month, -1);
    /* Status lipatan dibuang saat ganti bulan: kunci tanggal (YYYY-MM-DD)
       tidak akan sama di bulan lain, jadi menyimpannya hanya menumpuk sampah
       — dan lebih buruk, tanggal yang sama di bulan lain akan mewarisi
       keadaan buka/tutup yang tidak pernah diminta pengguna. */
    LIPAT_TANGGAL = {};
    await refresh();
  });
  $('btn-next-month').addEventListener('click', async () => {
    state.month = addMonths(state.month, 1);
    LIPAT_TANGGAL = {};
    await refresh();
  });

  /* Tombol tema: putar tiga keadaan. Ikut sistem tetap default, jadi kalau
     kamu tidak pernah menekan tombol ini, perilakunya sama seperti sebelum
     pemilih tema ada. */
  const btnTema = $('btn-tema');
  if (btnTema) {
    btnTema.addEventListener('click', () => {
      const kini = document.documentElement.dataset.tema || 'sistem';
      const berikut = TEMA[(TEMA.indexOf(kini) + 1) % TEMA.length];
      pasangTema(berikut);
    });
  }
  /* Kalau pilihan sedang "Ikut sistem", ikuti perubahan mode macOS tanpa
     perlu reload. */
  const mq = window.matchMedia('(prefers-color-scheme: dark)');
  const ikut = () => {
    if ((document.documentElement.dataset.tema || 'sistem') === 'sistem') {
      document.documentElement.classList.toggle('gelap', mq.matches);
      gambarTombolTema();
    }
  };
  if (mq.addEventListener) mq.addEventListener('change', ikut);
  else if (mq.addListener) mq.addListener(ikut);

  /* Tombol sensor: sembunyikan / tampilkan nominal. Karena penyamaran terjadi
     di rupiah(), seluruh tampilan harus digambar ulang supaya angkanya
     berubah — refresh() membaca ulang dari API dan menggambar semua bagian. */
  const btnSensor = $('btn-sensor');
  if (btnSensor) {
    btnSensor.addEventListener('click', async () => {
      saklarSensor(!SENSOR);
      gambarTombolSensor();
      await refresh();
    });
  }

  gambarTombolTema();
  gambarTombolSensor();

  /* Tombol keluar (di layar Akun paling bawah). */
  const btnKeluar = $('btn-keluar');
  if (btnKeluar) btnKeluar.addEventListener('click', keluar);

  $('composer-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const ta = $('chat-input');
    const text = ta.value.trim();
    if (!text) return;
    ta.value = '';
    await sendChat(text);
  });
  /* textarea tumbuh tanpa field-sizing (tidak didukung Safari) */
  const ta = $('chat-input');
  const autoGrow = () => {
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 132) + 'px';
  };
  ta.addEventListener('input', autoGrow);

  /* tinggi header diukur, bukan ditebak: header tanggal yang lengket harus
     menempel tepat di bawah appbar, berapa pun tingginya. */
  const syncHeaderOffset = () => {
    const h = Math.ceil($('appbar').getBoundingClientRect().height);
    document.documentElement.style.setProperty('--appbar-h', h + 'px');
  };
  syncHeaderOffset();
  window.addEventListener('resize', syncHeaderOffset);
  /* Navbar atas berubah tinggi saat teks label membesar (mis. font sistem
     berubah), jadi ukur ulang setelah font selesai dimuat. */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(syncHeaderOffset).catch(() => {});
  }

  $('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      $('composer-form').requestSubmit();
    }
  });
}

(async function init() {
  wire();
  /* Tahun footer diisi dari jam mesin supaya tidak perlu diperbarui manual. */
  const th = $('tahun');
  if (th) th.textContent = String(new Date().getFullYear());
  /* Sapa sekali di layar Catat.
     Kalimatnya TIDAK menyuruh "ketuk ＋ Catat" — pengguna sudah berada di
     layar Catat saat ini tampil, dan instruksi yang menyuruh pindah ke tempat
     yang sudah didatangi bikin bingung. Yang berguna disebut di sini adalah
     apa yang boleh ditulis dan bahwa hasilnya masih draft. */
  chatBubble('Tulis kalimat transaksinya, aku uraikan jadi draft — belum '
    + 'tersimpan sampai kamu tekan Simpan. Contoh: "makan malam 45000 sama '
    + 'parkir 5rb".');
  await refresh();
})();
