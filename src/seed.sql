-- finance — data awal (kategori bawaan)
-- Jalankan setelah schema.sql:  sqlite3 finance.db < seed.sql
--
-- PENTING: berkas ini dijalankan SETIAP server dinyalakan (lihat `init_db()` di
-- db.py), memakai `INSERT OR IGNORE`. Karena itu, apa pun yang ada di sini akan
-- MUNCUL KEMBALI setelah dihapus dari database.
--
-- Kejadian nyata: `Tunai` dan `BCA` pernah tercantum di sini. Deny menghapus
-- `Tunai`, lalu server dinyalakan ulang — akunnya kembali dengan id baru (44).
-- yuki yang menemukan ini. Karena itu sekarang TIDAK ADA akun contoh di sini.
--
-- ATURAN: jangan menambahkan akun ke berkas ini. Tambah akun lewat panel
-- (`POST /api/accounts`) atau `db.create_account()`. Akun bawaan yang muncul
-- kembali setiap restart adalah kejutan yang tidak diinginkan.

-- ─────────────────────────────────────────────────────────────────────────────
-- Kategori bawaan — aman di sini karena daftarnya memang tetap
-- ─────────────────────────────────────────────────────────────────────────────
INSERT OR IGNORE INTO categories (name, direction, is_system, sort_order) VALUES
    ('Makan',      'out', 1, 10),
    ('Transport',  'out', 1, 20),
    ('Belanja',    'out', 1, 30),
    ('Hiburan',    'out', 1, 40),
    ('Tagihan',    'out', 1, 50),
    ('Kesehatan',  'out', 1, 60),
    ('Pendidikan', 'out', 1, 70),
    ('Lainnya',    'out', 1, 80),
    ('Gaji',       'in',  1, 10),
    ('Bonus',      'in',  1, 20),
    ('Lainnya',    'in',  1, 30);

-- ─────────────────────────────────────────────────────────────────────────────
-- Akun — SENGAJA KOSONG
-- ─────────────────────────────────────────────────────────────────────────────
-- Database baru dimulai tanpa akun; Deny menambahnya sendiri lewat panel.
--
-- Saldo awal akun BRI (Rp 95.000) berasal dari rekening koran dan dimasukkan
-- lewat `scripts/import_statement_okt.py` — itu data keuangan, bukan data awal,
-- jadi tidak boleh ada di berkas ini.
