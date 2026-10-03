# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Halaman baru — **Analisa Bulanan**. Endpoint sudah jalan, kontrak lengkap di bawah

Deny meminta satu halaman baru: analisa bulanan yang dibuat **setelah bulan
selesai**, berisi pemasukan/pengeluaran, saran apa yang bisa ditekan, dan berapa
yang bisa ditabung.

Semua endpoint sudah jalan dan teruji. **Tidak ada yang perlu kamu tebak.**

---

## Ringkas untuk kamu

| # | Isi | Status |
|---|---|---|
| 1 | `GET /api/analysis?month=YYYY-MM` | ✅ jalan |
| 2 | `POST /api/analysis` — buat narasi | ✅ jalan |
| 3 | `DELETE /api/analysis/<YYYY-MM>` | ✅ jalan |
| 4 | Bentuk data lengkap | di §2 |
| 5 | Aturan yang wajib kamu patuhi | di §3 |

---

## 1. Keputusan Deny yang menentukan bentuk halaman ini

Empat keputusan, semuanya sudah dikunci:

| # | Keputusan | Akibat untuk UI |
|---|---|---|
| 1 | **Manual**, bukan terjadwal | Tidak ada proses otomatis. Deny menekan tombol. **Tidak ada analisa yang muncul sendiri.** |
| 2 | **Narasi dibuat sekali** | Sekali dibuat, narasinya tersimpan. Tidak dipanggil ulang tiap buka halaman. |
| 3 | **Angka selalu dihitung ulang** | Kalau transaksi dikoreksi, angka ikut benar. Narasinya yang ditandai **basi**. |
| 4 | **Bulan berjalan tidak bisa dianalisa** | Tombol "Buat analisa" mati untuk bulan ini. Bulan berjalan belum selesai. |

**Yang paling penting kamu tangani: `narasi_basi`.** Kalau `true`, tampilkan
peringatan — *"Narasi ini dibuat sebelum ada perubahan data"* — karena angkanya
sudah segar tapi kalimatnya belum.

---

## 2. Bentuk data

### `GET /api/analysis?month=2026-09`

Tanpa `?month=`, dipakai **bulan lalu** (karena analisa dibuat untuk bulan yang
sudah selesai).

```json
{
  "month": "2026-09",
  "nama_bulan": "September 2026",
  "bulan_berjalan": "2026-10",
  "boleh_dianalisa": true,

  "angka": {
    "month": "2026-09",
    "ada_data": true,
    "tx_count": 18,
    "masuk": 8096600,
    "keluar_semua": 3494124,
    "konsumsi": 1830000,
    "pelunasan_utang": 1378666,
    "talangan_piutang": 285458,
    "sisa_kas": 4602476,
    "sisa_bebas": 6266600,
    "kategori": [
      { "category": "Makan", "total": 780000, "tx_count": 1,
        "total_bulan_lalu": 450000, "perubahan_persen": 73, "wajib": false },
      { "category": "Transport", "total": 350000, "tx_count": 1,
        "total_bulan_lalu": 300000, "perubahan_persen": 17, "wajib": true }
    ],
    "kategori_lalu_ada": true,
    "net_worth": 5740751,
    "saldo_akun": [ { "name": "BRI", "balance": 5740751, "kind": "bank" } ],
    "kategori_wajib": ["Tagihan", "Transport"]
  },

  "saran": {
    "month": "2026-09",
    "bulan_pembanding": "2026-08",
    "ada_pembanding": true,
    "kategori": [
      { "kategori": "Makan", "total": 780000, "tx_count": 1, "wajib": false,
        "jenis": "naik", "potensi_hemat": 330000,
        "asumsi": "Makan naik dari Rp 450.000 (bulan lalu) ke Rp 780.000 — naik Rp 330.000. Angka hemat = selisihnya, kalau kembali ke pola bulan lalu." },
      { "kategori": "Transport", "total": 350000, "tx_count": 1, "wajib": true,
        "jenis": "wajib", "potensi_hemat": null,
        "asumsi": "Transport Rp 350.000 (bulan lalu Rp 300.000). Kategori ini dianggap wajib, jadi tidak disarankan dipotong." }
    ],
    "total_potensi_hemat": 330000
  },

  "ada_analisa": true,
  "dibuat_pada": "2026-10-01 08:12:33",
  "model": "kenari/deepseek-v4-1-flash",
  "narasi": {
    "ringkasan": "Di September 2026 ada 18 transaksi, dengan uang masuk Rp 8.200.000...",
    "per_kategori": {
      "Makan": "Makan keluar Rp 780.000 bulan ini, sementara bulan lalu Rp 450.000...",
      "Transport": "Transport Rp 350.000 (bulan lalu Rp 300.000). Kategori ini dianggap wajib..."
    },
    "penutup": "Dari uang masuk, sisa yang masih bebas Rp 7.700.000.",
    "kategori_diganti": ["Tagihan"]
  },
  "narasi_basi": false,
  "tx_terakhir": "2026-10-03 19:10:55",
  "catatan_analisa": null,

  "kelengkapan": {
    "month": "2026-09",
    "jumlah_hari_bulan": 30,
    "hari_tercatat": 30,
    "tx_count": 18,
    "tanggal_pertama": "2026-09-01",
    "tanggal_terakhir": "2026-09-30",
    "ambang_hari": 18,
    "lengkap": true,
    "peringatan": null
  }
}
```

### `kelengkapan` — WAJIB DITAMPILKAN kalau `lengkap: false`

Ini yang mencegah **"sisa bebas Rp 7.800.000"** dari 3 hari data terlihat seperti
uang yang benar-benar bisa ditabung.

```json
"kelengkapan": {
  "jumlah_hari_bulan": 31,
  "hari_tercatat": 3,
  "tanggal_pertama": "2026-10-01",
  "tanggal_terakhir": "2026-10-03",
  "ambang_hari": 18,
  "lengkap": false,
  "peringatan": "Data bulan ini baru mencakup 3 dari 31 hari (2026-10-01 s/d 2026-10-03). Angka sisa di bawah dihitung dari data yang ada saja — bukan gambaran sebulan penuh."
}
```

| Field | Arti |
|---|---|
| `lengkap` | `true` kalau hari tercatat ≥ 60% hari bulan itu |
| `ambang_hari` | batas hari untuk bulan itu (31 hari → 18) |
| `peringatan` | **kalimat siap tampil**, atau `null` kalau lengkap |

**Aturan UI:** kalau `peringatan` terisi, tampilkan **di atas angka sisa**, bukan
di bawah. Angkanya **tetap ditampilkan** — tidak disembunyikan. Yang perlu
dilakukan adalah menyatakan dasarnya, bukan menghapus angkanya.

Kalau tidak ada transaksi sama sekali, `peringatan` berbunyi
*"Belum ada transaksi sama sekali di bulan ini, jadi belum ada yang bisa
dianalisa."*

### `POST /api/analysis`

```json
{ "month": "2026-09" }
```

Balasan sukses = bentuk `GET` yang sama, dengan `ada_analisa: true`.

Gagal:

```json
{ "ok": false, "error": "bulan_belum_selesai",
  "message": "Bulan Oktober 2026 belum selesai, jadi belum bisa dianalisa. Angkanya masih bisa berubah." }
{ "ok": false, "error": "tidak_ada_data",
  "message": "Tidak ada transaksi di Januari 2026, tidak ada yang bisa dianalisa." }
{ "ok": false, "error": "bulan_tidak_sah",
  "message": "Format bulan harus YYYY-MM, contoh: 2026-10." }
{ "ok": false, "error": "bulan_kosong",
  "message": "Sebutkan bulan yang mau dianalisa, format YYYY-MM." }
```

**Tombol "Buat analisa" sebaiknya mati kalau `boleh_dianalisa: false`** —
jangan biarkan Deny menekan tombol yang pasti gagal. Pakai pesan `message` dari
server kalau tetap terkirim.

### `DELETE /api/analysis/2026-09`

```json
{ "ok": true, "month": "2026-09", "dihapus": true }
```

Menghapus **narasinya saja**. Angka tetap ada (dihitung ulang). Ini berguna kalau
narasi terasa tidak berguna dan Deny mau membuatnya ulang.

---

## 3. Aturan yang WAJIB kamu patuhi

### 3a. `sisa_bebas` yang dipakai sebagai "bisa ditabung" — BUKAN `sisa_kas`

Ini yang paling mudah salah, dan salahnya berbahaya.

| Field | Arti | Bahaya |
|---|---|---|
| `sisa_kas` | masuk − **semua** yang keluar | **Menyesatkan.** Pelunasan utang & talangan tidak hilang — uangnya sudah tidak ada |
| `sisa_bebas` | masuk − pengeluaran sungguhan | **Ini yang benar** untuk "bisa ditabung" |

Contoh nyata dari datamu: `sisa_kas` Rp 4.800.000 sementara `sisa_bebas`
Rp 7.700.000. Menampilkan `sisa_kas` sebagai "bisa ditabung" akan membuat Deny
mengira punya tabungan yang tidak pernah ada.

**Kartu "bisa ditabung" pakai `sisa_bebas`.** Kalau kamu mau menampilkan
`sisa_kas` juga, beri label jelas — mis. *"sisa arus kas"* — dan jangan
letakkan di sebelah angka tabungan tanpa penjelasan.

### 3b. `potensi_hemat: null` itu bukan nol

Hanya terisi kalau ada dasar hitungannya (kategori naik dibanding bulan lalu).
Kalau `null`, tampilkan **tanpa angka** — jangan tulis "Rp 0".

`jenis` yang mungkin muncul:

| `jenis` | Arti | `potensi_hemat` |
|---|---|---|
| `naik` | naik dibanding bulan lalu | **terisi** |
| `wajib` | kategori wajib (Tagihan, Transport) | `null` |
| `turun_atau_sama` | tidak lebih besar dari bulan lalu | `null` |
| `tanpa_pembanding` | bulan lalu belum ada data | `null` |

### 3c. `asumsi` WAJIB ditampilkan

Aturan dari `UI-MOBILE.md`. Angka hemat tanpa penjelasan tidak bisa dipercaya.
Kalau tempat kurang, perkecil — jangan dihapus.

### 3d. `narasi.per_kategori` selalu terisi lengkap

Aku menjamin ini: **setiap kategori punya kalimat**, baik dari AI maupun dari
hitungan. Kalau `kategori_diganti` berisi nama, artinya kalimat untuk kategori
itu berasal dari data (AI-nya dibuang karena menulis angka yang tidak ada).

Kamu tidak perlu memberi perlakuan khusus — tapi kalau mau transparan, bisa
ditandai kecil.

### 3e. Angka di narasi sudah diformat

Narasi dari AI sudah lewat pembersih: persentase dipotong (tidak bisa
diverifikasi), nominal sudah jadi `Rp 8.200.000`, dan angka yang tidak ada di
data dibuang. **Tampilkan apa adanya** — jangan diformat ulang.

### 3f. Bulan tanpa data

`angka.ada_data: false` → tampilkan **"belum ada data bulan ini"**, jangan
deretan nol. Dan `POST` akan ditolak dengan `tidak_ada_data`.

---

## 4. Saran susunan halaman

Bebas kamu tentukan — ini hanya usulanku, `UI-MOBILE.md` yang berlaku:

1. **Pemilih bulan** di atas, dengan penanda kalau belum ada analisa
2. **Kartu utama**: "Bisa ditabung bulan ini: Rp 7.700.000" (`sisa_bebas`)
3. **Ringkasan**: masuk / konsumsi / utang / talangan — dengan pemisahan jelas
4. **Narasi**: ringkasan AI, lalu per kategori dengan `asumsi` masing-masing
5. **Saran hemat**: kartu per kategori, angka + asumsinya
6. **Tombol "Buat analisa"** — mati kalau `boleh_dianalisa: false`

Kalau `narasi_basi: true`, taruh peringatan **di atas narasi**, bukan di bawah —
supaya terbaca sebelum Deny mempercayai kalimatnya.

---

## 5. Yang perlu kamu tahu

**Analisa ini akan tampak kosong untuk sementara.** Datamu baru mulai 3 Oktober
2026. Jadi:

- Analisa pertama yang berguna = **1 November**, untuk bulan Oktober
- Perbandingan "naik/turun dari bulan lalu" baru ada mulai **Desember**
  (butuh Oktober sebagai pembanding)
- Sampai itu, semua saran berjenis `tanpa_pembanding` dengan `potensi_hemat: null`

Itu **bukan kerusakan**. Tolong tampilkan sebagai keadaan jujur — jangan
ditutupi dengan angka nol atau pesan samar.

---

## Pertanyaanku

1. Apakah bentuk di §2 sudah cukup untuk halaman yang kamu rancang, atau butuh
   field lain?
2. Untuk pemilih bulan: mau daftar bulan yang **ada analisanya** saja, atau
   **semua bulan** (dengan penanda belum dianalisa)? Aku bisa menyediakan
   daftarnya kalau perlu.
3. Tombol "Buat analisa" — taruh di halaman Analisa saja, atau juga bisa
   dipicu dari Beranda?

---

*Ditulis monica, 3 Okt 2026. Semua di §2 sudah diverifikasi terhadap endpoint
yang berjalan. Perubahan ada di `src/db.py`, `src/monthly_analysis.py`,
`src/server.py`, `src/schema.sql`, `src/migrations/006_analyses.sql`, dan
`tests/` (2 berkas uji baru).*
