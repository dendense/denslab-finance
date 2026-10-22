# web/ — panel finance (yuki)

> ## ⚠️ Aturan wajib saat menguji panel ini
>
> database keuangan berisi **data sungguhan**. Data uji yang ditulis untuk
> verifikasi **wajib dihapus kembali** — jangan ditinggalkan.
>
> Sebelum menghapus: cetak baris yang akan dihapus beserta jumlahnya, pastikan
> jumlahnya cocok, dan **jangan sentuh baris yang bukan kamu buat** (Deny juga
> mencatat transaksi dari panel). Cara lengkapnya ada di skill
> `finance-app-testing`.
>
> Baris uji sebaiknya diberi penanda di catatan, mis. `UJI-yuki: kopi`, supaya
> bisa dibedakan dari catatan sungguhan.
>
> **Cara paling aman menguji alur tulis:** salin database keuangan ke `/tmp`,
> jalankan server kedua di port lain, dan uji di sana. Database Deny tidak
> tersentuh sama sekali, jadi tidak ada yang perlu dihapus. Dipakai untuk seluruh
> uji Simpan/Edit/Hapus — lihat "Cara menguji alur tulis" di bawah.

Dibangun mengikuti `docs/UI-MOBILE.md`, `docs/CONTRACT.md`, dan `docs/arsip/HANDOFF-YUKI.md`.

| Berkas | Isi |
|---|---|
| `index.html` | kerangka: navbar atas, **5 layar** (beranda, catat, daftar, akun, analisa) |
| `src.css` | **sumber gaya** — token, komponen, tema gelap |
| `tailwind.css` | **hasil build** dari `src.css`. Jangan diubah langsung |
| `app.js` | logika: ambil API, grafik, chat dua langkah, chip koreksi, lipat daftar |
| `login.html` | halaman masuk/pasang password (mandiri, tanpa app.js) |
| `package.json` | skrip build Tailwind |

## Menjalankan

```bash
cd ~/Documents/AI/finance && python3 src/server.py --port 8791   # server
cd web && npm run css                                       # bangun CSS (sekali)
cd web && npm run css:watch                                 # sambil mengerjakan
```

**Wajib:** `tailwind.css` harus ada. Kalau belum dibangun, panel tampil tanpa
gaya sama sekali. `npm run css` dijalankan setiap kali ada class baru di
`index.html` atau `app.js`.

**Reset password** (dijalankan di Terminal.app, bukan lewat agen — `getpass`
butuh TTY):

```bash
python3 scripts/reset_password.py
```

### Catatan pemasangan npm di mesin ini

`npm install` gagal dengan `EACCES` pada `~/.npm/_cacache`, dan `~/.npm` ada di
luar area kerja yang diizinkan. Jalan keluarnya: cache lokal di folder proyek.

```bash
npm install --cache "$PWD/.npm-cache"
```

## Tailwind — bagaimana berkas ini disusun

Tailwind memindai `index.html` **dan** `app.js` (keduanya terdaftar lewat
`@source` di `src.css`), karena sebagian besar elemen dibuat oleh JavaScript.
Tanpa `@source "./app.js"`, class yang hanya muncul di string JS akan dipangkas
dan panel kehilangan gaya.

**Target sentuh** dijaga lewat token `--spacing-tap: 44px` → class `min-h-tap`.
Dipasang di setiap tombol, chip, input, dan textarea.

**Warna hanya lewat CSS variable / token.** Jangan menulis hex di `app.js` atau
`index.html`.

### Dua jebakan Tailwind v4 yang sudah pernah menggigit

Ditulis di sini karena keduanya **tidak memunculkan error apa pun** — yang
terlihat hanya tampilan yang salah, dan hanya ketahuan dengan memeriksa
`tailwind.css` hasil build, bukan dengan melihat layar.

1. **`@apply` bertumpuk pada kelas yang sama menjatuhkan properti diam-diam.**
   Menulis `@apply border bg-white ...` di satu `@apply` lalu `@apply
   bg-transparent` di `@apply` kedua di kelas yang sama membuat `border` dan
   `background-color` **hilang total dari build**. Gejalanya: chip jadi teks
   mengambang di kedua tema.

2. **`.gelap .kelas` di dalam `@layer components` TIDAK menghasilkan scope.**
   Ia keluar di build sebagai `.kelas` biasa, jadi warna gelapnya bocor ke mode
   terang. Yang benar: pakai varian `dark:` lewat `@apply`, karena
   `@custom-variant dark (&:where(.gelap, .gelap *))` di `src.css` yang
   menambahkan scope-nya.

**Selalu periksa hasil build** setelah menambah/mengubah gaya:

```bash
grep -o '\.chip[^}]*}' tailwind.css
```

## Cara menguji alur tulis tanpa menyentuh database Deny

Dipakai untuk seluruh uji Simpan/Edit/Hapus. Database asli tidak tersentuh,
jadi tidak ada yang perlu dihapus sesudahnya.

```bash
# 1. Salin kode + data ke folder sementara
rm -rf /tmp/uji && mkdir -p /tmp/uji/src /tmp/uji/web /tmp/uji/data-tes
cd /tmp/uji
cp -R ~/Documents/AI/finance/src/. src/
cp -R ~/Documents/AI/finance/web/. web/
cp "${FINANCE_DATA:-$HOME/Documents/AI/Data/finance}/finance.db" data-tes/finance.db

# 2. Tandai folder data SEMENTARA (wajib — pengaman lokasi data akan menolak
#    folder berisi database tanpa penanda; lihat "Pengaman lokasi data" di bawah)
touch data-tes/.finance-data

# 3. Jalankan dengan FINANCE_DATA menunjuk ke SALINAN, bukan data Deny
FINANCE_DATA=/tmp/uji/data-tes python3 src/server.py --port 8795
```

Tanpa `FINANCE_DATA`, server akan menunjuk ke **data Deny** — dan tulisan uji
masuk ke catatan keuangan sungguhan. Kredensial sengaja tidak disalin, jadi
server uji mulai dalam mode "pasang password" dan kamu bisa memasang password
uji sendiri lewat panel.

Bersihkan setelah selesai: `kill <pid>` lalu `rm -rf /tmp/uji`.

**Jangan pernah menulis password di surat atau catatan.** Kesepakatan dengan
monica: surat-surat di folder ini dokumen yang berlaku, dan password lebih baik
tidak punya jejak tertulis.

## Daftar periksa pengujian

Dipakai ulang setiap kali ada perubahan yang menyentuh UI. **Semua angka di
bawah pernah diukur**, bukan perkiraan.

### Yang harus diulang setiap kali `src.css` / `index.html` / `app.js` berubah

| # | Yang diperiksa | Cara | Pernah lolos dengan |
|---|---|---|---|
| 1 | **Nol luber horizontal** di 6 lebar × 2 tema | `document.documentElement.scrollWidth - window.innerWidth` = 0 pada 360, 390, 640, 768, 1024, 1280 | 12/12 kombinasi bersih |
| 2 | **Nol target sentuh < 44 px** | saring semua `button, a, select, input` yang `height < 44` | nol di semua layar |
| 3 | **Nol chip/teks terpotong** | `el.scrollWidth > el.clientWidth + 1` | nol |
| 4 | **Build Tailwind memuat gaya baru** | `grep` kelasnya di `tailwind.css` | lihat §jebakan di atas |
| 5 | **Kontras teks ≥ 4.5:1**, garis/batas ≥ 3:1 | hitung dari `getComputedStyle`, konversi OKLCH→sRGB | lihat tabel di bawah |
| 6 | **Angka panel = API persis** | bandingkan teks di layar dengan respons `/api/summary`, `/api/analysis` | nol selisih |

### Alur tulis (uji di salinan `/tmp`, lihat caranya di atas)

| # | Alur | Yang harus terjadi |
|---|---|---|
| 7 | Chat → `/api/parse` → draft | draft muncul, **chip akun terisi** (bukan kosong) |
| 8 | Draft → Simpan | "Tersimpan: N transaksi.", draft hilang, nominal di daftar sesuai |
| 9 | Simpan **tanpa** `account_id` | **Gagal keras** + pesan menyebutkan akun mana yang tersedia |
| 10 | Simpan dengan `account_id` ngawur | **Gagal keras** + "akun id X tidak ada atau tidak aktif" |
| 11 | Edit nominal → Simpan perubahan | nominal berubah di daftar, form tertutup |
| 12 | Hapus → konfirmasi inline | baris jadi "Hapus transaksi ini?" + nama/nominal/akun disebut |
| 13 | Hapus → "Batal" | baris kembali utuh, nol perubahan |
| 14 | `net_worth` setelah tulis | berubah **tepat** sebesar nominal yang disimpan/dihapus |

### Yang khusus halaman Daftar (lipat per tanggal)

Aturan: **bulan > 8 transaksi → hanya hari ini yang terbuka**; bulan ≤ 8
transaksi → semua terbuka. Hari ini kosong → placeholder di atas, tanggal lain
tetap ada di bawahnya.

| # | Yang diperiksa |
|---|---|
| 15 | Bulan ramai (>8): hanya kelompok "Hari ini" `aria-expanded="true"` |
| 16 | Bulan sepi (≤8): semua kelompok terbuka |
| 17 | Hari ini kosong: placeholder muncul **di atas**, daftar tanggal lain tetap tampil |
| 18 | Klik header: `aria-expanded` **dan** jumlah transaksi (`· 4`) berganti bareng |
| 19 | Status lipatan **bertahan** setelah edit/hapus (renderDaftar ulang) |
| 20 | Ganti bulan (‹ ›): status lipatan **direset** |

### Yang belum pernah diuji — jujur, bukan daftar keberhasilan

Semuanya **bukan bug**, tapi keadaan data. Terbuka sendiri begitu Deny punya
lebih dari satu bulan transaksi:

- Jalur **sukses** pembuatan narasi analisa (`narasi_basi`, `per_kategori`,
  tombol "Hapus narasi") — tidak ada bulan selesai yang punya data.
- Panel "sisa bulan lalu" dengan bulan **berisi** angka — September kosong.
- Pemilih bulan halaman Analisa dengan > 2 bulan.
- Perbandingan naik/turun saran hemat antar bulan (butuh ≥ 2 bulan).
- Form edit `transfer` — sengaja ditahan, butuh kolom akun tujuan.

## Kontras terukur (bukan kesan)

| Tema | Elemen | Rasio | Ambang |
|---|---|---|---|
| terang | teks chip | 10.30:1 | Lulus AA 4.5:1 |
| terang | teks catatan kecil (11 px) | 4.84:1 | Lulus AA |
| gelap | teks chip | 14.33:1 | Lulus AA |
| gelap | garis tepi chip | 3.67:1 | Lulus 3:1 (WCAG 1.4.11) |
| gelap | teks catatan kecil (11 px) | 6.82:1 | Lulus AA |

Catatan 11 px pernah **gagal** karena memakai `text-gray-400 dark:text-gray-500`:
**2.60:1** (terang) dan **3.67:1** (gelap) — keduanya di bawah ambang AA 4.5:1
untuk teks kecil. Diganti ke `text-gray-500 dark:text-gray-400` → 4.84:1 dan
6.82:1. Delapan tempat ikut terperbaiki.

> **Hati-hati: 3.67:1 muncul dua kali dengan makna berbeda.** Untuk **teks**
> (ambang 4.5:1) angka itu **gagal**; untuk **garis tepi chip** (ambang 3:1)
> angka itu **lulus**. Jangan simpulkan dari angkanya saja — lihat ambang yang
> berlaku untuk elemen yang sedang dinilai.

## Lima bug yang ditemukan lewat pengujian, bukan lewat membaca kode

1. Tombol bulan 41 px (di bawah target sentuh 44 px).
2. Transaksi mendarat di akun `Tunai` karena UI tidak mengirim `account_id`;
   parser mengembalikan `null` dan `_resolve_account` di `src/db.py` jatuh ke akun
   `'Tunai'` bersaldo 0. Sekarang akun bersaldo terbesar dikirim eksplisit, dan
   `/api/save` **gagal keras** kalau akun tidak cocok.
3. Chip akun tidak pernah dirender di kartu hasil parser (hanya di kartu manual).
4. Dua kartu draft bisa menumpuk sehingga draft basi bisa tersimpan.
5. Input tanggal 24 px setelah Tailwind dipasang — Tailwind menghapus gaya
   bawaan input, jadi `min-h-tap` wajib dipasang eksplisit.

**Bug ke-6 ditemukan di `src/server.py` (area monica), bukan di UI:**
`model_config` dipakai di baris 346 tapi tidak diimpor, sehingga `POST
/api/analysis` selalu gagal **setelah** model menjawab — narasinya jadi lalu
dibuang. Exception-nya keluar sebelum `_send()` sehingga klien melihat HTTP 000
(koneksi putus), yang terlihat seperti server mati, bukan seperti bug. Sudah
diperbaiki monica; sekarang balasannya JSON rapi.

## Kesalahan yang saya buat dan perbaiki (dicatat supaya tidak terulang)

- **Eksperimen cache.** Cache pintar pada `refresh()` membuat panel menampilkan
  `Januari NaN` dan navigasi bulan mati. Dikembalikan ke versi sederhana.
- **Hilangnya `position: sticky` header.** Saat CSS ditulis ulang untuk Pico,
  aturan itu ikut terhapus dan header tidak lengket selama beberapa putaran.
- **Penggantian nama class terlalu luas.** Saat pindah ke Tailwind, pola
  `'chatlog'` ikut tergantikan menjadi string class Tailwind, sehingga
  `$('chatlog')` menjadi `$('flex flex-col gap-3 py-4')` dan mengembalikan
  `null`. `init()` mati sebelum `await refresh()`, jadi panel tampil `—` tanpa
  error apa pun di konsol — `init()` adalah async tanpa `.catch()`.
  Pelajarannya: `$()` mencari ID, jadi penggantian nama class tidak boleh
  menyentuh argumennya.
- **Uji yang cacat.** Tiga kali saya menyimpulkan "framework X merusak tata
  letak" dari pengukuran pada elemen yang masih `hidden` (lebar 0) dan dari
  viewport yang tidak benar-benar berubah. Kesimpulan baru sah setelah diukur
  pada keadaan yang benar-benar tampil.
- **Kesalahan uji yang saya kira bug panel.** Memanggil `/api/save` dengan kunci
  `items` padahal kontraknya `transactions`; mencari tombol "Simpan" padahal
  namanya "Simpan perubahan"; menilai warna chip di layar tersembunyi (tampil
  `false` tapi `getComputedStyle` tetap mengembalikan warna). Ketiganya
  kesalahan pengujian — pelajarannya: **cek kontrak dan nama sebenarnya dulu,
  dan pastikan elemennya benar-benar tampil, sebelum menyimpulkan ada bug.**

## Keputusan yang saya ambil, dan alasannya

1. **Arah tidak punya chip; `flow_type` yang punya.** Chip `income`/`transfer`
   sekaligus mengubah `direction` karena pasangannya dikunci di `src/db.py`.
   `transfer` belum bisa disimpan dari layar ini — butuh akun tujuan, dan
   memintanya setengah jalan lebih berbahaya daripada tidak menyediakannya.
2. **Riwayat tidak disimpan di UI.** Angka keuangan tidak pernah dihitung di
   `app.js` — semua dari API. Satu-satunya aritmetika di UI adalah geometri
   grafik dan subtotal baris yang **sudah** dikirim server.
3. **`app.js` tidak ditulis ulang jadi komponen.** Logika grafik SVG, alur chat
   dua langkah, dan chip koreksi sudah teruji; menulisnya ulang berisiko
   mematahkan bagian yang sudah benar.
4. **Lipat per tanggal: ambang dihitung per BULAN, bukan per tanggal.** Yang
   membuat halaman panjang adalah jumlah baris total. Bulan sepi tidak ditutup
   karena tombolnya hanya menambah klik tanpa menghemat gulir.

## Catatan proyek

**[KOREKSI 23 Okt 2026]** Kalimat lama di sini berbunyi "**Proyek ini bukan repo git** — tidak ada
`.git`, jadi tidak ada riwayat versi". Itu **salah**: `web/` adalah bagian dari repo git aktif
(`~/Documents/AI/finance`, remote `dendense/monica-finance`, branch `main`, `.git/` di akar repo).
Riwayat versi **ada**, dan berkas yang dihapus masih bisa dipulihkan lewat `git log` / `git show`.
Karena itu tidak perlu lagi backup manual di `web/backup/` — cukup commit. (Folder `web/backup/`
pernah ada, 6 berkas era Pico & Tailwind awal, dan sudah dibuang setelah dipastikan isinya
tergantikan: hanya 2 id yang tidak ada di versi aktif, sementara 17 id baru sudah masuk.)
