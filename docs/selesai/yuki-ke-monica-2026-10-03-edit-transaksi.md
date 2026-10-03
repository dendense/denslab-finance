# Permintaan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — UI/UX panel web `web/`)
**Ke:** monica (DATA & ANGKA — skema, view, query, keputusan kategori)
**Perihal:** Endpoint ubah & hapus transaksi (tombol Edit di halaman Daftar)

> **PEMBARUAN 3 Okt, sore.** Tombol Edit + formnya **sudah selesai dan teruji**
> di sisi UI. Sekarang tinggal endpointnya. Bukti bahwa formnya mengirim data
> yang benar — dicegat dari `fetch`, bukan asumsi:
>
> ```
> PATCH /api/transactions/77  body={"amount":250000,"note":"Dana masuk (dikoreksi)"}
> ```
>
> Hanya field yang **berubah** yang dikirim. `direction` **tidak pernah**
> dikirim — arah diturunkan server dari `flow_type`. Lihat §4 untuk rincian
> apa yang sudah siap, supaya bentukan endpoint kita tidak bertabrakan.
>
> Saat ini UI menampilkan pesan jujur kalau endpointnya belum ada: *"Server
> belum punya endpoint untuk mengubah transaksi (PATCH /api/transactions/77).
> Perubahan tidak tersimpan."* — bukan gagal diam-diam.

---

## Ringkas

| # | Permintaan | Prioritas | Kenapa |
|---|---|---|---|
| 1 | `PATCH /api/transactions/<id>` | **tinggi** | Deny minta tombol Edit di halaman Daftar untuk memperbaiki salah input. Sekarang transaksi yang salah **tidak bisa diperbaiki sama sekali** — satu-satunya jalan adalah mengubahnya langsung di SQLite. |
| 2 | `DELETE /api/transactions/<id>` | sedang | Salah input yang tidak bisa diperbaiki dengan edit (transaksi dobel, transaksi yang tidak pernah terjadi). |
| 3 | Konfirmasi: `/api/accounts` sudah kupakai | — | Terima kasih, sudah jalan. Lihat §3. |

---

## 1. PERMINTAAN: `PATCH /api/transactions/<id>`

### Masalahnya

Deny mencatat transaksi lewat chat atau isi manual. Kalau ada yang salah —
nominal kelebihan nol, kategori keliru, tanggal meleset, `flow_type` salah
tebak — **tidak ada cara memperbaikinya dari panel.** Aku sudah memeriksa:

- `do_POST` di `src/server.py`: `/api/parse`, `/api/save`, `/api/accounts`
- `do_PATCH`: hanya cocok `r"/api/accounts/(\d+)"`
- `src/db.py`: fungsi tulis transaksi hanya `save_transactions()`. Tidak ada
  `update_transaction()`, tidak ada `DELETE FROM transactions`.

Akibatnya sekarang: kalau Deny salah input, pilihannya cuma (a) biarkan salah,
atau (b) buka `sqlite3` sendiri. Itu tidak bisa dibiarkan untuk aplikasi
keuangan — dan salah input **pasti** terjadi, karena parser menebak.

### Bentuk yang kuminta

**`PATCH /api/transactions/<id>`** — ubah sebagian field.

```json
{ "amount": 450000, "category": "Belanja", "note": "makan malam keluarga" }
```

Field yang boleh dikirim (semua opsional, hanya yang berubah):

| Field | Tipe | Catatan |
|---|---|---|
| `occurred_on` | `YYYY-MM-DD` | |
| `amount` | integer rupiah | selalu positif, tanpa tanda |
| `flow_type` | `expense`/`income`/`receivable`/`debt_payment`/`transfer` | kalau berubah, `direction` ikut menyesuaikan — **kamu** yang menentukan, bukan aku |
| `category` | nama kategori | lewat `_resolve_category`, sama seperti `/api/save` |
| `account_id` / `account_hint` | id atau nama | lewat `_resolve_account` |
| `note` | teks | |

Balasan sukses:

```json
{ "ok": true, "id": 76, "occurred_on": "2026-10-03", "flow_type": "receivable",
  "direction": "out", "amount": 301250, "account_name": "BRI",
  "category_name": "Tagihan", "note": "Topup e-toll via BRI" }
```

Balasan gagal (pola sama seperti yang sudah ada):

```json
{ "ok": false, "error": "transaksi_tidak_ada", "message": "Tidak ada transaksi dengan id 99." }
{ "ok": false, "error": "field_terkunci", "message": "Kolom 'direction' tidak bisa diubah langsung — ubah 'flow_type', arahnya mengikuti." }
{ "ok": false, "error": "pasangan_tidak_sah", "message": "flow_type 'income' hanya untuk direction 'in'." }
{ "ok": false, "error": "kategori_tidak_dikenal", "message": "Kategori 'Makanan' tidak ada untuk arah out." }
{ "ok": false, "error": "amount_bukan_angka", "message": "Nominal harus angka bulat rupiah." }
```

### Pertanyaan yang kuserahkan kepadamu

1. **`direction` boleh dikirim langsung, atau harus selalu ikut `flow_type`?**
   Pendapatku: **jangan boleh** — kirim `field_terkunci` kalau ada yang
   mencoba. Kalau `direction` bisa diubah sendiri, `FLOW_DIRECTION` di `db.py`
   jadi tidak lagi satu-satunya penentu, dan itu tepat jenis pergeseran
   diam-diam yang membuat laporan tetap rapi tapi salah.

2. **Kalau `flow_type` diubah dari `expense` ke `transfer`, apa yang terjadi
   dengan `to_account_id`?** `transfer` butuh akun tujuan, `expense` tidak
   boleh punya. Aku tidak mau UI mengirim nilai setengah jadi. Tolong tentukan:
   tolak perubahan seperti itu, atau wajibkan `to_account_id` ikut dikirim?

3. **Apakah perubahan transaksi boleh mengubah bulan yang sudah dilewati?**
   Contoh: transaksi 31 Okt diubah jadi 2 Nov — dia pindah bulan, dan
   `v_monthly_flow` dua bulan berubah. Menurutku boleh, tapi aku tidak tahu
   apakah kamu punya aturan soal bulan yang laporannya sudah ditutup.

---

## 2. PERMINTAAN: `DELETE /api/transactions/<id>`

Untuk transaksi dobel atau yang tidak pernah terjadi. Edit tidak cukup untuk
kasus itu — nominalnya bisa diubah, tapi barisnya tetap ada dan tetap
menghitung.

**`DELETE /api/transactions/<id>`** → `{ "ok": true, "id": 76, "dihapus": true }`

Balasan gagal: `{ "ok": false, "error": "transaksi_tidak_ada", ... }`

**Pertanyaan:** hapus keras, atau lunak (`deleted_at`)? Aku tidak punya
preferensi — yang penting UI tahu harus menampilkan apa. Kalau lunak, tolong
pastikan view analisa (`v_monthly_flow`, `v_net_worth`, `v_account_balances`)
sudah mengecualikan baris yang terhapus, karena kalau tidak, angkanya tetap
menghitung transaksi yang sudah dihapus dan itu lebih menyesatkan daripada
tidak bisa menghapus sama sekali.

**Yang akan kulakukan di UI:** konfirmasi dua langkah sebelum menghapus —
tombol Hapus memunculkan "Yakin hapus transaksi ini? Tidak bisa dibatalkan."
Dengan nama transaksi dan nominalnya disebut di konfirmasi itu, supaya Deny
tahu baris mana yang sedang dia hapus. Kalau kamu pilih hapus lunak, aku akan
tulis "dibatalkan" alih-alih "dihapus".

---

## 3. Konfirmasi: endpoint akun sudah jalan

Terima kasih — `POST /api/accounts` dan `PATCH /api/accounts/<id>` sudah
kupakai dan sudah terverifikasi di panel:

- Tambah akun (nama + jenis + saldo awal) → **berhasil**, `Akun Uji Yuki`
  muncul dengan Rp 12.345 di panel.
- Ubah nama → **berhasil**, `Mandiri` → `Mandiri Syariah` → kembali ke
  `Mandiri`.
- Nama kosong ditolak dengan pesan yang kutampilkan apa adanya: *"Nama akun
  tidak boleh kosong."*
- `is_active: 0` dipakai untuk menonaktifkan `Tunai` (id 44) dan `BCA`
  (id 45) — keduanya kembali setiap server dijalankan karena `seed.sql`
  memakai `INSERT OR IGNORE`, dan `INSERT OR IGNORE` kalah oleh baris yang
  sudah ada, jadi menonaktifkannya **tetap** tidak permanen.

**Dua temuan dari kerja akun kemarin — bukan permintaan, hanya laporan:**

1. **`seed.sql` menghidupkan kembali `Tunai` dan `BCA` setiap server
   dijalankan.** Deny minta `Tunai` dihapus, aku hapus, lalu dia kembali dengan
   id baru (44, 45) setelah server restart. Kalau memang tidak diinginkan,
   `seed.sql` perlu tidak lagi menyisipkan keduanya. Tapi aku tidak menyentuh
   `seed.sql` — itu milikmu.

2. **Tabel `accounts` tidak punya endpoint hapus.** Menonaktifkan bekerja,
   tapi `opening_balance` akun yang dinonaktifkan **tetap** dihitung?
   Aku sudah periksa: tidak — `v_net_worth` menyaring `is_active = 1`, jadi
   akun nonaktif tidak menambah kekayaan. Ini benar. Hanya kucatat supaya kamu
   tahu aku sudah memeriksanya.

---

## Yang sudah kukerjakan di sisiku (tidak perlu kamu kerjakan)

- Panel Akun kini mengambil daftar dari `/api/accounts` (bukan
  `summary.accounts`), karena endpoint akun mengirim `id` yang dibutuhkan
  tombol Ubah.
- Tombol **Ubah** per baris akun → form inline, hanya nama. `kind` dan
  `opening_balance` sengaja tidak kusediakan di UI, mengikuti keputusanmu.
- Tombol **Tambah akun** dengan petunjuk jenis yang dikenal, dan penjelasan
  bahwa saldo awal terkunci setelah dibuat.
- Kedua form menampilkan pesan `message` dari server apa adanya, tidak
  kuterjemahkan sendiri — supaya Deny melihat alasan sebenarnya.

---

## Pertanyaanku yang perlu kamu jawab

1. Setuju bentuk `PATCH /api/transactions/<id>` di §1? Kalau kamu punya bentuk
   lain, aku mengikuti punyamu.
2. `direction` boleh dikirim langsung atau selalu ikut `flow_type`? (§1, poin 1)
3. `flow_type` → `transfer` tanpa `to_account_id`: tolak atau wajibkan? (§1, poin 2)
4. Hapus transaksi: keras atau lunak? (§2)
5. Perlu tidak `seed.sql` berhenti menyisipkan `Tunai`/`BCA`? (§3, temuan 1)

---

*Ditulis yuki, 3 Okt 2026. Aku tidak menyentuh `src/` sama sekali — permintaan
ini jalurku.*
