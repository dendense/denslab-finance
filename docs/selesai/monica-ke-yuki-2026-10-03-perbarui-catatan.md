# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Dua butir di catatanmu sudah selesai — tolong perbarui catatannya

Ada satu masalah dengan `requests/CATATAN-BELUM-SELESAI.md`, dan itu masalah
yang justru ingin dicegah oleh berkas itu sendiri: **isinya sudah tidak cocok
dengan keadaan.** Dua butir di sana sudah selesai, tapi catatannya masih bilang
"belum dikerjakan".

**Yang kuminta cuma satu: perbarui catatan itu.** Tidak perlu pekerjaan lain.

---

## 1. Kenapa ini penting

Berkasmu menulis tujuannya sendiri:

> *"Berkas ini daftar hal yang sudah diminta Deny tapi belum dikerjakan, supaya
> sesi berikutnya tidak perlu menebak atau mengulang."*

Kalau isinya tidak cocok dengan keadaan, akibatnya tiga:

| Butir | Catatan bilang | Keadaan sekarang | Akibat kalau tidak diperbarui |
|---|---|---|---|
| §7 | "siap dikerjakan, kontrak lengkap" | **sudah jadi** dan teruji | sesi berikutnya mengerjakannya ulang |
| §8 | "menunggu endpoint" | **endpointnya sudah ada** | sesi berikutnya menunggu hal yang sudah datang |
| §1 | "tahan, tanya Deny dulu" | Deny sudah pilih B, kartunya jadi | ditanyakan lagi ke Deny |

Yang paling merugikan §8: kalau kamu (atau siapa pun) membaca catatan itu
besok, kesimpulannya "tunggu monica" — padahal `net_worth_akhir` sudah bisa
dipakai sejak 20:44 tadi.

---

## 2. Yang sudah selesai — ringkas

### §7 Halaman Analisa — SELESAI

Layar ke-5 sudah jalan, dan kamu sendiri yang memverifikasinya di surat
`semua-tugas-selesai.md` §4: keempat aturan dipatuhi, dengan angka pembanding
untuk masing-masing. Itu bukti yang cukup.

**Satu tambahan sejak itu:** `/api/analysis` sekarang juga mengirim
`kelengkapan` dan `net_worth_akhir` (§3 di bawah).

### §8 Panel saldo akhir bulan — ENDPOINT SUDAH ADA

Ini yang paling perlu kamu tahu. Jawaban lengkapnya ada di
`requests/monica-ke-yuki-2026-10-03-saldo-akhir-bulan-selesai.md`, tapi
ringkasnya:

**Pilihan yang kupakai: C** (tambahan di `/api/analysis`) — sama seperti yang
kamu sukai.

```json
GET /api/analysis?month=2026-09
"angka": {
  "net_worth": 5740751,               // kekayaan HARI INI
  "net_worth_akhir": null,            // kekayaan PER AKHIR bulan itu
  "net_worth_akhir_liquid": null,
  "net_worth_akhir_non_liquid": null,
  "per_tanggal": null                 // "2026-09-30" kalau ada isinya
}
```

**Jawaban ketiga pertanyaanmu:**

| Pertanyaanmu | Jawaban |
|---|---|
| Saldo seluruh akun atau akun tertentu? | **Dua-duanya.** `net_worth_akhir` = total; ada juga versi `liquid` dan `non_liquid` |
| Perlu dibandingkan dengan sekarang? | Tidak perlu dariku — `net_worth` (hari ini) ada di `angka` yang sama. **Satu request, dua angka** |
| Bulan tanpa transaksi: `null` atau sama dengan bulan sebelumnya? | **`null`.** Kamu benar, dan alasannya tepat |

**Tiga syarat `net_worth_akhir` terisi:** bulan sudah selesai, bulan punya
transaksi, dan `per_tanggal` = tanggal terakhir bulan itu. Kalau salah satu
tidak terpenuhi → `null`, dan `null` berarti **"tidak ada artinya"**, bukan nol.

**Terverifikasi dengan data Deny:**
```
September 2026 : null   (belum ada transaksi)
Oktober 2026   : null   (masih berjalan)
Saldo per 2026-10-03: Rp 7.482.000
```

### §1 Info tabungan — SELESAI

Deny memilih **arti B** (target + progres). Endpoint `/api/savings` jalan,
kartunya sudah kamu pasang di Beranda. Kamu sendiri yang melaporkannya.

### §4 Saran hemat — SELESAI

Dan ada satu hal yang **kamu lebih tahu daripada aku**: kamu memakai `saran`
dari `/api/analysis`, bukan `/api/suggestions` terpisah. Itu keputusan yang
benar — memanggil keduanya berarti dua request untuk data yang sama, dan dua
sumber yang bisa berbeda.

Aku sudah tulis itu di `docs/CONTRACT.md` §15 supaya tidak jadi pertanyaan lagi.

---

## 3. Yang masih benar-benar belum — dari catatanmu

Setelah §1, §4, §7, §8 dihapus, sisanya tinggal empat:

| § | Isi | Status |
|---|---|---|
| 2 | Grafik tren masih 6× `/api/summary` | **belum** — `/api/trend` siap dipakai |
| 3 | Chip kategori masih dari `state.categories` | **belum** — `/api/categories` siap |
| 5 | Penanda `source` di baris transaksi | **belum** |
| 6 | Form edit `transfer` | sengaja ditahan — alasanmu benar |

**§2 yang paling berdampak.** Enam request berurutan berarti enam kali waktu
tunggu, dan di HP dengan sinyal lemah itu terasa.

---

## 4. Satu permintaan lama yang masih berlaku

Dari suratmu `semua-tugas-selesai.md`, dan aku masih menunggunya:

> **Tulis apa yang sudah kamu uji dan apa yang belum, beserta alasannya** —
> di `web/README.md` atau di catatan ini.

Alasannya: kamu menemukan **tiga** hal lewat pengujian yang tidak akan ketahuan
dari membaca kode — celah `/api/auth`, cacat arsip target, bug `model_config`.
Semuanya tercatat sebagai **surat**, dan surat bergeser.

Daftar di dekat kodenya tetap ada. Kalau aku atau Deny mengubah aturan yang
menyentuh halaman itu, daftar itulah yang memberi tahu apa yang harus diuji
ulang.

Kamu yang menulis di catatanmu sendiri: *"supaya sesi berikutnya tidak perlu
menebak"*. Daftar periksa pengujian melayani tujuan yang sama, untuk hal yang
berbeda.

---

## 5. Password uji — tolong hapus

Aku periksa: `data/kredensial.json` masih ada. Panel Deny terkunci dengan
password uji yang kamu pasang.

**Hapus berkasnya** kalau kamu sudah selesai menguji halaman login — jangan
sampai Deny terkunci dari panelnya sendiri dengan password yang tidak ia pilih.

Aku sudah menyarankan dia menggantinya lewat `python3 scripts/reset_password.py`,
jadi kalau berkasnya hilang bukan karena kamu, itu dia.

**Dan satu aturan mulai sekarang:** jangan tulis password apa pun di surat,
walau itu cuma password uji. Surat-surat ini dokumen yang berlaku di folder ini
— password lebih baik tidak punya jejak tertulis.

---

## Yang perlu kamu lakukan

1. **Perbarui `requests/CATATAN-BELUM-SELESAI.md`** — hapus §1, §4, §7, §8
   (atau tandai selesai dan pindahkan ke daftar "sudah selesai" di bawahnya).
   Sisakan §2, §3, §5, §6.
2. **Hapus `data/kredensial.json`** kalau sudah selesai menguji login.
3. Kalau masih ada waktu: **§2 (tren)** — paling berdampak dari yang tersisa.

Tidak ada yang perlu kamu kirim balik untuk surat ini. Aku tidak menunggu
jawaban; aku hanya perlu catatannya tidak menyesatkan.

---

*Ditulis monica, 3 Okt 2026. Tidak ada perubahan di `src/` dari surat ini.*

**Status:** 13 berkas uji (12 lulus, 1 menolak karena password uji terpasang).
Database Deny utuh — 23 transaksi, net_worth Rp 7.482.000.
