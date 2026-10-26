# Finance (denslab-finance)

Pencatatan keuangan pribadi yang jalan di komputer sendiri: catat pemasukan dan
pengeluaran lewat kalimat biasa, lalu lihat posisi keuangan dan analisa bulanan.
Dibuat untuk satu orang di satu Mac.

## Status

Yang jalan: panel web lokal (`src/server.py`), catat lewat chat dengan AI (opsional),
transfer antar akun, piutang dan utang, target tabungan, tren bulanan, analisa bulanan,
backup otomatis sebelum server dinyalakan.

Yang belum: aplikasi desktop di `app/` masih kerangka (Tauri 2 + Vite + React). Sumbernya
ada dan `app/src-tauri/target/` diabaikan git. Repo ini tidak punya CI.

## Kebutuhan

- Python 3.9 minimum, 3.11 direkomendasikan — `MINIMUM = (3, 9)` dan
  `REKOMENDASI = (3, 11)` di `src/versi_python.py`. Di bawah 3.9 server menolak jalan.
- `sqlite3` CLI, dipakai `scripts/backup-db.sh`.
- Opsional: Node + npm hanya kalau mengubah panel (`web/package.json`).
- Opsional: Node + pnpm dan Rust 1.90+ (`app/src-tauri/Cargo.toml`) untuk aplikasi desktop.

## Cara jalan

```bash
git clone https://github.com/dendense/denslab-finance.git
cd finance
python3 src/server.py --port 8791
```

Buka `http://localhost:8791`. Database dibuat otomatis saat pertama jalan (`init_db()` di
`src/db.py`) lengkap dengan 11 kategori bawaan. Akun sengaja kosong — tambahkan sendiri di
layar Akun, karena apa pun di `src/seed.sql` akan muncul kembali setiap server dinyalakan.

Port bawaan `src/server.py` adalah **8765**; `8791` dipakai karena itu port
`scripts/start-server.sh` (`FIN_PORT`, bawaan 8791).

Launcher dengan backup otomatis:

```bash
bash scripts/start-server.sh            # backup lalu start (kalau belum jalan)
bash scripts/start-server.sh --restart  # backup lalu restart
bash scripts/backup-db.sh               # backup saja
```

Backup memakai `sqlite3 .backup` (bukan `cp`), memeriksa `PRAGMA integrity_check` pada
salinannya, dan menyimpan 30 terakhir (`FINANCE_BACKUP_KEEP`) di
`~/Documents/AI/Backup/finance/`. Kalau folder tujuan tidak ada, backup dibatalkan
(`exit 1`) — server tetap dinyalakan dan kegagalannya masuk log.

Password panel (opsional):

```bash
python3 scripts/reset_password.py
```

Sesi disimpan di tabel `sesi` dan terikat ke `kern.bootsessionuuid`: bertahan melewati
restart server, mati saat laptop restart, dan kedaluwarsa 30 hari (`BATAS_UMUR_DETIK` di
`src/auth.py`).

## Struktur

- `src/` — server: `server.py` (HTTP API + penyaji panel), `db.py` (semua angka),
  `schema.sql`, `seed.sql`, `migrations/`, `auth.py`, `parser_wrap.py`,
  `monthly_analysis.py`, `model_config.py`, `versi_python.py`
- `web/` — panel HTML/JS; `tailwind.css` hasil build (`npm run css`)
- `app/` — kerangka aplikasi desktop Tauri
- `scripts/` — launcher, backup, reset password, uji model, alat sekali-pakai
- `tests/` — 20 berkas uji
- `docs/` — `SCHEMA.md`, `CONTRACT.md`, `PLAN.md`
- `requests/` — catatan permintaan antar-agent yang belum selesai

## Konfigurasi

| Env | Wajib | Fungsi |
|---|---|---|
| `FINANCE_DATA` | tidak | folder data; bawaan `../Data/finance`, di luar repo |
| `KENARI_API_KEY` | tidak | kunci endpoint AI; tanpa ini kolom catat jatuh ke isian manual |
| `KENARI_BASE` | tidak | alamat endpoint AI; bawaan `https://kenari.id/v1/chat/completions` |
| `FINANCE_BACKUP_DIR` | tidak | folder tujuan backup |
| `FINANCE_BACKUP_KEEP` | tidak | jumlah backup yang disimpan, bawaan 30 |
| `FINANCE_PYTHON` | tidak | interpreter Python yang dipakai `app/` |
| `FIN_PORT` | tidak | port `scripts/start-server.sh`, bawaan 8791 |

`KENARI_API_KEY` dan `KENARI_BASE` juga dibaca dari `<FINANCE_DATA>/secrets.env` kalau env
tidak menyetelnya — env menang. Berkas itu tidak di-`source`, isinya tidak pernah
dieksekusi.

Model AI diatur di `src/model_config.py` (`MODEL`, `MODEL_CADANGAN`). Setelah mengganti
model, uji dulu:

```bash
python3 scripts/uji_model.py <nama-model>
```

Nama model lewat kenari.id tidak memakai awalan `kenari/`; awalan itu konvensi router lain
dan menghasilkan HTTP 400 `no price for model`.

## Test

```bash
for t in tests/test_*.py; do python3 "$t"; done
```

20 berkas uji, semuanya skrip biasa (tanpa pytest). Uji yang menyentuh database memakai
folder sementara dari `tempfile`. Pengecualian: `tests/test_analysis_live.py` memanggil
model AI sungguhan — butuh `KENARI_API_KEY` dan memakai kuota.

## Aplikasi desktop

```bash
cd app
pnpm install
pnpm tauri build
```

Hasil: `app/src-tauri/target/release/bundle/macos/Finance.app` (tidak masuk git).
`identifier` = `id.denslab.finance`. Sidecar menjalankan `python3 src/server.py --port N`
dengan port dipilih Rust. Repo dicari dari `~/Library/Application Support/Finance/config.json`
(kunci `repo_path`), lalu lewat `FINANCE_PYTHON` atau `python_path` di config itu.

## Catatan

- Server hanya mendengarkan `127.0.0.1`; tidak ada flag `--host`. Akses dari HP butuh
  perubahan kode.
- Satu pengguna, satu database: tidak ada tabel pengguna dan tidak ada login terpisah.
- Data disimpan di luar folder repo secara fisik; `.gitignore` hanya pengingat.
- Tidak ada koneksi ke bank. `scripts/import_statement_okt.py` adalah skrip sekali-pakai
  untuk satu rekening koran tertentu — angkanya tertulis di skrip, bukan hasil parse PDF.
- `flow_type` wajib di skema (`NOT NULL` + `CHECK`) dan harus cocok dengan `direction`;
  kalau kosong, `src/db.py` menurunkannya dari `direction`.
- Menambah perubahan skema: berkas baru di `src/migrations/` (jangan edit yang lama) plus
  perbarui `src/schema.sql`, lalu jalankan semua uji.

MIT — lihat `LICENSE`.
