# Kontrak data — finance

Untuk **yuki** (frontend) dan **hana** (backend, kalau diperlukan).
Ditulis **monica** 1 Okt 2026. Ini bentuk data yang **sudah diverifikasi** terhadap
database nyata — bukan usulan. Kalau kamu butuh field tambahan, minta ke monica;
jangan hitung sendiri di UI.

**Aturan besi:** UI tidak pernah menghitung angka keuangan. Semua angka datang dari
`src/db.py`. Kalau UI menjumlahkan sendiri, cepat atau lambat UI dan laporan akan
berbeda dan tidak ada yang tahu mana yang benar.

---

## 1. Endpoint yang dibutuhkan

Server lokal (Python, karena parser-nya Python). Tujuh endpoint GET + empat POST/PATCH:

| Method | Path | Fungsi |
|---|---|---|
| `GET` | `/api/summary?month=YYYY-MM` | angka untuk kartu statistik |
| `GET` | `/api/transactions?month=&limit=&direction=` | daftar transaksi |
| `GET` | `/api/categories?direction=` | kategori untuk chip |
| `GET` | `/api/accounts?all=1` | akun + saldo |
| `GET` | `/api/trend?months=6` | tren N bulan (default 6, maks 24) |
| `GET` | `/api/spending-by-category?month=&direction=` | pengeluaran per kategori |
| `GET` | `/api/suggestions?month=` | saran hemat + asumsinya |
| `POST` | `/api/parse` | **parse saja** — kirim kalimat, terima draft, BELUM disimpan |
| `POST` | `/api/save` | simpan draft setelah Deny menekan "Simpan" |
| `POST` | `/api/accounts` | tambah akun |
| `PATCH` | `/api/accounts/<id>` | ubah nama / aktif-nonaktifkan akun |
| `PATCH` | `/api/transactions/<id>` | **ubah** transaksi (nominal, kategori, flow_type, tanggal, catatan) |
| `DELETE` | `/api/transactions/<id>` | **hapus** transaksi (keras, dengan jejak pemulihan) |

Pemisahan `/api/parse` dan `/api/save` bukan pilihan gaya — itu inti aturan dari
PLAN.md: AI tidak pernah menulis langsung ke database. Dua langkah, konfirmasi di
tengah.

---

## 2. `GET /api/summary`

Query param: `?month=2026-10` (opsional, default bulan berjalan).

```json
{
  "month": "2026-10",
  "ada_data": true,
  "tx_count": 15,

  "net_worth": {
    "total": 5922801,
    "liquid": 5922801,
    "non_liquid": 0,
    "account_count": 1
  },

  "flow": {
    "total_in": 8096600,
    "total_out": 2250196,
    "expense_real": 284000,
    "receivable_out": 285458,
    "debt_payment_out": 1680738,
    "net": 5846404,
    "net_real": 7812600
  },

  "accounts": [
    { "id": 1, "name": "BRI", "kind": "bank", "balance": 5922801, "is_active": 1 }
  ]
}
```

**Yang wajib kamu perhatikan:**

- **`ada_data: false`** artinya bulan itu belum ada transaksi sama sekali. Jangan
  tampilkan `0` — tampilkan "belum ada data bulan ini". Nol dan "tidak ada data"
  adalah dua hal berbeda; menampilkan nol membuat Deny mengira pengeluarannya nol.
- **`expense_real` vs `total_out`** — jangan tertukar. `total_out` semua uang yang
  keluar; `expense_real` yang benar-benar konsumsi. Di Oktober bedanya 8x lipat.
  **Kartu "Pengeluaran" di UI harus pakai `expense_real`.**
- **`net_real` vs `net`** — `net` selisih arus kas apa adanya, `net_real` perubahan
  kekayaan sebenarnya. Untuk panel analisa pakai `net_real`.
- Semua angka **integer rupiah penuh**, tanpa titik atau koma. Format `Rp 1.100.000`
  dilakukan di UI, bukan di sini.

---

## 3. `GET /api/transactions`

Query param: `?month=2026-10` · `?limit=50` · `?direction=out`

```json
{
  "month": "2026-10",
  "count": 15,
  "items": [
    {
      "id": 30,
      "occurred_on": "2026-10-02",
      "direction": "in",
      "flow_type": "income",
      "amount": 3870600,
      "account_name": "BRI",
      "to_account_name": null,
      "category_name": "Bonus",
      "note": "Tunjangan kinerja bulanan (flat)",
      "created_at": "2026-10-01 15:22:10"
    },
    {
      "id": 15,
      "occurred_on": "2026-10-01",
      "direction": "out",
      "flow_type": "debt_payment",
      "amount": 1378666,
      "account_name": "BRI",
      "to_account_name": null,
      "category_name": "Tagihan",
      "note": "Pembayaran VirtualAccount ke PinjamanOnline - pelunasan utang",
      "created_at": "2026-10-01 15:22:10"
    }
  ]
}
```

Diurutkan **terbaru dulu** (`occurred_on` DESC, lalu `id` DESC).

**Label yang harus ditampilkan per `flow_type`** — ini yang membuat laporanmu jujur:

| `flow_type` | Label UI | Warna saran |
|---|---|---|
| `expense` | Pengeluaran | merah |
| `income` | Pemasukan | hijau |
| `receivable` | Talangan (piutang) | biru |
| `debt_payment` | Bayar utang | oranye |
| `transfer` | Pindah akun | abu, netral |

Kalau semuanya ditampilkan merah sebagai "pengeluaran", panelnya menyesatkan.

---

## 4. `POST /api/parse`

Body:
```json
{ "text": "makan malam 45000 sama parkir 5rb" }
```

Balasan sukses:
```json
{
  "ok": true,
  "draft": {
    "transactions": [
      {
        "direction": "out",
        "flow_type": "expense",
        "amount": 45000,
        "category": "Makan",
        "account_hint": null,
        "to_account_hint": null,
        "note": "makan malam",
        "occurred_on": "2026-10-01",
        "assumed_date": false
      },
      {
        "direction": "out",
        "flow_type": "expense",
        "amount": 5000,
        "category": "Transport",
        "account_hint": null,
        "to_account_hint": null,
        "note": "parkir",
        "occurred_on": "2026-10-01",
        "assumed_date": false
      }
    ],
    "question": null
  }
}
```

Balasan kalau bukan transaksi:
```json
{ "ok": true, "draft": { "transactions": [], "question": "Maksudmu mencatat apa?" } }
```

Balasan gagal (model mati / JSON rusak):
```json
{ "ok": false, "error": "model_tidak_membalas", "message": "Model tidak membalas. Coba lagi atau isi manual." }
```

**Yang wajib kamu tangani:**

- **`assumed_date: true`** → tampilkan penanda *"tanggal dianggap hari ini"*. Deny
  harus bisa mengubahnya sebelum simpan. Jangan sembunyikan.
- **`transactions` kosong + `question` terisi** → tampilkan sebagai balasan chat biasa,
  bukan kartu draft.
- **`ok: false`** → tampilkan pesan gagal **dan tombol "isi manual"**. PLAN.md: fitur
  chat tidak boleh memblokir pencatatan kalau provider bermasalah.
- **Lebih dari satu transaksi** → tampilkan sebagai daftar yang bisa dicek satu-satu,
  bukan digabung.

---

## 5. `POST /api/save`

Body: daftar transaksi yang sudah dikonfirmasi Deny.
```json
{
  "transactions": [
    { "occurred_on": "2026-10-01", "direction": "out", "flow_type": "expense",
      "amount": 45000, "account_hint": "BRI", "category": "Makan",
      "note": "makan malam" }
  ]
}
```

Balasan sukses:
```json
{ "ok": true, "saved_ids": [31], "count": 1 }
```

Balasan gagal:
```json
{ "ok": false, "error": "kategori_tidak_dikenal",
  "message": "Kategori 'Makanan' tidak ada untuk arah out." }
```

**Semua-atau-tidak-sama-sekali.** Kalau satu baris gagal, tidak ada yang tersimpan.
Ini sudah ditegakkan di `src/db.py` dan sudah diuji — jangan tambahkan logika simpan
sendiri di UI.

---

## 6. `flow_type` — aturan yang harus dipatuhi

| `flow_type` | `direction` yang sah | Arti |
|---|---|---|
| `expense` | `out` | uang hilang (termasuk bantuan yang tidak kembali) |
| `receivable` | `out` | talangan, diharapkan kembali |
| `debt_payment` | `out` | melunasi utang lama, bukan konsumsi baru |
| `transfer` | `transfer` | pindah antar akun sendiri |
| `income` | `in` | uang masuk |

Pasangan di luar tabel ini **ditolak `src/db.py`**. Kalau UI mengirim `income` dengan
`direction: out`, request gagal — itu memang disengaja.

**Cara menentukan `flow_type` dari chat:** parser yang memutuskan, dan Deny yang
mengoreksi di layar konfirmasi. Aturan awal: ada kata "utang"/"cicilan"/"lunas" →
`debt_payment`; "topup project"/"talangan" → `receivable`; "transfer"/"pindah" →
`transfer`; sisanya `expense`.

---

## 7. Format tampilan

- Uang: `Rp 1.100.000` — titik pemisah ribuan, **selalu** diformat. Jangan pernah
  tampilkan `1250000` mentah.
- Tanggal di daftar: `1 Okt 2026`. Di header kelompok harian: `Hari ini`, `Kemarin`,
  lalu tanggal.
- Angka negatif: tidak ada. `amount` selalu positif; arah ditentukan `direction`.

---

## 8. Yang belum ada (jangan diasumsikan ada)

- **Pelacakan pelunasan piutang.** Piutang studio-contoh tercatat keluar,
  tapi belum ada mekanisme menandai "sudah dibayar". Kalau nanti dibayar, masuknya
  sebagai `income` biasa.
- **Saldo utang.** Pelunasan tercatat, tapi total utang berjalan tidak.
- **Target tabungan, budget per kategori, ekspor PDF.** Gelombang 2.
- **`DELETE /api/accounts`** — sengaja tidak disediakan. Pakai `PATCH` dengan
  `{"is_active": 0}`, karena `DELETE` yang benar hari ini (akun kosong) bisa salah
  minggu depan (akun sudah terisi).

Kalau UI butuh salah satu dari ini, bilang ke monica — jangan bikin field sendiri.

---

## 9. Endpoint tambahan (3 Okt 2026)

Ditambahkan setelah `docs/CONTRACT.md` versi pertama. Semuanya **sudah terverifikasi
terhadap data nyata**.

### `GET /api/categories?direction=out|in`

```json
{ "count": 11, "items": [
  { "id": 1, "name": "Makan", "direction": "out", "is_system": 1, "sort_order": 10 }
]}
```

Tanpa `direction`: keduanya dikembalikan.

### `GET /api/accounts?all=1`

```json
{ "count": 3, "items": [
  { "id": 7, "name": "BRI", "kind": "bank", "opening_balance": 76397,
    "is_active": 1, "balance": 5904551 }
]}
```

Tanpa `all=1`: hanya akun aktif. `balance` sudah final — **jangan dihitung ulang
di UI.**

### `GET /api/trend?months=6`

Default **6**, maksimal 24. Urutan **lama → baru** (siap digambar kiri ke kanan).

```json
{ "months": 6, "items": [
  { "month": "2026-09", "ada_data": false, "total_in": null, "total_out": null,
    "expense_real": null, "net": null, "net_real": null, "tx_count": 0 },
  { "month": "2026-10", "ada_data": true, "total_in": 8096600, "total_out": 2250196,
    "expense_real": 301000, "net": 5846404, "net_real": 7795600, "tx_count": 18 }
]}
```

**Bulan tanpa data → `null`, bukan `0`.** Gambar sebagai slot kosong.

### `GET /api/spending-by-category?month=&direction=out`

```json
{ "month": "2026-10", "items": [
  { "category": "Tagihan", "total": 184000, "tx_count": 5 }
]}
```

**Hanya `flow_type = 'expense'`.** Talangan dan pelunasan utang tidak ikut —
kalau ikut, kategori "Tagihan" akan terlihat raksasa padahal isinya pelunasan
pinjaman.

### `GET /api/suggestions?month=`

```json
{ "month": "2026-10",
  "items": [
    { "jenis": "kenaikan_kategori", "kategori": "Makan", "potensi_hemat": 120000,
      "asumsi": "Makan naik dari Rp 300.000 (bulan lalu) ke Rp 420.000 bulan ini..." },
    { "jenis": "sering_kecil", "kategori": "Tagihan", "potensi_hemat": null,
      "asumsi": "..." },
    { "jenis": "talangan_project", "kategori": null, "potensi_hemat": null,
      "asumsi": "..." },
    { "jenis": "rasio_sisa", "kategori": null, "potensi_hemat": null, "asumsi": "..." }
  ],
  "catatan": "Semua saran menyebut asumsinya..." }
```

**`potensi_hemat` hanya terisi pada `kenaikan_kategori`** — dan itu hanya muncul
kalau bulan sebelumnya punya data sebagai pembanding. Selain itu `null`, dan itu
memang tidak ada angka tunggal yang jujur.

**`asumsi` WAJIB ditampilkan** (aturan `docs/UI-MOBILE.md`). Kalau tempatnya kurang,
perkecil — jangan dihapus.

### `POST /api/accounts`

```json
{ "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }
→ { "ok": true, "id": 8, "name": "Mandiri", "kind": "bank", "opening_balance": 1500000 }
```

`kind` harus salah satu: `bank`, `cash`, `ewallet`, `savings`, `investment`.

Gagal:
```json
{ "ok": false, "error": "nama_kosong",        "message": "Nama akun tidak boleh kosong." }
{ "ok": false, "error": "nama_sudah_ada",     "message": "sudah ada akun bernama 'BRI'" }
{ "ok": false, "error": "jenis_tidak_dikenal","message": "Jenis 'kripto' tidak dikenal. Pilihan: bank, cash, ewallet, savings, investment." }
{ "ok": false, "error": "saldo_awal_bukan_angka", "message": "Saldo awal harus angka bulat rupiah." }
```

Nama duplikat ditolak tanpa memandang huruf besar/kecil dan spasi tepi.

### `PATCH /api/accounts/<id>`

```json
{ "name": "Mandiri Syariah" }   → ubah nama
{ "is_active": 0 }              → nonaktifkan (hilang dari daftar, riwayat utuh)
{ "is_active": 1 }              → aktifkan lagi
```

**Ditolak:**

```json
{ "ok": false, "error": "field_terkunci",
  "message": "Kolom 'kind' dan 'opening_balance' tidak bisa diubah setelah akun dibuat — keduanya mengubah angka kekayaan tanpa transaksi. Perbaikannya lewat migrasi yang tercatat." }
{ "ok": false, "error": "akun_tidak_ada",     "message": "tidak ada akun dengan id 9999" }
{ "ok": false, "error": "tidak_ada_perubahan","message": "Tidak ada field yang bisa diubah. Kirim 'name' atau 'is_active'." }
```

**Kenapa `kind` dan `opening_balance` terkunci:** keduanya mengubah `v_net_worth`
tanpa satu pun transaksi. `opening_balance` lebih berbahaya lagi —
`v_account_balances` dihitung dari `opening_balance + semua transaksi`, jadi
mengubahnya akan menggeser **semua** saldo lama, termasuk bulan yang laporannya
sudah ditunjukkan ke Deny.

**Nonaktifkan ≠ uangnya hilang.** Akun nonaktif tetap dihitung di `net_worth`;
saldonya dipisah ke `balance_inactive` di `/api/summary`.

---

## 10. Perubahan `v_net_worth` (3 Okt 2026)

```json
"net_worth": { "total": 5904551, "liquid": 5904551, "non_liquid": 0,
               "account_count": 1, "account_count_all": 3, "balance_inactive": 0 }
```

| Field | Arti |
|---|---|
| `total` | jumlah saldo **semua** akun, termasuk yang nonaktif |
| `account_count` | akun aktif yang benar-benar dipakai (punya saldo/transaksi) |
| `account_count_all` | jumlah akun aktif (termasuk yang kosong) |
| `balance_inactive` | saldo yang ada di akun nonaktif |

**Bug yang diperbaiki:** sebelumnya `v_net_worth` memakai `WHERE is_active = 1`,
sehingga menonaktifkan akun akan **menghapus saldonya dari total kekayaan**
tanpa error apa pun. Sekarang seluruh akun dijumlahkan.

---

## 11. Akun tidak lagi ditebak (3 Okt 2026)

`_resolve_account` **gagal keras** kalau akun tidak bisa ditentukan — tidak lagi
jatuh ke akun mana pun.

```json
{ "ok": false, "error": "gagal_simpan",
  "message": "akun 'gopay' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" }
{ "ok": false, "error": "gagal_simpan",
  "message": "akun tidak disebutkan. Ada 3 akun aktif (BRI, Mandiri, Tabungan) — sebutkan salah satunya." }
```

Pengecualian: kalau hanya ada **satu** akun aktif, transaksi tanpa petunjuk
disimpan ke akun itu (tidak ada ambiguitas).

**Konsekuensi UI:** pastikan kartu draft selalu mengirim `account_id` sebelum
tombol simpan aktif. Kalau tidak, simpan akan gagal dengan pesan di atas —
lengkap dengan daftar akun yang ada, jadi Deny langsung tahu harus pilih apa.

---

## 12. Ubah & hapus transaksi (3 Okt 2026)

### `PATCH /api/transactions/<id>`

Field yang boleh dikirim (semua opsional — hanya yang dikirim yang berubah):

| Field | Catatan |
|---|---|
| `occurred_on` | `YYYY-MM-DD` |
| `amount` | integer rupiah, **harus > 0** |
| `flow_type` | `direction` **ikut menyesuaikan sendiri** |
| `category` | nama kategori, lewat `_resolve_category` |
| `account_id` / `account_hint` | lewat `_resolve_account` |
| `to_account_id` / `to_account_hint` | **hanya** kalau `flow_type` = `transfer` |
| `note` | teks |

**Terkunci:** `direction`, `id`, `created_at`, `source`.

```json
{ "ok": true, "id": 76, "occurred_on": "2026-10-03", "direction": "out",
  "flow_type": "receivable", "amount": 301250, "account_id": 7,
  "account_name": "BRI", "category_id": 5, "category_name": "Tagihan",
  "note": "Topup e-toll via BRI", "source": "manual",
  "to_account_id": null, "to_account_name": null }
```

Gagal:

```json
{ "ok": false, "error": "transaksi_tidak_ada",   "message": "tidak ada transaksi dengan id 9999" }
{ "ok": false, "error": "field_terkunci",        "message": "Kolom 'direction' tidak bisa diubah langsung — ubah 'flow_type', arahnya mengikuti." }
{ "ok": false, "error": "pasangan_tidak_sah",    "message": "flow_type 'hibah' tidak dikenal" }
{ "ok": false, "error": "amount_bukan_angka",    "message": "nominal harus lebih besar dari nol" }
{ "ok": false, "error": "kategori_tidak_dikenal","message": "..." }
{ "ok": false, "error": "akun_tidak_ditemukan",  "message": "akun 'gopay' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" }
{ "ok": false, "error": "tidak_ada_perubahan",   "message": "Tidak ada field yang dikirim." }
```

**Gagal = tidak ada yang berubah.** Sudah diuji: kirim `{"amount": 999,
"flow_type": "ngawur"}` → ditolak, dan nominalnya tetap seperti semula. UI boleh
menampilkan pesan error dan membiarkan form terbuka tanpa memuat ulang.

**`direction` sengaja terkunci.** Arah mengikuti `flow_type`, karena
`FLOW_DIRECTION` di `db.py` satu-satunya penentu pasangan arah/sifat. Kalau arah
bisa diubah sendiri, akan ada baris dengan `flow_type='income'` tapi
`direction='out'` dan tidak ada yang tahu.

**Ubah ke/dari `transfer`:** masuk ke `transfer` **wajib** menyertakan akun
tujuan. Keluar dari `transfer` **melepas** `to_account_id` otomatis — UI tidak
perlu mengirim apa pun, cukup `flow_type` yang baru.

### `DELETE /api/transactions/<id>`

**Hapus keras**, tapi barisnya dicatat lebih dulu ke `data/terhapus.log`.

```json
{ "ok": true, "id": 77, "dihapus": true, "pemulihan": "data/terhapus.log",
  "transaksi": { "id": 77, "amount": 300000, "note": "Dana masuk", ... } }
```

Gagal: `{ "ok": false, "error": "transaksi_tidak_ada", "message": "..." }`

Kenapa tidak hapus lunak (`deleted_at`): itu mewajibkan **ketiga view**
(`v_account_balances`, `v_monthly_flow`, `v_net_worth`) mengecualikan baris
terhapus. Satu kelalaian membuat angkanya tetap menghitung transaksi yang sudah
dibuang — lebih menyesatkan daripada tidak bisa menghapus sama sekali.

**UI:** konfirmasi dua langkah, sebutkan nama transaksi + nominalnya, dan pakai
kata **"dihapus"** (bukan "dibatalkan"), karena memang keras.

### `source` di `/api/transactions`

Nilainya `"manual"` atau `"statement"`.

- `manual` — Deny mencatatnya saat kejadian; `created_at` bermakna.
- `statement` — diimpor dari PDF bank; `created_at` cuma waktu skrip berjalan,
  **tidak bermakna**.

Kalau `source == 'statement'`, jangan tampilkan tanggal dicatat — 15 transaksi
impor dibuat dalam detik yang sama dan itu membingungkan.

---

## 13. Perubahan `v_net_worth` (3 Okt 2026, kedua)

**PENYARINGAN `is_active` DIHAPUS.** Ini koreksi atas versi sebelumnya.

Dulu `v_net_worth` memakai `WHERE is_active = 1`. Akibatnya **menonaktifkan
akun menghapus saldonya dari total kekayaan** — seolah uangnya lenyap. Tidak ada
error, angkanya cuma berubah. Untuk akun bersaldo 0 efeknya tidak terasa,
sehingga bug ini lama tidak ketahuan.

Sekarang `net_worth` menjumlahkan **semua** akun; `is_active` hanya menentukan
apakah akun muncul di daftar.

```json
"net_worth": { "total": 5904551, "liquid": 5904551, "non_liquid": 0,
               "account_count": 1, "account_count_all": 3, "balance_inactive": 0 }
```

| Field | Arti |
|---|---|
| `total` | **angka utama** — semua akun, termasuk yang nonaktif |
| `account_count` | akun aktif yang benar-benar dipakai |
| `account_count_all` | jumlah akun aktif (termasuk yang kosong) |
| `balance_inactive` | saldo yang ada di akun nonaktif |

**UI: pakai `total`. Jangan hitung ulang dari daftar akun** — kalau dihitung
dari akun aktif saja, angkanya berbeda begitu ada akun nonaktif bersaldo.

---

## 14. Saldo akhir bulan (3 Okt 2026)

**Masalah yang dijawab:** semua sumber saldo yang lama selalu mengembalikan
saldo **HARI INI** — `v_account_balances` tidak punya dimensi tanggal, dan
`/api/summary?month=` hanya menyaring arus, bukan saldo.

**Solusinya di `angka` pada `GET /api/analysis`:**

```json
"angka": {
  "net_worth": 5740751,               // kekayaan HARI INI
  "net_worth_akhir": null,            // kekayaan PER AKHIR bulan itu
  "net_worth_akhir_liquid": null,
  "net_worth_akhir_non_liquid": null,
  "per_tanggal": null                 // "2026-09-30" kalau ada isinya
}
```

### Kapan `net_worth_akhir` terisi

Tiga syarat, semuanya harus terpenuhi:

```
1. bulan itu sudah selesai   (bukan bulan berjalan / bulan depan)
2. bulan itu punya transaksi (ada_data: true)
3. per_tanggal = tanggal terakhir bulan itu
```

Kalau salah satu tidak terpenuhi → **`null`**.

**`null` berarti "tidak ada artinya", bukan nol.** Dua alasan:

- **Bulan berjalan** belum berakhir. Mengirim saldo hari ini dengan label
  "akhir bulan" berarti panel menampilkan angka yang berubah besok.
- **Bulan tanpa transaksi** saldonya SAMA dengan bulan sebelumnya. Mengirim
  angkanya membuat Deny mengira bulan itu punya aktivitas.

### Rumusnya

Sama persis dengan `v_account_balances`, hanya ditambah saringan tanggal:

```
saldo(tanggal) = opening_balance
               + in masuk      - out keluar
               - transfer keluar + transfer masuk
  ...dihitung hanya dari transaksi dengan occurred_on <= tanggal
```

**Kalau rumus ini berubah, `v_account_balances` di `src/schema.sql` harus
berubah bersamaan.** Kalau keduanya menyimpang, "saldo hari ini" dan "saldo
akhir bulan" tidak akan nyambung dan sulit ditelusuri.

Diuji dengan cara: saldo pada tanggal **jauh di depan** (2099-12-31) harus
sama persis dengan saldo hari ini. Lihat `tests/test_saldo_akhir_bulan.py` §10.

---

## 15. `/api/suggestions` vs `saran` di `/api/analysis` — JANGAN PAKAI DUANYA

**Keduanya ada, dan isinya tumpang tindih. Pakai salah satu.**

| | `/api/analysis` → `saran` | `/api/suggestions` |
|---|---|---|
| Bentuk | sama (`kategori[]` dengan `asumsi`) | sama |
| Ikut dalam response | ya, satu request dengan angka bulan itu | endpoint terpisah |
| Kapan dipakai | **halaman Analisa** | kalau butuh saran **tanpa** angka bulan |

**Untuk halaman Analisa, pakai `saran` dari `/api/analysis`.** Alasannya:
memanggil `/api/suggestions` terpisah berarti dua request dan **dua sumber
untuk data yang sama** — begitu keduanya berbeda, tidak ada yang tahu mana
yang benar.

`/api/suggestions` tetap ada untuk kalau-kalau saran hemat mau ditampilkan di
Beranda tanpa membuka halaman Analisa. Kalau itu tidak diminta, biarkan saja
tidak terpakai.

**Catatan penting:** karena September belum punya data, **semua saran bulan
ini berjenis `tanpa_pembanding` dengan `potensi_hemat: null`**. Tampilannya
adalah daftar kategori tanpa angka hemat — dan itu benar, bukan kerusakan.
