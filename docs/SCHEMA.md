# Skema data — finance (rancangan, belum diterapkan)

Supabase project: **baru, terpisah dari Rin Studio** (dibuat Deny di dashboard).
Semua tabel pakai RLS. Karena ini single-user (Deny saja), policy-nya sederhana:
hanya `auth.uid()` yang cocok boleh baca/tulis barisnya sendiri.

## Tabel

### `accounts`
Tempat uang berada. Contoh: BCA, Mandiri, Tunai, OVO/GoPay, Tabungan.

| kolom | tipe | catatan |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid | → `auth.users`, pemilik baris |
| `name` | text | "BCA", "Tunai" |
| `kind` | text | `bank` \| `cash` \| `ewallet` \| `savings` \| `investment` |
| `opening_balance` | numeric(16,2) | saldo awal saat mulai mencatat |
| `is_active` | boolean | akun lama bisa dinonaktifkan tanpa dihapus |
| `created_at` | timestamptz | |

Alasan `opening_balance` ada: sistem mulai mencatat di tengah jalan, jadi saldo harus
bisa dihitung dari titik awal yang jujur, bukan dari nol.

### `categories`
Pengeluaran dan pemasukan punya kategori. Gelombang 1 pakai daftar bawaan
(`is_system = true`); kategori kustom masuk gelombang berikutnya.

| kolom | tipe | catatan |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid | |
| `name` | text | "Makan", "Transport", "Gaji" |
| `direction` | text | `in` \| `out` |
| `is_system` | boolean | true = bawaan, tidak bisa dihapus |
| `sort_order` | int | urutan tampil |

### `transactions`
Inti sistem. **Satu baris = satu kejadian uang.**

| kolom | tipe | catatan |
|---|---|---|
| `id` | uuid pk | |
| `user_id` | uuid | |
| `occurred_on` | date | tanggal transaksi (bukan tanggal input) |
| `direction` | text | `in` \| `out` \| `transfer` |
| `amount` | numeric(16,2) | **selalu positif**; arah ditentukan `direction` |
| `account_id` | uuid | → `accounts` |
| `to_account_id` | uuid null | hanya untuk `transfer` (tujuan) |
| `category_id` | uuid null | null untuk `transfer` |
| `note` | text null | |
| `created_at` | timestamptz | waktu input; beda dari `occurred_on` |

Catatan penting:
- `amount` selalu positif. Arah disimpan di `direction`, bukan di tanda angka. Ini mencegah
  bug klasik "pengeluaran minus" yang bikin total salah saat dijumlahkan.
- `occurred_on` dipisah dari `created_at`: Deny bisa memasukkan transaksi kemarin hari ini,
  dan laporan harus mengikuti tanggal kejadian, bukan tanggal input.
- `transfer` punya `to_account_id` dan tidak punya kategori — pindah uang bukan pemasukan
  maupun pengeluaran. Kalau ini salah dimodelkan, total kekayaan akan terlihat naik/turun
  padahal cuma berpindah. Ini alasan `transfer` dipisah sebagai arah tersendiri.

### `savings_goals` (gelombang 2, disiapkan sekarang)
Target tabungan dengan progres.

| kolom | tipe |
|---|---|
| `id`, `user_id` | uuid |
| `name` | text |
| `target_amount` | numeric(16,2) |
| `target_date` | date null |
| `account_id` | uuid (akun tabungan terkait) |
| `is_archived` | boolean |

## View analisa

### `v_account_balances`
Saldo tiap akun = `opening_balance` + semua transaksi yang menyentuhnya.

```
saldo(account) = opening_balance
  + sum(amount) where direction='in'  and account_id = account
  - sum(amount) where direction='out' and account_id = account
  - sum(amount) where direction='transfer' and account_id = account      -- keluar
  + sum(amount) where direction='transfer' and to_account_id = account   -- masuk
```

### `v_monthly_flow`
Per bulan: total masuk, total keluar, selisih, jumlah transaksi.
**Jumlah transaksi ikut ditampilkan** supaya Deny tahu kalau datanya bolong.

### `v_net_worth`
`sum(saldo semua akun aktif)` — inilah "total keuangan saat ini" di panel analisa.
**Akun tabungan dan investasi ikut dihitung**, karena itu tetap miliknya; yang membedakan
hanya likuiditas, dan itu ditampilkan terpisah, bukan dikeluarkan.

## Pertanyaan yang belum diputuskan

- **Mata uang:** saat ini IDR saja. Kalau nanti ada USD, `accounts` perlu kolom `currency`
  dan `v_net_worth` perlu kurs. Belum diperlukan sekarang.
- **Multi-user:** sekarang single-user. Kalau nanti istri/keluarga ikut, `user_id` sudah ada
  tapi perlu tabel `households` dan policy baru. Tidak dikerjakan sampai diminta.
- **Kategori vs tag:** kategori tunggal per transaksi cukup untuk gelombang 1. Belanja
  campuran (mis. belanja bulanan yang isinya makan + sabun) akan butuh split atau tag — tunda
  sampai Deny benar-benar menemui masalahnya.
