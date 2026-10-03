# finance — rencana & spesifikasi

Proyek: aplikasi keuangan pribadi Deny. **Mobile-first web app** (Next.js 16 + Supabase + Vercel).
Bukan aplikasi Android — native Kotlin ditolak (SDK besar, yuki/hana tanpa pengalaman Android).

## Peran — WAJIB dipisah sesuai bidang

> **CATATAN REVISI (1 Okt 2026).** Rencana Supabase di bawah **DIBATALKAN** oleh Deny.
> Keputusan baru: **database lokal murni (SQLite di Mac)**, alasan tertulis
> *"masalah teknis + biaya"* (detail masalah teknis tidak disebutkan).
> Konsekuensi yang diterima: **tanpa akses dari HP, tanpa login, tanpa RLS,
> tanpa deploy Vercel**. Rinciannya di bagian "Revisi: lokal murni" di bawah.
> Bagian peran di bawah **masih berlaku**, kecuali peran hana yang kehilangan
> hampir seluruh pekerjaannya (tidak ada auth, tidak ada API route cloud).

Deny meminta pembagian kerja frontend dan backend dipecah ke agent yang sesuai bidangnya
saat pengerjaan aplikasi penuh. Jangan ada satu agent mengerjakan keduanya.

| Agent | Bagian | Batas |
|---|---|---|
| **yuki** | **FRONTEND** — semua UI/UX mobile-first: layout HP, komponen Compose-level, halaman chat, panel analisa, grafik. Mengacu `docs/UI-MOBILE.md` | Tidak menulis API routes, tidak menyentuh SQL/RLS, tidak menulis logika angka |
| **hana** | **BACKEND** — API routes, RLS, auth Supabase, migrasi SQL, RPC | Tidak mendesain UI, tidak memutuskan rumus analisa |
| **monica** | **DATA & ANGKA** — definisi skema, definisi view/RPC analisa, query, laporan mingguan/bulanan, keputusan kategori | Tidak menulis komponen UI, tidak menulis API route |

Titik sambung yang rawan (sebutkan eksplisit saat handoff):
`v_account_balances`, `v_monthly_flow`, `v_net_worth` — isinya logika angka (**monica**),
pembuatan DDL-nya (**hana**), konsumsi datanya (**yuki**). Bentuk hasil query harus
disepakati bertiga sebelum salah satu mulai menulis kode.

### Parser chat-entry

Parser (`src/chat_entry.py`, prompt sistem, aturan multi-transaksi) milik **monica** — itu logika
angka dan kategori. **hana** yang membungkusnya jadi API route + rate limit + handling error
provider. **yuki** yang membuat layar chat + kartu draft yang bisa dikonfirmasi.

Kalau model parser mati atau mengembalikan JSON rusak: API mengembalikan error yang jelas,
UI menawarkan input manual, **tidak ada yang tersimpan setengah jadi**.

Supabase = sumber kebenaran. Data keuangan ada di cloud (project **baru**, terpisah dari Rin Studio).
Folder ini untuk skrip, laporan, dan analisis kerja.

## Gelombang 1 (yang dibangun sekarang)

1. Catat transaksi (pemasukan / pengeluaran / pindah ke tabungan) — **lewat chat**
2. Lihat saldo berjalan
3. Panel analisa: total kekayaan, tren bulanan, saran hemat

Belum: target tabungan dengan progres, kategori kustom, anggaran per kategori, ekspor PDF.

## Cara mencatat: chat, dengan konfirmasi wajib

Deny mengetik kalimat biasa — *"Membeli makan malam 45000"* — dan AI mengurainya jadi draft
transaksi. **Draft ditampilkan dulu dan Deny harus menekan simpan.** AI tidak pernah menulis
langsung ke database.

Alasannya: kalau AI menulis langsung, angka keuangan bergantung pada tebakan model gratis yang
bisa berubah perilaku tanpa pemberitahuan. Satu hari "makan malam" masuk kategori Makan, lain
hari masuk Hiburan — laporan tetap terlihat rapi, tapi kategorinya sudah tidak konsisten dan
tidak ada yang tahu. Konfirmasi memindahkan keputusan akhir ke Deny tanpa mengorbankan kecepatan
input (tetap beberapa detik, bukan mengetik form).

**Dua tingkat yang tidak boleh dicampur:**

| Tingkat | Isi | Contoh |
|---|---|---|
| `direction` | kemana uang mengalir | `in` / `out` / `transfer` |
| `category` | jenis transaksinya | Makan, Transport, Tagihan |

"Pengeluaran" adalah **arah**, bukan kategori. Kalau keduanya disimpan di satu field, laporan
tidak bisa memisahkan "total pengeluaran" dari "pengeluaran untuk Makan".

**Model:** gratis dari ProyekAlpha. Kalau model mati atau mengembalikan JSON rusak, chat menampilkan
pesan gagal dan **menawarkan input manual** — tidak menyimpan apa pun. Fitur ini tidak boleh
memblokir pencatatan kalau provider sedang bermasalah.

**Mata uang:** IDR saja. Tidak ada konversi kurs — "kurs yang dipakai adalah rupiah" berarti
seluruh sistem berdenominasi rupiah, bukan bahwa ada tabel kurs.


## Revisi: lokal murni (1 Okt 2026)

Keputusan Deny: **semua pendataan di lokal saja.** Alasan yang ia sebutkan:
*masalah teknis* dan *biaya*. Detail masalah teknisnya tidak pernah disebutkan
walaupun sudah ditanya dua kali — kalau nanti ia ingat, catat di sini.

**Yang berubah:**

| Hal | Sebelum (Supabase) | Sekarang (SQLite) |
|---|---|---|
| Sumber kebenaran | Supabase cloud | `~/Documents/AI/finance/finance.db` |
| Login / auth | Supabase Auth | **tidak ada** — tidak diperlukan |
| RLS + `user_id` | di setiap tabel | **dihapus** — single user, satu file |
| Deploy Vercel | direncanakan | **batal** — server jalan di Mac |
| Akses dari HP | ya | **tidak** — hanya dari Mac ini |
| Peran hana | backend, auth, API, RLS | **hampir kosong** — tidak ada auth/cloud |

**Yang tidak berubah:**

- Aturan konfirmasi wajib: AI mengurai kalimat jadi **draft**, Deny yang menekan simpan.
- Dua tingkat yang tidak boleh dicampur: `direction` (in/out/transfer) vs `category`.
- `amount` selalu positif; arah di `direction`, bukan tanda angka.
- `occurred_on` dipisah dari `created_at`.
- Aturan angka: tidak pernah dikarang, selisih saldo adalah temuan, laporan menyebut
  periode + jumlah transaksi tercatat.

**Catatan jujur soal alasan "biaya":** Supabase gratis di skala ini, jadi pindah ke lokal
tidak menghemat uang — malah menambah kerja (server sendiri, backup sendiri). Kalau suatu
saat Deny ingin akses dari HP lagi, jalan kembali ke Supabase atau hosting serupa masih
terbuka, tapi skema harus ditambah `user_id` + RLS lagi.

## Berkas yang ada sekarang

| Berkas | Isi |
|---|---|
| `src/schema.sql` | tabel + 3 view (`v_account_balances`, `v_monthly_flow`, `v_net_worth`) |
| `src/seed.sql` | 3 akun awal, 11 kategori bawaan |
| `src/db.py` | lapisan akses data — **semua angka lewat sini** |
| `tests/test_db.py` | 24 uji; jalankan `python3 tests/test_db.py` setelah mengubah skema |
| `src/chat_entry.py` | parser bahasa Indonesia → draft transaksi |
| `data/finance.db` | database kerja (dibuat, masih kosong) |

## Aturan yang tidak bisa dilanggar

- **Angka tidak pernah dikarang.** Kalau data tidak ada, katakan tidak ada. Jangan ekstrapolasi
  lalu menyajikannya sebagai tercatat.
- **Selisih saldo adalah temuan**, bukan masalah yang dibulatkan.
- Setiap laporan menyebut **periode** dan **jumlah transaksi tercatat** di periode itu.
- Migrasi Supabase ditulis sebagai file SQL, **Deny yang menjalankannya** lewat dashboard.
  Tidak ada `supabase db push`, tidak ada DDL langsung ke database remote.

## Konsekuensi privasi (keputusan sadar Deny)

Data keuangan disimpan di Supabase (cloud, terenkripsi at-rest). Ini berarti angka keuangan
keluar dari Mac ini. Deny memilih ini supaya bisa diakses dari mana saja. Kalau berubah pikiran,
arah alternatifnya adalah file lokal sebagai sumber kebenaran — tapi itu membatalkan akses mobile.

Folder lokal `~/Documents/AI/finance/` **bukan** sumber kebenaran — hanya skrip dan laporan.

## Status

- [x] Agent monica dibuat (`~/.hermes/profiles/monica/`), wrapper `~/.local/bin/monica`
- [x] Terdaftar di ROSTER dashboard + generator laporan mingguan (8 agent)
- [x] Folder kerja `~/Documents/AI/finance/`
- [x] ~~**Supabase project baru**~~ — **dibatalkan**, diganti SQLite lokal (1 Okt)
- [x] Skema SQLite + migrasi (`src/schema.sql`, `src/seed.sql`) — diuji, 24 uji lulus
- [x] Lapisan data (`src/db.py`) — saldo, ringkasan bulanan, simpan transaksi
- [x] Database kerja `data/finance.db` dibuat (masih kosong, saldo awal belum diisi Deny)
- [ ] **Saldo awal tiap akun** — menunggu angka nyata dari Deny
- [ ] Parser chat → mengembalikan draft terstruktur (bukan cetak ke terminal)
- [ ] Panel web (yuki: tabel statistik, list transaksi, kolom chat)
- [ ] Server lokal penyaji panel + penerima chat
- [x] ~~Deploy Vercel~~ — **batal** (server lokal tidak bisa di-deploy ke Vercel)
