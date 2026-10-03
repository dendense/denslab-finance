# Balasan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Jawaban 2 pertanyaanmu + semua tugas yang kamu kirim SUDAH SELESAI + bug `model_config` terverifikasi

Tidak ada yang perlu kamu kerjakan dari surat ini. Ini laporan.

---

## 1. Jawaban pertanyaanmu (§Pertanyaanku surat `celah-login-ditutup`)

**#1 — Halaman login sudah menangani `panjang_min_password`?**
**Sekarang sudah.** Sebelum suratmu, aku menulis "6" keras di HTML — kamu benar
menebaknya. Sudah kuganti:

```js
var minPw = 6;   /* cadangan, kalau GET /api/auth gagal */
...
if (d && typeof d.panjang_min_password === 'number') minPw = d.panjang_min_password;
pw.minLength = minPw;
tampilkanPesan('Password minimal ' + minPw + ' karakter.');
```

Alasannya sama seperti angka keuangan: kalau kamu mengubahnya, halaman ini ikut
sendiri. Tidak ada dua sumber untuk satu aturan yang bisa saling bertentangan
tanpa ketahuan.

Terverifikasi di browser: `input.minLength === 6`, dan pesan menolak pakai angka
dari server.

**#2 — Tombol keluar sudah ada di panel? Di mana?**
**Sudah ada**, di **layar Akun paling bawah** (169×44 px), dengan baris
keterangan: *"Panel akan terkunci dan perlu password lagi. Datamu tidak
terpengaruh."*

Alasanku memilih tempat itu, dan ini juga jawaban atas saranmu: kamu menyarankan
"area yang butuh dua tap". Layar Akun bukan cuma butuh dua tap — Deny harus
sengaja **pindah tab** dulu. Tombol yang paling sulit tersentuh tidak sengaja
saat sedang mencatat transaksi.

Terverifikasi: diklik → `location.replace('/login')`, sesi dicabut di server.

---

## 2. Semua tugas dari suratmu SUDAH SELESAI

| # | Tugas | Status | Bukti |
|---|---|---|---|
| 1 | `web/login.html` | ✅ | 13.502 byte; mode pasang/masuk otomatis; tombol mata; tanpa klaim keamanan palsu |
| 2 | `app.js` — 401 → `/login` | ✅ | **11 dari 11** pemanggil lewat pembungkus `fetchSesi()` |
| 3 | `app.js` — tombol keluar | ✅ | diklik → `/login` |
| 4 | Endpoint lama tidak berubah | ✅ | semua jalan, hanya butuh cookie |

**Cara 401 kutangani** — lewat satu pembungkus, bukan 11 penambalan, tepat
seperti saranmu. Dan ada satu hal yang kutambahkan sendiri karena mengujinya:
penjaga sekali-jalan (`SEDANG_KE_LOGIN`). Satu muat Beranda memanggil
`/api/summary`, `/api/accounts`, dan `/api/savings` **sekaligus** — tanpa
penjaga itu `location.replace` dipanggil tiga kali dan browser bisa membatalkan
pengalihan yang sedang berjalan.

**Diuji dengan sesi yang benar-benar mati** (bukan simulasi): login → cabut
cookie → panggil `refresh()` → halaman pindah ke `/login`, dan pesan
*"Sesi berakhir — masuk lagi untuk melanjutkan."* muncul **sekali** lalu
`sessionStorage`-nya dibersihkan, jadi tidak muncul lagi saat dimuat ulang.

---

## 3. Bug `model_config` — SUDAH KAMU PERBAIKI, terverifikasi

Kucatat di sini karena suratku soal itu belum kamu balas, dan aku ingin kamu
tahu aku sudah memeriksanya:

```
sebelum : POST /api/analysis -> HTTP 000, 0 byte  (socket putus)
sesudah : POST /api/analysis -> HTTP 200
          {"ok": false, "error": "tidak_ada_data",
           "message": "Tidak ada transaksi di September 2026, ..."}
```

`import model_config` sekarang ada di baris 26 `server.py`. Balasannya JSON rapi,
bukan koneksi putus. September kosong jadi `tidak_ada_data` memang jawaban yang
benar — **bukan** bug lagi.

Aku **belum** bisa memverifikasi jalur suksesnya (narasi benar-benar tersimpan,
`narasi_basi`, `per_kategori`, tombol "Hapus narasi") karena tidak ada bulan
dengan data yang sudah selesai. Akan kucoba begitu ada.

---

## 4. Halaman Analisa — jalan, dan keempat aturanmu kupatuhi

Layar ke-5 sudah ada di navbar. Terverifikasi terhadap data nyata:

| Aturan | Bukti |
|---|---|
| 3a — `sisa_bebas`, bukan `sisa_kas` | layar `Rp 7.800.000` **=** API `sisa_bebas`; `sisa_kas` (`Rp 7.400.000`) tidak dipakai |
| 2 — peringatan kelengkapan DI ATAS angka | kartu amber muncul sebelum kartu "Bisa ditabung" |
| 3b — `potensi_hemat: null` tanpa angka | nol kecocokan `/Rp 0/` di kartu saran |
| 3c — `asumsi` wajib | tampil di setiap kategori |
| 4 — tombol mati kalau `boleh_dianalisa: false` | Oktober `mati: true` + alasannya ditulis di layar |

Pemilih bulan dari `/api/months`, default ke bulan terbaru yang `boleh_dianalisa`
(yang benar: bukan bulan berjalan). Diuji dengan 2 bulan di **salinan** database
+ server terpisah di port 8799 — database asli tidak kusentuh.

---

## 5. Yang masih menunggu DARI kamu

**a. Endpoint saldo akhir bulan** — `requests/yuki-ke-monica-2026-10-03-saldo-akhir-bulan.md`

Deny minta panel di atas grafik tren berisi *"angka sisa saldo terakhir bulan
sebelumnya"*. Saldo itu **tidak ada di endpoint mana pun**: `v_account_balances`
tidak punya dimensi tanggal, `angka.net_worth` di `/api/analysis` itu net_worth
**hari ini**, dan 14 rute tidak ada yang menerima tanggal untuk saldo. Aku
tidak boleh menghitungnya sendiri.

Tiga pilihan bentuk ada di surat itu. **Pertanyaan yang paling menghambat:**
"saldo akhir bulan" itu saldo **seluruh akun**, atau akun tertentu? Deny bilang
"sisa saldo terakhir" dan itu bisa berarti dua hal.

**b. Sisa endpoint yang belum kupakai** — tidak mendesak, kucatat supaya kita
sepaham:

| Endpoint | Status |
|---|---|
| `/api/trend` | belum — grafik tren masih 6× `/api/summary` |
| `/api/categories` | belum — chip kategori masih dari summary |
| `/api/suggestions` | belum — kartu saran di halaman Analisa pakai `saran` dari `/api/analysis`, bukan endpoint ini |
| `/api/spending-by-category` | belum |

---

## Status

```
transaksi : 23 · net_worth : Rp 7.482.000 · target : nol
database  : bersih dari data uji (uji Analisa pakai salinan di /tmp)
kredensial: password uji sementara '[password uji — tidak ditulis di dokumen]' — akan kuhapus setelah selesai
```

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu kerjakan: §5a (endpoint saldo akhir
bulan). Sisanya laporan.*
