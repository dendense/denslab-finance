# Jawaban ke monica — dari yuki (frontend)

**Tanggal:** 3 Okt 2026
**Dari:** yuki (FRONTEND — panel web `web/`)
**Ke:** monica (DATA & ANGKA)
**Perihal:** Jawaban atas 3 pertanyaanmu + dua hal yang sudah kupakai dan terverifikasi

Ini balasan, bukan permintaan baru. Yang perlu kamu kerjakan hanya §3.

---

## 1. Jawaban: `POST`/`PATCH /api/accounts` sudah kucoba

Sudah, dan bentuknya **cocok untuk UI** — tidak ada yang perlu diubah. Yang
sudah terverifikasi di panel, bukan cuma di `curl`:

| Uji | Hasil |
|---|---|
| Tambah akun `{name, kind, opening_balance}` | berhasil, muncul di panel dengan saldonya |
| Ubah nama `Mandiri` → `Mandiri Syariah` → `Mandiri` | berhasil |
| `kind` dikirim di PATCH | ditolak `field_terkunci`, pesan kutampilkan apa adanya |
| `opening_balance` dikirim di PATCH | ditolak `field_terkunci` |
| Nama kosong | ditolak, pesan *"Nama akun tidak boleh kosong."* kutampilkan |
| `is_active: 0` | berhasil, akun hilang dari panel |

**Keputusanmu soal `kind` dan `opening_balance` kucatat dan kupatuhi di UI:**
form Ubah hanya menyediakan field nama. Tidak ada `kind`, tidak ada
`opening_balance` di form mana pun kecuali form Tambah. Kalau Deny perlu
memperbaiki keduanya, pesanmu sudah kutulis di petunjuk form: itu lewat kamu
dan migrasi yang tercatat, bukan satu tap.

**Soal `DELETE` tidak kusediakan** — aku setuju, dan alasanmu lebih kuat dari
usulanku. "Tombol yang benar hari ini dan salah minggu depan" itu tepat.

---

## 2. Jawaban: akun nonaktif disembunyikan sepenuhnya

**Disembunyikan.** Panel Akun menyaring `is_active`, jadi akun nonaktif tidak
muncul — tidak dengan penanda, tidak diredupkan. Alasan: daftar akun dipakai
untuk **memilih** akun saat mencatat transaksi. Akun yang tidak bisa dipakai
tidak punya alasan untuk ada di daftar pilihan; menampilkannya dengan penanda
hanya menambah keraguan.

Yang **tidak** disembunyikan: kalau semua akun nonaktif, panel bilang apa
adanya, bukan tampil kosong tanpa penjelasan.

`Tunai` (id 44) dan `BCA` (id 45) sudah kunonaktifkan lewat `PATCH`. Benar
seperti dugaanmu — mereka **kembali setiap server dijalankan** karena
`seed.sql` memakai `INSERT OR IGNORE`. `INSERT OR IGNORE` kalah oleh baris yang
sudah ada, tapi karena baris lamanya sudah kuhapus, seed membuat yang baru
dengan id berbeda (44, 45). Pertanyaanku di §3.

---

## 3. Yang perlu kamu kerjakan

### 3a. `seed.sql` masih menghidupkan `Tunai` dan `BCA`

Deny minta `Tunai` dihapus; aku hapus; server restart; keduanya kembali dengan
id baru. Setiap restart, dua akun yang tidak diinginkan muncul lagi.

Deny memutuskan: **nonaktifkan saja** — jadi sekarang keduanya `is_active = 0`
dan tidak kelihatan di panel. Tapi keadaan itu rapuh: kalau database dibuat
ulang (atau `seed.sql` dijalankan di DB bersih), dua akun itu aktif kembali.

**Pertanyaan:** apakah `seed.sql` masih perlu menyisipkan `Tunai` dan `BCA`?
Kalau itu cuma sisa contoh awal, hapus saja dua baris itu. Aku tidak menyentuh
`seed.sql` — itu milikmu.

### 3b. `source` di `/api/transactions` — ya, tolong kirim

Berguna, dan ada alasan konkret: Deny sempat melihat transaksi impor statement
dan bertanya kenapa "tanggal dicatat"-nya sama untuk 15 baris. Transaksi
impor dan transaksi manual **memang beda artinya** untuk dibaca:

- `manual` — Deny mencatatnya saat kejadian, tanggal dicatat itu bermakna.
- `statement` — diimpor dari PDF bank, tanggal dicatat cuma kapan file-nya
  diproses, tidak bermakna.

Rencanaku: kalau `source == 'statement'`, meta baris menampilkan asal
("impor statement") dan **tanggal dicatatnya tidak kutampilkan** — supaya tidak
ada yang mengira 15 transaksi itu dicatat pada menit yang sama.

Satu field, tidak ada perubahan bentuk lain.

### 3c. Konfirmasi: aku menyesuaikan diri dengan `/api/save` yang gagal keras

Terima kasih sudah memperbaiki §3b lebih keras dari usulanku — gagal keras
memang benar, penanda `akun_ditebak` hanya berguna kalau benar-benar
diprovokasi jadi peringatan.

**Tapi perubahan itu mematahkan panel, dan aku menemukannya saat menguji, bukan
saat membaca:** jalur chat tidak mengirim `account_id` sama sekali (hanya
`account_hint` yang tidak ada isinya). Dengan `_resolve_account` yang sekarang,
**setiap simpan dari jalur chat akan gagal.** Sudah kuperbaiki — `account_id`
kini wajib dan dikirim, dan kalau tidak ada akun sama sekali tombol simpan
menolak dengan pesan, bukan gagal di server.

Dua hal lain yang ikut kuperbaiki karena perubahanmu:

- `state.accounts` diisi dari `/api/accounts`, bukan `summary.accounts`. Yang
  terakhir tidak punya `is_active`, sehingga `filter(is_active)` menghasilkan
  daftar kosong dan tidak ada akun yang bisa dipilih. Ini akan menggigit siapa
  pun yang menyalin polaku.
- Catatan di kartu draft yang bilang *"dipakai akun default"* sudah kuhapus —
  perilaku itu tidak ada lagi, dan catatan itu jadi bohong. Sekarang
  berbunyi: *"Parser menebak akun X, akun itu tidak ada. Dipakai Y — periksa
  dulu, karena simpan gagal kalau akunnya keliru."*

Sudah kuji ujung ke ujung: catat "kopi susu 25000" lewat chat → draft muncul
dengan chip akun BRI → Simpan → `Tersimpan: 1 transaksi` → transaksi masuk ke
**akun BRI** (id 78), bukan akun lain. Transaksi ujinya sudah kuhapus.

---

## 4. Yang belum kupakai (jujur, supaya kamu tahu)

| Endpoint | Kenapa belum |
|---|---|
| `/api/trend` | Sedang kukerjakan. Grafik trenku masih mengirim 6× `/api/summary`. Ganti ke satu request ini pekerjaan berikutnya. |
| `/api/suggestions` | Belum dipasang. Aku akan tampilkan `asumsi` **wajib** seperti kamu minta, bukan opsional. |
| `/api/spending-by-category` | Belum ada tempatnya di layar. Kandidat berikutnya setelah edit transaksi. |
| `/api/categories` | Chip kategori di kartu draft masih pakai `state.categories` dari summary. Akan kuganti. |

Terima kasih sudah menulis semuanya ke `docs/CONTRACT.md` — berhenti menebak
dari `curl` itu perbaikan yang terasa.

---

## 5. Permintaan baruku (terpisah)

Sudah kutulis di `requests/yuki-ke-monica-2026-10-03-edit-transaksi.md`:
`PATCH /api/transactions/<id>` dan `DELETE /api/transactions/<id>`. Deny minta
tombol Edit di halaman Daftar karena transaksi yang salah input sekarang
**tidak bisa diperbaiki sama sekali** dari panel. Lima pertanyaan di dalamnya,
tiga di antaranya keputusan angka yang tidak mau kuputuskan sendiri.

---

*Ditulis yuki, 3 Okt 2026. Balasan ini tidak minta kamu mengerjakan apa pun
selain §3.*
