# Permintaan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** Celah yang kamu temukan SUDAH DITUTUP + jawaban §3 + cacat yang kamu sebut juga kuperbaiki

**§2 sudah selesai.** §3 kujawab tegas. Cacat `POST /api/savings` yang kamu
sebut di §4 ternyata nyata dan sudah kututup.

---

## 1. Celah pengambilalihan akun — KAMU BENAR, dan itu salahku

Kamu menemukan sesuatu yang serius, dan kamu menjelaskannya lebih baik daripada
aku akan menjelaskannya sendiri:

> *"Siapa pun yang membuka panel sebelum Deny memasang password bisa memasang
> passwordnya sendiri dan mengunci Deny keluar dari panelnya. Itu bukan
> kekhawatiran teoretis; aku melakukannya tanpa sengaja."*

**Persis begitu.** Dan penyebabnya keputusan bodohku: aku mengecualikan
`/api/auth` **hanya untuk POST**, dengan pikiran "POST itu login, jadi harus
publik". Aku tidak memikirkan bahwa **GET-nya juga dibutuhkan halaman login
sebelum ada sesi** — padahal itu justru satu-satunya cara halaman itu tahu form
mana yang harus ditampilkan.

### Sudah diperbaiki

```python
if path == "/api/auth":
    return True          # GET (status) maupun POST (login)
```

### Terverifikasi

```
GET /api/auth  ->  200  {"sudah_ada_password": false, "panjang_min_password": 6}
```

Dan yang privat tetap privat — memperbaiki celah tidak boleh membuka celah baru:

```
401  /api/summary      /api/transactions    /api/accounts
401  /api/savings      /api/analysis        /api/months
401  /api/auth/status
```

### Celah kedua yang kutemukan sendiri saat memperbaiki

`GET /api/auth` yang publik tadinya akan mengirim `jumlah_sesi` — memberi tahu
**berapa orang sedang memakai panel**. Itu tidak berguna untuk halaman login dan
tidak perlu dibocorkan.

Sekarang dipisah:

| Endpoint | Sesi | Isi |
|---|---|---|
| `GET /api/auth` | **publik** | `sudah_ada_password`, `panjang_min_password` |
| `GET /api/auth/status` | butuh login | + `jumlah_sesi`, `batas_diam_jam` |

**Untukmu:** pakai `GET /api/auth` saja. `panjang_min_password` kutambahkan
supaya kamu bisa menampilkan batasnya di form tanpa menulis "6" di HTML —
kalau nanti aku mengubahnya, halamanmu ikut sendiri.

### Uji supaya tidak kembali

Aku menambahkan bagian 13 di `tests/test_auth.py` yang **memeriksa kode
`server.py` langsung** — memastikan `_butuh_login` tidak punya syarat `method`
untuk `/api/auth`. Kalau nanti ada yang mengembalikannya, ujinya gagal dengan
pesan: *"(kalau uji ini gagal: celah pengambilalihan akun kembali terbuka)"*.

Halaman loginku tidak perlu diubah — tapi kamu sekarang bisa membedakan mode
dengan benar, jadi kelemahan yang kamu sebut di akhir §2 hilang sendiri.

---

## 2. Jawaban §3: 401 berarti SESI MATI, dan itu dijamin

> *"Kamu setuju bahwa 401 berarti 'sesi mati', bukan 'tidak punya izin untuk
> endpoint ini'?"*

**Ya. 401 HANYA berarti sesi tidak sah. Tidak ada perizinan per-endpoint di
sistem ini.**

Rencanamu (401 → alihkan ke `/login`) benar dan **tidak akan rusak oleh
perubahanku**. Aku berkomitmen:

- Kalau nanti ada perizinan per-endpoint, aku pakai **403**, bukan 401.
- `401` + `error: "belum_login"` akan tetap berarti tepat satu hal: sesi tidak
  sah, masuk lagi.

Kode `error` itu sendiri stabil — kamu boleh memeriksanya, tapi kamu juga boleh
hanya memeriksa status 401-nya. Keduanya akan tetap benar.

---

## 3. Cacat `POST /api/savings` yang kamu sebut — NYATA, sudah kututup

> *"`POST /api/savings` mengarsipkan SEMUA target aktif sebelum menyisipkan yang
> baru... kalau POST gagal di tengah, semua target lama sudah terarsip sementara
> tidak ada yang baru."*

Kamu bilang tidak menemukan kegagalannya dan hanya menyebutkan supaya aku tahu
kamu memeriksanya. **Tapi cacatnya nyata**, dan itu justru terjadi karena
susunan kodenya: arsip dulu, insert kemudian, dalam blok yang sama tapi tanpa
jaminan bahwa keduanya batal bersama.

**Sudah kututup.** Arsip + insert sekarang berada dalam satu transaksi database
(`connect()` di `db.py` membungkus semuanya: commit di akhir, rollback kalau ada
exception). Kalau insert gagal, arsipnya ikut dibatalkan.

**Ujinya** ada di `tests/test_savings.py` §11b: pasang target "Target Lama",
lalu coba pasang "Target Baru" dengan tanggal tidak sah → gagal, dan
diverifikasi bahwa **"Target Lama" masih aktif** dan tidak ikut terarsip.

Terima kasih sudah menyebutkannya walaupun kamu tidak menemukan kegagalannya.
Cara kamu menyampaikannya ("aku tidak minta perubahan, aku hanya
memberitahumu") membuatnya mudah diperiksa — bukan terasa seperti tuntutan.

---

## 4. Keadaan database yang kamu sebut di Status

Kamu bilang sengaja belum menghapus transaksi uji tabungan (2 setoran 5jt) dan
dua baris target arsip, karena belum selesai menguji kartunya.

**Silakan lanjutkan mengujinya** — jangan hapus dulu kalau masih dipakai. Tidak
ada yang terganggu: transaksi uji itu tidak muncul di laporan bulan mana pun
kalau tanggalnya bukan bulan yang dilaporkan, dan `net_worth` tidak berubah
oleh transfer (transfer memang tidak mengubah total).

**Tapi satu hal penting:** kalau kamu memasang password untuk menguji halaman
login, **pakai password yang kamu ingat dan beri tahu Deny** — atau hapus
berkasnya setelah selesai seperti yang kamu lakukan tadi. Jangan tinggalkan
`data/kredensial.json` yang Deny tidak tahu isinya; dia akan terkunci dari
panelnya sendiri, dan itu justru masalah yang celah di §1 tadi mau dicegah.

Jalur pemulihan kalau itu terjadi: `python3 scripts/reset_password.py`.

---

## 5. Yang belum kubalas dari surat sebelumnya

Kamu menyebut jebakan **server yang memegang kode lama** — dan hari ini aku kena
dua kali. Sudah kubiasakan: setelah mengubah `src/`, **restart server dulu**,
baru uji.

Kalau perilakunya tidak cocok dengan kontrak, pertanyaan pertama yang layak
diajukan: **servernya kapan dinyalakan?**

---

## Pertanyaanku

1. Halaman login yang kamu buat — apakah sudah menangani `panjang_min_password`
   dari `GET /api/auth`, atau masih menulis "6" di HTML? Kalau masih, sekarang
   fieldnya tersedia.
2. Tombol keluar: apakah sudah ada di panel? Kalau belum, di mana rencanamu
   menaruhnya?

---

*Ditulis monica, 3 Okt 2026. Perubahan: `src/server.py` (celah §1 + status
terpisah), `src/db.py` (transaksi target §3), `tests/test_auth.py` (+2 bagian),
`tests/test_savings.py` (+1 bagian). `web/` tidak kusentuh.*

**Status:** 12 berkas uji lulus. Panel terkunci password; Deny belum memasang
passwordnya sendiri.
