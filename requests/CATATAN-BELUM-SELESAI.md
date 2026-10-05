# Catatan pekerjaan belum selesai — panel web finance

**Dari:** yuki (FRONTEND)
**Terakhir diperbarui:** 4 Okt 2026, 00:50

Berkas ini daftar hal yang **sudah diminta Deny tapi belum dikerjakan**, supaya
sesi berikutnya tidak perlu menebak atau mengulang. Setiap butir menyebut apa
yang menghalanginya.

> ## ⏸️ PENGEMBANGAN DIHENTIKAN — keputusan Deny, 4 Okt 2026
>
> > *"cukupkan development sampai saat ini, kita lanjutkan jika ditemukan bug
> > yang serius atau ingin menambahkan fitur baru"*
>
> **Jadi jangan kerjakan butir 1-3 di bawah tanpa Deny memintanya.** Butir 4
> (temuan jalur gagal) **bukan** pekerjaan baru — itu daftar tempat yang perlu
> diperiksa kalau ada bug serius. §1, §2, §3 sengaja tidak dikerjakan: keduanya
> memperbaiki hal yang **berfungsi**, bukan yang **rusak**.
>
> Kalau kamu membuka berkas ini di sesi berikutnya: **tanya Deny dulu** apakah
> pengembangannya sudah dibuka lagi. Jangan mengerjakan §2/§3 hanya karena
> tertulis di sini.

**Cara memakai berkas ini:** butir 1–3 **belum dikerjakan** (dan ditahan).
Butir 4 **temuan**, bukan tugas. Bagian "Sudah selesai" jangan dikerjakan ulang.

---

## 1. Chip kategori masih dari `state.categories`, bukan `/api/categories`

**Status:** ⏸️ **ditahan** — bukan karena halangan teknis, tapi karena Deny
menghentikan pengembangan. `/api/categories` sudah ada (11 kategori) dan bisa
langsung jadi chip, sama seperti chip akun yang sudah jalan.

**Sumber sekarang:** `state.categories` yang diisi dari `/api/summary`.
Berfungsi. Menggantinya menghilangkan sumber ganda, tapi tidak memperbaiki apa
pun yang rusak.

**Kapan dikerjakan:** kalau ada bug yang menyentuh chip kategori, atau kalau
Deny memintanya. Itu saat yang tepat.

---

## 2. `transfer` belum bisa diedit dari panel

**Status:** ⏸️ sengaja ditahan sejak awal. Kalau `flow_type` diubah ke
`transfer`, tombol Simpan mati dengan keterangan bahwa akun tujuan belum ada di
layar itu.

**Kenapa:** `PATCH /api/transactions/<id>` menolak `transfer` tanpa
`to_account_id`/`to_account_hint`. Monica menegaskan: **jangan kirim request
setengah jadi.** Jadi ini butuh kolom akun tujuan di form edit dulu.

**Kapan dikerjakan:** kalau Deny benar-benar perlu memperbaiki transaksi
`transfer` yang salah input.

---

## 3. Perbandingan naik/turun yang belum teruji (bukan bug)

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

## 4. TEMUAN: pola "gagal" yang terbaca seperti "data kosong" — perlu disisir

**Status:** ⏸️ **temuan, bukan tugas.** Satu sudah diperbaiki; sisanya belum
diperiksa.

Ini ketemu saat menguji jalur gagal grafik tren: ketika `/api/trend` mati,
layar berkata **"Belum ada data 6 bulan terakhir — Catat transaksi dulu"**.
Itu **menyalahkan Deny untuk kegagalan koneksi** — dan kalau dia percaya, dia
akan mengira datanya hilang lalu mencatat ulang transaksi yang sudah ada.

Sudah diperbaiki di `drawChart()`: sekarang membedakan
*"tidak ada transaksi"* dari *"gagal membaca"*.

**Yang belum disisir:** mungkin ada tempat lain di `app.js` dengan pola sama —
pesan gagal yang terbaca seperti pesan data-kosong. Kandidat yang perlu
diperiksa kalau nanti ada bug serius:

- `renderSisaBulanLalu()` — pembacaan gagal sudah ditangani terpisah, **tapi
  belum diuji dengan `/api/analysis` benar-benar mati**
- `renderTargetTabungan()` — belum diperiksa apakah bedakan gagal vs kosong
- `renderAkun()` — sudah ada penanganan terpisah, terverifikasi
- kartu saran & narasi di halaman Analisa — belum diperiksa

**Prinsipnya:** kegagalan tidak boleh menyamar jadi keadaan data. Sejalan
dengan aturan `ada_data: false` — jangan tampilkan "nol" untuk sesuatu yang
sebenarnya "tidak diketahui".

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
