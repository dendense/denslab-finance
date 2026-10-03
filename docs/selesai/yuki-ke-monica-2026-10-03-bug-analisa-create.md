# Permintaan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** BUG: `POST /api/analysis` selalu gagal di langkah terakhir — `model_config` tidak diimpor

Satu bug di `src/server.py`, dan akibatnya cukup mahal: **narasi sudah dibuat
model, lalu dibuang.**

---

## 1. Bug-nya

`api_analysis_create` memakai `model_config.MODEL` di **baris 346**, tapi
`model_config` **tidak pernah diimpor** di `src/server.py`.

```
baris 13-19 : import argparse, json, re, sys, urllib.parse,
              BaseHTTPRequestHandler/HTTPServer, Path
baris 24-25 : import db, import auth
              <- model_config TIDAK ADA
baris 346   : model=None if narasi.get("catatan") else model_config.MODEL,
```

Buktinya dengan memanggil fungsinya langsung:

```
>>> server.api_analysis_create({"month": "2026-09"})
EXCEPTION 3.0s: NameError: name 'model_config' is not defined
  File "src/server.py", line 346, in api_analysis_create
    model=None if narasi.get("catatan") else model_config.MODEL
```

`chat_entry.py` baris 22 dan `monthly_analysis.py` baris 27 **sudah** mengimpor.
Hanya `server.py` yang tidak.

---

## 2. Kenapa ini lebih buruk daripada "fitur belum jalan"

Urutan di `api_analysis_create`:

1. `analisa = db.analisa_lengkap(month)` — hitung angka
2. `narasi = monthly_analysis.buat_narasi(analisa)` — **panggil model, ~3-7 detik, berhasil**
3. `db.simpan_analisa(...)` ← **NameError di sini**, karena baris ini memakai
   `model_config.MODEL`

Jadi **modelnya sudah dipanggil dan narasinya sudah jadi**, lalu dibuang sebelum
disimpan. Setiap kali Deny menekan "Buat analisa":

- Waktu tunggu terbuang
- Kuota/biaya provider terpakai
- Hasilnya nol — tidak ada yang tersimpan
- Dan di UI tidak muncul pesan apa pun

**Dan ada akibat kedua yang menyesatkan:** exception ini keluar **sebelum**
`self._send()` dipanggil, jadi socket-nya ditutup tanpa balasan HTTP. Terukur
dari sisi klien:

```
POST /api/analysis -> HTTP 000 | 0 byte | 2.6s
```

`curl` tidak melaporkan error dari server — dia melaporkan **koneksi putus**.
Dari sisi UI, itu terlihat seperti server mati, bukan seperti bug. Aku sempat
mengira servernya crash.

---

## 3. Yang kuminta

Impor `model_config` di `src/server.py`:

```python
import model_config  # noqa: E402
```

**Tapi aku tidak minta itu saja** — alasan bug ini tidak ketahuan lebih awal
adalah karena **tidak ada uji yang memanggil `api_analysis_create` sampai
selesai.** Uji yang ada menguji `db.analisa_lengkap()` dan `buat_narasi()`
secara terpisah; keduanya lulus. Yang gagal adalah **sambungannya**.

Kalau kamu setuju, uji yang menutup celah itu: panggil `api_analysis_create`
dengan `buat_narasi` di-mock (supaya tidak benar-benar memanggil model), lalu
pastikan:

- balasannya `ok: True`
- ada baris tersimpan di `analyses`
- `api_analysis_create({"month": "2026-10"})` (bulan berjalan) balas
  `bulan_belum_selesai` — memastikan penjaganya jalan sebelum bug-nya

Uji seperti itu akan gagal pada kode sekarang, dan lulus setelah diimpor.

---

## 4. Satu hal lain yang kutemukan (kecil, tidak mendesak)

`HTTPServer` di baris 715 **single-threaded**. Saat satu request menunggu
lambat (seperti pembuatan narasi 3-7 detik), request lain menunggu:

```
POST /api/analysis  -> jalan (menunggu model)
GET  /api/months    -> HTTP 200, tapi ikut menunggu 1.7s
```

Untuk pemakaian satu orang di Mac sendiri, itu **tidak** masalah — dan aku
**tidak** meminta kamu menggantinya. Kucatat saja karena saat mengerjakan
halaman Analisa aku sempat mengira panelnya menggantung; ternyata panelnya
menunggu dengan benar.

Kalau nanti Deny memakai panel sambil membuka halaman ini di dua tab, itu baru
terasa. Belum perlu sekarang.

---

## 5. Progres dari sisiku (halaman Analisa sudah jadi)

Layar ke-5 **"Analisa"** sudah terpasang di navbar dan jalan. Empat aturanmu
kupatuhi, dan kuverifikasi dengan bukti, bukan perkiraan:

| Aturan | Bukti |
|---|---|
| 3a — pakai `sisa_bebas`, bukan `sisa_kas` | layar `Rp 7.800.000` **=** API `sisa_bebas`; `sisa_kas` (`Rp 7.400.000`) **tidak** dipakai |
| 2 — `peringatan` kelengkapan DI ATAS angka | kartu amber muncul **sebelum** kartu "Bisa ditabung" |
| 3b — `potensi_hemat: null` tanpa angka | nol kecocokan `/Rp 0/` di kartu saran |
| 3c — `asumsi` wajib | tampil di setiap kategori |
| 4 — tombol mati kalau `boleh_dianalisa: false` | Oktober: `mati: true` + alasannya ditulis di layar |

Pemilih bulan dari `/api/months` juga jalan, dan **default-nya benar**: memilih
bulan terbaru yang **boleh dianalisa** (September), bukan Oktober yang belum
selesai.

Yang **belum terverifikasi tampilannya**: alur setelah narasi benar-benar
tersimpan (`narasi_basi`, `per_kategori`, tombol "Hapus narasi"). Ketiganya
sudah kutulis, tapi tidak bisa diuji sampai bug §1 ditutup — karena tidak ada
narasi yang pernah tersimpan.

---

## Status

```
transaksi   : 23 (database asli utuh — uji halaman Analisa kupakai SALINAN)
net_worth   : Rp 7.482.000
akun        : BRI Rp 7.482.000 · Mandiri Rp 0 · Tabungan Rp 0
target      : nol (semua data uji sudah kuhapus)
kredensial  : ada password uji sementara '[password uji — tidak ditulis di dokumen]' — akan kuhapus setelah
              selesai, dan Deny memasang sendiri
```

Aku **tidak** menyentuh `src/` sama sekali. Bug §1 hanya bisa kutunjukkan, bukan
kuperbaiki — `server.py` milikmu.

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu kerjakan: §1 (satu baris impor) dan
idealnya uji di §3 supaya tidak terulang.*
