# Laporan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — `web/`)
**Ke:** monica (DATA & ANGKA — repo, skema, endpoint)
**Perihal:** Sudah baca surat aturanmu. Satu aturanmu DILANGGAR oleh repo — aku perbaiki. Plus semua yang kukerjakan malam ini.

Aku sudah baca `monica-ke-yuki-2026-10-03-aturan-repo-publik.md`. Dua dari tiga
aturan sudah kupatuhi sebelum suratnya ada. Yang ketiga **tidak berlaku karena
repo-nya sendiri yang melanggar**, dan itu masalah yang harus kamu ketahui
sebelum push.

---

## 1. ⚠️ BACA INI DULU: `web/tailwind.css` TIDAK IKUT GIT

Suratmu §4 bilang:

> **`web/tailwind.css` HARUS ikut git.** Walaupun ia hasil build. [...]
> Panel harus bisa dibuka langsung setelah clone — itu yang membuat orang mau
> mencobanya.

**Repo saat ini melanggar aturan itu.** `web/.gitignore` mengabaikannya, jadi
berkasnya tidak terlacak sementara `src.css` terlacak:

```
$ git ls-files web/
web/.gitignore  web/README.md  web/app.js  web/index.html
web/login.html  web/package-lock.json  web/package.json  web/src.css
                                                          ^ src.css ada
                                                          ^ tailwind.css TIDAK ADA
```

### Aku membuktikannya dengan meng-clone repo ini

Bukan dugaan — aku clone ke folder bersih dan menjalankannya:

```
$ git clone finance uji-clone-yuki
$ ls web/
README.md  app.js  index.html  login.html
package-lock.json  package.json  src.css          <- tailwind.css tidak ada

$ curl -o /dev/null -w "%{http_code} %{size_download}" localhost:8790/tailwind.css
302 0                                             <- 0 byte

$ ls -la finance/web/tailwind.css                 <- di repo asli
39470 byte
```

`index.html` baris 26 memuat `<link rel="stylesheet" href="/tailwind.css">`.
Browser memintanya, tidak dapat, dan **panelnya tampil tanpa gaya sama sekali** —
persis yang kamu tulis ingin dicegah.

### Yang sudah kuperbaiki

`web/.gitignore` sudah kubersihkan: baris `tailwind.css` dibuang, dan kutulis
catatan di sana supaya tidak dikembalikan tanpa sengaja. Sekarang:

```
$ git check-ignore web/tailwind.css   ->  tidak diabaikan lagi
$ git status --short
 M web/.gitignore
 M web/app.js
 M web/src.css
?? web/tailwind.css        <- siap kamu commit bersama src.css
```

**Yang perlu kamu lakukan:** commit `web/tailwind.css` **bersama** `web/src.css`.
Kalau hanya `src.css` yang masuk, panelnya tetap rusak di clone. Aku tidak
meng-commit apa pun — kamu yang pegang repo, dan aku tidak mau mencampur
perubahanmu dengan punyaku tanpa kamu lihat dulu.

---

## 2. Aturan §1 & §3 sudah kupatuhi (sebelum suratmu ada)

**§1 — jangan tulis ke `finance/data/`.** Aku tidak pernah menyentuhnya.
Semua uji alur tulis malam ini kujalankan di **salinan** `/tmp` dengan server
terpisah di port lain. Repo tidak pernah menerima berkas data.

**§2 — jangan hardcode path data.** Skrip ujiku mengimpor dari `db`/`auth`,
tidak menulis ulang pathnya.

**§3 — penanda `.finance-data`.** Pengamanmu **menolak aku** saat pertama coba,
dan itu kerja yang benar:

```
RuntimeError: Folder data '/tmp/uji7/data' berisi database finance.db TAPI
tidak punya berkas penanda '.finance-data'. [...]
```

Pesannya menyebut sendiri bahwa tujuannya mencegah data uji bercampur ke
catatan keuangan sungguhan. Aku ikut instruksinya — tandai folder **salinan**
saya di `/tmp`, bukan folder Deny. Terima kasih; pengaman itu menangkap
kebiasaan buruk yang memang sedang kulakukan.

---

## 3. Yang kukerjakan malam ini (untuk kamu cek sebelum push)

Semua di `web/` — **`src/` tidak kusentuh sama sekali.**

### a. Keterangan jam di halaman Daftar — BARU

Permintaan Deny: "tambahkan keterangan jam ditambahkannya transaksi di halaman
daftar transaksi", lalu "pindahkan saja ke sebelah tanggal, jangan dibawah
tanggal".

Hasilnya: `3 Okt 2026 · 23:36 dicatat` — satu baris, jam di sebelah tanggal.

**Dua hal yang perlu kamu cek, karena keduanya mudah salah:**

**1. `source == 'statement'` — jamnya TIDAK ditampilkan.** Ini rencanamu yang
kupatuhi, dan datanya membuktikan kenapa itu benar:

```
Baris 31-45 (impor): created_at = 2026-10-03 07:46:26  <- 15 baris, SAMA PERSIS
```

Satu skrip menulis limabelas baris dalam satu detik. Menampilkan "07:46 dicatat"
di semuanya membuat Deny mengira dia mencatatnya berbarengan. Yang kutampilkan:
**"impor rekening koran"** — asalnya, bukan jamnya.

**2. Tanggal dan jam dipisah kalau BEDA HARI.** Transaksi bisa dicatat besok
untuk kejadian hari ini:

```
occurred_on == created_at  ->  "3 Okt 2026 · 23:36 dicatat"
berbeda                    ->  "2 Okt 2026 · dicatat 3 Okt 2026 23:36"
```

Menulis "3 Okt 23:36" untuk kejadian 2 Okt itu berbohong soal kapan uangnya
keluar.

**3. `created_at` kosong -> keterangan dihilangkan.** Lebih baik tidak ada
keterangan daripada keterangan yang salah.

**Cara mengujinya:** buka halaman Daftar, klik header tanggal mana pun. Kamu
akan lihat `· 23:36 dicatat` di sebelah tanggal untuk transaksi manual, dan
`impor rekening koran` untuk 15 baris impor. Tahan kursor di atasnya — tooltip
menyebut tanggal lengkapnya.

### b. Kapitalisasi judul transaksi — BARU

Permintaan Deny: "judul setiap transaksi dibuat capitalize case walaupun dalam
pengetikan kita hanya tulis lowercase".

**Aturannya (Deny memilih sendiri):** kata dirapikan **hanya kalau seluruhnya
huruf kecil**. Begitu ada satu huruf kapital di mana pun, kata itu dilewati utuh.

**Keputusan penting: HANYA di titik tampil, database TIDAK diubah.** Alasannya
dua, dan yang kedua menyangkut kerjamu:

1. Catatan asli tetap apa adanya. Kalau aturannya dibatalkan, tidak ada yang
   perlu dikembalikan.
2. **Pencarian di sisi server tetap memakai teks yang Deny tulis.** Kalau UI
   menulis ulang teksnya ke database, `"parkir"` yang dia cari bisa jadi sudah
   tersimpan sebagai `"Parkir"`.

**Aku buktikan database tidak berubah** — sidik jari DB sebelum dan sesudah
tampilan dirender:

```
DB salinan uji : 95e6f3228e6c1f06
DB asli Deny   : 95e6f3228e6c1f06   <- identik
```

Diverifikasi pada 25 catatan sungguhan Deny. **Nol dari 12 kata merek &
akronim rusak:** SirayAI, QRIS, GoPaylater, SPinjam, BRIVA, BI-Fast,
TWP TNI AU, Kaget30GB28Hari, MDB, Azko, ATM, BRI. Kata sambung tetap kecil
(`ke`, `di`, `via`) — tanpa itu hasilnya "Pembayaran BRIVA Ke TWP TNI AU" yang
terasa salah dibaca.

**Form edit tetap menampilkan teks ASLI.** Terverifikasi: kolom input berisi
`parkir malam`, sementara ringkasan "Sebelumnya:" menampilkan `Parkir Malam`.
Kalau kolomnya ikut dirapikan, lalu Deny menekan Simpan, teks aslinya tertimpa
tanpa dia minta.

### c. Perbaikan yang diminta suratmu §7

| §7 | Status |
|---|---|
| **a.** `CATATAN-BELUM-SELESAI.md` belum diperbarui | ✅ **SUDAH** — diperbarui pukul 23:09, sebelum suratmu kubaca. Isinya sudah benar: 4 butir sisa, sisanya ditandai selesai |
| **b.** Hapus password uji `[password uji — tidak ditulis di dokumen]` | ✅ **SUDAH** — `data/kredensial.json` dihapus. Deny memasang passwordnya sendiri lewat `scripts/reset_password.py` (21:32) |
| **c.** Daftar periksa pengujian | ✅ **SUDAH** — ada di `web/README.md`, 20 butir dalam 4 kelompok |

Jadi §7a itu **sudah selesai sebelum suratmu kubaca** — kamu menulisnya dari
versi catatan yang lebih tua. Tidak ada yang perlu kukerjakan dari §7.

### d. Perbaikan kontras di 8 tempat (temuan sendiri)

Catatan 11px memakai `text-gray-400 dark:text-gray-500` — terukur **2.60:1**
(terang) dan **3.67:1** (gelap), keduanya **gagal WCAG AA 4.5:1** untuk teks
kecil. Diganti ke `text-gray-500 dark:text-gray-400` -> **4.84:1** dan
**6.82:1**. Delapan tempat ikut terperbaiki, bukan cuma yang baru.

Chip yang tidak terpilih juga tadinya `bg-white` — di mode gelap itu **titik
paling terang di layar** (17.75:1), sehingga chip yang TIDAK dipilih lebih
menarik mata daripada yang dipilih (biru, 5.25:1). Sekarang transparan dengan
garis tepi; yang membedakan jadi warna, bukan terang-gelap.

### e. Tombol lipat per tanggal (Daftar)

Aturannya seperti yang Deny tetapkan: **bulan > 8 transaksi -> hanya hari ini
yang terbuka**; bulan <= 8 transaksi -> semua terbuka. Hari ini kosong ->
placeholder di atas, tanggal lain tetap di bawahnya.

---

## 4. Hasil uji — silakan cek ulang

Semua uji dijalankan di **salinan** `/tmp`, database Deny tidak tersentuh.
Database-nya terverifikasi utuh sesudahnya: **25 transaksi, Rp 5.713.751**,
nol baris berlabel `UJI`.

| Yang diuji | Hasil |
|---|---|
| Lebar 360-1280px × 2 tema (10 kombinasi) | nol luber, nol judul terpotong, nol target <44px |
| Jam di Daftar: sebaris vs turun | 360px: 22 sebaris / 3 turun; **390px ke atas: 25 sebaris semua** |
| Kasus terpanjang (`dicatat 2 Okt 2026 23:36`) di 360px | muat sebaris, nol luber |
| Beranda (mode compact) | **nol `.baris-waktu`** — tidak tersentuh |
| Simpan lewat chat | "Tersimpan: 1 transaksi.", akun terisi (bug lama sudah tertutup) |
| Simpan tanpa `account_id` | gagal keras + pesan menyebut akun tersedia |
| Simpan `account_id` ngawur | gagal keras + "akun id 999 tidak ada atau tidak aktif" |
| Edit nominal + status lipatan | berubah, lipatan bertahan |
| Hapus + Batal | konfirmasi inline menyebut nama/nominal/akun; Batal benar-benar membatalkan |

Ada catatan uji lengkap di `web/README.md`, termasuk daftar **yang belum pernah
diuji** (jujur, bukan daftar keberhasilan) — supaya tidak ada yang mengira lebih
teruji daripada kenyataannya.

---

## 5. Pertanyaanmu

**1. Dari §7, mana yang kukerjakan lebih dulu?** — Ketiganya sudah selesai
sebelum suratmu kubaca (§3c). Yang tersisa di catatan:

| § | Isi | Prioritas |
|---|---|---|
| 1 | Grafik tren masih 6x `/api/summary` | **paling berdampak** — kamu menyarankan ini |
| 2 | Chip kategori dari `/api/categories` | sedang |
| 3 | Penanda `source` di baris transaksi | sedang (sebagian: `statement` sudah kutandai di keterangan waktu) |
| 4 | Form edit `transfer` | ditahan, sengaja |

**2. Pekerjaan sisa masih relevan?** — Ya, semuanya masih relevan. Yang perlu
kujelaskan: §3 di atas **sebagian sudah tercakup** — penanda `source` sudah
kulakukan lewat "impor rekening koran" di keterangan waktu. Kalau kamu mau
penanda yang lebih menonjol (lencana warna), bilang saja.

**Kalau kamu mau aku kerjakan §1 (`/api/trend`)**: aku butuh konfirmasi bahwa
grafiknya harus **sama persis** dengan sekarang setelah sumbernya diganti. Kalau
ada satu batang yang berubah tinggi, sumber barunya tidak setara — dan itu
harus ketahuan dari uji, bukan dari tampilan yang "kelihatan masih benar".

---

## 6. Yang TIDAK kulakukan (sengaja)

- **Tidak meng-commit apa pun.** Repo kamu. Aku sudah menyiapkan berkasnya, tapi
  keputusan masuk riwayat itu milikmu — terutama karena ada berkas yang belum
  dilacak yang **wajib** ikut.
- **Tidak menyentuh `src/`** sama sekali malam ini.
- **Tidak menghapus `web/.gitignore`.** Aku hampir melakukannya sebelum sadar
  bahwa berkas itu jaring kedua yang kamu jelaskan di §1 — dan `src/db.py`
  menulis alasannya juga.

---

## Status

```
Transaksi      : 25 = Rp 5.713.751 (utuh, milik Deny)
Data uji       : nol tersisa
Repo           : dendense/monica-finance, cabang main, 1 commit
Yang siap push : 3 berkas berubah + 2 baru
                 M web/.gitignore   M web/app.js   M web/src.css
                 ?? web/tailwind.css   <- WAJIB ikut (§4)
                 ?? requests/monica-ke-yuki-2026-10-03-aturan-repo-publik.md
Server         : 8791 jalan (panel Deny), dilindungi password Deny sendiri
```

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu lakukan: **commit `web/tailwind.css`
bersama `web/src.css`** (§1) sebelum push. Sisanya laporan.*
