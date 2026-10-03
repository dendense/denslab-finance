# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Target tabungan — endpoint sudah jalan, kontrak lengkap

Menanggapi `requests/CATATAN-BELUM-SELESAI.md` §1: Deny memilih **arti B**
(target tabungan dengan progres), bukan sekadar saldo akun. Endpoint sudah jalan
dan teruji. **Tidak ada yang perlu kamu tebak.**

---

## Ringkas

| # | Isi | Status |
|---|---|---|
| 1 | `GET /api/savings` | ✅ jalan |
| 2 | `POST /api/savings` — pasang/ubah target | ✅ jalan |
| 3 | `DELETE /api/savings` — arsipkan target | ✅ jalan |
| 4 | Bentuk data lengkap | §2 |
| 5 | Empat hal yang wajib kamu patuhi | §3 |

---

## 1. Keputusan Deny yang menentukan bentuknya

| # | Keputusan | Akibat untuk UI |
|---|---|---|
| 1 | Yang dihitung = **saldo akun Tabungan** (`kind: savings`) | Uang di reksadana/deposito **tidak** terhitung |
| 2 | **Satu target** saja untuk sekarang | Tidak perlu daftar target, tidak perlu pilih-pilih |
| 3 | **Target total**, bukan bulanan | Garis akhir: "kumpulkan Rp X", bukan "sisihkan Rp X/bulan" |
| 4 | Mulai menabung **bulan depan** | Sekarang belum ada target. Tangani keadaan kosong dengan benar |

Posisi yang diminta Deny: **di bawah panel "transaksi terakhir"** di layar
Beranda (`#recent-host`), bukan di layar Akun.

---

## 2. Bentuk data

### `GET /api/savings`

**Belum ada target:**

```json
{
  "ada_target": false,
  "target": null,
  "akun_bisa_dipakai": [
    { "id": 3, "name": "Tabungan", "kind": "savings", "balance": 0 }
  ],
  "catatan": "Progres dihitung dari SALDO AKUN target, bukan dari total kekayaan. Uang yang disimpan di akun lain tidak ikut terhitung."
}
```

**Sudah ada target:**

```json
{
  "ada_target": true,
  "target": {
    "id": 1,
    "name": "Dana Darurat",
    "target_amount": 20000000,
    "target_date": null,
    "account_id": 3,
    "account_name": "Tabungan",
    "account_kind": "savings",

    "terkumpul": 2000000,
    "sisa": 18000000,
    "persen": 10,
    "status": "berjalan",

    "riwayat_setoran": [
      { "month": "2026-11", "total": 2000000, "tx_count": 1 }
    ],
    "riwayat_penarikan": [],

    "rata_setoran_bulanan": 2000000,
    "bulan_ada_setoran": 1,
    "perkiraan_bulan_lagi": 9,

    "is_archived": 0,
    "created_at": "2026-10-03 20:15:00"
  },
  "akun_bisa_dipakai": [ { "id": 3, "name": "Tabungan", "kind": "savings", "balance": 2000000 } ],
  "catatan": "..."
}
```

### `POST /api/savings`

```json
{ "name": "Dana Darurat", "target_amount": 20000000, "account_id": 3 }
```

`account_id` boleh diganti `account_hint` (nama akun, mis. `"Tabungan"`).
`target_date` opsional — kalau diisi, panel bisa menunjukkan tenggatnya.

Balasan sukses:

```json
{ "ok": true, "target": { ...bentuk target seperti di atas... } }
```

Gagal:

```json
{ "ok": false, "error": "nama_kosong",        "message": "Nama target tidak boleh kosong." }
{ "ok": false, "error": "target_kosong",      "message": "Target harus diisi, angka bulat rupiah." }
{ "ok": false, "error": "target_tidak_sah",   "message": "target harus lebih besar dari nol" }
{ "ok": false, "error": "akun_tidak_ditemukan","message": "akun 'gopay' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" }
{ "ok": false, "error": "tanggal_tidak_sah",  "message": "tanggal target '2026-13-99' tidak sah. Pakai YYYY-MM-DD." }
```

**Pasang target baru = target lama otomatis diarsipkan.** Kamu tidak perlu
menghapus dulu. Kalau Deny salah isi lalu mengisi ulang, yang lama tetap
tersimpan sebagai jejak.

### `DELETE /api/savings`

```json
{ "ok": true, "diarsipkan": true }
{ "ok": false, "error": "tidak_ada_target", "message": "Belum ada target tabungan yang aktif." }
```

**Arsipkan, bukan hapus.** Datanya masih ada di database. Panel tidak menampilkannya lagi.

---

## 3. Empat hal yang WAJIB kamu patuhi

### 3a. `null` ≠ `0` pada dua field ini

| Field | `null` artinya | Jangan ditampilkan sebagai |
|---|---|---|
| `rata_setoran_bulanan` | belum pernah menabung sepeser pun | "Rp 0 per bulan" |
| `perkiraan_bulan_lagi` | tidak ada dasar untuk memperkirakan | "0 bulan" / tanggal karangan |

Kalau `null`, **jangan tampilkan angkanya sama sekali.** Tampilkan kalimat
seperti *"Belum ada setoran, jadi belum bisa diperkirakan."*

Ini penting: kalau kamu menulis "perkiraan 0 bulan lagi", Deny akan mengira
targetnya sudah tercapai.

### 3b. `status` — pakai ini, jangan hitung sendiri dari persen

| `status` | Kapan | Tampilkan |
|---|---|---|
| `belum_mulai` | saldo ≤ 0 | "Belum mulai" — jangan tampilkan progres bar kosong seolah gagal |
| `berjalan` | 0 < saldo < target | progres normal |
| `tercapai` | saldo ≥ target | "Tercapai" |

**`persen` bisa lebih dari 100** kalau tabungan melebihi target. Jangan di-cap
di 100 — kelebihan itu informasi (Deny menabung lebih dari rencana), bukan error.
Kalau progress bar-nya tidak bisa lebih dari 100%, tampilkan angkanya di teks
saja (mis. "125% dari target").

### 3c. `terkumpul` adalah SALDO AKUN, bukan jumlah setoran

Kalau Deny menyetor Rp 2 juta lalu menarik Rp 500 ribu, `terkumpul` = Rp 1,5 juta.
`riwayat_setoran` tetap mencatat Rp 2 juta, dan `riwayat_penarikan` mencatat
Rp 500 ribu. **Dua-duanya benar dan tidak saling bertentangan** — bedanya:
`terkumpul` = keadaan sekarang, riwayat = kejadian.

Kalau kamu menampilkan "total menabung" dari `riwayat_setoran`, angkanya akan
berbeda dari `terkumpul`. Itu benar, tapi beri label yang jelas supaya tidak
terlihat seperti salah hitung.

### 3d. Tampilkan `catatan` — konsekuensinya nyata

Field `catatan` di balasan `GET` berisi:

> *"Progres dihitung dari SALDO AKUN target, bukan dari total kekayaan. Uang
> yang disimpan di akun lain tidak ikut terhitung."*

Ini bukan hiasan. Kalau Deny nanti menabung lewat reksadana, progresnya tidak
akan bergerak dan dia akan mengira panelnya rusak. Satu baris kecil di kartu
tabungan mencegah kebingungan itu.

---

## 4. Keadaan kosong — ini yang akan kamu lihat sekarang

Deny mulai menabung **bulan depan**. Jadi sampai itu terjadi:

```json
{ "ada_target": false, "target": null,
  "akun_bisa_dipakai": [{ "id": 3, "name": "Tabungan", "kind": "savings", "balance": 0 }] }
```

**Yang sebaiknya kamu tampilkan:** kartu dengan ajakan, bukan angka nol.

- Judul: *"Target tabungan"*
- Isi: *"Belum ada target. Pasang target untuk mulai memantau."*
- Tombol: *"Pasang target"* → form dengan nama, jumlah, akun (dari `akun_bisa_dipakai`)

Jangan tampilkan bar progres 0% atau "Rp 0 dari Rp 0" — itu terlihat seperti
kerusakan, bukan keadaan awal.

**Dan:** akun `Tabungan` saldonya Rp 0. Kalau Deny memasang target tanpa mengisi
akun itu, `status` akan `belum_mulai` dan tampil apa adanya. Itu benar.

---

## 5. Saran susunan kartu

Bebas kamu tentukan — `UI-MOBILE.md` yang berlaku. Usulanku:

```
┌─ Dana Darurat ──────────────────────┐
│  Rp 1.900.000  dari  Rp 14.500.000  │
│  ████░░░░░░░░░░░░░░░░  10%          │
│                                     │
│  Kurang Rp 11.900.000               │
│  Rata-rata Rp 1.900.000/bulan       │
│  + 9 bulan lagi kalau konsisten     │
│                                     │
│  Progres dihitung dari saldo akun   │
│  Tabungan.                          │
└─────────────────────────────────────┘
```

Kalau `perkiraan_bulan_lagi` null, baris "9 bulan lagi" diganti kalimat jujur.

---

## Pertanyaanku

1. Kartu tabungan taruh persis di bawah `#recent-host` seperti permintaan Deny,
   atau menurutmu ada tempat lebih baik?
2. Riwayat setoran per bulan — mau ditampilkan di kartu, atau cukup angkanya saja
   dulu?
3. Kalau `persen > 100`, progress bar-nya kamu lebarkan sampai penuh lalu
   tampilkan angkanya, atau kamu punya cara lain?

---

*Ditulis monica, 3 Okt 2026. Perubahan ada di `src/db.py`, `src/server.py`,
`src/schema.sql`, `src/migrations/007_savings_goal.sql`, dan uji baru
`tests/test_savings.py` (12 bagian).*

**Status bersama:** target uji sudah kuarsipkan, jadi `GET /api/savings`
mengembalikan `ada_target: false` sampai Deny memasangnya sendiri.
