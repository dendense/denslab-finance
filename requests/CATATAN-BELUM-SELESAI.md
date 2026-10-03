# Catatan pekerjaan belum selesai — panel web finance

**Dari:** yuki (FRONTEND)
**Terakhir diperbarui:** 3 Okt 2026, 21:00

Berkas ini daftar hal yang **sudah diminta Deny tapi belum dikerjakan**, supaya
sesi berikutnya tidak perlu menebak atau mengulang. Setiap butir menyebut apa
yang menghalanginya.

**Cara memakai berkas ini:** butir 1–4 **belum dikerjakan**. Bagian
"Sudah selesai" di bawah jangan dikerjakan ulang.

---

## 1. Grafik tren masih 6× `/api/summary` — SEHARUSNYA 1× `/api/trend`

**Status:** belum dikerjakan. Prioritas tertinggi dari yang tersisa.

`/api/trend?months=6` sudah ada dan satu request menggantikan enam. Sudah
kukonfirmasi ke monica: bentuk `items` (urut lama → baru, bulan kosong `null`)
**cukup** untuk grafik yang ada, jadi ini murni penggantian sumber + hapus loop
6 fetch. Tidak butuh koordinasi lagi.

**Kenapa penting:** 6 request berurutan = 6× waktu tunggu di HP dengan sinyal
lemah.

**Yang harus diuji ulang setelah diganti** (dari surat
`monica-ke-yuki-2026-10-03-tugas-malam-ini.md`): grafiknya harus **sama persis**
seperti sekarang. Kalau ada batang yang berubah tinggi, sumber barunya tidak
setara — bukan sekadar "tampilan masih kelihatan benar".

---

## 2. Chip kategori masih dari `state.categories`, bukan `/api/categories`

**Status:** belum dikerjakan. `/api/categories` sudah ada (11 kategori) dan bisa
langsung jadi chip, sama seperti chip akun yang sudah jalan.

**Sumber sekarang:** `state.categories` yang diisi dari `/api/summary`.
Berfungsi, tapi membuat dua sumber berbeda untuk hal yang sama — dan itu jenis
masalah yang nanti sulit dilacak.

---

## 3. Penanda `source` di baris transaksi belum ditampilkan

**Status:** belum dikerjakan. `source` (`manual` / `statement`) sudah dikirim
`/api/transactions` dan balasan `PATCH`.

**Rencana yang sudah disetujui monica:** kalau `source == 'statement'`, **jangan
tampilkan tanggal dicatat** — transaksi impor dibuat dalam detik yang sama oleh
skrip, dan menampilkan `created_at`-nya membuat orang mengira 15 transaksi
dicatat berbarengan. Tampilkan asalnya ("impor statement") sebagai gantinya.

---

## 4. `transfer` belum bisa diedit dari panel

**Status:** sengaja ditahan. Kalau `flow_type` diubah ke `transfer`, tombol
Simpan mati dengan keterangan bahwa akun tujuan belum ada di layar itu.

**Kenapa:** `PATCH /api/transactions/<id>` menolak `transfer` tanpa
`to_account_id`/`to_account_hint`. Monica menegaskan: **jangan kirim request
setengah jadi.** Jadi ini butuh kolom akun tujuan di form edit dulu.

---

## Hal yang sudah selesai (jangan dikerjakan ulang)

### Panel & layar

Panel 4 layar + layar ke-5 **Analisa** · grafik batang tren · chat dua langkah +
chip koreksi `flow_type` · tombol sensor nominal · 2 tema (terang/gelap/sistem) ·
footer · panel Akun (tambah + ubah nama) · tombol Edit & Hapus ikon di halaman
Daftar · `balance_inactive` di Beranda & Akun · navbar bebas overflow di 20 lebar
(360–1440px).

### Halaman login — selesai

`web/login.html` (mode pasang/masuk otomatis, tombol mata, `panjang_min_password`
diambil dari `GET /api/auth` — tidak lagi menulis "6" keras) · **11 dari 11**
pemanggil API lewat pembungkus `fetchSesi()` yang menangani 401 → `/login` ·
penjaga sekali-jalan `SEDANG_KE_LOGIN` (satu muat Beranda memanggil 3 endpoint
sekaligus; tanpa penjaga itu `location.replace` dipanggil 3×) · tombol keluar di
layar Akun (169×44 px) · pesan "Sesi berakhir" muncul sekali lalu `sessionStorage`
dibersihkan.

### Halaman Analisa Bulanan — selesai

Layar ke-5 di navbar, pemilih bulan dari `/api/months` (default: bulan terbaru
yang `boleh_dianalisa`, **bukan** bulan berjalan). Keempat aturan monica dipatuhi
dan diverifikasi dengan angka pembanding:

| Aturan | Bukti |
|---|---|
| "Bisa ditabung" pakai `sisa_bebas` | layar `Rp 7.800.000` = API `sisa_bebas`; `sisa_kas` (`Rp 7.400.000`) tidak dipakai |
| `peringatan` kelengkapan di ATAS angka | kartu amber muncul sebelum kartu "Bisa ditabung" |
| `potensi_hemat: null` tanpa angka | nol kecocokan `/Rp 0/` |
| `asumsi` wajib | tampil di setiap kategori |
| Tombol mati kalau `boleh_dianalisa: false` | Oktober `mati: true` + alasannya ditulis di layar |

Diuji dengan 2 bulan di **salinan** database + server terpisah (port 8798/8799).
Database Deny tidak disentuh.

### Kartu target tabungan (Beranda) — selesai

`renderTargetTabungan()` dari `/api/savings`, dipindah ke **atas** panel
transaksi terakhir. Tiga keadaan `null` ditangani: belum ada setoran, target
sudah terlampaui, dan `persen` > 100 ("433% dari target · Lebih Rp 9.500.000").

### Panel "sisa bulan lalu" di atas grafik tren — selesai

`renderSisaBulanLalu()` — Deny minta panel di atas grafik tren berisi sisa bulan
sebelumnya, dengan placeholder kalau belum ada data.

**Sumber:** `angka.net_worth_akhir` + `angka.per_tanggal` dari
`/api/analysis?month=<bulan lalu>` — dibangun monica (pilihan C, yang kusukai)
lewat `db.saldo_per_tanggal()` + `db.akhir_bulan()`.

**Dua keadaan `null` dibedakan, dan ini bagian yang mudah salah:**

| Keadaan | Yang ditampilkan |
|---|---|
| bulan belum selesai | "Bulan X belum selesai, jadi belum ada angka akhir bulan untuk dibandingkan." |
| bulan selesai tapi kosong | "Tidak ada transaksi tercatat di X, jadi saldo akhir bulan itu sama dengan bulan sebelumnya." |

`null` **tidak pernah** ditulis sebagai Rp 0. Placeholder bergaris putus-putus.

**Diuji:** placeholder (September kosong) dan jalur ada angka — dengan salinan
DB yang sengaja dibuat berbeda, terbukti `▼ Rp 34.800 lebih rendah dari sekarang`
dan angka itu cocok dengan hitungan dari API (`100.000 in − 27.000 out −
107.800 out` di Oktober). 12 kombinasi tema × lebar: nol luber di 360–1280px.

**Kontras — temuan yang menular ke 8 tempat lain:** catatan 11px dengan
`text-gray-400 dark:text-gray-500` hanya **2,60:1** (terang) dan **3,67:1**
(gelap) — **gagal WCAG AA 4.5:1**. Diganti ke `text-gray-500 dark:text-gray-400`
yang sudah dipakai 28 tempat lain di berkas yang sama → **4,84:1** dan **6,82:1**,
lulus. Delapan tempat ikut terperbaiki: baris 674, 1121, 1613, 2509, 2701, 2750,
2762, 2855.

### Bug `POST /api/analysis` — diperbaiki monica, terverifikasi

`model_config` tidak diimpor di `server.py` (dipakai di baris 346) → `NameError`
setelah model menjawab, jadi narasi sudah jadi lalu dibuang, dan exception keluar
sebelum `_send()` sehingga klien melihat **HTTP 000 / koneksi putus** — tampak
seperti server mati, bukan seperti bug. Sekarang `import model_config` ada di
baris 26; `POST /api/analysis` balas JSON rapi.

**Belum terverifikasi:** jalur sukses pembuatan narasi (`narasi_basi`,
`per_kategori`, tombol "Hapus narasi") — tidak ada bulan dengan data yang sudah
selesai, jadi tidak ada yang bisa diuji. Coba lagi setelah ada.

### Password uji — SUDAH DIHAPUS

`data/kredensial.json` dihapus 3 Okt 21:00 setelah pengujian login selesai. Deny
memasang passwordnya sendiri lewat `python3 scripts/reset_password.py`.

**Aturan mulai sekarang:** **jangan tulis password apa pun di surat**, walau cuma
password uji. Surat-surat ini dokumen yang berlaku di folder ini — password lebih
baik tidak punya jejak tertulis. (Diminta monica; alasannya benar.)

---

## Yang belum pernah diuji sama sekali (jujur, bukan daftar keberhasilan)

| Hal | Kenapa belum |
|---|---|
| Jalur sukses narasi analisa | tidak ada bulan selesai yang punya data |
| Panel "sisa bulan lalu" dengan **bulan ini punya** transaksi | Deny baru punya 1 bulan data (Oktober, berjalan) |
| Pemilih bulan di halaman Analisa dengan >2 bulan | `/api/months` mengembalikan 1 bulan |
| Form edit `transfer` | sengaja ditahan (§4) |
| Perbandingan naik/turun saran hemat antar bulan | butuh ≥2 bulan data |

Empat yang terakhir bukan bug — itu **keadaan data**, dan semuanya akan
terbuka sendiri begitu Deny punya lebih dari satu bulan transaksi.

---

*Ditulis yuki. Setiap butir di sini pernah salah sekali: §1, §4, §7, §8 di versi
sebelumnya sudah selesai tapi masih tertulis "belum dikerjakan" — dan itu justru
masalah yang berkas ini dibuat untuk mencegahnya. Kalau kamu membaca ini dan
isinya tidak cocok dengan keadaan, perbarui dulu sebelum mengerjakan apa pun.*
