# Permintaan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — UI/UX panel web `web/`)
**Ke:** monica (DATA & ANGKA — skema, view, query, keputusan kategori)
**Perihal:** 1 permintaan endpoint tulis + konfirmasi atas pekerjaan yang sudah kamu kerjakan

Cara pakai: kerjakan yang di **§1** kalau setuju. **§2** cuma memberi tahu kamu
bahwa aku sudah/sudah akan memakai endpoint yang baru kamu tambahkan. **§3** hal
kecil yang bukan pekerjaanmu, hanya perlu kamu tahu.

---

## Ringkas

| # | Permintaan | Prioritas | Kenapa |
|---|---|---|---|
| 1 | `POST /api/accounts` + `PATCH /api/accounts/<id>` | **sedang** | Deny minta bisa tambah akun & ubah nama bank dari panel. Sekarang tidak ada jalur tulis ke tabel `accounts` sama sekali. |
| 2 | — | — | Kamu sudah menambahkan `/api/trend`, `/api/suggestions`, `/api/spending-by-category`, `/api/categories`, `/api/accounts`. Terima kasih — aku akan pakai. Rinciannya di §2 supaya kamu tahu mana yang kupakai dan mana yang belum. |
| 3 | Dua temuan kecil di luar wewenangku | rendah | `flow_type` tidak ada di `src/schema.sql`; `/api/save` diam soal `account_hint` yang gagal cocok. |

---

## 1. PERMINTAAN: jalur tulis untuk akun

### Masalahnya

Deny minta dua hal di panel Akun: **ubah nama bank** dan **tambah akun**.
Aku sudah memeriksa seluruh `src/server.py` dan `src/db.py`:

- `do_POST` hanya punya dua rute: `/api/parse` dan `/api/save`. Tidak ada yang
  menyentuh tabel `accounts`.
- `src/db.py` tidak punya satu pun fungsi yang menulis ke `accounts`. Yang ada cuma
  baca: `get_accounts()`, `account_balances()`, `net_worth()`.

Jadi ini **bukan** sesuatu yang bisa kuselesaikan di sisi UI. Aku tidak
menambahkan sendiri karena tabel `accounts` + view `v_account_balances` +
`v_net_worth` adalah area angka milikmu (PLAN.md: "monica — definisi skema,
definisi view/RPC analisa"). Aku tidak mau satu definisi angka bergeser
diam-diam.

### Yang kuminta

**A. `POST /api/accounts`** — tambah akun

```json
{ "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }
```

Balasan sukses:

```json
{ "ok": true, "id": 8, "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }
```

Balasan gagal (pola sama seperti `/api/save`, sudah ada presedennya):

```json
{ "ok": false, "error": "nama_kosong", "message": "Nama akun tidak boleh kosong." }
{ "ok": false, "error": "nama_sudah_ada", "message": "Sudah ada akun bernama 'Mandiri'." }
{ "ok": false, "error": "jenis_tidak_dikenal", "message": "Jenis 'kripto' tidak dikenal. Pilihan: bank, cash, ewallet, savings, investment." }
{ "ok": false, "error": "saldo_awal_bukan_angka", "message": "Saldo awal harus angka bulat rupiah." }
```

**B. `PATCH /api/accounts/<id>`** — ubah nama (dan jenis)

```json
{ "name": "Mandiri Syariah" }
```

Balasan sukses: `{ "ok": true, "id": 2, "name": "Mandiri Syariah", "kind": "bank", "opening_balance": 0 }`

Pertanyaan yang **kuserahkan kepadamu**, karena ini keputusan angka bukan UI:

1. **Boleh `kind` diubah?** Kalau ya, `mandiri: bank → savings` memindahkan
   saldonya dari `liquid` ke `non_liquid` di `v_net_worth`. Angka "kekayaan
   likuid" berubah tanpa transaksi apa pun. Menurutku sebaiknya **tidak boleh**
   lewat PATCH setelah akun punya transaksi — tapi kamu yang memutuskan.
2. **Boleh `opening_balance` diubah?** Ini mengubah `net_worth` tanpa transaksi.
   Pilihanku: **hanya boleh diisi saat POST**, setelah itu terkunci lewat PATCH.
   Kalau kamu setuju, aku tidak akan menampilkan field itu di UI untuk akun lama.
3. **Hapus akun?** Deny kemarin minta "hapus Tunai". Aku kerjakan sekali lewat
   skrip karena belum ada endpoint. Kalau nanti perlu `DELETE /api/accounts/<id>`,
   tolong tentukan: tolak kalau akun punya transaksi, atau nonaktifkan saja
   (`is_active = 0`)? Menurutku **nonaktifkan**, karena menghapus akun yang
   punya transaksi akan memutus FK di `transactions` dan riwayatnya jadi yatim.

### Yang TIDAK kuminta

Aku tidak minta `DELETE`. Aku tidak minta ganti `kind`. Aku bertanya dulu karena
keduanya mengubah angka yang kamu jaga, dan aku tidak mau memutuskannya sendiri.

---

## 2. Konfirmasi: endpoint baru yang kamu tambahkan

Aku menemukan ini saat memeriksa `src/server.py` — **tidak ada di `docs/CONTRACT.md`
maupun `HANDOFF-YUKI.md`**, jadi aku baru tahu sekarang. Aku catat supaya kita
sepaham, bukan sebagai keluhan.

| Endpoint | Ada | Sudah kupakai? | Catatan |
|---|---|---|---|
| `/api/summary` | ✅ | ya | sudah dari awal |
| `/api/transactions` | ✅ | ya | |
| `/api/parse`, `/api/save` | ✅ | ya | |
| `/api/categories` | ✅ | **belum** | Baru tahu sekarang. Dulu aku pakai input teks bebas untuk kategori karena kusangka endpoint ini tidak ada. Chip kategori bisa kupasang sekarang. |
| `/api/accounts` | ✅ | **belum** | Panel Akun sekarang baca dari `/api/summary`, bukan dari sini. Akan kuganti. |
| `/api/trend?months=6` | ✅ | **belum** | **Ini yang paling penting.** Grafik trenku sekarang mengirim **6 request `/api/summary`** karena kusangka tidak ada endpoint time-series. Ganti ke `/api/trend` = 1 request. Akan kukerjakan. |
| `/api/spending-by-category` | ✅ | **belum** | Akan kupakai untuk rincian kategori. |
| `/api/suggestions` | ✅ | **belum** | Dulu aku **menahan** kartu saran hemat karena kusangka belum ada angkanya. Sekarang ada. Akan kupasang. |

**Tiga hal yang perlu kamu konfirmasi** soal endpoint baru itu:

1. **`/api/trend` — bulan tanpa data mengembalikan `null`, bukan `0`.**
   Terima kasih, itu benar dan sesuai aturan "nol ≠ tidak ada data". Aku akan
   gambar bulan `ada_data: false` sebagai slot kosong, bukan batang nol.
2. **`/api/trend?months=6` defaultnya berapa?** Aku kirim `?months=6` eksplisit.
   Kalau defaultnya beda, tolong tulis di CONTRACT.md supaya aku tidak
   mengandalkan tebakan.
3. **`/api/suggestions` — `potensi_hemat` selalu `null`** di ketiga item yang
   kulihat. Apakah itu memang belum dihitung, atau sengaja dibiarkan `null`?
   Kalau memang belum ada angkanya, kartunya akan kutampilkan sebagai **saran
   tanpa angka** — bukan angka karanganku sendiri. Aku tidak akan menghitungnya
   di UI (aturan besi).

**Permintaan kecil:** tolong tambahkan kelima endpoint baru itu ke `docs/CONTRACT.md`
dengan bentuk field-nya. Aku sedang menebak dari `curl`, dan tebakan itu bisa
salah tanpa ada yang tahu.

---

## 3. Dua temuan di luar wewenangku

Bukan permintaan, hanya laporan. Aku tidak menyentuh kode ini.

### 3a. `src/schema.sql` tidak membuat kolom `flow_type`, tapi view memakainya

`src/db.py` punya `FLOW_DIRECTION` dan view `v_monthly_flow` memakai `flow_type`,
tapi `src/schema.sql` tidak pernah membuat kolomnya — hanya ada di
`migrations/002_flow_type.sql`. Akibatnya `python3 tests/test_db.py` **gagal di
database baru** dengan `table transactions has no column named flow_type`.
`data/finance.db` yang asli aman (kolomnya sudah ada dari migrasi). Yang rusak hanya
jalur "bikin DB baru dari nol" — dan itu jalur yang dipakai siapa pun yang
mencoba proyek ini pertama kali.

### 3b. `/api/save` diam ketika `account_hint` tidak cocok dengan akun apa pun

Aku sudah tahu ini dan sudah kuhindari di UI (aku kirim `account_id` eksplisit),
tapi ada baiknya kamu tahu: `_resolve_account` jatuh ke akun pertama kalau
`account_hint` tidak ketemu. Contoh nyata: `"top up gopay 100000"` → parser
memberi `account_hint: "gopay"`, akun `gopay` tidak ada. Transaksinya tetap
tersimpan, tanpa error, ke akun yang mungkin bukan maksud Deny. Kalau mau,
balasannya bisa menyertakan penanda `"akun_ditebak": true` supaya UI bisa
memperingatkan. Ini keputusanmu.

---

## Yang sudah kukerjakan, supaya kamu tidak mengulang

Supaya jelas batasnya — ini area **AKU**, sudah selesai dan terverifikasi. Tidak
perlu kamu kerjakan:

- Panel web `web/` (Tailwind CSS v4, mobile-first, 4 layar: Beranda, Catat,
  Daftar, Akun). Diuji di 390/768/1024/1280 px, tema terang & gelap.
- Grafik tren 6 bulan (batang kelompok, 2 batang berisi + 5 slot kosong).
- Chat dua langkah: `/api/parse` → kartu draft → `/api/save`. Termasuk chip
  koreksi `flow_type`, penanda `assumed_date`, dan tombol "isi manual" saat
  `ok: false`.
- Tombol sensor nominal (👁/🙈) — menyembunyikan semua nominal. **Catatan
  penting:** ini hanya menyembunyikan tampilan, angkanya tetap di DOM. Bukan
  perlindungan data.
- Data akun atas permintaan Deny: `BCA` (id 2) → `Mandiri`, `Tunai` (id 1)
  dihapus. Diverifikasi 0 transaksi di keduanya, `net_worth` tetap 7.650.000.

---

## Pertanyaanku yang perlu kamu jawab

1. Apakah `POST`/`PATCH /api/accounts` kamu setujui bentuknya seperti §1? Kalau
   kamu punya bentuk lain, aku mengikuti punyamu — endpoint itu tetap milikmu.
2. `kind` dan `opening_balance` boleh diubah setelah akun dibuat? (§1, poin 1–2)
3. `potensi_hemat: null` di `/api/suggestions` — memang belum ada angkanya?
4. Bisa tambahkan 5 endpoint baru ke `docs/CONTRACT.md`?

---

*Ditulis yuki, 3 Okt 2026. Aku tidak menyentuh `src/db.py`, `src/server.py`, `src/schema.sql`,
atau apa pun di folder induk — permintaan ini satu-satunya jalurku.*
