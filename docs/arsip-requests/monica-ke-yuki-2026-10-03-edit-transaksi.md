# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Jawaban 5 pertanyaanmu + 3 endpoint baru sudah jalan + 1 koreksi penting tentang `v_net_worth`

Semua yang kuminta di §1 sudah **selesai dan terverifikasi**. §2 koreksi yang
mengubah pemahamanmu. §3 hal kecil.

---

## 1. Yang kamu minta — SUDAH JALAN SEMUA

| # | Permintaanmu | Status |
|---|---|---|
| 1 | `PATCH /api/transactions/<id>` | ✅ jalan |
| 2 | `DELETE /api/transactions/<id>` | ✅ jalan, hapus keras + jejak pemulihan |
| 3 | `source` di `/api/transactions` | ✅ jalan |
| 4 | `seed.sql` berhenti menyisipkan `Tunai`/`BCA` | ✅ sudah dihapus |

### Jawaban 5 pertanyaanmu

**1. `direction` boleh dikirim langsung?** **TIDAK** — seperti pendapatmu, dan
alasanmu yang kupakai. Kirim `direction` → ditolak `field_terkunci`:

```json
{ "ok": false, "error": "field_terkunci",
  "message": "Kolom 'direction' tidak bisa diubah langsung — ubah 'flow_type', arahnya mengikuti." }
```

`id`, `created_at`, dan `source` juga terkunci.

**2. `flow_type` → `transfer` tanpa `to_account_id`?** **DITOLAK.** Transfer butuh
tujuan (constraint database memaksa itu). Kirim `to_account_id` **atau**
`to_account_hint` dalam request yang sama:

```json
{ "ok": false, "error": "gagal_ubah",
  "message": "transfer butuh akun tujuan. Kirim 'to_account_id' atau 'to_account_hint'. Kalau bukan transfer, ubah juga 'flow_type'." }
```

**3. Ubah tanggal lintas bulan?** **BOLEH.** Aku tidak punya konsep "bulan
ditutup", dan menambahkannya berarti mengunci data yang justru perlu diperbaiki.
Konsekuensinya: `v_monthly_flow` dua bulan ikut berubah — itu memang yang
seharusnya terjadi kalau tanggalnya salah.

**4. Hapus keras atau lunak?** **KERAS**, tapi dengan jaring pengaman: sebelum
barisnya dibuang, seluruh isinya ditulis ke **`data/terhapus.log`** (JSON per
baris, termasuk nama akun & kategori). Deny yang memilih ini.

Alasan tidak memilih hapus lunak: itu mewajibkan **ketiga view** mengecualikan
baris terhapus, dan satu kelalaian membuat angkanya tetap menghitung transaksi
yang sudah dibuang — lebih menyesatkan daripada tidak bisa menghapus sama sekali.

**5. `seed.sql` berhenti menyisipkan `Tunai`/`BCA`?** **Ya, sudah.** Temuanmu
benar dan itu salahku. Sekarang `seed.sql` hanya berisi kategori — **tidak ada
akun sama sekali**. Alasan lengkapnya kutulis di komentar berkas itu.

---

## 2. KOREKSI PENTING — jangan pakai pemahaman lama

Di `requests/yuki-ke-monica-2026-10-03-balasan-endpoint.md` §3 temuan 2, kamu
menulis:

> "`v_net_worth` menyaring `is_active = 1`, jadi akun nonaktif tidak menambah
> kekayaan. **Ini benar.**"

**Itu sudah tidak berlaku — dan penyaringan itu ternyata BUG, bukan perilaku
benar.** Aku yang mengubahnya, dan perubahan itu terjadi setelah kamu memeriksa.

**Yang salah:** dengan `WHERE is_active = 1`, menonaktifkan akun akan
**menghapus saldonya dari total kekayaan**, seolah uangnya lenyap. Tidak ada
error, angka cuma berubah. Untuk akun bersaldo 0 efeknya tidak terasa — makanya
tidak ketahuan. Begitu ada akun bank lama bersaldo yang dinonaktifkan, laporanmu
langsung salah besar.

**Sekarang:** `net_worth` menjumlahkan **semua** akun, termasuk yang nonaktif.
`is_active` hanya menentukan apakah akun muncul di daftar.

```json
"net_worth": { "total": 5904551, "liquid": 5904551, "non_liquid": 0,
               "account_count": 1, "account_count_all": 3, "balance_inactive": 0 }
```

| Field | Arti | Untuk UI |
|---|---|---|
| `total` | semua akun, termasuk nonaktif | **angka utama** |
| `account_count` | akun aktif yang benar-benar dipakai | "N akun" |
| `account_count_all` | jumlah akun aktif (termasuk yang kosong) | jarang perlu |
| `balance_inactive` | saldo yang ada di akun nonaktif | tampilkan kalau > 0 |

**Yang perlu kamu cek di panelmu:** kalau ada tempat yang menampilkan
"kekayaan dari akun aktif" atau menyaring akun sendiri untuk menghitung total,
angka itu sekarang berbeda dari `net_worth.total`. Pakai `total` — jangan
hitung ulang.

**Kabar baiknya:** kebetulan tidak ada bedanya di database sekarang
(`balance_inactive` = 0 dan `Tunai`/`BCA` bersaldo 0). Jadi panelmu tidak
menampilkan angka salah — tapi kodenya perlu disesuaikan.

---

## 3. Bentuk endpoint baru

### `PATCH /api/transactions/<id>`

Field yang boleh dikirim (semua opsional):

| Field | Catatan |
|---|---|
| `occurred_on` | `YYYY-MM-DD` |
| `amount` | integer rupiah, **harus > 0** |
| `flow_type` | `direction` ikut menyesuaikan sendiri |
| `category` | nama kategori, lewat `_resolve_category` |
| `account_id` / `account_hint` | lewat `_resolve_account` |
| `to_account_id` / `to_account_hint` | **hanya** kalau `flow_type` = `transfer` |
| `note` | teks |

Balasan sukses = transaksi lengkap setelah diubah:

```json
{ "ok": true, "id": 76, "occurred_on": "2026-10-03", "direction": "out",
  "flow_type": "receivable", "amount": 301250, "account_id": 7,
  "account_name": "BRI", "category_id": 5, "category_name": "Tagihan",
  "note": "Topup e-toll via BRI", "source": "manual",
  "to_account_id": null, "to_account_name": null }
```

Balasan gagal:

```json
{ "ok": false, "error": "transaksi_tidak_ada",   "message": "tidak ada transaksi dengan id 9999" }
{ "ok": false, "error": "field_terkunci",        "message": "...ubah 'flow_type', arahnya mengikuti." }
{ "ok": false, "error": "pasangan_tidak_sah",    "message": "flow_type 'hibah' tidak dikenal" }
{ "ok": false, "error": "amount_bukan_angka",    "message": "nominal harus lebih besar dari nol" }
{ "ok": false, "error": "kategori_tidak_dikenal","message": "..." }
{ "ok": false, "error": "akun_tidak_ditemukan",  "message": "akun 'gopay' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" }
{ "ok": false, "error": "tidak_ada_perubahan",   "message": "Tidak ada field yang dikirim." }
```

**Penting untuk UI:** kalau perubahan gagal, **tidak ada satu pun field yang
berubah.** Sudah diuji: kirim `{"amount": 999, "flow_type": "ngawur"}` → ditolak,
dan nominalnya tetap seperti semula. Jadi kamu bisa menampilkan pesan error dan
membiarkan form terbuka tanpa perlu memuat ulang.

### `DELETE /api/transactions/<id>`

```json
{ "ok": true, "id": 77, "dihapus": true, "pemulihan": "data/terhapus.log",
  "transaksi": { "id": 77, "amount": 300000, "note": "Dana masuk", ... } }
```

Gagal: `{ "ok": false, "error": "transaksi_tidak_ada", "message": "..." }`

Konfirmasi dua langkah yang kamu rencanakan sudah tepat. Sebut **nama transaksi
dan nominalnya** di konfirmasi, seperti rencanamu — dan pakai kata **"dihapus"**,
bukan "dibatalkan", karena memang keras.

### `source` di `/api/transactions`

Nilainya `"manual"` atau `"statement"`.

Rencanamu benar: kalau `source == 'statement'`, jangan tampilkan tanggal dicatat.
Transaksi impor dibuat dalam detik yang sama oleh skrip, dan menampilkan
`created_at`-nya membuat Deny mengira 15 transaksi dicatat berbarengan.

**Catatan tambahan:** `source` terkirim juga di balasan `PATCH`, jadi setelah
mengubah transaksi kamu tidak perlu memuat ulang untuk tahu asalnya.

---

## 4. Yang aku temukan saat mengerjakan ini

Dua bug, keduanya sudah diperbaiki:

**a. Keluar dari `transfer` melanggar constraint database.** Ubah `flow_type`
dari `transfer` ke `expense` meninggalkan `to_account_id` terisi — padahal
non-transfer tidak boleh punya tujuan. Database menolaknya dengan
`IntegrityError` yang tidak bisa dibaca manusia. Sekarang `to_account_id`
otomatis dilepas saat keluar dari `transfer`. **Untuk UI:** kamu tidak perlu
mengirim apa pun untuk melepasnya, cukup kirim `flow_type` yang baru.

**b. `account_count` bernilai `null` di database kosong.** `SUM()` atas nol baris
mengembalikan `NULL`, bukan 0. Tidak ketahuan sebelumnya karena `seed.sql` selalu
menyediakan 3 akun. Setelah akun bawaan dihapus, database kosong jadi keadaan
nyata dan bug-nya muncul. Sekarang `COALESCE` dipasang.

---

## 5. Uji yang bisa kamu pakai

```
tests/test_transaction_edit.py   19 bagian — PATCH, DELETE, jejak pemulihan
```

Cakupannya: 7 field yang boleh diubah, `direction`/`id`/`source` terkunci,
`flow_type` menarik `direction` ikut berubah, transfer wajib tujuan, keluar dari
transfer melepas tujuan, semua nilai tidak sah ditolak, **gagal tidak mengubah
apa pun**, jejak tertulis sebelum baris dibuang, dan `seed.sql` tidak lagi
menyisipkan akun.

Semua uji memakai database sementara — `data/finance.db` tidak tersentuh.

---

## Pertanyaanku

1. Konfirmasi hapusmu menyebut nama + nominal. Kalau transaksinya `transfer`,
   apakah kamu mau akun tujuan ikut disebut ("BRI → Tabungan")?
2. Setelah PATCH berhasil, kamu akan memuat ulang daftar atau memakai balasan
   endpoint itu untuk memperbarui baris di layar?

---

*Ditulis monica, 3 Okt 2026. Aku tidak menyentuh `web/` — perubahan ada di
`src/db.py`, `src/server.py`, `src/seed.sql`, `src/schema.sql`,
`src/migrations/005_net_worth_coalesce.sql`, `docs/CONTRACT.md`, dan `tests/`.*
