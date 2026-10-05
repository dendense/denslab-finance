# Catatan pekerjaan belum selesai — panel web finance

**Dari:** yuki (FRONTEND)
**Terakhir diperbarui:** 5 Okt 2026 (monica) — §5 endpoint selesai, §4 duplikat dibersihkan

Berkas ini daftar hal yang **sudah diminta Deny tapi belum dikerjakan**, supaya
sesi berikutnya tidak perlu menebak atau mengulang. Setiap butir menyebut apa
yang menghalanginya.

> ## ⏸️ PENGEMBANGAN DIBUKA LAGI — 5 Okt 2026
>
> Deny membuka pengembangan untuk **bug serius**. Yang dikerjakan 5 Okt: §1
> (chip kategori), §4 (pesan gagal), §5 (panel cek AI). Butir §2 dan §3 **masih
> ditahan** — keduanya memperbaiki yang *berfungsi*, bukan yang *rusak*.
>
> Sebelum mengerjakan apa pun di sini: **tanya Deny dulu** apakah masih dibuka.

**Cara memakai berkas ini:** §5 = pekerjaan **baru** (5 Okt). §2–§3 ditahan.
§4 = temuan, **sudah disisir dan dikerjakan**. Bagian "Sudah selesai" jangan
dikerjakan ulang.

---

## 5. Panel cek jaringan AI di halaman Catat — SIAP (5 Okt)

**Status:** ✅ UI selesai · ✅ **endpoint selesai** (monica, 5 Okt —
`requests/monica-ke-yuki-2026-10-05-endpoint-ai-status.md`). Tinggal
menyambungkan.

`GET /api/ai-status` → `{ok, model, endpoint, latensi_ms, keadaan, pesan}`

`keadaan` berisi `ok` / `lambat` / `gagal` — **ambang "lambat" (5 detik) ada di
server, jangan diduplikasi di UI.** Panggil saat Deny menekan "Periksa", bukan
setiap muat halaman: setiap panggilan membakar kuota.

Deny minta panel di atas panel chat untuk melihat apakah AI-nya bisa dipakai.
Deny awalnya minta **kolom URL + API key yang bisa diisi sendiri dari UI** —
itu **ditolak yuki**, dan alasannya dicatat di §5b. Yang dikerjakan: versi
**tanpa kunci** dengan indikator hijau/kuning/merah.

### 5a. Yang sudah dikerjakan (UI)

`renderStatusAI()` di `web/app.js` + `#ai-host` di `web/index.html`. Selalu
terbuka (bukan dilipat), di atas panel chat, memakai token warna yang ada.

Indikatornya punya **empat** keadaan, bukan tiga — "belum diperiksa" bukan
"hijau":

| Keadaan | Warna | Arti |
|---|---|---|
| `ok` | hijau | AI menjawab |
| `lambat` | kuning | menjawab tapi lambat |
| `gagal` | merah | tidak menjawab — sebabnya ditampilkan |
| `belum` | abu | belum diperiksa — **jangan tampilkan hijau** |

### 5b. KENAPA panel ini TIDAK punya kolom API key — jangan tambahkan

Ini keputusan sengaja, sudah ditolak sekali. **Jangan "memperbaiki" dengan
menambahkan kolom kunci.**

1. Kunci di UI = kunci di browser = kunci terkirim lewat HTTP dan tersimpan di
   `localStorage`/`finance.db`. Berkas `finance.db.cadangan-sebelum-rapi` dan
   `cadangan-*.tgz` di `finance-pribadi/` akan **ikut memuat kunci** itu.
2. `env.sh` sengaja diletakkan **di luar repo** justru supaya kunci tidak ikut
   ter-push. Repo ini pernah publik (monica menulis aturan repo publik 3 Okt).
   Menaruh kunci di DB membatalkan pengaman itu.
3. `CONTRACT.md` §1 menetapkan UI hanya memanggil endpoint finance. UI **tidak
   boleh tahu alamat provider** (9Router/Kenari) — itu pengetahuan server.
4. Cara mengganti endpoint/kunci: **satu baris di `env.sh`**
   (`NINE_ROUTER_BASE`, `NINE_ROUTER_API_KEY`), dibaca `src/model_config.py:34`.
   Bukan lewat UI.

### 5c. Yang DIBUTUHKAN dari monica — endpoint baru

| Method | Path | Isi yang dibutuhkan |
|---|---|---|
| `GET` | `/api/ai-status` | `ok`, `model`, `endpoint`, `latensi_ms`, `pesan` |

`endpoint` ditampilkan sebagai **INFORMASI** (Deny bilang endpoint sudah pindah
ke Kenari langsung) — dibaca dari server, **tidak bisa diubah dari UI**.

Sebelum endpoint ini ada, panel jatuh ke keadaan `belum` dan **tidak
menampilkan hijau** — lebih baik terlihat "belum tahu" daripada berpura-pura
sehat. Jangan juga memakai `/api/parse` untuk cek lalu lintas setiap muat
halaman: itu mengirim kalimat ke model dan membakar kuota Deny diam-diam.

---

## 4. TEMUAN: pola "gagal" yang terbaca seperti "data kosong" — SELESAI 5 Okt

**Status:** ✅ **selesai.** Disisir satu per satu; semuanya sudah membedakan
gagal vs kosong: `renderSisaBulanLalu()`, `renderTargetTabungan()`,
`renderAkun()`, pemilih bulan serta `/api/analysis` di halaman Analisa.

**Satu yang sengaja TIDAK diuji hidup:** `/api/analysis` benar-benar mati
(kodenya terpisah dan sudah ditangani, tapi belum dibuktikan dengan endpoint
yang dimatikan sungguhan). Bukan bug yang diketahui — cuma lubang bukti.

**Tiga cacat nyata ketemu saat menyisir ini, sudah diperbaiki 5 Okt:**

| Cacat | Sebelum | Sesudah |
|---|---|---|
| Tombol "Isi manual" menempel ke kalimat | `...environmentIsi manual` | elemen terpisah, ukur `menempel: false` |
| Pesan gagal bocorkan nama env var | `Model tidak bisa dihubungi: NINE_ROUTER_API_KEY tidak ada di environment` | `Catat pintar sedang tidak bisa dipakai — model tidak menjawab. Kamu tetap bisa mengisi manual.` |
| `favicon.ico` 404 di setiap muat | 404 di log | ikon data-URI; `performance` mencatat **nol** permintaan favicon |

**Bug ketiga yang ketemu sendiri** — `src/chat_entry.py:98`: `except Exception:`
tidak menangkap `e2`, jadi `% e` merujuk kegagalan model **utama**. Saat model
utama dan cadangan sama-sama gagal, sebab kegagalan **cadangan hilang** —
padahal itu yang paling berguna untuk mendiagnosa. Sekarang menangkap `e2` dan
menyebut keduanya.

**Tempat KEDUA yang bisa membocorkan nama env var:** `/api/ai-status` (monica,
5 Okt). Versi pertamanya menulis `NINE_ROUTER_API_KEY` di pesannya — ketahuan
karena ada uji khusus yang men-`grep` nama variabel di seluruh JSON balasan,
dan uji itu gagal. Sudah diperbaiki. **Kalau kamu menambah pesan gagal baru
dari server, jalankan uji yang sama.**

---

## 1. Chip kategori — SELESAI (5 Okt)

**Status:** ✅ **selesai.** Ditahan di versi sebelumnya, dikerjakan 5 Okt.

**Ternyata BUKAN "belum ada endpoint"** seperti tertulis di versi catatan
sebelumnya. `/api/categories` sudah ada dan mengembalikan 11 kategori;
komentar di `app.js:445` sudah **basi** dan membohongi tiga sesi. Yang
sebenarnya terjadi:

```
state.categories = []   ← dideklarasikan kosong
grep "state.categories ="  → NOL pengisian, dari hari pertama
grep "api/categories"      → NOL pemanggilan dari app.js
```

Akibatnya chip kategori **tidak pernah muncul** di layar Catat (jatuh ke kolom
teks bebas, sehingga salah ketik lolos ke `/api/save`), dan pemilih kategori di
form edit hanya menulis *"Tidak ada pilihan kategori"*.

**Perbaikan:** `refresh()` mengisi `state.categories` dari `/api/categories`,
persis pola `state.accounts` di atasnya, **sebelum** `renderDaftar()` dipanggil
(kalau sesudah, chip di halaman Daftar tetap kosong). Komentar basi diperbaiki.

**Bukti di browser** (server uji di salinan `/tmp`, 32 transaksi):

| Keadaan | Chip yang tergambar |
|---|---|
| `state.categories = []` (kode lama) | **0 chip** + teks "Kategori sekarang: Makan" |
| terisi (kode baru) | **8**: Makan, Transport, Belanja, Hiburan, Tagihan, Kesehatan, Pendidikan, Lainnya |
| pilih *Pemasukan* | **3**: Gaji, Bonus, Lainnya |
| pilih *Pindah akun* | "Pindah akun tidak memakai kategori." |

Log server juga membuktikan: `GET /api/categories → 200` muncul di **setiap**
muat halaman. Sebelumnya baris itu tidak pernah ada.

---

## 2. Chip kategori dari `/api/categories` — DITAHAN

**Status:** ⏸️ **ditahan** — bukan karena halangan teknis, tapi karena Deny
menghentikan pengembangan. `/api/categories` sudah ada (11 kategori) dan bisa
langsung jadi chip, sama seperti chip akun yang sudah jalan.

**Sumber sekarang:** `state.categories` **sudah diisi dari `/api/categories`**
(§1, dikerjakan 5 Okt). Menggantinya dari `/api/summary` menghilangkan sumber
ganda, tapi tidak memperbaiki apa pun yang rusak.

**Kapan dikerjakan:** kalau ada bug yang menyentuh chip kategori, atau kalau
Deny memintanya. Itu saat yang tepat.

---

## 3. `transfer` belum bisa diedit dari panel

**Status:** ⏸️ sengaja ditahan sejak awal. Kalau `flow_type` diubah ke
`transfer`, tombol Simpan mati dengan keterangan bahwa akun tujuan belum ada di
layar itu.

**Kenapa:** `PATCH /api/transactions/<id>` menolak `transfer` tanpa
`to_account_id`/`to_account_hint`. Monica menegaskan: **jangan kirim request
setengah jadi.** Jadi ini butuh kolom akun tujuan di form edit dulu.

**Kapan dikerjakan:** kalau Deny benar-benar perlu memperbaiki transaksi
`transfer` yang salah input.

---

## 6. Perbandingan naik/turun yang belum teruji (bukan bug)

**Status:** ⏸️ menunggu **keadaan data**, bukan pekerjaan.

Deny baru punya satu bulan transaksi (Oktober, masih berjalan). Empat hal ini
akan terbuka sendiri begitu ada bulan kedua:

| Hal | Kenapa belum bisa diuji |
|---|---|
| Jalur **sukses** narasi analisa (`narasi_basi`, `per_kategori`, tombol "Hapus narasi") | belum ada bulan selesai yang punya data |
| Panel "sisa bulan lalu" dengan bulan **berisi** angka | September kosong |
| Pemilih bulan halaman Analisa dengan > 2 bulan | `/api/months` mengembalikan 1 bulan |
| Saran hemat naik/turun antar bulan | butuh ≥ 2 bulan data |

**Jangan kerjakan apa pun di sini.** Uji ulang saja kalau ada bulan kedua.

---

## 7. TEMUAN lama — sudah dilebur ke §4 di atas

*(Duplikat ini sudah tidak berlaku; isinya ada di §4 "pola gagal yang terbaca
seperti data kosong".)*

---

## Hal yang sudah selesai (jangan dikerjakan ulang)

### Panel & layar

Panel 4 layar + layar ke-5 **Analisa** · grafik batang tren · chat dua langkah +
chip koreksi `flow_type` · tombol sensor nominal · 2 tema (terang/gelap/sistem) ·
footer · panel Akun (tambah + ubah nama) · tombol Edit & Hapus ikon di halaman
Daftar · `balance_inactive` di Beranda & Akun · navbar bebas overflow di 20 lebar
(360–1440px).

### Grafik tren 1× `/api/trend` — SELESAI 4 Okt

Dulu 6× `/api/summary` (satu per bulan). Sekarang **1 request**. Diukur dengan
membungkus `window.fetch`:

```
SEBELUM : /api/summary x7  (1 state + 6 grafik)
SESUDAH : /api/summary x1  + /api/trend x1
```

**Diverifikasi dengan pembanding angka, bukan tangkapan layar** — prosedur
monica di `requests/monica-ke-yuki-2026-10-04-trend-dan-balasan.md` §3, skripnya
di `/tmp/banding-tren.py`:

```
Empat field dibandingkan per bulan: total_in, total_out, net_real, expense_real
2026-05..09  (None,None,None,None) di kedua sisi        -> sama
2026-10      (8496600,2859246,7603550,893050) kedua sisi -> sama
SEMUA SAMA — sumber baru setara
```

Dijalankan **dua kali** (sebelum dan sesudah perubahan); hasilnya identik.
Rasio grafik tetap `3.60` di 8 kombinasi tema × lebar.

**Catatan penting:** skrip asli monica hanya membandingkan `total_in` dan
`total_out` — padahal grafiknya menggambar `net_real` dan `expense_real`.
Sudah kuperluas jadi empat field; tanpa itu, sumber baru bisa berbeda di dua
field yang benar-benar digambar dan ujinya tetap bilang "semua sama".

`loadTrend()` **mengembalikan bentuk yang sama persis** seperti sebelumnya, jadi
`drawChart()` tidak disentuh — grafiknya sudah teruji.

### Keterangan waktu di halaman Daftar — SELESAI 3 Okt

Jam dicatat tampil **di sebelah tanggal** (permintaan Deny): `3 Okt 2026 · 23:36 dicatat`.

Empat keadaan, dua di antaranya yang mudah salah:

| Keadaan | Yang ditampilkan |
|---|---|
| dicatat hari sama | `· 23:36 dicatat` |
| **dicatat beda hari** | `· dicatat 3 Okt 2026 23:36` — tanggalnya disebut, supaya tidak menipu soal kapan uangnya keluar |
| `created_at` kosong | **tidak ada keterangan** — bukan "NaN" atau karangan |
| **`source: statement`** | `impor rekening koran` — **jamnya sengaja tidak ditampilkan** |

**Kenapa statement tidak menampilkan jam:** terukur, ke-15 baris impor punya
`created_at` **sama persis** (`2026-10-03 07:46:26`) karena ditulis satu skrip
dalam sedetik. Menampilkan "07:46 dicatat" di limabelas baris membuat Deny
mengira dia mencatatnya berbarengan.

**Wadahnya `flex-wrap`, bukan satu baris dipaksa** — alasan lama di kode: memaksa
sebaris di kolom sempit pernah memotong nama akun. Terukur: di 360px, 22 baris
sebaris dan 3 turun (yang terpanjang); **di 390px ke atas semuanya sebaris**.

### Kapitalisasi judul transaksi — SELESAI 3 Okt

Aturan yang Deny pilih: kata dirapikan **hanya kalau seluruhnya huruf kecil**;
begitu ada satu huruf kapital, kata itu dilewati utuh.

**HANYA di titik tampil — database TIDAK diubah.** Dibuktikan dengan sidik jari
DB identik (`95e6f3228e6c1f06`), diuji pada 25 catatan sungguhan. Alasan kedua
yang penting: **pencarian di sisi server tetap memakai teks yang Deny tulis** —
kalau UI menulis ulang ke database, `"parkir"` yang dia cari bisa tersimpan
sebagai `"Parkir"`.

Nol dari 12 kata merek/acronym rusak (SirayAI, QRIS, GoPaylater, SPinjam,
BRIVA, BI-Fast, TWP TNI AU, Kaget30GB28Hari, MDB, Azko, ATM, BRI). Kata sambung
tetap kecil (`ke`, `di`, `via`) lewat `KECIL_SELALU`; `e-toll` lewat
`PERTAHANKAN`.

**Form edit tetap menampilkan teks ASLI** — kolom input `parkir malam`,
ringkasan "Sebelumnya:" `Parkir Malam`. Kalau kolomnya ikut dirapikan, teks
aslinya tertimpa tanpa Deny minta.

**Soal `rin-studio`:** Deny memutuskan **dibiarkan**. 12 catatan lama akan tampil
`Rin-studio` — konsisten dengan "Rin Studio" yang akan dia tulis mulai sekarang.
Tidak ada pengecualian di kode untuk itu.

### Tombol lipat per tanggal (halaman Daftar) — SELESAI 3 Okt

Aturan yang Deny tetapkan: **bulan > 8 transaksi → hanya hari ini yang terbuka**;
bulan ≤ 8 transaksi → semua terbuka. Hari ini kosong → placeholder di atas,
tanggal lain tetap di bawahnya.

Status lipatan diingat (`LIPAT_TANGGAL`) dan dibersihkan saat ganti bulan.

### Halaman login — SELESAI

`web/login.html` (mode pasang/masuk otomatis, tombol mata, `panjang_min_password`
diambil dari `GET /api/auth` — tidak lagi menulis "6" keras) · **11 dari 11**
pemanggil API lewat pembungkus `fetchSesi()` yang menangani 401 → `/login` ·
penjaga sekali-jalan `SEDANG_KE_LOGIN` (satu muat Beranda memanggil 3 endpoint
sekaligus; tanpa penjaga itu `location.replace` dipanggil 3×) · tombol keluar di
layar Akun (169×44 px) · pesan "Sesi berakhir" muncul sekali lalu `sessionStorage`
dibersihkan.

### Halaman Analisa Bulanan — SELESAI

Layar ke-5 di navbar, pemilih bulan dari `/api/months` (default: bulan terbaru
yang `boleh_dianalisa`, **bukan** bulan berjalan). Keempat aturan monica dipatuhi
dan diverifikasi dengan angka pembanding:

| Aturan | Bukti |
|---|---|
| "Bisa ditabung" pakai `sisa_bebas` | layar = API `sisa_bebas`; `sisa_kas` tidak dipakai |
| `peringatan` kelengkapan di ATAS angka | kartu amber muncul sebelum kartu "Bisa ditabung" |
| `potensi_hemat: null` tanpa angka | nol kecocokan `/Rp 0/` |
| `asumsi` wajib | tampil di setiap kategori |
| Tombol mati kalau `boleh_dianalisa: false` | Oktober `mati: true` + alasannya ditulis di layar |

Diuji dengan 2 bulan di **salinan** database + server terpisah.

### Kartu target tabungan (Beranda) — SELESAI

`renderTargetTabungan()` dari `/api/savings`, dipindah ke **atas** panel
transaksi terakhir. Tiga keadaan `null` ditangani: belum ada setoran, target
sudah terlampaui, dan `persen` > 100.

### Panel "sisa bulan lalu" di atas grafik tren — SELESAI

`renderSisaBulanLalu()` — sumber `angka.net_worth_akhir` + `angka.per_tanggal`
dari `/api/analysis?month=<bulan lalu>`.

**Dua keadaan `null` dibedakan:** bulan belum selesai vs bulan selesai tapi
kosong. `null` **tidak pernah** ditulis sebagai Rp 0.

### Kontras — 8 tempat diperbaiki

Catatan 11px dengan `text-gray-400 dark:text-gray-500` hanya **2,60:1** (terang)
dan **3,67:1** (gelap) — **gagal WCAG AA 4.5:1**. Diganti ke
`text-gray-500 dark:text-gray-400` → **4,84:1** dan **6,82:1**. Delapan tempat
ikut terperbaiki.

Chip yang tidak terpilih tadinya `bg-white` — di mode gelap itu **titik paling
terang di layar** (17,75:1), sehingga chip yang TIDAK dipilih lebih menarik mata
daripada yang dipilih (biru, 5,25:1). Sekarang transparan + garis tepi.

### Bug `POST /api/analysis` — diperbaiki monica, terverifikasi

`model_config` tidak diimpor di `server.py` → `NameError` **setelah** model
menjawab, jadi narasi sudah jadi lalu dibuang; exception keluar sebelum `_send()`
sehingga klien melihat **HTTP 000** — tampak seperti server mati. Sudah diperbaiki.

**Belum terverifikasi:** jalur sukses pembuatan narasi — tidak ada bulan dengan
data yang sudah selesai (§3).

### Password uji — SUDAH DIHAPUS

`kredensial.json` dihapus; Deny memasang passwordnya sendiri. **Aturan: jangan
tulis password apa pun di surat**, walau cuma password uji.

### Aturan repo publik (surat monica 3 Okt)

- Data keuangan hidup **di luar repo** (`../finance-pribadi/`). Jangan pernah
  menulis ke `finance/data/` — folder itu tidak ada lagi.
- **`web/tailwind.css` WAJIB ikut git** walaupun hasil build. `web/.gitignore`
  sempat mengabaikannya — akibatnya orang yang meng-clone dapat panel **tanpa
  gaya sama sekali** (terbukti: clone + `curl /tailwind.css` → `302`, 0 byte).
  Sudah diperbaiki; setiap kali `src.css` berubah: `npm run css` lalu commit
  `src.css` **dan** `tailwind.css` bersama.
- Uji yang menyentuh database: `FINANCE_DATA=/tmp/uji-kamu python3 ...`.
  **Tanpa itu, uji menulis ke database Deny.** Prosedur lengkapnya di
  `web/README.md` (bagian "Cara menguji alur tulis").

---

## Yang belum pernah diuji sama sekali (jujur, bukan daftar keberhasilan)

| Hal | Kenapa belum |
|---|---|
| Jalur sukses narasi analisa | tidak ada bulan selesai yang punya data |
| Panel "sisa bulan lalu" dengan **bulan ini punya** transaksi | Deny baru punya 1 bulan data (Oktober, berjalan) |
| Pemilih bulan di halaman Analisa dengan >2 bulan | `/api/months` mengembalikan 1 bulan |
| Form edit `transfer` | sengaja ditahan (§2) |
| `/api/analysis` benar-benar mati (bukan disimulasikan) | baru disimulasikan untuk `/api/trend` |
| Panel dengan >2 bulan data | keadaan data, bukan bug |

Yang terakhir bukan bug — itu **keadaan data**, dan semuanya akan terbuka
sendiri begitu Deny punya lebih dari satu bulan transaksi.

---

*Ditulis yuki. Setiap butir di sini pernah salah sekali: §1, §4, §7, §8 di versi
sebelumnya sudah selesai tapi masih tertulis "belum dikerjakan" — dan itu justru
masalah yang berkas ini dibuat untuk mencegahnya. Kalau kamu membaca ini dan
isinya tidak cocok dengan keadaan, perbarui dulu sebelum mengerjakan apa pun.*

*Diperbarui 4 Okt 00:50: pengembangan dihentikan atas keputusan Deny. Butir 1-3
ditahan; butir 4 temuan untuk diperiksa kalau ada bug serius. Semua yang selesai
sudah dipindah ke bagian atas dengan bukti angkanya.*
