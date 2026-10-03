-- finance — migrasi 007: target tabungan
--
-- Satu target, total, dihitung dari SALDO AKUN.
--
-- Keputusan Deny 3 Okt 2026:
--   1. Yang dihitung sebagai menabung = saldo akun Tabungan (kind 'savings').
--      Bukan total kekayaan, bukan semua transfer ke akun non-harian.
--   2. SATU target saja untuk sekarang. Tabel ini memang dirancang menampung
--      beberapa baris (kolom is_archived sudah disiapkan), tapi panelnya
--      menampilkan yang aktif saja.
--   3. Target TOTAL, bukan bulanan. Garis akhirnya jelas: "kumpulkan Rp X".
--   4. Mulai menabung bulan depan — jadi targetnya disiapkan dulu, kosong.
--
-- KONSEKUENSI YANG DISADARI: kalau Deny menyimpan uang di instrumen lain
-- (reksadana, deposito) yang bukan akun kind 'savings', uang itu TIDAK
-- terhitung di progres. Ini harus ditulis di panelnya supaya tidak
-- membingungkan — bukan sesuatu yang bisa diselesaikan oleh skema.
--
-- Jalankan:  sqlite3 $FINANCE_DATA/finance.db < src/migrations/007_savings_goal.sql

CREATE TABLE IF NOT EXISTS savings_goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    target_amount  INTEGER NOT NULL CHECK (target_amount > 0),

    -- Akun tempat uangnya dikumpulkan. Progres dihitung dari saldo akun ini.
    -- Kalau akunnya dihapus, targetnya tidak bisa dihitung — jadi RESTRICT.
    account_id     INTEGER NOT NULL REFERENCES accounts(id),

    -- Opsional. Kalau diisi, panel bisa menunjukkan tanggalnya; kalau kosong,
    -- target dibiarkan tanpa tenggat ("kumpulkan Rp X, kapan saja").
    target_date    TEXT,

    is_archived    INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0,1)),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_savings_goals_aktif
    ON savings_goals(is_archived, account_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- v_savings_progress — progres target, DIHITUNG dari saldo akun
--
-- Tidak ada kolom "terkumpul" yang disimpan. Kalau disimpan, koreksi transaksi
-- akan membuat angkanya basi dan tidak ada yang tahu — kesalahan yang sama
-- dengan menyimpan snapshot di tabel analyses. Saldo selalu benar karena
-- dihitung dari transaksi.
-- ─────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_savings_progress;
CREATE VIEW v_savings_progress AS
SELECT
    g.id,
    g.name,
    g.target_amount,
    g.target_date,
    g.account_id,
    a.name AS account_name,
    a.kind AS account_kind,

    COALESCE(b.balance, 0) AS terkumpul,

    -- Sisa yang masih perlu dikumpulkan. Bisa negatif kalau tabungan
    -- melebihi target — itu keadaan yang sah (target terlampaui), bukan error.
    g.target_amount - COALESCE(b.balance, 0) AS sisa,

    -- Persentase 0-100, dibulatkan. Sengaja TIDAK di-cap di 100,supaya
    -- target yang terlampaui tetap terlihat lebih dari 100%.
    CASE WHEN g.target_amount > 0
         THEN CAST(ROUND(COALESCE(b.balance, 0) * 100.0 / g.target_amount) AS INTEGER)
         ELSE NULL END AS persen,

    CASE
        WHEN COALESCE(b.balance, 0) <= 0                 THEN 'belum_mulai'
        WHEN COALESCE(b.balance, 0) >= g.target_amount   THEN 'tercapai'
        ELSE 'berjalan'
    END AS status,

    g.is_archived,
    g.created_at
FROM savings_goals g
JOIN accounts a ON a.id = g.account_id
LEFT JOIN v_account_balances b ON b.id = g.account_id;
