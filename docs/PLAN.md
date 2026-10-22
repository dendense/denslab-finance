# finance — rencana & spesifikasi

Proyek: aplikasi keuangan pribadi Deny. **Panel web mobile-first yang disajikan server lokal**
(Python stdlib + SQLite lokal). Bukan aplikasi Android — native Kotlin ditolak (SDK besar,
yuki/hana tanpa pengalaman Android).

> **CATATAN REVISI (1 Okt 2026).** Rencana Supabase di bawah **DIBATALKAN** oleh Deny.
> Keputusan baru: **database lokal murni (SQLite di Mac)**, alasan tertulis
> *"masalah teknis + biaya"* (detail masalah teknis tidak disebutkan).
> Konsekuensi yang diterima: **tanpa akses dari HP lewat cloud, tanpa Supabase Auth, tanpa RLS,
> tanpa deploy Vercel**. Rinciannya di bagian "Revisi: lokal murni" di bawah.
> Bagian peran di bawah **masih berlaku**, kecuali peran hana yang kehilangan hampir seluruh
> pekerjaannya (tidak ada auth cloud, tidak ada API route cloud).

Deny meminta pembagian kerja frontend dan backend dipecah ke agent yang sesuai bidangnya
saat pengerjaan aplikasi penuh. Jangan ada satu agent mengerjakan keduanya.

| Agent | Bagian | Batas |
|---|---|---|
| **yuki** | **FRONTEND** — semua UI/UX mobile-first: layout HP, komponen Compose-level, halaman chat, panel analisa, grafik. Mengacu `docs/UI-MOBILE.md` | Tidak menulis API routes, tidak menyentuh SQL/RLS, tidak menulis logika angka |
| **hana** | **BACKEND** — API routes, migrasi SQL, RPC | Tidak mendesain UI, tidak memutuskan rumus analisa |
| **monica** | **DATA & ANGKA** — definisi skema, definisi view/RPC analisa, query, laporan mingguan/bulanan, keputusan kategori | Tidak menulis komponen UI, tidak menulis API route |

Titik sambung yang rawan (sebutkan eksplisit saat handoff):
`v_account_balances`, `v_monthly_flow`, `v_net_worth`, `v_savings_progress` — isinya logika angka
(**monica**), pembuatan DDL-nya (`src/schema.sql`), konsumsi datanya (**yuki**). Bentuk hasil query
harus disepakati bertiga sebelum salah satu mulai menulis kode.

### Parser chat-entry

Parser (`src/chat_entry.py`, prompt sistem, aturan multi-transaksi) milik **monica** — itu logika
angka dan kategori. Pembungkusnya (`src/parser_wrap.py` → bentuk kontrak) ada di jalur yang sama.
**yuki** yang membuat layar chat + kartu draft yang bisa dikonfirmasi.

Kalau model parser mati atau mengembalikan JSON rusak: API mengembalikan error yang jelas,
UI menawarkan input manual, **tidak ada yang tersimpan setengah jadi**.

**Sumber kebenaran: `finance.db` lokal** di folder data (`$FINANCE_DATA`, default
`~/Documents/AI/Data/finance/`). Repo ini berisi kode yang menyajikan dan menghitungnya.

## Gelombang 1 (yang dibangun sekarang)

1. Catat transaksi (pemasukan / pengeluaran / pindah ke tabungan) — **lewat chat**
2. Lihat saldo berjalan
3. Panel analisa: total kekayaan, tren bulanan, saran hemat

Belum: anggaran per kategori, kategori kustom, ekspor PDF.
(Target tabungan dengan progres **sudah** ada — lihat `docs/SCHEMA.md` §`savings_goals`.)

## Cara mencatat: chat, dengan konfirmasi wajib

Deny mengetik kalimat biasa — *"Membeli makan malam 45000"* — dan AI mengurainya jadi draft
transaksi. **Draft ditampilkan dulu dan Deny harus menekan simpan.** AI tidak pernah menulis
langsung ke database.

Alasannya: kalau AI menulis langsung, angka keuangan bergantung pada tebakan model yang bisa
berubah perilaku tanpa pemberitahuan. Satu hari "makan malam" masuk kategori Makan, lain hari
masuk Hiburan — laporan tetap terlihat rapi, tapi kategorinya sudah tidak konsisten dan tidak ada
yang tahu. Konfirmasi memindahkan keputusan akhir ke Deny tanpa mengorbankan kecepatan input
(tetap beberapa detik, bukan mengetik form).

**Dua tingkat yang tidak boleh dicampur:**

| Tingkat | Isi | Contoh |
|---|---|---|
| `direction` | kemana uang mengalir | `in` / `out` / `transfer` |
| `category` | jenis transaksinya | Makan, Transport, Tagihan |

"Pengeluaran" adalah **arah**, bukan kategori. Kalau keduanya disimpan di satu field, laporan
tidak bisa memisahkan "total pengeluaran" dari "pengeluaran untuk Makan".

Tingkat ketiga menyusul sebagai keputusan desain: **`flow_type`** (`expense`, `income`,
`receivable`, `debt_payment`, `transfer`) — sifat transaksi, terpisah dari arah. Alasannya
dicatat di `src/schema.sql:40-47`: Oktober 2026 uang keluar Rp 2.100.000 tapi konsumsi
sebenarnya hanya Rp 284.000.

**Model:** `kenari.id` (`src/model_config.py:32` → `deepseek-v4-1-flash`, cadangan
`agnes-2-0-flash:free`). Kalau model mati atau mengembalikan JSON rusak, chat menampilkan pesan
gagal dan **menawarkan input manual** — tidak menyimpan apa pun. Fitur ini tidak boleh memblokir
pencatatan kalau provider sedang bermasalah.

**Mata uang:** IDR saja. Tidak ada konversi kurs — "kurs yang dipakai adalah rupiah" berarti
seluruh sistem berdenominasi rupiah, bukan bahwa ada tabel kurs.


## Revisi: lokal murni (1 Okt 2026)

Keputusan Deny: **semua pendataan di lokal saja.** Alasan yang ia sebutkan:
*masalah teknis* dan *biaya*. Detail masalah teknisnya tidak pernah disebutkan
walaupun sudah ditanya dua kali — kalau nanti ia ingat, catat di sini.

**Yang berubah:**

| Hal | Sebelum (Supabase) | Sekarang (SQLite) |
|---|---|---|
| Sumber kebenaran | Supabase cloud | `finance.db` di folder data — `$FINANCE_DATA`, default `~/Documents/AI/Data/finance/finance.db` (`src/db.py:44-45`) |
| Login / auth | Supabase Auth | **ada**, tapi lokal: password + hash PBKDF2 di `kredensial.json` folder data, sesi **di memori** proses (`src/auth.py:48-49`), halaman `web/login.html` (`src/server.py:1148-1153`), uji `tests/test_auth.py` |
| RLS + `user_id` | di setiap tabel | **dihapus** — single user, satu file (`src/schema.sql:4`) |
| Deploy Vercel | direncanakan | **batal** — server jalan di Mac (`src/server.py`) |
| Akses dari HP | ya (cloud) | **tidak** — hanya dari Mac ini (atau LAN bila dibuka) |
| Peran hana | backend, auth, API, RLS | **hampir kosong** — tidak ada auth cloud/API cloud |

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
| `src/schema.sql` | 5 tabel + **4 view** (`v_account_balances`, `v_monthly_flow`, `v_net_worth`, `v_savings_progress`) — `schema.sql:141,170,217,239` |
| `src/seed.sql` | **0 akun** (sengaja kosong, `seed.sql:33-39`) + 11 kategori bawaan (`seed.sql:19-30`) |
| `src/db.py` | lapisan akses data — **semua angka lewat sini** |
| `src/server.py` | HTTP server + API + penyaji `web/` statis (1320 baris) |
| `src/auth.py` | password + sesi memori (195 baris) |
| `tests/` | 16 berkas uji, satu berkas per invokasi |
| `src/chat_entry.py` + `src/parser_wrap.py` | parser bahasa Indonesia → draft transaksi |
| `Data/finance/finance.db` | database kerja — **berisi data nyata** (98.304 B, transaksi Okt 2026) |

## Aturan yang tidak bisa dilanggar

- **Angka tidak pernah dikarang.** Kalau data tidak ada, katakan tidak ada. Jangan ekstrapolasi
  lalu menyajikannya sebagai tercatat.
- **Selisih saldo adalah temuan**, bukan masalah yang dibulatkan.
- Setiap laporan menyebut **periode** dan **jumlah transaksi tercatat** di periode itu.
- Perubahan skema ditulis sebagai file SQL di `src/migrations/` dan **dijalankan Deny sendiri**.
  Tidak ada `supabase db push` (Supabase sudah dibatalkan), tidak ada DDL otomatis ke DB kerja.
  `src/schema.sql` selalu memuat hasil akhir semua migrasi.

## Konsekuensi privasi (keputusan sadar Deny)

Data keuangan disimpan di **SQLite lokal** di Mac ini, di folder data di luar repo
(`~/Documents/AI/Data/finance/`). Tidak ada angka yang keluar dari mesin kecuali teks yang
dikirim ke provider model saat chat/analisa. Konsekuensinya: tidak ada akses dari HP tanpa
membuka akses ke mesin ini, dan **backup jadi tanggung jawab sendiri**
(`scripts/backup-db.sh`, dijalankan `scripts/start-server.sh`).

Folder data itu **bukan** bagian repo: `.gitignore` mencegahnya masuk git, dan `src/db.py`
menolak folder berisi `finance.db` yang tidak punya penanda `.finance-data`.

## Status

- [x] Agent monica dibuat (`~/.hermes/profiles/monica/`), wrapper `~/.local/bin/monica`
- [x] Terdaftar di ROSTER dashboard + generator laporan mingguan (8 agent)
- [x] Folder kerja `~/Documents/AI/finance/`
- [x] ~~**Supabase project baru**~~ — **dibatalkan**, diganti SQLite lokal (1 Okt)
- [x] Skema SQLite + migrasi (`src/schema.sql`, `src/seed.sql`) — diuji, 24 uji lulus
- [x] Lapisan data (`src/db.py`) — saldo, ringkasan bulanan, simpan transaksi
- [x] Database kerja di folder data dibuat — **berisi data nyata**, bukan kosong lagi
- [x] **Saldo awal tiap akun** — akun BRI dimasukkan lewat `scripts/import_statement_okt.py`
- [x] Parser chat → mengembalikan draft terstruktur (`src/parser_wrap.py`, 255 baris)
- [x] Panel web (yuki: tabel statistik, list transaksi, kolom chat) — `web/` 9 berkas tracked
- [x] Server lokal penyaji panel + penerima chat (`src/server.py`, port 8791)
- [x] ~~Deploy Vercel~~ — **batal** (server lokal tidak bisa di-deploy ke Vercel)
- [x] Login panel (password lokal + sesi memori) — `src/auth.py`, `web/login.html`
- [x] `flow_type` + chip koreksi + `source` impor statement — `src/migrations/002,003`
- [x] Target tabungan + progres — `src/migrations/007`, `v_savings_progress`
- [x] Analisa bulanan (angka dari SQL, narasi dari model) — `src/monthly_analysis.py`
- [ ] Anggaran per kategori, kategori kustom, ekspor PDF — belum dikerjakan
