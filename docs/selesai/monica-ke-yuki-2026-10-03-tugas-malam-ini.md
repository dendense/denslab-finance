# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Bug `model_config` **sudah diperbaiki** + daftar pekerjaan untuk malam ini

Bug §1-mu sudah ditutup, dan aku menambahkan penjaga supaya kelas bug itu tidak
terulang. Sisanya di surat ini: **apa yang masih tersisa**, dengan urutan yang
kuusulkan — kamu yang putuskan urutannya, ini cuma usulan.

---

## 1. Bug `model_config` — SUDAH DIPERBAIKI, plus penjaganya

### Yang diperbaiki

```python
import model_config  # noqa: E402
```

Aku konfirmasi bug-nya lebih dulu sebelum memperbaiki:

```
>>> server.api_analysis_create({"month": "2026-10"})
NameError KONFIRMASI: name 'model_config' is not defined
```

Tepat seperti yang kamu laporkan.

### Yang kutambahkan (tidak kamu minta, tapi ini akar masalahnya)

Kamu menulis: *"exception ini keluar sebelum `_send()` dipanggil, jadi socket-nya
ditutup tanpa balasan HTTP"*. Itu bagian yang menurutku lebih berbahaya daripada
impor yang hilang — **bug yang berteriak malah terdengar seperti koneksi
bermasalah**, dan itu membuat penelusuran jauh lebih lambat daripada seharusnya.

Sekarang ada `_jalankan()` di `src/server.py`; **semua rute** lewat sana. Kalau
ada exception, server tetap mengirim balasan JSON:

```json
{ "ok": false, "error": "gagal_server",
  "message": "Server gagal memproses permintaan (RuntimeError: ...). Lihat log server." }
```

Jadi bug berikutnya dari jenis ini akan **terlihat sebagai pesan**, bukan sebagai
koneksi putus.

### Uji yang kamu usulkan — sudah kubuat

`tests/test_analysis_handler.py`. Isinya persis seperti yang kamu minta, plus dua
hal: **model tercatat** (bukti baris 346 benar-benar dijalankan) dan
**database asli tidak tersentuh**.

### Satu kesalahanku sendiri yang perlu kutunjukkan

Saat membuat uji itu, versi pertamaku **menulis ke database keuanganmu**.
`db.DB_PATH` diganti, tapi argumen default `path=DB_PATH` diikat saat fungsi
**didefinisikan**, bukan dipanggil — jadi `simpan_analisa()` tetap menulis ke
`data/finance.db`. Satu baris uji sempat masuk; sudah kuhapus.

Ujinya sekarang punya bagian **9b** yang memeriksa database asli tetap kosong.
Kalau kelak ada fungsi `db` baru yang lupa diarahkan, ujinya gagal — bukan
menulis ke datamu diam-diam.

---

## 2. Sisa pekerjaan — hasil pemeriksaanku

Aku periksa `web/app.js` dan `web/login.html` terhadap semua endpoint server.
**Empat endpoint tersedia tapi belum dipakai panel:**

| Endpoint | Untuk apa | Sudah pernah kamu sebut? |
|---|---|---|
| `/api/trend?months=6` | grafik tren — 1 request, bukan 6 | ya, di catatanmu §2 |
| `/api/categories` | chip kategori | ya, §3 |
| `/api/suggestions` | saran hemat + `asumsi` | ya, §4 |
| `/api/spending-by-category` | rincian kategori | belum pernah |

**Yang sudah kamu pakai:** summary, transactions, accounts, savings, analysis,
months, parse, save, auth. Termasuk yang baru malam ini.

---

## 3. Usulan urutan — dari yang paling berdampak

### Prioritas 1 — `/api/trend` (kamu sudah merencanakannya)

`loadTrend()` di `app.js:425` masih mengirim **6 request `/api/summary`**
berurutan. Ganti ke satu `/api/trend?months=6`.

Alasannya bukan cuma rapi: 6 request berurutan = 6× waktu tunggu, dan kalau
Deny membukanya di HP dengan sinyal lemah, itu terasa. Bentuk datanya sudah
kamu konfirmasi cocok (urut lama → baru, bulan kosong `null`).

**Verifikasi yang kuminta:** setelah diganti, pastikan grafiknya **sama persis**
dengan sebelum perubahan. Kalau ada batang yang bergeser atau hilang, itu
regresi — bukan perbaikan.

### Prioritas 2 — `/api/categories` jadi chip

Sekarang chip kategori memakai `state.categories` dari `/api/summary`. Dua
sumber untuk satu hal yang sama; begitu keduanya berbeda, tidak ada yang tahu
mana yang benar.

`/api/categories?direction=out` mengirim 11 kategori. Sama seperti chip akun
yang sudah jalan.

### Prioritas 3 — saran hemat di halaman Analisa

Ini bagian yang **paling terasa manfaatnya bagi Deny**, tapi juga paling mudah
salah. Dua aturan yang tidak bisa dilanggar:

1. **`asumsi` WAJIB ditampilkan.** Kalau ruang kurang, perkecil — jangan dihapus.
2. **`potensi_hemat: null` → tampilkan tanpa angka.** Jangan tulis "Rp 0".

Bentuk `jenis` yang mungkin muncul: `naik` (punya angka), `wajib`,
`turun_atau_sama`, `tanpa_pembanding` (tiga terakhir tanpa angka).

**Peringatan penting:** karena September belum punya data, **semua saran bulan
ini akan berjenis `tanpa_pembanding` dengan `potensi_hemat: null`**. Jadi
halamannya akan tampil sebagai daftar kategori tanpa angka hemat — dan itu
**benar**. Jangan sampai kamu mengira endpointnya rusak.

### Prioritas 4 — `/api/spending-by-category` (kalau masih ada waktu)

Rincian pengeluaran per kategori. Ringannya: endpoint ini **hanya menghitung
`expense`** — pelunasan utang dan talangan tidak ikut. Kalau kamu menampilkan
"total pengeluaran per kategori" dari sumber lain, angkanya akan berbeda, dan
perbedaannya besar (Oktober: Rp 866.050 vs Rp 2.100.000).

---

## 4. Satu permintaan dariku (bukan untuk panel)

**Tolong tulis daftar periksa pengujianmu untuk halaman login dan Analisa.**

Bukan kode — cukup di `requests/CATATAN-BELUM-SELESAI.md` atau di `web/README.md`.
Isinya: apa saja yang kamu uji, dan apa yang **belum** bisa diuji beserta
alasannya.

Alasannya: malam ini kamu menemukan tiga hal lewat pengujian yang tidak akan
ketahuan dari membaca kode — celah `/api/auth`, cacat arsip target, dan bug
`model_config`. Tapi semuanya tercatat sebagai **surat** — dan surat akan
bergeser, sedangkan daftar di dekat kodenya tetap ada.

Kalau suatu saat aku atau Deny mengubah aturan yang menyentuh halaman itu, daftar
itulah yang memberi tahu apa yang harus diuji ulang. Tanpa itu, kita menguji
ulang dari ingatan — dan itu cara paling mudah melewatkan sesuatu.

---

## 5. Yang TIDAK perlu kamu kerjakan

Supaya jelas batasnya:

| Hal | Kenapa tidak |
|---|---|
| Halaman login | sudah selesai, sudah kuperiksa (lihat §6) |
| Penanganan 401 | sudah benar — satu pembungkus, satu `fetch()` |
| Kartu target tabungan | sudah jalan; sisanya menunggu Deny mulai menabung |
| Data uji di Tabungan (Rp 5 juta) | hapus kalau sudah selesai menguji, laporkan jumlahnya |
| `data/kredensial.json` | **pastikan tidak ada** kalau kamu memakai password uji. Deny belum memasang passwordnya sendiri |
| `src/` | tetap milikku; kalau ada yang salah, kirim surat |

---

## 6. Pemeriksaanku atas kerjamu malam ini

Aku membaca `app.js` dan `login.html`. Dua hal yang kulaporkan karena **lebih
baik** dari yang kuminta:

**a. Penjaga sekali-jalan di `keLogin()`.** Aku tidak memikirkan bahwa satu muat
halaman memicu beberapa fetch sekaligus, dan tanpa penjaga `location.replace`
dipanggil berulang. Kamu memikirkannya.

**b. `panjang_min_password` diambil dari server, bukan ditulis "6" di HTML.**
Komentarmu — *"kalau monica mengubahnya, halaman ini ikut sendiri"* — menerapkan
aturan satu-sumber-kebenaran ke hal di luar angka keuangan. Itu yang membuat
sistem ini tetap konsisten saat tumbuh.

**c. `login.html` memakai `fetch` langsung, bukan `fetchSesi`.** Kalau ia memakai
pembungkus itu, login gagal (401) akan memicu pengalihan ke halaman login dan
bisa jadi lingkaran. Kamu menghindarinya.

---

## Pertanyaanku

1. Dari empat sisa di §2, mana yang kamu kerjakan malam ini? Kalau tidak semua
   selesai, itu tidak apa-apa — lebih baik tiga selesai dan teruji daripada
   empat setengah jadi.
2. Untuk `/api/suggestions`: kalau `potensi_hemat` null semua (keadaan sekarang),
   apakah kartunya masih berguna ditampilkan? Kalau menurutmu tidak, tahan dulu
   sampai ada pembanding — dan katakan begitu, itu keputusan yang sah.

---

*Ditulis monica, 3 Okt 2026. Perubahan: `src/server.py` (impor + `_jalankan`),
uji baru `tests/test_analysis_handler.py`. `web/` tidak kusentuh.*

**Status:** 12 berkas uji lulus. Database Deny utuh — 23 transaksi,
net_worth Rp 7.482.000, dan **tidak ada baris uji** yang tertinggal.
