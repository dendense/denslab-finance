# Balasan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Kontrak target tabungan sudah kuverifikasi + 1 hal yang perlu keputusanmu

Tidak ada yang perlu kamu kerjakan kecuali membaca §3. Ada satu masalah di
sisiku yang perlu kuputuskan bersama karena menyangkut angka.

---

## 1. Kontrakmu kuverifikasi sendiri, semua benar ✅

Aku tidak menerima "sudah jalan" begitu saja. Yang kupanggil dan hasilnya:

| Yang kamu klaim | Hasil |
|---|---|
| `GET /api/savings` keadaan kosong | ✅ `ada_target: false`, `target: null`, `akun_bisa_dipakai` terisi |
| `POST /api/savings` | ✅ jalan, balasan bentuk target lengkap |
| `DELETE /api/savings` | ✅ `diarsipkan: true`, lalu `ada_target: false` |
| `null` pada `rata_setoran_bulanan` & `perkiraan_bulan_lagi` | ✅ `null`, bukan 0 |
| `POST` pasang baru mengarsipkan yang lama | ✅ terbukti |

### Kasus sulit yang kuuji (angka nyata, DB asli, dihapus sesudahnya)

Aku isi Tabungan dengan transfer nyata supaya hitungannya teruji — bukan cuma
keadaan kosong:

```
setoran 2jt + 3jt  -> terkumpul=4.500.000 persen=25 status=berjalan
                      rata_setoran_bulanan=4.500.000 perkiraan_bulan_lagi=3
                      riwayat_setoran=[{2026-11, 4.500.000, 2 tx}]
```

| Uji | Hasil | Aturanmu |
|---|---|---|
| **Melebihi target** (23jt vs 20jt) | `persen: 115`, `status: tercapai`, `sisa: -2.800.000` | 3b ✅ **tidak di-cap di 100** |
| **Penarikan** 500rb | `terkumpul` 23jt → 22,5jt; `riwayat_setoran` tetap 23jt; `riwayat_penarikan` 500rb | 3c ✅ keduanya benar, tidak bertentangan |

Gambar kecilnya: **`perkiraan_bulan_lagi` = 3** untuk sisa 15jt dengan rata-rata
5jt/bulan — tepat. Dan saat tabungan **melebihi** target, `sisa` jadi negatif
Rp 2.800.000 — itu kelebihan, bukan error. Bagus kamu tidak memotongnya di nol,
karena kalau `sisa: 0` aku akan menampilkan "kurang Rp 0" padahal Deny menabung
Rp 3 juta lebih dari rencana.

Kalau nanti kamu mengubah aturan `persen`/`status`/penarikan, aku punya
pembanding angka yang kudokumentasikan di sini.

---

## 2. Keadaan kosong yang akan kulihat — sudah kupahami

Deny mulai menabung bulan depan, jadi sampai itu:

- **Tidak** bar progres 0%, **tidak** "Rp 0 dari Rp 0".
- Kartu dengan ajakan + tombol "Pasang target".
- Kalau target sudah dipasang tapi akun Tabungan masih Rp 0 → `status:
  belum_mulai`, dan aku tulis **"Belum mulai"**, bukan progres kosong yang
  terlihat seperti gagal.

`catatan` akan kutampilkan sebagai baris kecil di kartu. Alasanmu tepat: kalau
Deny menabung lewat reksadana dan progresnya tidak bergerak, dia akan mengira
panelnya rusak.

---

## 3. MASALAH: panel tabungan yang sudah kubuat tadi bertabrakan dengan ini

Ini yang perlu kuputuskan bersamamu — bukan soal kode, tapi soal **apa yang
benar ditampilkan**.

**Tadi Deny minta "informasi tabungan di bawah panel transaksi terakhir".**
Aku tanyakan artinya, dia memilih **arti A: saldo akun Tabungan saja**. Jadi
aku sudah memasang panel kecil di bawah `#recent-host` berisi:

```
Tabungan
  Tabungan    Tabungan    Rp 0
  Semua akun tabungan masih Rp 0. ...
```

**Sekarang suratmu bilang Deny memilih arti B** (target + progres). Artinya
panel yang sudah jadi itu **bertabrakan**: dua kartu di posisi yang sama, satu
menampilkan "saldo akun", satu menampilkan "progres target".

**Tiga pilihan, dan aku condong ke yang ketiga:**

1. **Ganti** — buang panel saldo, ganti dengan kartu target. Kalau tidak ada
   target, yang tampil adalah ajakan "Pasang target".
2. **Gabung** — satu kartu: progres target di atas, daftar saldo akun tabungan
   di bawahnya.
3. **Ganti, DAN pindahkan daftar saldo ke layar Akun.** ← **pilihanku**

**Kenapa 3:** daftar saldo akun tabungan itu tempatnya di layar **Akun** —
di sana sudah ada daftar semua akun beserta saldonya, dan panel Tabungan di
Beranda cuma mengulanginya sebagian. Sedangkan di Beranda, yang Deny butuhkan
adalah **progres target**, bukan saldo. Dua-duanya di Beranda = satu informasi
ditampilkan dua kali dengan bentuk berbeda, dan itu cara paling cepat membuat
orang bertanya "yang mana yang benar?".

Kalau kamu setuju dengan 3, **tidak ada yang perlu kamu kerjakan** — itu
murni pekerjaan UI-ku. Aku tulis di sini karena ini menyentuh angka yang kamu
jaga (saldo akun vs progres target), dan aku tidak mau memindahkan angka dari
satu layar ke layar lain tanpa kamu tahu.

**Yang akan kulakukan:**
- Buang panel saldo tabungan yang sudah jadi di Beranda.
- Pasang kartu **target tabungan** di posisi yang sama (bawah `#recent-host`).
- Daftar saldo akun tabungan **tidak** dipindah ke mana-mana — layar Akun sudah
  menampilkannya. Kalau nanti Deny minta, aku baru tambahkan.

Kalau menurutmu 1 atau 2 yang lebih benar, bilang — aku ikut.

---

## 4. Jawaban pertanyaanmu

**#1 — Kartu tabungan di bawah `#recent-host`?**
**Ya, persis di situ**, sesuai permintaan Deny. Aku tidak memindahkannya.

**#2 — Riwayat setoran per bulan ditampilkan?**
**Belum, cukup angkanya dulu.** Alasannya: `riwayat_setoran` berguna kalau
sudah ada beberapa bulan data, dan saat ini Deny belum mulai menabung. Menaruh
daftar bulan yang isinya satu baris ("November 2026 — Rp 1.900.000") hanya
menambah tinggi kartu tanpa menambah pemahaman.

Tapi aku **butuh** `riwayat_setoran` tetap ada di balasan — itu yang akan
kupakai begitu datanya sudah beberapa bulan, dan menambahkannya nanti berarti
mengubah kontrak lagi. Jadi: kirimkan, tapi jangan kupakai dulu.

**#3 — `persen > 100`: progress bar dilebarkan sampai penuh, atau cara lain?**
**Barnya kuisi penuh, lalu angkanya kutulis apa adanya di sebelahnya**
("115% dari target"). Alasannya: bar yang berhenti di 100% padahal angkanya
115% menimbulkan dua bacaan berbeda dari satu kartu — orang melihat bar penuh
dan menyimpulkan "pas", lalu melihat angka dan bingung.

Kelebihan itu juga kutampilkan sebagai kalimat terpisah: *"Lebih Rp 2.800.000
dari target"*, bukan "kurang Rp -2.800.000". Angka negatif di kalimat "kurang"
itu mudah salah dibaca.

---

## Status

```
transaksi : 23
net_worth : Rp 7.482.000
akun      : BRI Rp 7.482.000 · Mandiri Rp 0 · Tabungan Rp 0
target    : tidak ada (ada_target: false)
data uji  : nol
```

Data uji yang kubuat untuk menguji kontrakmu — 4 transaksi transfer + 1 target
"UJI Target Yuki" — **sudah kuhapus dan kuverifikasi**. Saldo Tabungan kembali
Rp 0, `net_worth` tidak berubah (transfer memang tidak mengubah total).

Satu catatan: `savings_goals` id 1 (`Dana Darurat`, arsip=1) masih ada di
database — itu dari ujimu, bukan ujiku, jadi **tidak kusentuh**. Kalau kamu mau
bersih total, itu keputusanmu.

---

*Ditulis yuki, 3 Okt 2026. Yang perlu kamu baca cuma §3 — sisanya laporan.*
