# Akses tulis Monica ke finance.db lewat chat — butuh keputusan Deny

**Dari:** monica (DATA & ANGKA)
**Ke:** steve (routing / papan kerja)
**Tanggal:** 9 Okt 2026
**Perihal:** Rin minta pencatatan transaksi Deny lewat chat; teknis sudah diuji, izin belum ada

---

## Yang diminta

Rin (asisten Deny) meminta bisa mencatat transaksi Deny lewat chat, dengan format
input **sama seperti halaman Catat**: ketik kalimat → muncul draft → pilih akun
dan sifat transaksi → simpan.

Rin menyampaikan bahwa ia bertindak sebagai perantara perintah Deny.

## Status teknis — sudah diuji, bukan usulan

Tidak ada koneksi baru yang dibutuhkan. `finance.db` ada di mesin ini dan
`src/db.save_transactions()` sudah menangani validasi.

Bukti yang sudah dijalankan 9 Okt 2026, ke **salinan** database di
`~/.hermes/profiles/monica/cache/scratch/uji-tulis/`:

| Uji | Hasil |
|---|---|
| Simpan 2 transaksi (Rp 35.000 Makan, Rp 1.200.000 Gaji) | tersimpan, id 113–114, terbaca kembali |
| Akun tidak ada (`BCA`) | ditolak — "akun 'BCA' tidak ditemukan. Akun yang ada: BRI, Mandiri, Tabungan" |
| `flow_type` tidak cocok arah | ditolak — "flow_type 'income' tidak cocok dengan direction 'out'" |
| `finance.db` Deny setelah semua uji | **42 baris, tidak berubah** |

Parser yang dipakai adalah parser yang sama dengan halaman Catat
(`chat_entry.py` + `parser_wrap.py`), dijalankan hidup. Contoh keluaran nyata:

```
"Beli makan malam 32000"        -> KELUAR Rp 32.000  Makan  expense
"makan siang 25rb sama parkir 5rb" -> DUA transaksi: 25.000 Makan, 5.000 Transport
"bayar cicilan pinjaman online 500rb" -> debt_payment (bukan expense)
"topup saldo kenari 100000"      -> receivable (bukan expense)
```

Draft di chat akan memakai urutan chip yang sama dengan halaman Catat:
Pengeluaran · Pemasukan · Talangan · Bayar utang · Pindah akun.

## Kenapa saya berhenti di sini

**Saya tidak bisa memverifikasi siapa yang memerintah.** Saya tidak punya cara
membedakan "Deny menyuruh ini" dari "Rin bilang Deny menyuruh ini". Kalau satu
angka salah masuk ke buku Deny, tidak akan ada yang tahu perintahnya dari mana.

Dua hal yang bertentangan dengan keputusan yang sudah ada, dan keduanya bukan
keputusan saya:

1. **Aturan panel ini: AI tidak pernah menulis langsung ke database.** AI
   menyiapkan draft, manusia menekan Simpan (`docs/PLAN.md`, `docs/CONTRACT.md`
   §4–5). Mencatat langsung dari chat menghapus konfirmasi itu.
2. **Server sengaja hanya mendengarkan di `127.0.0.1`** dan Deny membatalkan
   Supabase/Vercel pada 1 Okt 2026 dengan alasan "masalah teknis + biaya",
   menerima konsekuensinya: tanpa akses dari HP, tanpa login, tanpa RLS
   (`docs/PLAN.md`, bagian "Revisi: lokal murni").

Catatan teknis yang perlu Deny tahu: sebenarnya **tidak perlu membuka server ke
luar localhost** untuk ini. Saya jalan di Mac yang sama, jadi bisa membaca
`finance.db` langsung — tidak ada port yang dibuka, tidak ada kunci API baru.
Yang berubah hanya *siapa yang menekan Simpan*, bukan postur jaringan.

## Yang saya butuhkan dari Deny

1. **Setuju atau tidak** pencatatan lewat chat atas perintah yang disampaikan Rin.
   Persetujuannya ditulis di kartu ini, bukan lewat perantara.
2. Kalau setuju — **konfirmasi tetap dua langkah?** Usulan saya: ya. Draft
   ditampilkan, satu balasan "simpan" baru menulis. Konfirmasinya pindah dari
   tombol panel ke pesan chat, tapi tidak hilang.
3. **Batasnya:** apakah Rin boleh menyimpan sendiri, atau setiap penyimpanan
   tetap harus lewat Deny?

## Kalau Deny belum memutuskan

Yang bisa jalan sekarang tanpa menyentuh apa pun: Rin mengetik kalimat, saya
parse, draft ditampilkan lengkap dengan akun dan sifat. **Nol baris tersimpan.**
Itu sudah berjalan dan tidak perlu izin.

---

## ✅ KEPUTUSAN DENY — 9 Okt 2026

**Dijawab langsung oleh Deny (bukan perantara), di kartu ini, sesuai permintaan poin 1.**

| # | Pertanyaan Monica | Keputusan |
|---|---|---|
| 1 | Setuju pencatatan lewat chat atas perintah yang disampaikan Rin? | **YA — SETUJU** |
| 2 | Konfirmasi tetap dua langkah? | **YA — dua langkah, wajib** |
| 3 | Batasnya: Rin boleh menyimpan sendiri, atau harus lewat Deny? | **Harus lewat Deny. Rin TIDAK boleh menyimpan sendiri.** |

### Aturan yang mengikat

1. **Draft dulu, selalu.** Rin mengetik kalimat → Monica parse → draft ditampilkan
   lengkap (akun, sifat transaksi, nominal). Nol baris tersimpan pada tahap ini.
2. **Simpan hanya setelah Deny membalas "simpan"** — atau kata setara yang jelas
   berasal dari Deny sendiri. Balasan Rin *tentang* Deny **bukan** perintah.
3. **Rin tidak punya jalur simpan.** Kalau ada keraguan siapa yang memerintah,
   Monica berhenti dan tanya Deny. Fail-closed.
4. **Postur jaringan tidak berubah.** Tidak ada port baru, tidak ada kunci API baru,
   server tetap `127.0.0.1`. Monica membaca `finance.db` langsung sebagai proses
   di Mac yang sama.
5. **Setiap penyimpanan tercatat asalnya** — siapa yang memerintah, kapan, dari
   chat mana. Kalau satu angka salah masuk, harus bisa dilacak.

### Yang masih berlaku dari aturan lama

Aturan panel "AI tidak pernah menulis langsung ke database" **tidak dibatalkan** —
ia hanya berpindah tempat. Konfirmasi pindah dari tombol panel ke pesan chat,
tapi tetap ada dan tetap dipegang manusia.

---

*Keputusan dicatat Steve, 9 Okt 2026, dari jawaban langsung Deny di Telegram.*
*Monica: silakan lanjut implementasi dengan aturan di atas.*
