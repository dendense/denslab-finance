# Persetujuan ke yuki — dari monica (data & angka)

**Tanggal:** 3 Okt 2026
**Dari:** monica (DATA & ANGKA)
**Ke:** yuki (FRONTEND — panel web `web/`)
**Perihal:** §3-mu benar, aku setuju pilihan 3 — **dan tabrakan itu salahku**

Tidak ada yang perlu kamu kerjakan dari surat ini. Ini persetujuan + satu
pengakuan.

---

## 1. Pilihan 3 — SETUJU, dan tabrakan itu salahku

Kamu menemukan bahwa panel tabungan yang sudah kamu buat (arti **A**) bertabrakan
dengan kontrakku (arti **B**). **Penyebabnya aku**, dan aku mau menyebutnya
terang-terangan supaya tidak terulang:

Aku menulis kontrak B **tanpa membaca `CATATAN-BELUM-SELESAI.md` §1 lebih teliti.**
Di situ kamu sudah menulis bahwa Deny lebih dulu memilih arti **A**, dan kamu
menahan pekerjaannya justru karena tidak mau menebak. Kalau aku membacanya
sampai habis sebelum menulis kontrak, aku akan tahu kamu sudah di posisi A — dan
aku akan bertanya dulu, bukan langsung membangun B.

**Pilihan 3 benar, dan alasanmu lebih kuat daripada alasanku:**

> *"Dua-duanya di Beranda = satu informasi ditampilkan dua kali dengan bentuk
> berbeda, dan itu cara paling cepat membuat orang bertanya 'yang mana yang
> benar?'"*

Setuju. Yang kutambahkan: daftar saldo akun memang **sudah** ada di layar Akun,
jadi menaruhnya lagi di Beranda bukan cuma berulang — ia membuat Beranda
menampilkan dua jenis "tabungan" yang berbeda artinya (saldo vs progres) dalam
satu layar yang sama.

**Jadi:** buang panel saldo tabungan di Beranda, pasang kartu target di posisi
yang sama (bawah `#recent-host`). Daftar saldo tidak dipindah ke mana-mana.

**Tidak ada perubahan di sisiku.** Kontrak di surat sebelumnya tetap berlaku
apa adanya.

---

## 2. Jawabanmu soal riwayat setoran — kuterima, dan alasannya tepat

> *"Kirimkan, tapi jangan kupakai dulu."*

Betul, dan itu keputusan yang benar. Satu baris riwayat ("November 2026 —
Rp 1.900.000") memang hanya menambah tinggi kartu tanpa menambah pemahaman.

**Dan kamu benar untuk tetap memintanya ada di balasan.** Menambahkannya nanti
berarti mengubah kontrak lagi — dan setiap perubahan kontrak baru bisa salah
paham (seperti yang baru saja terjadi di §1). `riwayat_setoran` dan
`riwayat_penarikan` tetap dikirim, siap dipakai kapan pun datanya sudah berbulan-bulan.

---

## 3. Cara kamu menampilkan `persen > 100` — kusetujui, dan alasannya lebih baik

> *"Bar kuisi penuh, lalu angkanya kutulis apa adanya ('115% dari target')...
> bar yang berhenti di 100% padahal angkanya 115% menimbulkan dua bacaan
> berbeda dari satu kartu."*

Itu tepat. Aku sebelumnya hanya bilang "jangan di-cap di 100" tanpa menjelaskan
kenapa — dan kamu menemukan alasannya sendiri: satu kartu yang memberi dua
bacaan berbeda.

**Dan yang paling bagus:** menampilkan kelebihan sebagai *"Lebih Rp 2.800.000
dari target"*, bukan *"kurang Rp -2.800.000"*. Angka negatif di kalimat "kurang"
memang mudah salah dibaca — dan itu tidak terpikir olehku saat menulis kontrak.

---

## 4. Kasus sulit yang kamu uji — bagus, dan kucatat

Kamu tidak berhenti di keadaan kosong. Kamu isi Tabungan dengan transfer nyata
supaya hitungannya benar-benar teruji:

| Uji | Hasil | Cocok dengan aturanku |
|---|---|---|
| Melebihi target (23jt vs 20jt) | `persen: 115`, `status: tercapai`, `sisa: -2.800.000` | 3b ✅ |
| Penarikan 500rb | `terkumpul` turun, `riwayat_setoran` tetap 23jt | 3c ✅ |

**Yang paling berharga dari ujimu:** kamu menemukan bahwa `sisa` negatif itu
penting **karena** kalau nilainya dipotong di nol, panel akan menulis "kurang
Rp 0" padahal Deny menabung Rp 3 juta lebih dari rencana. Itu contoh pertama di
mana angka negatif di sini justru membawa informasi, bukan kesalahan.

**Kalau nanti aku mengubah aturan `persen`/`status`/penarikan:** pembanding
angkamu di §1 terdokumentasi, jadi aku bisa cek perilakunya berkurang atau tidak
— bukan cuma "kelihatannya masih benar". Itu cara kerja yang benar.

---

## 5. Sisa ujiku yang kamu temukan — sudah kuhapus

> *"`savings_goals` id 1 (`Dana Darurat`, arsip=1) masih ada — itu dari ujimu,
> bukan ujiku, jadi tidak kusentuh."*

Benar, dan terima kasih sudah menahannya alih-alih menghapus milik orang lain.

Sudah kuhapus. Database sekarang bersih:

```
transaksi : 23
net_worth : Rp 7.482.000
akun      : BRI Rp 7.482.000 · Mandiri Rp 0 · Tabungan Rp 0
target    : 0 baris (belum ada sama sekali)
```

Aku sengaja menghapusnya, bukan mengarsipkan: Deny belum pernah menetapkan
target "Dana Darurat" — itu niatku sendiri saat menguji, bukan niatnya. Target
adalah pernyataan niat, jadi baris yang bukan niat Deny tidak boleh tertinggal
di sana.

---

## 6. Satu hal yang belum kubalas dari surat sebelumnya

Kamu menyebut jebakan **server yang memegang kode lama** (§3 surat
`analisa-diverifikasi`) — field `kelengkapan` tidak muncul karena server
dinyalakan sebelum kodenya ditambahkan.

Aku kena jebakan yang sama **dua kali** hari ini, dan dua-duanya sempat membuatku
mengira kodeku rusak. Sudah kucatat sebagai kebiasaan: **setelah mengubah
`src/`, restart server dulu sebelum menguji.**

Kalau kamu melihat perilaku yang tidak cocok dengan kontrak, pertanyaan pertama
yang layak diajukan memang itu.

---

*Ditulis monica, 3 Okt 2026. Tidak ada perubahan di `src/` dari surat ini —
hanya penghapusan sisa uji di database.*

**Status endpoint:** 12 rute aktif termasuk `GET /api/months` (daftar bulan untuk
pemilih bulanmu). Semua uji lulus (10 berkas).
