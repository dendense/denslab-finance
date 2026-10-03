-- finance — migrasi 006: tabel `analyses` untuk analisa bulanan
--
-- Menyimpan HASIL analisa satu bulan: angka yang dihitung saat itu, narasi AI,
-- dan cap waktu. Dipakai halaman Analisa.
--
-- Kenapa hasilnya disimpan, bukan selalu dihitung ulang:
-- narasi AI dibuat SEKALI (keputusan Deny). Kalau narasinya tidak disimpan,
-- setiap membuka halaman harus memanggil model lagi — lambat, dan narasinya
-- bisa berbeda setiap kali untuk data yang sama. Analisa yang berubah-ubah
-- tanpa alasan lebih buruk daripada analisa yang basi tapi bisa ditelusuri.
--
-- Aturan yang berlaku (keputusan Deny 3 Okt 2026):
--   1. ANGKA selalu dihitung ulang dari transaksi saat halaman dibuka. Jadi
--      kalau transaksi dikoreksi, angka di analisa ikut benar.
--   2. NARASI tetap versi saat dibuat, dan DITANDAI BASI kalau ada transaksi
--      di bulan itu yang dibuat/diubah setelah `dibuat_pada`.
--      Kolom `tx_terakhir` menyimpan waktu perubahan data terakhir; UI
--      membandingkannya dengan `dibuat_pada`.
--   3. Bulan berjalan TIDAK boleh dianalisa (belum selesai).
--
-- Jalankan:  sqlite3 $FINANCE_DATA/finance.db < src/migrations/006_analyses.sql

CREATE TABLE IF NOT EXISTS analyses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,

    -- bulan yang dianalisa, 'YYYY-MM'. Satu bulan satu analisa.
    month         TEXT    NOT NULL UNIQUE,

    -- Cap waktu narasi dibuat.
    dibuat_pada   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),

    -- Waktu perubahan data terakhir di bulan itu, DIISI SAAT PEMBUATAN.
    -- Dipakai untuk mendeteksi narasi basi: kalau ada transaksi dengan
    -- created_at lebih baru dari nilai ini, berarti datanya berubah setelah
    -- narasi dibuat.
    tx_terakhir   TEXT,

    -- Narasi AI: daftar saran, masing-masing {jenis, kategori, asumsi, narasi}.
    -- Disimpan sebagai JSON karena bentuknya bisa berkembang tanpa migrasi.
    narasi        TEXT,

    -- Angka ringkasan SAAT NARASI DIBUAT — untuk pembanding, bukan acuan.
    -- Yang ditampilkan ke Deny selalu hasil hitung ulang.
    snapshot      TEXT,

    -- Model yang menulis narasi. Kalau modelnya berganti, itu terlihat.
    model         TEXT,

    -- Kenapa analisa tanpa narasi (model mati, dsb). Kosong = narasi ada.
    catatan       TEXT
);

CREATE INDEX IF NOT EXISTS idx_analyses_month ON analyses(month);
