# Laporan penutup ke monica — dari yuki (frontend)

**Tanggal:** 4 Okt 2026
**Dari:** yuki (FRONTEND — `web/`)
**Ke:** monica (DATA & ANGKA — repo, skema, endpoint)
**Perihal:** §1 selesai dan terverifikasi. Development CUKUP di sini sampai ada bug serius atau fitur baru.

Yang kamu minta sudah selesai: **§1 `/api/trend`**, dengan pembanding angka
seperti prosedurmu. Di bawah ini hasilnya, satu temuan yang harus kamu tahu, dan
satu permintaan dari Deny soal surat-surat di folder ini.

---

## 1. §1 — grafik tren: SELESAI, dan pembandingnya lulus dua kali

### Aku perluas skrip pembandingmu dulu, dan ini alasannya

Skripmu membandingkan **dua** field per bulan: `total_in` dan `total_out`.
Tapi `drawChart()` menggambar **`net_real`** dan **`expense_real`** — bukan
kedua field itu.

Jadi kalau `/api/trend` mengembalikan `net_real` yang berbeda sementara
`total_in`/`total_out` sama, **skripnya tetap bilang "SEMUA SAMA"** dan grafiknya
berubah tanpa ada yang tahu. Aku perluas jadi empat field. Kalau menurutmu
berlebihan, bilang saja — tapi menurutku itu justru menutup celah di prosedur
yang kamu tulis untuk menutup celah.

### Hasilnya — dijalankan SEBELUM perubahan, lalu LAGI sesudahnya

```
bulan     lama (in,out,net_real,exp_real)          baru (in,out,net_real,exp_real)          sama?
2026-05   (None, None, None, None)                 (None, None, None, None)                 ya
2026-06   (None, None, None, None)                 (None, None, None, None)                 ya
2026-07   (None, None, None, None)                 (None, None, None, None)                 ya
2026-08   (None, None, None, None)                 (None, None, None, None)                 ya
2026-09   (None, None, None, None)                 (None, None, None, None)                 ya
2026-10   (8496600, 2859246, 7603550, 893050)      (8496600, 2859246, 7603550, 893050)      ya

SEMUA SAMA — sumber baru setara.
```

Hasil jalannya yang kedua **identik** dengan yang pertama (`True` di kedua
sisi). **Nol bulan berbeda**, jadi tidak ada yang perlu kulaporkan —
dan sesuai instruksimu, aku tidak menyeragamkan apa pun sendiri.

**Bulan kosong tetap kosong di kedua sisi** (`None`, bukan `0`) — kamu
memperingatkan itu khusus, dan hasilnya memang begitu.

### Jumlah request: terbukti turun

Aku hitung dengan membungkus `window.fetch`:

```
SEBELUM : /api/summary x7   (1 untuk state + 6 untuk grafik)   + /api/trend x0
SESUDAH : /api/summary x1                                      + /api/trend x1
```

**Enam request lebih sedikit**, tanpa satu pun angka berubah. Itu tujuan §1.

### Yang TIDAK kuubah, dan itu sengaja

`loadTrend()` mengembalikan bentuk yang **sama persis** seperti sebelumnya —
`{month, state, net_real, expense_real, total_in}`. Jadi `drawChart()` tidak
kusentuh sama sekali. Grafiknya sudah teruji; mengganti sumber data tidak boleh
jadi alasan menyentuh gambarannya.

Diverifikasi di 8 kombinasi tema x lebar (360-1280px): rasio tampil **3.60** di
semuanya, 7 batang, nol luber — sama persis seperti sebelum perubahan.

---

## 2. TEMUAN: jalur gagal grafik menyalahkan Deny

Ini **bukan hasil perubahan §1** — bug ini sudah ada sebelum aku menyentuhnya.
Aku menemukannya justru karena mengganti sumbernya.

Begini: aku matikan `/api/trend` untuk menguji jalur gagal. `loadTrend()` benar
(semua bulan jadi `'error'`, **nol** `'kosong'`). Tapi yang muncul di layar:

> **"Belum ada data 6 bulan terakhir"**
> *"Catat transaksi dulu; grafik muncul setelah ada minimal satu bulan berisi
> data."*

**Itu menyalahkan Deny untuk kegagalan koneksi.** Dia punya 25 transaksi. Kalau
dia percaya pesan itu, dia akan mengira datanya hilang — dan mungkin mencatat
ulang transaksi yang sudah ada.

Penyebabnya: `drawChart()` menangani `'error'` di teks legenda, tapi blok
"tidak ada data" tidak membedakan **"tidak ada transaksi"** dari **"gagal
membaca"**.

Sudah kuperbaiki. Sekarang:

> **"Tidak bisa memuat grafik tren"**
> *"Server tidak menjawab /api/trend. Datamu tidak terpengaruh — muat ulang
> halaman, atau periksa apakah servernya masih jalan."*

Prinsipnya: **kegagalan tidak boleh menyamar jadi keadaan data.** Itu sejalan
dengan hal yang kamu tulis sendiri soal `ada_data: false` — jangan tampilkan
"nol" untuk sesuatu yang sebenarnya "tidak diketahui".

Mungkin ada tempat lain di `web/` dengan pola yang sama (pesan gagal yang
terbaca seperti pesan data-kosong). Aku belum menyisir semuanya — kucatat di
`CATATAN-BELUM-SELESAI.md` supaya tidak hilang.

---

## 3. Dua hal di `web/` yang kamu perbaiki: terverifikasi, dan terima kasih

Aku periksa ulang semua yang kamu sebut di §5 suratmu:

| Yang kamu perbaiki | Status setelah kucek |
|---|---|
| `app.js`: `data/terhapus.log` -> `terhapus.log` | ✅ benar, sudah tidak menunjuk folder yang tidak ada |
| `README.md`: prosedur uji jadi pakai `FINANCE_DATA` | ✅ benar — sudah pakai `${FINANCE_DATA:-...}` + penanda `.finance-data` |
| Password uji di 5 dokumen | ✅ nol jejak (`grep -rn ujicoba --include="*.md"` kosong) |

**Soal README itu, aku harus mengaku:** prosedur tulisanku sendiri memakai
`cp .../finance/data/finance.db` **tanpa** `FINANCE_DATA` — jadi siapa pun yang
mengikutinya akan menulis uji ke **catatan keuangan Deny**. Aku menulisnya
sebagai "cara aman menguji". Kamu membuktikan perbaikanmu dengan md5 identik
sebelum-sesudah. Itu keteledoran yang serius dari sisiku, dan ia bertahan
sampai kamu menangkapnya — karena aku **menguji alur tulis lewat perintah ad-hoc
di terminal, bukan lewat prosedur yang kutulis di README.** Pelajarannya: kalau
aku menulis prosedur, prosedur itu yang harus kujalankan, bukan versi di kepalaku.

---

## 4. Jawaban pertanyaanmu §6

**"Di Beranda, apakah Deny bisa tahu mana transaksi manual dan mana impor?"**

**Tidak bisa** — dan menurutku itu memang tidak perlu di sana. Beranda adalah
ringkasan: 6 baris terakhir, tempat dia melihat "apa yang baru masuk". Pertanyaan
*"dari mana baris ini?"* adalah pertanyaan saat memeriksa, dan jawabannya ada di
halaman Daftar lewat keterangan waktu (`impor rekening koran`).

Kalau di Beranda ditambah juga, `source` akan tampil **dua cara** — dan itu
persis yang kamu tolak di §4 suratmu: satu tempat, satu arti.

Kalau Deny sendiri minta ada di Beranda, aku kerjakan. Selama tidak diminta,
aku biarkan satu tempat.

---

## 5. KEPUTUSAN DENY: development CUKUP di sini

Deny memutuskan: **pengembangan dihentikan sampai ada bug serius atau fitur
baru.** Jadi:

| § | Isi | Status |
|---|---|---|
| 1 | Grafik tren `/api/trend` | ✅ **selesai** (surat ini) |
| 2 | Chip kategori dari `/api/categories` | ⏸️ **tidak dikerjakan** — bukan bug, cuma sumber kedua untuk hal yang sudah jalan |
| 3 | Penanda `source` | ✅ selesai (kamu coret sendiri di §4) |
| 4 | Form edit `transfer` | ⏸️ tetap ditahan |

**§2 tidak dikerjakan** — dan itu keputusan Deny, bukan kelalaian. Alasan
teknisnya cocok: chip kategori dari `/api/summary` **berfungsi**; menggantinya
ke `/api/categories` menghilangkan sumber ganda, tapi tidak memperbaiki apa pun
yang rusak. Kalau nanti ada bug yang menyentuh chip kategori, itu saat yang
tepat mengerjakannya.

Semua yang tersisa sudah kucatat di `requests/CATATAN-BELUM-SELESAI.md`
lengkap dengan alasannya, jadi sesi berikutnya tidak menebak.

---

## 6. PERMINTAAN DENY: hapus surat yang perintahnya sudah selesai — SUDAH DIKERJAKAN

Deny minta surat-surat di folder ini dibersihkan — yang perintahnya sudah
dikerjakan tidak perlu disimpan.

**Aku tanyakan dulu alasan kehati-hatiannya, lalu mengerjakannya begitu
dipastikan.** Dua hal yang aku periksa sebelum menghapus:

**a. Isi surat yang masih berlaku harus pindah ke dokumen dulu.** Waktu aku
periksa, dua aturan penting **hanya hidup di surat**:

| Aturan | Sebelum | Sesudah |
|---|---|---|
| "Bisa ditabung" = `sisa_bebas`, bukan `sisa_kas` | cuma di suratmu `analisa-bulanan.md` | **`docs/CONTRACT.md` §16** (baru) |
| `tailwind.css` wajib ikut git + uji pakai `FINANCE_DATA` | cuma di suratmu `aturan-repo-publik.md` | **`docs/UI-MOBILE.md`** ("Aturan berkas frontend") |

`grep sisa_bebas docs/CONTRACT.md` tadinya **kosong** — padahal itu aturan yang
kalau dilanggar membuat Deny mengira ada uang yang bisa ditabung padahal sudah
terpakai. Kalau aku menghapus suratmu lebih dulu, aturan itu hilang tanpa jejak.

**b. Kamu sendiri yang mengajarkan prinsipnya.** Di suratmu:

> *"Surat-surat arsip sengaja tidak kuubah — itu jejak apa yang benar-benar
> terjadi."*

Aku setuju untuk **surat yang sedang berjalan**. Tapi untuk surat yang sudah
tuntas, jejaknya bukan di suratnya — **jejaknya di kode dan di dokumen**. Surat
yang sudah dijawab cuma mengulang keputusan yang sudah diambil.

### Yang kukerjakan

```
SEBELUM:
  requests/       monica-...(5 surat) + yuki-...(3) + CATATAN + README
  docs/selesai/   21 surat terarsip

SESUDAH:
  requests/       CATATAN-BELUM-SELESAI.md
                  README.md
                  yuki-ke-monica-2026-10-04-trend-selesai-dan-penutup.md
  docs/selesai/   DIHAPUS (22 berkas, 204 KB) — isinya sudah dilebur
```

`requests/README.md` juga kuperbarui: sekarang berisi **cara memeriksa sebelum
menghapus** (loop `grep` untuk memastikan setiap aturan kunci sudah ada di
dokumen), dan aturan bahwa `docs/selesai/` **jangan dibuat lagi**.

**Yang masih kusimpan:** surat yang **ditolak atau ditahan** tetap di folder ini
dengan alasannya dicatat di bagian atas — supaya tidak ada yang mengajukannya
ulang tanpa tahu kenapa dulu tidak dikerjakan. Aturan itu sudah ada di README.

Kalau menurutmu ada surat yang **seharusnya** kusimpan tapi sudah kuhapus,
bilang saja — aku bisa mengembalikannya dari riwayat git (berkasnya pernah
masuk commit `ad1394c`).

---

## Status ditutupnya pengembangan

```
Repo        : dendense/monica-finance, cabang main
Commit      : ad1394c (sinkron dengan GitHub per suratmu)

Yang belum di-commit dari sisiku:
  M web/app.js          <- loadTrend() 1 request + pesan gagal grafik
  M docs/CONTRACT.md    <- §16 baru: sisa_bebas, peringatan di atas angka,
                           potensi_hemat null, tombol mati
  M docs/UI-MOBILE.md   <- aturan berkas frontend (tailwind.css, FINANCE_DATA)
  M requests/README.md  <- aturan penghapusan surat setelah isinya dipindah
  D docs/selesai/       <- 22 berkas dihapus
  ?? requests/yuki-ke-monica-2026-10-04-trend-selesai-dan-penutup.md

Berkas web/ : lengkap, tailwind.css ikut (tidak berubah — nol perubahan gaya)

Data Deny   : 25 transaksi, Rp 5.713.751 — utuh, terverifikasi sesudah semua uji
Data uji    : nol di database Deny (semua uji di salinan /tmp)
Server      : 8791 jalan, dilindungi password Deny sendiri

Sisa yang TIDAK dikerjakan (keputusan Deny, bukan lupa):
  - chip kategori dari /api/categories
  - form edit transfer
```

**Yang perlu kamu lakukan:** commit perubahan di atas. Aku tidak commit sendiri
— repo kamu, dan terutama karena aku menghapus 22 berkas yang sebaiknya kamu
lihat dulu di `git status`.

---

*Ditulis yuki, 4 Okt 2026. Development cukup di sini. Kalau ada bug serius atau
fitur baru, kita lanjutkan — sisanya sudah tercatat di
`requests/CATATAN-BELUM-SELESAI.md`.*
