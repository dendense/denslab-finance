# Spesifikasi UI mobile-first — finance

Untuk **yuki**. Ini acuan desain; kalau ada yang bertentangan dengan kenyamanan pakai di HP,
kenyamanan di HP yang menang.

> **Koreksi 23 Okt 2026.** Empat bagian di dokumen ini sudah tidak benar dan dikoreksi di tempat,
> ditandai **[KOREKSI]**: §Auth (Supabase), §Mode gelap (sudah diputuskan & diimplementasi),
> rujukan surat yang tidak ada, dan §Laporan (bukan lagi "file dari monica").
> Catatan struktur: aplikasi kini **lokal** (SQLite + server di Mac, lihat `docs/PLAN.md`
> §Revisi), jadi panel dibuka dari Mac/lebar desktop juga. Prinsip mobile-first di bawah tetap
> berlaku sebagai disiplin desain — layar tersempit tetap harus enak dipakai — tapi bukan lagi
> karena Deny membukanya dari HP di jalan.

## Prinsip

**Dirancang dari layar HP, bukan desktop yang dikecilkan.** Layar tersempit (360 px) adalah
batas yang menentukan; kalau muat di sana, lebar lain aman. Asumsinya:

- **Satu tangan.** Aksi utama harus terjangkau ibu jari — separuh bawah layar, bukan pojok atas.
- **Sekali lihat.** Informasi terpenting terbaca tanpa scroll.
- **Input cepat.** Mencatat transaksi harus selesai dalam beberapa detik. Kalau mencatat
  terasa lambat, Deny akan berhenti mencatat, dan seluruh sistem jadi tidak berguna.

## Token dasar

- Font: sistem (`-apple-system`, `Inter`) — jangan muat webfont, lambat di jaringan seluler.
- Warna: gunakan CSS variable, jangan hardcode hex di komponen.
- Radius dan spacing konsisten; jangan campur dua skala.
- Target sentuh minimum **44×44 px**. Jangan ada tombol kecil di dekat tepi layar.
- Aman terhadap notch: pakai `env(safe-area-inset-*)` di header dan bottom bar.

## Layar

### 1. Beranda / panel analisa
Urutan dari atas: **total kekayaan** (angka besar, ini yang pertama dicari) → pemasukan dan
pengeluaran bulan berjalan → selisih → grafik tren 6 bulan → kartu saran hemat → daftar
transaksi terakhir.

Kartu "Pengeluaran" di beranda memakai `total_out` (semua uang keluar). Grafik tren dan
konsumsi per kategori memakai `expense_real` dengan label **"konsumsi"** — dua angka berbeda
dengan sengaja, lihat `docs/CONTRACT.md` §2 dan `web/app.js:537`.

Grafik harus bisa dibaca di lebar 360 px. Kalau label tidak muat, ringkas jadi "Jul", jangan
putar teks atau perkecil sampai tidak terbaca.

**Saran hemat wajib menyebut asumsinya.** "Bisa dihemat Rp 300.000/bulan" tanpa penjelasan
adalah angka yang tidak bisa dipercaya.

### 2. Catat transaksi
Layar paling sering dipakai — investasikan waktu di sini.

- Tiga pilihan arah: **Masuk / Keluar / Pindah** sebagai segmented control besar di atas.
- **Numpad besar muncul langsung** — jangan suruh tap field dulu baru keluar keyboard.
- Akun dan kategori sebagai chip yang bisa di-tap, bukan dropdown (dropdown di HP menyiksa).
- Tanggal default **hari ini**, bisa diubah; jangan paksa Deny memilih tanggal setiap kali.
- Catatan opsional, jangan wajib. Kolom wajib hanya: jumlah, arah, akun.

### 3. Daftar transaksi
Dikelompokkan per hari, header tanggal lengket (sticky) saat scroll. Edit/hapus lewat geser
(swipe) atau tap panjang — jangan taruh tombol hapus kecil yang gampang salah tekan.

### 4. Akun & saldo
Kartu per akun dengan saldo. Total di atas. Tabungan dan investasi boleh dipisah secara visual
dari akun harian, tapi tetap masuk total kekayaan.

### 5. Laporan
**[KOREKSI]** Dulu ditulis "dibaca dari file yang dihasilkan monica". Sekarang halaman analisa
punya endpoint sendiri: `GET /api/analysis` dan `POST /api/analysis` (`src/server.py:1164,1209`),
angkanya dihitung dari SQL dan narasinya dari model (`src/monthly_analysis.py`, 393 baris).
Teks, bukan dashboard — Deny membacanya seperti laporan, bukan mengoperasikannya. Bulan berjalan
tidak bisa dianalisa; analisa dibuat untuk bulan yang sudah selesai.

## Yang harus dihindari

- Tabel lebar yang butuh scroll horizontal.
- Hover sebagai satu-satunya cara memunculkan aksi (HP tidak punya hover).
- Modal bertumpuk (modal di atas modal) — di HP cepat bikin bingung.
- Angka penting yang tersembunyi di balik tap.
- Animasi yang memakan waktu. Transisi maksimal ~150 ms.
- Format angka mentah. Selalu `Rp 1.100.000`, bukan `1250000`.

## Auth

**[KOREKSI]** Dulu bagian ini menyebut "Login Supabase" dan token di penyimpanan aman browser.
Tidak ada Supabase — arsitekturnya dibatalkan 1 Okt 2026. Yang berlaku sekarang
(`src/auth.py`, `src/server.py:1148-1153`):

- **Password lokal.** Hash PBKDF2-SHA256 (200.000 iterasi) di `kredensial.json` di folder data
  (`src/auth.py:45,47`), bukan di repo. Dipasang lewat `web/login.html` atau
  `scripts/reset_password.py`.
- **Sesi di memori proses** (`src/auth.py:50` → `_SESI = {}`). Token acak 32 byte, batas diam
  12 jam. **Restart server = semua sesi hilang.** Ini disengaja, bukan bug — jangan menjanjikan
  "sesi bertahan" tanpa mengubah backend.
- **Cookie `sesi`**: `Path=/; HttpOnly; SameSite=Lax`, **tanpa** `Max-Age` dan **tanpa** `Secure`
  (`src/server.py:42`). Jadi ini cookie sesi browser: hilang saat browser ditutup.
- Halaman tanpa sesi diarahkan ke `/login` (302). Halaman `/login` sendiri disajikan 200.

Kalau nanti sesi harus bertahan antar-restart, itu perubahan backend — bukan pekerjaan UI.
Jangan menyimpan token di `localStorage`; cookie-nya sudah `HttpOnly`.

## Yang belum diputuskan

- **[KOREKSI] Mode gelap: SUDAH diputuskan dan SUDAH diimplementasi.** Tiga pilihan —
  **Ikut sistem / Terang / Gelap** — lewat tombol `#btn-tema` (`web/index.html:98`), logika di
  `web/app.js:3891-3905` (`TEMA = ['sistem','terang','gelap']`), class `.gelap` di `<html>`, dan
  varian Tailwind `@custom-variant dark (&:where(.gelap, .gelap *))` (`web/src.css:19`).
  **Aturan untuk perubahan baru:** jangan pakai `prefers-color-scheme` langsung — semua warna
  gelap harus lewat varian `dark:` / class `.gelap` supaya pilihan manual tetap menang.
- Offline: belum dikerjakan. Server-nya lokal, jadi "offline" berarti server mati — bukan
  jaringan seluler hilang.

---

## Aturan berkas frontend (4 Okt 2026)

**[KOREKSI]** Dulu bagian ini mengaku dipindah dari surat
`monica-ke-yuki-2026-10-03-aturan-repo-publik.md`. **Surat itu tidak ada** di
`docs/arsip/` (isinya surat lain). Aturan di bawah tetap berlaku dan sekarang
tinggal di sini sebagai tempat asalnya — tidak ada dokumen lain yang perlu dirujuk.

**Repo ini publik** — aturan ini berlaku untuk siapa pun yang mengubah `web/`.

### `web/tailwind.css` WAJIB ikut git, walaupun hasil build

`web/index.html` memuat `<link rel="stylesheet" href="/tailwind.css">`. Kalau
berkas itu tidak ikut repo, orang yang meng-clone mendapat panel **tanpa gaya
sama sekali** kecuali dia memasang Node.js lebih dulu dan menjalankan build.

**Pernah terjadi:** `web/.gitignore` mengabaikan `tailwind.css`, sehingga
`src.css` terlacak tapi hasil buildnya tidak. Terbukti dengan meng-clone repo
dan `curl` — `/tailwind.css` balas `302`, **0 byte**, sementara di repo asli
39.470 byte.

**Setiap kali mengubah `src.css` atau class Tailwind:**

```bash
cd web && npm run css
git add src.css tailwind.css      # keduanya, selalu berpasangan
```

### Uji yang menyentuh database WAJIB pakai `FINANCE_DATA`

Tanpa itu, uji **menulis ke database keuangan Deny**. Data hidup di luar repo
(`../Data/finance/`), dan `src/db.py` punya pengaman: folder yang berisi
`finance.db` tapi tanpa penanda `.finance-data` akan **ditolak** server.

```bash
cp "${FINANCE_DATA:-$HOME/Documents/AI/Data/finance}/finance.db" /tmp/uji/data/finance.db
touch /tmp/uji/data/.finance-data
FINANCE_DATA=/tmp/uji/data python3 src/server.py --port 8795
```

Prosedur lengkapnya (termasuk cara memasang password uji di salinan) ada di
`web/README.md`, bagian "Cara menguji alur tulis tanpa menyentuh database Deny".

### Jangan tulis password di dokumen mana pun

Walau cuma password uji. Dokumen di folder ini dibaca orang lain nanti, dan
password lebih baik tidak punya jejak tertulis.

### Kegagalan tidak boleh menyamar jadi keadaan data

Kalau sebuah endpoint gagal dihubungi, pesannya harus bilang **gagal** — bukan
"belum ada data". Contoh yang pernah salah: grafik tren berkata *"Belum ada data
6 bulan terakhir, catat transaksi dulu"* padahal `/api/trend`-nya yang mati.
Itu menyalahkan Deny untuk kegagalan koneksi.

Prinsipnya sejalan dengan `ada_data: false`: jangan tampilkan "nol" untuk
sesuatu yang sebenarnya "tidak diketahui".
