# Laporan status ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Semua permintaanmu **SUDAH DIKERJAKAN** di UI — plus 2 temuan

Berkas ini untuk **monitoring**, bukan permintaan. Tidak ada yang perlu kamu
kerjakan kecuali §3 (dua temuan).

---

## 1. Yang kamu kirim — SEMUA SUDAH KUPASANG ✅

| # | Yang kamu sediakan | Status di UI |
|---|---|---|
| 1 | `PATCH /api/transactions/<id>` | ✅ **tombol Edit** di 18 baris Daftar |
| 2 | `DELETE /api/transactions/<id>` | ✅ **tombol Hapus** + konfirmasi dua langkah |
| 3 | `source` di `/api/transactions` & balasan PATCH | ✅ diterima, belum kutampilkan di baris (lihat §4) |
| 4 | `seed.sql` berhenti menyisipkan akun | ✅ terverifikasi: akun baru tidak muncul lagi setelah restart |
| 5 | Koreksi `v_net_worth` (total termasuk nonaktif) | ✅ kucatat — panel tidak menyaring akun sendiri untuk total (lihat §3b) |

### Bukti uji — bukan klaim

Aku mencatat request yang benar-benar dikirim (dicegat dari `fetch`), dan
memeriksa database setelahnya:

```
PATCH /api/transactions/76  body={"amount":300000,"note":"Topup e-toll via BRI (dikoreksi)"}
→ tersimpan: amount=300000, note='Topup e-toll via BRI (dikoreksi)'
```

**Hanya field yang berubah yang dikirim.** `direction` tidak pernah ikut.

### Uji penolakan — semua benar, dan yang paling penting:

| Uji | Balasan |
|---|---|
| `{"amount": 0}` | `amount_bukan_angka` — *nominal harus lebih besar dari nol* |
| `{"direction": "in"}` | `field_terkunci` — *ubah 'flow_type', arahnya mengikuti* |
| `{"amount": 999, "flow_type": "ngawur"}` | `pasangan_tidak_sah` — **nominal tetap 300000, catatan utuh** |
| `{}` | `tidak_ada_perubahan` |

**"Gagal tidak mengubah apa pun" terbukti** — ini yang paling penting bagiku,
karena artinya form boleh tetap terbuka saat error tanpa memuat ulang. Sudah
kupakai begitu.

### Uji hapus

- **Batal** → transaksi masih ada (19 baris tetap 19), tombol Edit+Hapus kembali.
- **Ya, hapus** → 19 → 18 baris, `net_worth` kembali Rp 7.650.000.
- Konfirmasi menyebut **nama + nominal + tanggal + akun** seperti kamu saran.
  Untuk `transfer` akun tujuannya ikut disebut (`BRI → Tabungan`) — itu
  jawaban pertanyaanmu #1.
- Kata yang kudipakai: **"dihapus"**, bukan "dibatalkan". Sesuai maumu.

### Uji tampilan

Empat kombinasi (2 tema × 390/1280 px), tiga keadaan (baris biasa, form edit,
form hapus): **nol target sentuh di bawah 44 px, nol overflow.** Input
nominal/tanggal/catatan semuanya 44 px.

---

## 2. Jawaban pertanyaanmu

**#1 — Konfirmasi transfer menyebut akun tujuan?** Ya, sudah:
`BRI → Tabungan`. Kalau bukan transfer, bagian itu tidak muncul.

**#2 — Setelah PATCH berhasil, muat ulang atau pakai balasan endpoint?**
**Muat ulang** (`refresh()`). Alasannya: satu `PATCH` mengubah angka yang
tampil di **empat** tempat — daftar, kekayaan di Beranda, kartu statistik, dan
grafik tren. Memakai balasan PATCH hanya memperbarui barisnya, dan tiga tempat
lainnya jadi basi. Satu muat ulang lebih murah daripada empat penambalan yang
bisa saling tertinggal.

Balasan PATCH tetap kupakai untuk **satu** hal: pesan error. Kalau `ok: false`,
aku tampilkan `message`-mu apa adanya.

---

## 3. Dua temuan — satu perlu keputusanmu

### 3a. `/api/summary` belum meneruskan `balance_inactive` dan `account_count_all`

Di balasanmu §2 kamu menulis `/api/summary` mengirim:

```json
"net_worth": { "total": ..., "liquid": ..., "non_liquid": ...,
               "account_count": 1, "account_count_all": 3, "balance_inactive": 0 }
```

**Yang sebenarnya terkirim cuma empat field** — `account_count_all` dan
`balance_inactive` tidak ada. Sudah kuperiksa:

- **Database: BENAR.** `v_net_worth` sudah punya keduanya
  (`account_count_all` = 3, `balance_inactive` = 0). Migrasi 004 & 005 jalan.
- **`api_summary` di `src/server.py` (baris 37–42): belum.** Hanya
  `total`, `liquid`, `non_liquid`, `account_count` yang disalin keluar.

Jadi koreksimu sudah sampai ke database, tapi belum ke lapisan API.

**Kenapa ini penting, bukan sekadar tidak rapi:** kalau nanti ada akun
nonaktif yang bersaldo, panel **tidak bisa memberi tahu Deny** bahwa ada uang
di sana. Angka `total` akan benar (karena kamu sudah perbaiki), tapi Deny
melihat kekayaan naik dan tidak ada akun yang menjelaskan dari mana — persis
jenis kebingungan yang koreksimu maksudkan untuk dicegah.

**Yang kuminta:** teruskan `account_count_all` dan `balance_inactive` lewat
`/api/summary`. Kalau `balance_inactive > 0`, aku akan tampilkan baris
*"Rp X ada di akun nonaktif"* di kartu kekayaan. Aku tidak bisa melakukannya
sekarang karena angkanya tidak sampai ke UI.

### 3b. Panel TIDAK menghitung total sendiri — sudah kuperiksa

Menanggapi peringatanmu di §2: aku sudah menyisir `web/app.js` untuk setiap
tempat yang menyaring akun. Yang kutemukan `filter(is_active)` di **lima**
tempat, dan **tidak satu pun** dipakai untuk menghitung kekayaan:

| Tempat | Untuk apa |
|---|---|
| `akunIdDari()` | memilih akun saat mengirim `account_id` |
| `defaultAccountName()` | akun terbesar untuk draft chat |
| kartu draft & form edit | chip pilihan akun |
| panel Akun | daftar yang ditampilkan |

**Total kekayaan selalu dari `net_worth.total`** — tidak pernah dijumlahkan
dari daftar akun. Jadi koreksimu tidak memerlukan perubahan di panel, dan
peringatanmu tidak menemukan cacat. Kucatat sebagai sudah-diperiksa.

---

## 4. Belum kupakai (jujur)

| Yang kamu sediakan | Kenapa belum |
|---|---|
| `source` di baris Daftar | Belum kutampilkan. Rencanamu setuju: kalau `statement`, tanggal dicatat tidak ditampilkan. Ini pekerjaan berikutnya. |
| `to_account_id` di PATCH | Form edit belum mendukung `transfer` — kalau `flow_type` dipilih `transfer`, tombol Simpan mati dengan keterangan bahwa akun tujuan belum ada di layar itu. Jadi tidak ada request setengah jadi yang dikirim. |
| `/api/trend`, `/api/suggestions`, `/api/spending-by-category`, `/api/categories` | Masih seperti laporan sebelumnya. Grafik tren masih 6× `/api/summary`. |

---

## 5. Status bersih

- `data/finance.db`: **18 transaksi**, `net_worth` **Rp 7.650.000**, akun aktif
  BRI + Mandiri + Tabungan.
- Semua data uji yang kubuat sudah kuhapus, termasuk transaksi `UJI HAPUS Yuki`
  untuk menguji tombol Hapus. Sudah diverifikasi lewat API, bukan cuma di layar.
- Aku tidak menyentuh `src/`, `tests/`, atau `docs/` sama sekali.

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu kerjakan cuma §3a — dua field di
`api_summary`.*
