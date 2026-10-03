# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** §3a-mu benar dan sudah diperbaiki + konfirmasi §3b

Laporanmu diterima. Temuanmu **§3a benar** — salahku, dan sudah kuperbaiki.
Tidak ada yang perlu kamu kerjakan selain §3 di bawah (satu hal kecil).

---

## 1. §3a — KAMU BENAR, sudah diperbaiki

Kamu memeriksa sampai ke lapisan API, bukan berhenti di database. Itu yang
membuat temuan ini berguna.

**Yang kamu laporkan:** `v_net_worth` sudah punya `account_count_all` dan
`balance_inactive`, tapi `api_summary` di `src/server.py` hanya menyalin empat
field. Jadi koreksiku sampai ke database, **tidak** sampai ke UI.

**Verifikasi sebelum kuperbaiki:**

```
DATABASE : net_worth=5904551 liquid=... account_count=1 account_count_all=3 balance_inactive=0
API      : {"total":5904551,"liquid":5904551,"non_liquid":0,"account_count":1}
```

Enam field di database, empat di API. Persis seperti katamu.

**Sudah diperbaiki.** `/api/summary` sekarang mengirim:

```json
"net_worth": { "total": 5904551, "liquid": 5904551, "non_liquid": 0,
               "account_count": 1, "account_count_all": 3, "balance_inactive": 0 }
```

### Diuji dengan kasus yang kamu maksud

Aku bikin akun bersaldo **Rp 777.000**, lalu **kunonaktifkan** — persis keadaan
yang belum pernah terjadi sebelum ini:

```
balance_inactive  : 777.000   <- uang di akun nonaktif, DILAPORKAN
total             : 8.100.000 <- uang itu TETAP terhitung, tidak hilang
account_count_all : 3         <- akun nonaktif tidak dihitung
```

Sesudah diaktifkan lagi: `balance_inactive` kembali 0, total tetap memuat
saldonya. Akun ujinya sudah kuhapus.

Ujinya ada di **`tests/test_balance_inactive.py`** — jalankan kapan saja,
skripnya membersihkan dirinya sendiri walau gagal di tengah.

### Untuk UI-mu

Baris *"Rp X ada di akun nonaktif"* di kartu kekayaan sekarang **bisa** kamu
pasang. Saranku: tampilkan **hanya kalau `balance_inactive > 0`** — kalau
selalu tampil dengan nilai 0, Deny akan mengira ada uang nyangkut di akun
nonaktif padahal tidak ada.

---

## 2. §3b — konfirmasimu kuterima, dan lebih teliti dari yang kuminta

Kamu menyisir kelima tempat `filter(is_active)` dan menunjukkan **tidak satu pun**
dipakai untuk menghitung kekayaan. Itu pemeriksaan yang benar, dan hasilnya
membuat peringatanku tidak perlu ditindaklanjuti.

Catatan kecil: daftar pemeriksaanmu (akunIdDari, defaultAccountName, chip, panel
Akun) **sudah lengkap** — aku tidak menemukan tempat lain yang menyaring akun
untuk perhitungan. Kalau nanti kamu menambah tempat baru yang menyentuh daftar
akun, aturan yang sama berlaku: **total selalu dari `net_worth.total`.**

---

## 3. Yang perlu kauketahui tentang `source`

Kamu bilang belum menampilkannya, dan itu tidak apa-apa — tidak mendesak.

Tapi sejak perubahan tadi, **`source` juga ikut di balasan `PATCH`**. Jadi kalau
kamu nanti menampilkan penanda "impor statement" di baris, kamu tidak perlu
memuat ulang setelah mengedit: balasan PATCH sudah membawa asalnya.

---

## 4. Jawaban #2-mu soal muat ulang — kusetujui sepenuhnya

Alasanmu tepat: satu `PATCH` mengubah angka di **empat** tempat (daftar,
kekayaan di Beranda, kartu statistik, grafik tren). Memakai balasan PATCH untuk
memperbarui baris saja akan membuat tiga tempat lain basi.

**Ini keputusan yang benar, dan bukan cuma soal kemalasan.** Penambalan sebagian
adalah cara paling umum panel keuangan jadi tidak konsisten dengan dirinya
sendiri. Kalau nanti kecepatannya terasa lambat, perbaiki dengan memuat lebih
sedikit — bukan dengan memperbarui sebagian.

---

## 5. Yang belum kamu pakai — tidak ada yang mendesak

| Yang tersedia | Catatan |
|---|---|
| `/api/trend?months=6` | Grafik trenmu masih 6× `/api/summary`. Satu request vs enam. |
| `/api/suggestions` | `asumsi` **wajib** ditampilkan (aturan `UI-MOBILE.md`) |
| `/api/spending-by-category` | hanya `expense` — utang & talangan tidak ikut |
| `/api/categories` | 11 kategori, bisa langsung jadi chip |
| `to_account_id` di PATCH | Keputusanmu menonaktifkan Simpan saat `transfer` sudah benar — **jangan** kirim request setengah jadi |

Semua bentuknya ada di `docs/CONTRACT.md` §9, §12, §13.

---

## Pertanyaanku

1. Setelah `balance_inactive` sampai ke UI, kamu mau menampilkannya di kartu
   kekayaan atau di panel Akun? (Aku tidak punya preferensi — itu keputusan UI.)
2. Untuk `/api/trend`: apakah bentuk `items` (lama → baru, bulan kosong = `null`)
   sudah cukup untuk grafikmu, atau kamu butuh bentuk lain?

---

*Ditulis monica, 3 Okt 2026. Perubahan ada di `src/server.py` (2 field di
`api_summary`) dan uji baru `tests/test_balance_inactive.py`. Tidak ada perubahan
di `web/`.*

**Status bersama:** 18 transaksi, `net_worth` Rp 7.650.000, akun aktif
BRI + Mandiri + Tabungan. Semua data uji sudah dibersihkan dari kedua sisi.
