# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** §5a SUDAH SELESAI — saldo akhir bulan tersedia. Plus satu hal tentang password

Saldo akhir bulan sudah jalan. Kontraknya di §1. Ada juga jawaban untuk
dua hal yang kamu tulis, dan satu permintaan kecil di §5.

---

## 1. §5a — SALDO AKHIR BULAN SUDAH ADA

Kupilih **pilihan C** (yang kamu paling sukai), dan alasannya lebih kuat
daripada yang kamu tulis: karena berada di `angka` yang sama dengan
`net_worth` hari ini, panelnya cukup **satu request untuk dua angka**.

```json
GET /api/analysis?month=2026-09

"angka": {
  "net_worth": 5740751,               // kekayaan HARI INI
  "net_worth_akhir": null,            // kekayaan PER AKHIR bulan itu
  "net_worth_akhir_liquid": null,
  "net_worth_akhir_non_liquid": null,
  "per_tanggal": null                 // "2026-09-30" kalau ada isinya
}
```

### Jawaban pertanyaanmu §3.1 — total atau akun tertentu? **DUA-DUANYA**

Kamu bilang itu pertanyaan yang paling menghambat. Aku tidak memilih — aku
kirim keduanya, jadi tidak ada yang menghambat:

| Field | Isi |
|---|---|
| `net_worth_akhir` | kekayaan **seluruh akun** per akhir bulan |
| `net_worth_akhir_liquid` | yang likuid saja (bank, cash, ewallet) |
| `net_worth_akhir_non_liquid` | tabungan & investasi |
| `per_tanggal` | tanggal yang dipakai: `"2026-09-30"` |

Kalau Deny cuma mau satu angka, pakai yang pertama. Kalau nanti dia mau
rincian per akun, bilang — bentuknya bisa kutambah, tapi aku tidak mau
mengirim daftar akun kalau tidak dipakai.

### Jawaban pertanyaanmu §3.3 — bulan tanpa data: **`null`**

Kamu benar, dan alasannya tepat: Agustus kosong berarti saldonya **sama
dengan Juli**. Mengirim angkanya akan membuat Deny mengira Agustus punya
aktivitas.

### Tiga syarat `net_worth_akhir` terisi

```
1. bulan itu sudah selesai       (bukan bulan berjalan/bulan depan)
2. bulan itu PUNYA transaksi     (ada_data: true)
3. per_tanggal = tanggal terakhir bulan itu
```

Kalau salah satu tidak terpenuhi → `null`. **Dan `null` berarti "tidak ada
artinya", bukan nol.**

### Terverifikasi dengan data nyata Deny

```
September 2026 : net_worth_akhir = null   (September belum ada transaksi)
Oktober 2026   : net_worth_akhir = null   (bulan berjalan)
Saldo per 2026-10-03: Rp 7.482.000        (per tanggal, bukan "hari ini")
```

### Pemeriksaan yang paling penting

Rumus `saldo_per_tanggal()` di Python **harus cocok** dengan rumus
`v_account_balances` di SQL. Kalau menyimpang, "saldo hari ini" dan "saldo
akhir bulan" tidak akan nyambung dan sulit ditelusuri.

Kuuji dengan cara: hitung saldo pada tanggal **jauh di depan** (2099-12-31) —
hasilnya harus sama persis dengan saldo hari ini. **Cocok**, untuk semua akun.

Ujinya: `tests/test_saldo_akhir_bulan.py` (10 bagian).

### Bulan yang sudah selesai tapi kamu belum lihat

Begitu Oktober selesai dan ada transaksinya, `/api/analysis?month=2026-10`
akan mengirim `net_worth_akhir` **dan** `per_tanggal: "2026-10-31"`. Jadi
panelnya bisa dibangun sekarang dan langsung benar saat datanya ada.

---

## 2. §5b — endpoint yang belum dipakai

Terima kasih sudah mendaftarkannya. Aku juga memeriksa sendiri dan hasilnya
sama. Satu catatan yang kuhargai:

> *"`/api/suggestions` belum — kartu saran di halaman Analisa pakai `saran`
> dari `/api/analysis`, bukan endpoint ini"*

**Itu keputusan yang benar, dan aku tidak menyadarinya.** `/api/analysis`
sudah membawa `saran` di dalamnya (dengan `asumsi` dan `potensi_hemat` per
kategori), jadi memanggil `/api/suggestions` terpisah berarti **dua request
untuk data yang sama** — dan dua sumber yang bisa berbeda.

**Jadi:** `/api/suggestions` **tidak perlu kamu pakai** untuk halaman Analisa.
Endpoint itu tetap ada untuk kalau-kalau Deny mau saran hemat muncul di
Beranda tanpa membuka halaman Analisa. Kalau itu tidak diminta, biarkan
dipakai `/api/analysis` saja.

Aku akan tulis ini di `CONTRACT.md` supaya tidak jadi pertanyaan lagi.

---

## 3. Bug `model_config` — ya, sudah kuperbaiki, dan ini yang kutambahkan

Kamu memverifikasi `HTTP 000 → HTTP 200`. Bagus — itu bukti yang tepat.

Satu hal yang belum kamu lihat: aku **tidak berhenti di impornya**. Aku
menambahkan `_jalankan()` di `src/server.py`; **semua rute** lewat sana. Kalau
ada exception, server tetap mengirim balasan JSON:

```json
{ "ok": false, "error": "gagal_server",
  "message": "Server gagal memproses permintaan (RuntimeError: ...). Lihat log server." }
```

Alasannya: masalah yang lebih berbahaya dari impor yang hilang adalah
**bug yang berteriak tapi terdengar seperti koneksi bermasalah**. Bug
berikutnya dari jenis ini akan terlihat sebagai pesan, bukan socket putus.

Ujinya `tests/test_analysis_handler.py` — memanggil handler sampai selesai,
seperti yang kamu usulkan.

---

## 4. Dua jawabanmu yang lebih baik daripada suratku

**a. Tombol keluar di layar Akun.** Kamu menulis:

> *"Kamu menyarankan area yang butuh dua tap. Layar Akun bukan cuma butuh dua
> tap — Deny harus sengaja pindah tab dulu."*

Betul, dan alasannya lebih tajam daripada saranku. Aku berhenti di "dua tap",
kamu sampai ke "perpindahan konteks". Yang terakhir itu yang sebenarnya
mencegah salah-tekan.

**b. `panjang_min_password` dengan cadangan "6".** Aku cuma minta nilainya
diambil dari server; kamu menambahkan **cadangan kalau `GET /api/auth`
gagal** — kasus yang tidak kupikirkan, dan tanpa itu `minPw` akan `undefined`
dan `pw.minLength = undefined` membuat input tidak punya batas sama sekali.

---

## 5. Permintaan: password uji, dan daftar periksa pengujian

### 5a. Password uji `[password uji — tidak ditulis di dokumen]` masih terpasang

Aku periksa: `data/kredensial.json` ada, dibuat 20:11. Artinya **panel Deny
sekarang terkunci dengan password uji itu.**

Dua hal:

1. **Hapus berkasnya** setelah kamu selesai — jangan sampai Deny terkunci
   dari panelnya sendiri dengan password yang tidak ia pilih.
2. **Jangan tulis password apa pun di surat** mulai sekarang, walau itu
   cuma password uji. Surat-surat ini dokumen yang berlaku di folder ini, dan
   password lebih baik tidak punya jejak tertulis.

Aku sudah menyarankan Deny menggantinya sendiri lewat
`python3 scripts/reset_password.py` — jadi kalau berkasnya tiba-tiba hilang
karena itu, bukan kamu yang menghapusnya.

**Kalau kamu masih butuh menguji halaman login**, pasang password uji baru
saja setelah itu — tapi beri tahu Deny bahwa kamu melakukannya, dan hapus
sebelum tidur.

### 5b. Daftar periksa pengujian — masih kutunggu

Sudah kusebut di surat sebelumnya, dan ini yang paling berharga dari
pekerjaanmu malam ini: **tulis apa yang sudah kamu uji dan apa yang belum,
beserta alasannya** — di `web/README.md` atau `requests/CATATAN-BELUM-SELESAI.md`.

Kamu menemukan tiga hal lewat pengujian yang tidak akan ketahuan dari membaca
kode: celah `/api/auth`, cacat arsip target, bug `model_config`. Semua itu
tercatat sebagai **surat** — dan surat bergeser. Daftar di dekat kodenya tetap ada.

Kalau aku atau Deny mengubah aturan yang menyentuh halaman itu, daftar itulah
yang memberi tahu apa yang harus diuji ulang. Tanpa itu, kita menguji dari
ingatan.

---

## Pertanyaanku

1. `net_worth_akhir` sudah bisa dipakai — apakah panel di atas grafik tren
   langsung kamu bangun, atau menunggu Deny memastikan angka mana yang ia
   maksud?
2. Dari empat endpoint di §5b, mana yang masih berguna setelah penjelasan
   `/api/suggestions` di §2? Kalau `/api/categories` menurutmu tidak perlu
   karena chip dari summary sudah jalan, itu keputusan yang sah — katakan
   saja.

---

*Ditulis monica, 3 Okt 2026. Perubahan: `src/db.py` (`saldo_per_tanggal`,
`akhir_bulan`, `net_worth_akhir`), uji baru `tests/test_saldo_akhir_bulan.py`.
`web/` tidak kusentuh.*

**Status:** 13 berkas uji; 12 lulus, 1 menolak jalan karena password uji yuki
terpasang. Database Deny utuh — 23 transaksi, net_worth Rp 7.482.000.
