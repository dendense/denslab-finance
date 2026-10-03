# Aturan repo — untuk yuki

**Tanggal:** 3 Okt 2026
**Dari:** monica
**Ke:** yuki (FRONTEND — `web/`)
**Perihal:** Repo ini sudah jadi repo publik (privat dulu). Baca ini sebelum menulis kode lagi.

---

## Kenapa surat ini ada

Semalaman ini repo berubah lebih banyak daripada kelihatannya. Perubahannya
bukan di fitur — **di aturan mainnya**. Kalau kamu menulis kode seperti kemarin,
ada tiga hal yang akan salah:

1. Kamu akan menaruh berkas di tempat yang **tidak boleh** ada berkasnya
2. Kamu akan memakai path yang **sudah tidak menunjuk** ke tempat lama
3. Kamu akan meng-commit berkas yang **tidak boleh** masuk git

Surat ini menutup ketiganya. Bagian 5 berisi daftar periksa — pakai itu sebelum
kamu push apa pun.

---

## 1. Yang paling penting: data keuangan TIDAK ADA di dalam repo lagi

**Dulu:**
```
finance/
└── data/
    ├── finance.db          <- database keuangan Deny
    ├── kredensial.json
    └── statements/*.pdf
```

**Sekarang:**
```
Documents/AI/
├── finance/                <- REPO (kode saja)  <-- kamu bekerja DI SINI
│   ├── src/
│   ├── web/
│   └── tests/
└── finance-pribadi/        <- DATA (di luar repo, tidak akan pernah masuk git)
    ├── finance.db
    ├── kredensial.json
    ├── terhapus.log
    └── statements/
```

### Kenapa dipisah FISIK, bukan cuma di-`.gitignore`

`.gitignore` hanya mencegah `git add .` menambahkan berkas. Ia **tidak** mencegah
`git add -f`, alat yang mengabaikan `.gitignore`, atau salah ketik.

Dan yang paling menentukan: **begitu data keuangan masuk satu commit, menghapusnya
tidak cukup.** Git menyimpan riwayat. Berkasnya tetap bisa di-checkout siapa pun
yang meng-clone. Untuk benar-benar hilang, riwayatnya harus ditulis ulang dan
di-force-push — di repo yang sudah dibagikan, itu merusak fork orang lain.

Pemisahan fisik mencegahnya. `.gitignore` hanya mengingatkan.

### ATURAN untuk kamu

**Jangan pernah menulis berkas ke `finance/data/`.** Folder itu tidak ada lagi.
Kalau kodemu butuh berkas baru, simpan di `web/` (kalau bagian dari panel) atau
bilang ke aku.

**Jangan pernah menaruh database, PDF, atau kredensial di dalam repo.**

---

## 2. Cara menemukan data — JANGAN hardcode

Sekarang ada variabel yang menentukannya. Semua di `src/db.py`:

```python
SRC_DIR   = Path(__file__).resolve().parent        # .../finance/src
ROOT_DIR  = SRC_DIR.parent                          # .../finance
REPO_DIR  = ROOT_DIR

DATA_DIR  = Path(os.environ.get("FINANCE_DATA")
                 or (REPO_DIR.parent / "finance-pribadi"))   # di LUAR repo
DB_PATH   = DATA_DIR / "finance.db"

PENANDA   = ".finance-data"     # berkas penanda folder data
```

Dan di `src/auth.py`:

```python
DATA_DIR   = Path(os.environ.get("FINANCE_DATA") or (ROOT_DIR.parent / "finance-pribadi"))
KREDENSIAL = DATA_DIR / "kredensial.json"
```

### ATURAN untuk kamu

**Kalau butuh lokasi data dari JavaScript, JANGAN menghitungnya sendiri.**
Ambil dari API. UI tidak boleh tahu di mana datanya disimpan — itu urusan server.

**Kalau butuh dari Python** (mis. skrip uji), impor dari `db`/`auth`, jangan
menulis ulang path-nya. Kalau kamu menulis `Path(__file__).parent.parent / "data"`,
kode itu akan **membuat folder baru** dan menulis ke sana — persis bug yang
hampir terjadi malam ini.

---

## 3. Pengaman baru: folder data punya penanda

Aku menambahkan pengaman supaya kode tidak diam-diam menulis ke folder yang salah.
Aturannya:

| Keadaan folder | Hasil |
|---|---|
| Folder belum ada | izinkan (pemakaian pertama) |
| Ada berkas penanda `.finance-data` | izinkan |
| **Ada `finance.db` TAPI tanpa penanda** | **TOLAK — server berhenti** |
| Folder kosong | izinkan |

Yang ditolak hanya keadaan berbahaya: database yang tidak dikenal.

**Ini pernah menyelamatkan data Deny.** Aku menjalankan skrip uji di folder clone
dengan maksud memakai database clone — ternyata `FINANCE_DATA` tidak ter-set di
lingkungan skrip itu, jadi kode menulis ke database keuangan Deny. Yang
menyelamatkan hanya kebetulan.

### ATURAN untuk kamu

Kalau kamu membuat skrip atau uji yang menyentuh database:

```bash
FINANCE_DATA=/tmp/uji-kamu python3 skrip_kamu.py
```

Atau di dalam Python, panggil fungsinya dengan path eksplisit:

```python
db.init_db(TMP / "uji.db")        # BENAR — path eksplisit
db.init_db()                       # BAHAYA — menyentuh data Deny
```

**Dan satu jebakan yang sudah menggigitku:** argumen default (`path=DB_PATH`)
diikat saat fungsi **DIDEFINISIKAN**, bukan saat dipanggil. Jadi mengganti
`db.DB_PATH` setelah impor **tidak cukup** — `db.simpan_analisa(x)` tetap menulis
ke database lama. Kalau perlu mengganti lokasi, panggil dengan path eksplisit.

---

## 4. `.gitignore` — apa yang boleh dan tidak boleh masuk git

### TIDAK boleh masuk (sudah diabaikan)

```
data/                    finance-pribadi/          *.db
*.pdf                    kredensial.json           terhapus.log
.env                     *.key                     node_modules/
__pycache__/             .DS_Store
```

### WAJIB masuk — jangan pernah kamu abaikan

**`web/tailwind.css` HARUS ikut git.** Walaupun ia hasil build.

Kenapa: kalau diabaikan, orang yang meng-clone mendapat panel **tanpa gaya sama
sekali** kecuali ia memasang Node.js lebih dulu. Panel harus bisa dibuka langsung
setelah clone — itu yang membuat orang mau mencobanya.

Jadi kalau kamu mengubah class Tailwind, **jalankan `npm run css` dan commit
`tailwind.css` bersama perubahannya.** Jangan serahkan ke langkah setup.

Yang tetap diabaikan dan itu benar: `web/node_modules/` dan `web/.npm-cache/` —
bisa dipasang ulang dengan `npm install`.

### ATURAN untuk kamu

Sebelum `git add`, jalankan:

```bash
git status --short
```

dan periksa tidak ada `*.db`, `*.pdf`, atau berkas di `data/` yang muncul.

---

## 5. Daftar periksa sebelum kamu push

- [ ] Tidak ada berkas baru di `finance/data/` (folder itu sudah tidak ada)
- [ ] Tidak ada `*.db`, `*.pdf`, atau kredensial di dalam repo
- [ ] Kalau aku mengubah `web/src.css`: `web/tailwind.css` **ikut di-commit**
- [ ] Kalau ada skrip/uji baru yang menyentuh database: pakai `FINANCE_DATA`
      atau path eksplisit — **bukan** `db.init_db()` tanpa argumen
- [ ] `git status --short` bersih dari berkas data
- [ ] Uji lulus: `for t in tests/test_*.py; do python3 "$t"; done`

---

## 6. Yang berubah di `src/` (jangan heran)

| Perubahan | Kenapa |
|---|---|
| `db.py`: `DATA_DIR`, `PENANDA`, `periksa_lokasi_data()`, `pastikan_lokasi_aman()` | pengaman lokasi data |
| `db.py`: `init_db()` menandai folder + memeriksa lokasi | satu-satunya tempat pemeriksaan |
| `auth.py`: `KREDENSIAL` pindah ke `DATA_DIR` | kredensial ikut pindah ke luar repo |
| `auth.py`: `sudah_ada_password()` menandai folder data | `/api/auth` jalan lebih dulu dari `init_db()` |
| `.gitignore`, `LICENSE`, `README.md` | repo publik |

**`web/` tidak kusentuh.** Semua perubahan di atas di `src/`.

---

## 7. Yang masih kutunggu darimu

Tiga hal, dan semuanya sudah kusebut di surat-surat sebelumnya:

**a. `requests/CATATAN-BELUM-SELESAI.md` belum diperbarui.** Isinya masih
menyebut §1, §4, §7, §8 sebagai "belum dikerjakan" — padahal semuanya sudah
selesai. Kalau tidak diperbarui, sesi berikutnya akan mengerjakan ulang hal yang
sudah jadi, atau menunggu endpoint yang sudah ada.

**b. Hapus `data/kredensial.json`** kalau masih ada di tempat lama. Password uji
`[password uji — tidak ditulis di dokumen]` masih terpasang di panel Deny. Sekarang kredensialnya pindah ke
`finance-pribadi/kredensial.json` — **yang di `finance/data/` sudah tidak dipakai**,
dan folder itu sudah kuhapus.

**c. Daftar periksa pengujian.** Kamu menemukan **tiga** hal lewat pengujian yang
tidak akan ketahuan dari membaca kode: celah `/api/auth`, cacat arsip target, dan
bug `model_config`. Semua itu tercatat sebagai **surat** — dan surat bergeser.
Daftar di dekat kodenya tetap ada.

---

## 8. Keadaan repo sekarang

```
Repo        : dendense/monica-finance (PRIVAT)
Cabang      : main
Berkas      : 72
Uji         : 13/14 lulus (1 menolak — butuh password Deny)
Data Deny   : di luar repo, 25 transaksi, Rp 5.713.751 — terverifikasi utuh
```

Email commit: `denyfarras@gmail.com`.

---

## Pertanyaanku

1. Dari §7, mana yang kamu kerjakan lebih dulu? Kalau `CATATAN-BELUM-SELESAI.md`
   dulu, itu paling cepat dan paling mencegah kesalahan berikutnya.
2. Untuk pekerjaan sisa di `web/` (`/api/trend`, `/api/categories`, penanda
   `source`, form edit `transfer`) — masih relevan semua, atau ada yang mau kamu
   tanyakan dulu?

Tidak ada yang perlu dikirim balik kalau semuanya sudah jelas. Aku hanya perlu
tahu kamu sudah membaca §1, §3, dan §4 sebelum menulis kode berikutnya.

---

*Ditulis monica, 3 Okt 2026. Tidak ada perubahan di `src/` dari surat ini —
surat ini murni catatan aturan.*
