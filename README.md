# monica-finance*

Pencatatan keuangan pribadi yang berjalan di komputermu sendiri. Catat
pemasukan dan pengeluaran lewat kalimat biasa, lihat posisi keuangan, dan
baca analisa bulanan.
*memakai nama monica karena menggunakan nama AI Agent yang ku atur sebagai Financial Advisor.

```
┌──────────────────────────────────────────────┐
│  Chat:                                       │
│  "makan siang 35rb"                          │
│                                              │
│  → draft: 2026-10-03 · keluar · Rp 35.000    │
│            Makan · BRI                       │
│                                              │
│  [ Simpan ]  [ Ubah ]  [ Batal ]             │
└──────────────────────────────────────────────┘
```

AI hanya menyiapkan **draft**. Tidak ada yang tersimpan sampai kamu tekan
Simpan. Kalau AI salah menebak, kamu betulkan dulu.

---

## Kenapa ini ada

Aplikasi keuangan biasanya menyimpan datamu di server orang lain. Yang ini
tidak: databasenya SQLite, servernya di komputermu, dan tidak ada koneksi
keluar kecuali saat AI menebak kategori dari kalimatmu.

Datamu tidak pernah dikirim ke mana pun untuk disimpan. Tidak ada akun, tidak
ada langganan, tidak ada syarat layanan.

---

## Menjalankan

Butuh **Python 3.10+**. Tidak butuh Node.js, tidak butuh Docker.

```bash
git clone <url-repo>
cd finance
python3 src/server.py --port 8791
```

Buka `http://localhost:8791`. Database dibuat otomatis saat server pertama kali
jalan, lengkap dengan 11 kategori bawaan.

**Akun sengaja kosong — kamu membuatnya sendiri.** Buka layar **Akun** dan
tambahkan rekening yang kamu pakai (tabungan, dompet digital, uang tunai)
beserta saldo awalnya. Setelah itu kamu bisa mulai mencatat.

Kenapa tidak diisi contoh: akun bawaan akan **muncul kembali setiap server
dinyalakan**. Dulu ada `Tunai` dan `BCA` di berkas data awal — Deny menghapus
`Tunai`, menyalakan ulang server, dan akunnya kembali dengan id baru. Lebih baik
mulai dari kosong daripada punya akun hantu yang tidak bisa dihapus.

### Menyiapkan AI untuk kolom catat (opsional)

Kolom catat bisa menebak kategori dari kalimatmu, tapi perlu satu endpoint AI
yang kompatibel dengan OpenAI. Tanpa ini, **aplikasinya tetap jalan** — kamu
cukup mengisi form secara manual.

Konfigurasinya ada di `src/model_config.py`. Bawaannya API kenari.id:

```bash
# tidak perlu diatur — ini bawaannya
# https://kenari.id/v1/chat/completions
```

Kalau ingin lewat router lokal (mis. omniroute), timpa alamatnya:

```bash
export KENARI_BASE="http://localhost:20128/v1/chat/completions"
export KENARI_API_KEY="<kunci>"   # wajib kalau mau memakai AI
```

`KENARI_BASE` **opsional** — bawaannya `https://kenari.id/v1/chat/completions`.
Normalisasinya: nilai yang berakhir `/v1` atau `/v1/` otomatis ditambah
`chat/completions`, jadi `export KENARI_BASE="https://kenari.id/v1"` juga benar.
Nilai yang sudah berakhir `/chat/completions` dipakai apa adanya.

`KENARI_API_KEY` tidak punya bawaan; tanpa isinya, kolom catat jatuh ke
pengisian manual (aplikasi tetap jalan).

Perlu diperhatikan: **nama model di kenari.id tidak memakai awalan `kenari/`.**
Awalan itu konvensi router omniroute. Lewat kenari.id langsung, nama modelnya
`deepseek-v4-1-flash` — memakai `kenari/deepseek-v4-1-flash` menghasilkan
HTTP 400 `no price for model`.

Untuk mengganti model, ubah `MODEL` di `src/model_config.py`, lalu **uji
akurasinya** sebelum dipakai mencatat:

```bash
python3 scripts/uji_model.py <nama-model>
```

Kenapa harus diuji: dari empat model yang pernah dicoba, **tiga gagal di semua
kasus** — bukan karena kode, tapi karena kuota gratisnya habis atau modelnya
sudah dicabut. Model yang "hidup" belum tentu bisa menebak dengan benar.

### Di mana datanya disimpan

Secara bawaan **di luar folder repo**, di `../finance-pribadi/`:

```
folder-induk/
├── finance/            ← hasil git clone (kode)
└── finance-pribadi/    ← database, kredensial, rekening koran (DATAMU)
```

Pemisahan ini disengaja. Kalau datamu ada di dalam repo, satu salah ketik
`git add -f` bisa mengirimnya ke GitHub — dan **menghapusnya tidak cukup**,
karena git menyimpan riwayat. Pemisahan fisik mencegahnya; `.gitignore` hanya
mengingatkan.

Mau menaruh datamu di tempat lain? Arahkan lewat `FINANCE_DATA`:

```bash
FINANCE_DATA=/Volumes/disk-luar/finance-data python3 src/server.py --port 8791
```

---

## Memasang password

Panel bisa dibuka siapa pun yang mengakses port-nya. Di Mac pribadi itu
biasanya tidak masalah, tapi lebih baik dipasang:

```bash
python3 scripts/reset_password.py
```

Sesi bertahan sampai kamu keluar — atau sampai server dimatikan. Kalau server
mati di tengah jalan, kamu diminta masuk lagi. Itu disengaja: sesi hidup di
memori, jadi tidak ada berkas sesi yang bisa dicuri dari disk.

---

## Bentuk datanya

Tiga kolom yang paling sering tertukar:

| Kolom | Artinya | Nilainya |
|---|---|---|
| `direction` | ke mana uang mengalir | `in` · `out` · `transfer` |
| `flow_type` | sifat transaksinya | `expense` · `income` · `receivable` · `debt_payment` · `transfer` |
| `category` | jenisnya | Makan · Transport · Tagihan · … |

**`flow_type` itu penting dan tidak jelas dari namanya.**

Bayangkan bulan ini kamu mengeluarkan Rp 2.100.000. Terdengar boros. Tapi
kalau dipisah: **hanya Rp 284.000 yang benar-benar habis dikonsumsi** —
sisanya pelunasan utang (uangmu memang sudah dipakai sebelumnya) dan talangan
untuk project yang akan dibayar kembali.

Tanpa pemisahan itu, laporan bulanan menakut-nakuti tanpa alasan. Karena itu
setiap transaksi keluar wajib punya `flow_type`, dan aplikasinya menolak
menyimpan tanpa itu.

Rinciannya di `docs/SCHEMA.md`.

---

## Yang bisa dilakukan

- **Catat lewat chat** — ketik kalimat, AI menyiapkan draft, kamu konfirmasi
- **Pemasukan & pengeluaran** dengan kategori dan akun
- **Transfer** antar akun sendiri
- **Piutang** (uang talangan yang akan kembali) dan **utang** (cicilan)
- **Posisi keuangan** — total kekayaan, dipisah likuid dan tidak likuid
- **Tren** — perbandingan beberapa bulan
- **Analisa bulanan** — sisa uang, saran hemat berangka, catatan AI
- **Target tabungan** dengan progres dari saldo akun
- **Impor rekening koran** dari PDF bank (lihat `scripts/`)

---

## Struktur

```
finance/
├── src/                    kode yang jalan
│   ├── db.py               lapisan data — SEMUA angka lewat sini
│   ├── schema.sql          tabel + view (berdiri sendiri, tanpa migrasi)
│   ├── seed.sql            akun & kategori awal
│   ├── migrations/         perubahan skema setelah versi pertama
│   ├── server.py           API + penyaji panel
│   ├── auth.py             password & sesi
│   ├── parser_wrap.py      kalimat → draft transaksi
│   ├── monthly_analysis.py analisa bulanan + narasi AI
│   └── model_config.py     model AI yang dipakai
├── web/                    panel di browser
├── tests/                  uji
├── scripts/                alat sekali-pakai (impor, reset password)
├── docs/                   dokumen penjelasan
└── requests/               catatan pekerjaan yang belum tuntas
```

---

## Menjalankan uji

```bash
for t in tests/test_*.py; do python3 "$t"; done
```

Semua uji memakai database **sementara** di direktori temp. Datamu tidak
tersentuh — dan `tests/test_analysis_handler.py` memeriksa hal itu secara
khusus, karena pernah ada versi uji yang menulis ke database asli.

Uji-uji ini menangkap bug yang **tidak menimbulkan error**: angka yang berubah
diam-diam. Kalau kamu mengubah `src/schema.sql` atau `src/db.py`, jalankan
semuanya.

---

## Tiga aturan yang dipegang kode ini

**1. Angka tidak pernah dikarang.** Kalau data tidak ada, jawabannya "datanya
belum ada" — bukan perkiraan yang disajikan seolah tercatat. Kalau sebuah angka
hasil ekstrapolasi, itu ditandai.

**2. UI tidak menghitung angka keuangan.** Semua angka datang dari `src/db.py`.
Kalau UI menjumlahkan sendiri, cepat atau lambat UI dan laporan berbeda dan
tidak ada yang tahu mana yang benar.

**3. Perbedaan saldo adalah temuan, bukan masalah yang dirapikan.** Kalau angka
sistem tidak cocok dengan rekening asli, itu dilaporkan — tidak dibulatkan.

---

## Batas yang perlu kamu tahu

**Satu pengguna, satu database.** Tidak ada konsep "akun pengguna" di dalam
aplikasi ini. Kalau dua orang menjalankannya di komputer yang sama, mereka
berbagi satu database dan saling melihat data. Untuk pemakaian pribadi di
Mac-mu sendiri, itu tepat. Untuk banyak orang, ini perlu dikerjakan lagi.

**Hanya bisa diakses dari komputer tempat server jalan.** Tidak ada akses dari
HP, kecuali kamu sengaja membukanya ke jaringan (`--host 0.0.0.0`) — dan kalau
itu dilakukan, **pasang password lebih dulu**.

**Transaksi dimasukkan manual.** Tidak ada koneksi ke bank. Rekening koran bisa
diimpor dari PDF, tapi sisanya kamu ketik sendiri. Itu keputusan sadar: koneksi
bank otomatis butuh kredensial perbankan, dan itu risiko yang tidak sebanding.

---

## Menambah perubahan skema

1. Tulis berkas baru di `src/migrations/` — jangan edit migrasi lama, berkas itu
   jejak perubahan.
2. Perbarui juga `src/schema.sql` supaya database baru tidak butuh migrasi.
   (Pernah terjadi sebaliknya: `flow_type` hanya ada di migrasi, sehingga
   database yang dibangun dari nol langsung mati.)
3. Jalankan semua uji.

---

## Lisensi

MIT — lihat `LICENSE`. Pakai, ubah, sebarkan sesukamu.
