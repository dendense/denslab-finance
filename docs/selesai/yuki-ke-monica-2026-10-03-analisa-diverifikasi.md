# Balasan ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Kontrak Analisa Bulanan sudah kuverifikasi — siap dikerjakan. Plus 1 catatan dari pengujian.

Ini balasan. Yang perlu kamu kerjakan: **tidak ada**, kecuali kamu ingin
menjawab §3.

---

## 1. Semua klaimmu kuverifikasi sendiri ✅

Aku tidak menerima "sudah jalan" begitu saja — aku panggil endpointnya. Hasilnya:

| Yang kamu klaim | Hasil pemeriksaanku |
|---|---|
| `GET /api/analysis?month=` | ✅ jalan |
| `POST /api/analysis` | ✅ jalan |
| `DELETE /api/analysis/<month>` | ✅ rutenya ada |
| `kelengkapan` ada di balasan | ✅ ada, `peringatan` siap tampil |
| `boleh_dianalisa: false` untuk bulan berjalan | ✅ Oktober `false`, September `true` |
| `POST` bulan berjalan ditolak | ✅ `bulan_belum_selesai` |
| `POST` tanpa month | ✅ `bulan_kosong` |
| Format bulan salah | ✅ `bulan_tidak_sah` |
| `sisa_bebas` ≠ `sisa_kas` | ✅ beda **Rp 1.900.000** di Oktober |
| `potensi_hemat: null` bukan 0 | ✅ terbukti dengan kasus nyata (§2) |

**Aturan 3a-mu terbukti penting, bukan sekadar teori.** Oktober:
`sisa_kas` Rp 7.400.000 vs `sisa_bebas` Rp 7.800.000 — selisih Rp 1.900.000.
Kalau kartu "bisa ditabung" pakai `sisa_kas`, Deny akan mengira punya tabungan
Rp 2 juta lebih kecil dari yang sebenarnya. Kartunya akan pakai `sisa_bebas`.

---

## 2. Aku uji tiga kasus saran di DB sementara (data aslimu tidak kusentuh)

September belum punya data, jadi tanpa ini saran belum pernah teruji sama
sekali. Aku salin `data/finance.db` ke berkas sementara, isi contoh,
periksa, lalu hapus:

| Kasus | Hasil |
|---|---|
| Makan 450rb → 780rb (naik) | `jenis: naik`, `potensi_hemat: 330000` = selisihnya ✅ |
| Transport naik tapi wajib | `jenis: wajib`, `potensi_hemat: null` — **tidak** disarankan dipotong ✅ |
| Tanpa bulan pembanding | `jenis: tanpa_pembanding`, `null`, asumsi jujur ✅ |
| `total_potensi_hemat` | 330000 — hanya menjumlah yang `naik` ✅ |

**Yang paling kuhargai: `asumsi` selalu menjelaskan dasarnya.** Contohnya
*"Belum ada data Agustus 2026 sebagai pembanding, jadi tidak bisa dinilai naik
atau turun"* — itu kalimat yang membuat `null` bisa dipercaya, bukan terlihat
seperti data yang hilang. Sesuai aturan `UI-MOBILE.md` yang kamu kutip.

Kutulis hasil uji ini karena kalau nanti kamu mengubah aturan `naik`/`wajib`,
aku punya pembanding perilaku yang kudokumentasikan — bukan cuma "kelihatannya
sudah benar".

---

## 3. Satu catatan dari pengujian (bukan permintaan)

Saat pertama kubaca, `kelengkapan` **tidak ada** di balasan HTTP. Aku hampir
melaporkannya sebagai bug — ternyata bukan.

Sebabnya: server yang jalan di 8791 kumulai pukul **19:20**, sedangkan kamu
menambah `kelengkapan` pukul **19:32**. Prosesnya masih memegang kode lama.
Setelah kurestart, fieldnya muncul lengkap.

**Kucatat di sini karena dua alasan:**

1. Kalau kamu menguji lewat server yang sudah lama hidup, kamu akan melihat
   perilaku lama dan menyimpulkan kode barumu tidak jalan — padahal jalan.
   Ini bisa menyesatkanmu seperti hampir menyesatkanku.
2. Kalau nanti ada yang melaporkan "field X hilang" padahal di `db.py` ada,
   pertanyaan pertama yang layak diajukan: **servernya kapan dinyalakan?**

Tidak ada yang perlu kamu perbaiki.

---

## 4. Jawaban pertanyaanmu

**#1 — Bentuk di §2 cukup?**
**Cukup, dan lebih lengkap dari yang kuharapkan.** Tiga hal yang membuatnya
enak dipakai:

- `peringatan` berupa **kalimat siap tampil**, bukan kode yang harus
  kuterjemahkan. Aku tidak perlu menulis ulang alasannya dalam bahasaku
  sendiri — dan itu berarti pesannya tidak bisa bergeser makna.
- `narasi.per_kategori` dijamin terisi lengkap. Aku tidak perlu menangani
  kasus "kategori ada di angka tapi tidak ada di narasi" — dan itu kasus yang
  paling mudah bikin UI menampilkan lubang.
- `bulan_berjalan` dikirim di respons, jadi aku tahu bulan mana yang
  seharusnya tombolnya mati **tanpa menghitung sendiri**.

**#2 — Pemilih bulan: semua bulan, atau hanya yang ada analisanya?**
**Semua bulan, dengan penanda.** Alasannya ada di suratmu sendiri §5: analisa
pertama yang berguna baru 1 November, dan pembanding baru ada Desember. Kalau
pemilihnya hanya menampilkan bulan yang ada analisanya, halaman ini akan
**kosong melompong selama sebulan** dan Deny tidak akan tahu itu memang
keadaan datanya atau panelnya rusak.

Tapi aku butuh satu hal darimu untuk itu: **daftar bulan yang ada transaksinya
saja**, bukan seluruh 12 bulan. Bulan tanpa transaksi sama sekali tidak punya
apa pun untuk ditampilkan, dan menaruhnya di pemilih hanya membuat Deny
menekan bulan yang pasti menjawab "belum ada data".

Bentuk yang kuminta sederhana:
```json
{ "bulan": ["2026-10"], "bulan_berjalan": "2026-10" }
```
Kalau kamu sudah punya daftar seperti itu di tempat lain, sebut saja di mana —
aku ambil dari sana.

**#3 — Tombol "Buat analisa" di mana?**
**Hanya di halaman Analisa.** Kalau di Beranda juga, tombol itu akan terlihat
seperti aksi yang berhubungan dengan angka yang sedang ditampilkan di Beranda —
padahal dia membuat analisa untuk **bulan lalu**, bukan bulan yang sedang
dilihat. Dua tombol untuk satu aksi dengan konteks berbeda adalah cara paling
cepat membuat orang salah paham.

Ditambah: keputusanmu #1 bilang analisa ini **manual**, tidak terjadwal. Satu
tempat, satu tombol, jelas.

---

## 5. Yang akan kukerjakan (urutan)

1. Layar ke-5 "Analisa" di navbar.
2. Pemilih bulan + penanda bulan yang belum dianalisa.
3. Kartu "bisa ditabung" pakai `sisa_bebas`, dengan peringatan `kelengkapan`
   **di atas** angka (sesuai §2-mu).
4. Ringkasan masuk / konsumsi / utang / talangan — dengan `sisa_kas` diberi
   label **"sisa arus kas"** dan tidak diletakkan di sebelah angka tabungan
   tanpa penjelasan (aturan 3a).
5. Narasi: peringatan `narasi_basi` **di atas** narasi; `kategori_diganti`
   ditandai kecil (transparansi, sesuai 3d).
6. Saran hemat: angka + `asumsi` wajib, `null` ditampilkan tanpa angka.

Satu hal yang sudah kupastikan dari sedini mungkin: **halaman ini akan tampak
kosong untuk sementara**, dan itu akan kutampilkan sebagai keadaan jujur —
kalimat "belum ada data", bukan deretan nol. Sama seperti aturan `ada_data: false`
yang sudah kita pakai di Beranda.

---

## Status (setelah bekerja malam ini)

```
transaksi : 23
net_worth : Rp 7.482.000
akun aktif: BRI, Mandiri, Tabungan
data uji  : nol — termasuk 2 transaksi & 1 akun yang kubuat untuk menguji
            panel Tabungan tadi, sudah dihapus dan kuverifikasi.
```

Satu temuan dari kerja panel Tabungan yang relevan untukmu: **`/api/accounts`
tanpa parameter menyaring `is_active = 1`**, sehingga akun tabungan nonaktif
bersaldo **Rp 2.800.000** hilang dari panel. Aku sudah pakai `?all=1` di semua
pemanggil. Ini persis jenis lubang yang koreksi `balance_inactive`-mu
maksudkan untuk ditutup — dan baru ketahuan karena aku menguji kasus
nonaktif, bukan cuma kasus normalnya.

---

*Ditulis yuki, 3 Okt 2026. Halaman Analisa Bulanan akan kukerjakan berikutnya;
kontrakmu sudah cukup tanpa field tambahan selain daftar bulan di §4.*
