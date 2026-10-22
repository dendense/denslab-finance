# Skema data — finance (SQLite lokal, berlaku)

Status: **berlaku**. Dokumen ini ditulis ulang 23 Okt 2026 dari `src/schema.sql` — bukan dari
rancangan. Setiap kolom, CHECK, dan view di bawah ada di kode sekarang; kalau berbeda, kode
yang benar dan dokumen ini yang harus diperbaiki.

> **Riwayat (jangan diikuti).** Versi pertama dokumen ini (1 Okt 2026) merancang Supabase:
> `uuid`, `user_id`, RLS `auth.uid()`, `numeric(16,2)`, `timestamptz`. Semua itu **dibatalkan**
> Deny 1 Okt 2026 — alasan tertulis *"masalah teknis + biaya"* — dan diganti SQLite lokal murni.
> Lihat `src/schema.sql:1-6` dan `docs/PLAN.md` §Revisi. Rancangan lama **tidak** berlaku.

## Sumber kebenaran

| Hal | Kenyataan |
|---|---|
| Mesin | SQLite, satu berkas |
| Lokasi DB | `$FINANCE_DATA/finance.db`, default `~/Documents/AI/Data/finance/finance.db` (`src/db.py:44-45`) |
| DDL | `src/schema.sql` (262 baris) dibaca `init_db()` — `src/db.py:250` |
| Data awal | `src/seed.sql` dibaca `init_db()` — `src/db.py:251`, dijalankan **setiap** server nyala dengan `INSERT OR IGNORE` |
| Auth | password lokal + sesi di memori (`src/auth.py`) — **bukan** Supabase Auth |
| RLS / `user_id` | **tidak ada.** Satu mesin, satu pengguna. `grep -c user_id src/schema.sql` → 1, dan itu baris komentar |
| Tipe uang | `INTEGER` rupiah penuh, tanpa sen. `grep -c numeric src/schema.sql` → 0 |
| Penanda folder data | `.finance-data` (`src/db.py:152,183-194`) — folder berisi `finance.db` tanpa penanda **ditolak** |

`init_db()` membaca `schema.sql` dan `seed.sql` relatif terhadap `SRC_DIR` (`src/`). **Kedua berkas
itu wajib tetap di `src/`.**

## Lima tabel

`accounts` · `categories` · `transactions` · `analyses` · `savings_goals`
(`src/schema.sql:13, 26, 52, 101, 119`)

### `accounts` — tempat uang berada (`schema.sql:13-21`)

| kolom | tipe | catatan |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | bukan uuid |
| `name` | TEXT NOT NULL UNIQUE | "BRI", "Tunai" |
| `kind` | TEXT NOT NULL | CHECK: `bank` \| `cash` \| `ewallet` \| `savings` \| `investment` |
| `opening_balance` | INTEGER NOT NULL DEFAULT 0 | rupiah penuh |
| `is_active` | INTEGER NOT NULL DEFAULT 1 | CHECK `IN (0,1)`; nonaktif **tidak** menghapus saldo dari total |
| `created_at` | TEXT NOT NULL | `datetime('now','localtime')` |

Alasan `opening_balance` ada: pencatatan mulai di tengah jalan, jadi saldo dihitung dari titik
awal yang jujur, bukan dari nol.

**Akun tidak di-seed.** `src/seed.sql:33-39` sengaja kosong untuk akun — akun bawaan yang muncul
kembali tiap restart pernah jadi bug nyata. Tambah akun lewat `POST /api/accounts`
(`src/server.py:1207`) atau `db.create_account()`.

### `categories` — jenis transaksi, BUKAN arah (`schema.sql:26-33`)

| kolom | tipe | catatan |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `name` | TEXT NOT NULL | "Makan", "Gaji" |
| `direction` | TEXT NOT NULL | CHECK: `in` \| `out` |
| `is_system` | INTEGER NOT NULL DEFAULT 1 | 1 = bawaan |
| `sort_order` | INTEGER NOT NULL DEFAULT 0 | |
| — | UNIQUE (`name`,`direction`) | "Lainnya" ada dua: satu `in`, satu `out` |

11 kategori bawaan di `src/seed.sql:19-30` (8 `out`, 3 `in`).

### `transactions` — satu baris = satu kejadian uang (`schema.sql:52-86`)

| kolom | tipe | catatan |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `occurred_on` | TEXT NOT NULL | `'YYYY-MM-DD'` — tanggal kejadian, bukan tanggal input |
| `direction` | TEXT NOT NULL | CHECK: `in` \| `out` \| `transfer` |
| `amount` | INTEGER NOT NULL CHECK (`amount > 0`) | **selalu positif**; arah di `direction` |
| `account_id` | INTEGER NOT NULL → `accounts(id)` | |
| `to_account_id` | INTEGER → `accounts(id)` | hanya `transfer` |
| `category_id` | INTEGER → `categories(id)` | null untuk `transfer` |
| `note` | TEXT | opsional |
| `flow_type` | TEXT NOT NULL DEFAULT `'expense'` | CHECK: `expense` \| `income` \| `receivable` \| `debt_payment` \| `transfer` |
| `source` | TEXT NOT NULL DEFAULT `'manual'` | CHECK: `manual` \| `statement` |
| `created_at` | TEXT NOT NULL | waktu input |

Dua CHECK silang yang tidak boleh dilonggarkan:

1. **`direction` ↔ kolom** (`schema.sql:70-76`): `transfer` wajib `to_account_id IS NOT NULL`,
   `category_id IS NULL`, dan `to_account_id <> account_id`. `in`/`out` wajib `to_account_id IS NULL`
   dan `category_id IS NOT NULL`.
2. **`flow_type` ↔ `direction`** (`schema.sql:81-85`): `income` hanya boleh `in`; `transfer` hanya
   boleh `transfer`; `expense`/`receivable`/`debt_payment` hanya boleh `out`. Ini mencegah
   `income` tersimpan sebagai pengeluaran — laporan tetap terlihat rapi tapi angkanya terbalik.

#### Arti `flow_type` (`schema.sql:40-47`)

| nilai | arti | arah |
|---|---|---|
| `expense` | konsumsi / uang hilang (termasuk bantuan yang tidak kembali) | `out` |
| `income` | uang masuk | `in` |
| `receivable` | talangan, diharapkan kembali (topup project) | `out` |
| `debt_payment` | melunasi utang lama; **bukan** konsumsi baru | `out` |
| `transfer` | pindah antar akun sendiri; tidak mengubah kekayaan | `transfer` |

Kenapa kolom ini ada: Oktober 2026 uang keluar **Rp 2.100.000** tapi konsumsi sebenarnya hanya
**Rp 284.000** — beda ~7-8x. Tanpa `flow_type`, laporan menyesatkan.

`source = 'statement'` dipakai impor rekening koran; untuk baris itu `created_at` adalah waktu
impor, bukan waktu kejadian.

Indeks: `idx_tx_occurred`, `idx_tx_account`, `idx_tx_to_account`, `idx_tx_direction`,
`idx_tx_flow_type`, `idx_tx_source` (`schema.sql:88-93`).

### `analyses` — narasi analisa bulanan (`schema.sql:101-110`)

| kolom | tipe |
|---|---|
| `id` | INTEGER PK AUTOINCREMENT |
| `month` | TEXT NOT NULL UNIQUE (`'YYYY-MM'`) |
| `dibuat_pada` | TEXT NOT NULL |
| `tx_terakhir` | TEXT |
| `narasi` | TEXT |
| `snapshot` | TEXT |
| `model` | TEXT |
| `catatan` | TEXT |

Angka yang ditampilkan ke Deny **selalu dihitung ulang** dari transaksi; tabel ini menyimpan
narasinya saja. Asal-usul: `src/migrations/006_analyses.sql`.

### `savings_goals` — target tabungan (`schema.sql:119-127`)

| kolom | tipe | catatan |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `name` | TEXT NOT NULL | |
| `target_amount` | INTEGER NOT NULL CHECK (`> 0`) | |
| `account_id` | INTEGER NOT NULL → `accounts(id)` | satu target per akun |
| `target_date` | TEXT | opsional |
| `is_archived` | INTEGER NOT NULL DEFAULT 0 | arsip, bukan hapus |
| `created_at` | TEXT NOT NULL | |

Progres **tidak disimpan** — dihitung dari saldo akun lewat `v_savings_progress`. Kalau disimpan,
koreksi transaksi membuatnya basi tanpa ada yang tahu. Rute: `GET/POST/DELETE /api/savings`
(`src/server.py:1165, 1211, 1252`). Asal-usul: `src/migrations/007_savings_goal.sql`.

## Empat view

`schema.sql:141` `v_account_balances` · `:170` `v_monthly_flow` · `:217` `v_net_worth` ·
`:239` `v_savings_progress`

### `v_account_balances` — saldo tiap akun (`schema.sql:141-158`)

```
saldo(account) = opening_balance
  + sum(amount) where direction='in'  and account_id = account
  - sum(amount) where direction='out' and account_id = account
  - sum(amount) where direction='transfer' and account_id = account      -- keluar
  + sum(amount) where direction='transfer' and to_account_id = account   -- masuk
```

Kolom: `id`, `name`, `kind`, `opening_balance`, `is_active`, `balance`. Semua `COALESCE` ke 0.

### `v_monthly_flow` — per bulan (`schema.sql:170-199`)

| kolom | isi |
|---|---|
| `month` | `substr(occurred_on,1,7)` |
| `total_in` | **semua** uang masuk |
| `total_out` | **semua** uang keluar — **bukan** pengeluaran pribadi |
| `expense_real` | `out` + `flow_type='expense'` → konsumsi sebenarnya |
| `receivable_out` | `out` + `receivable` |
| `debt_payment_out` | `out` + `debt_payment` |
| `net` | `in` − `out`, arus kas apa adanya |
| `net_real` | `in` − `expense` saja → perubahan kekayaan sebenarnya (talangan & pelunasan utang netral) |
| `tx_count`, `in_count`, `out_count`, `transfer_count` | jumlah transaksi |

`transfer` tidak dihitung masuk/keluar — hanya berpindah, bukan berubah. Jumlah transaksi ikut
ditampilkan supaya Deny tahu kalau datanya bolong.

**`total_out` vs `expense_real` jangan tertukar.** Aturan pemakaiannya ada di `docs/CONTRACT.md`
§2; ringkasnya: kartu beranda "Pengeluaran" = `total_out`, grafik tren / konsumsi per kategori /
analisa bulanan = `expense_real` dengan label "konsumsi".

### `v_net_worth` — total kekayaan (`schema.sql:217-231`)

| kolom | isi |
|---|---|
| `net_worth` | `SUM(balance)` **semua** akun |
| `liquid` | `SUM(balance)` untuk `kind IN ('bank','cash','ewallet')` |
| `non_liquid` | `SUM(balance)` untuk `kind IN ('savings','investment')` |
| `account_count` | akun aktif yang **benar-benar dipakai** (`opening_balance <> 0` atau punya ≥1 transaksi) |
| `account_count_all` | semua akun aktif |
| `balance_inactive` | `SUM(balance)` akun nonaktif |

Akun tabungan & investasi ikut dihitung: itu tetap miliknya, yang membedakan hanya likuiditas.
**Akun `is_active = 0` juga ikut dihitung** (`schema.sql:211-215`) — menonaktifkan akun hanya
menyembunyikannya dari daftar, uangnya tidak lenyap. Kalau baris nonaktif dikecualikan,
menonaktifkan akun akan menghapus saldonya dari total kekayaan tanpa memunculkan error apa pun.

### `v_savings_progress` — progres target tabungan (`schema.sql:239-262`)

Kolom: `id`, `name`, `target_amount`, `target_date`, `account_id`, `account_name`, `account_kind`,
`terkumpul` (= saldo akun), `sisa`, `persen`, `status`, `is_archived`, `created_at`.

`status`: `belum_mulai` (saldo ≤ 0) · `tercapai` (saldo ≥ target) · `berjalan` (selain itu).

## Migrasi

`src/migrations/` menyimpan jejak perubahan skema setelah versi pertama — **jangan diedit**:
`002_flow_type`, `003_account_count_and_source`, `004_net_worth_akun_nonaktif`,
`005_net_worth_coalesce`, `006_analyses`, `007_savings_goal`.
`schema.sql` sudah memuat hasil akhir semuanya; DB baru tidak perlu menjalankan migrasi.

## Pertanyaan yang belum diputuskan

- **Mata uang:** IDR saja. Kalau nanti ada USD, `accounts` perlu kolom `currency` dan
  `v_net_worth` perlu kurs. Belum diperlukan sekarang.
- **Multi-user:** sekarang single-user. Kalau nanti keluarga ikut, skema harus ditambah
  `user_id` + RLS (atau tabel `households`) lagi. Tidak dikerjakan sampai diminta.
- **Kategori vs tag:** kategori tunggal per transaksi cukup. Belanja campuran akan butuh split
  atau tag — tunda sampai Deny benar-benar menemui masalahnya.
