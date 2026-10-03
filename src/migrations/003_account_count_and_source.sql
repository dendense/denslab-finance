-- finance — migrasi 003: akun kosong tidak dihitung + kolom sumber data
--
-- Dua perbaikan:
--
-- 1. v_net_worth.account_count sebelumnya menghitung SEMUA akun aktif,
--    termasuk akun bawaan (BCA, Tunai, Tabungan) yang saldonya masih 0 dan
--    belum pernah dipakai. Panel jadi bilang "4 akun" padahal cuma 1 yang
--    nyata. Sekarang hanya akun yang punya saldo awal atau transaksi.
--    account_count_all tetap ada untuk yang butuh jumlah mentah.
--
-- 2. transactions.source — transaksi hasil impor statement tidak punya arti
--    "created_at" seperti transaksi input manual. Tanpa penanda ini, UI akan
--    menampilkan 15 transaksi seolah dicatat dalam detik yang sama.
--
-- Jalankan:  sqlite3 finance.db < migrations/003_account_count_and_source.sql
-- CATATAN: ALTER akan gagal "duplicate column name" kalau dijalankan ulang —
-- itu normal dan aman.

-- >>> ALTER (lewati kalau kolomnya sudah ada) <<<
ALTER TABLE transactions ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';

-- manual      : diketik Deny lewat chat atau form
-- statement   : hasil impor rekening koran bank (created_at bukan waktu kejadian)

CREATE INDEX IF NOT EXISTS idx_tx_source ON transactions(source);

UPDATE transactions SET source = 'statement'
 WHERE created_at LIKE '20%' AND id IN (SELECT id FROM transactions);

-- ── view v_net_worth diperbarui ─────────────────────────────────────────────
DROP VIEW IF EXISTS v_net_worth;
CREATE VIEW v_net_worth AS
SELECT
    COALESCE(SUM(b.balance), 0)                                      AS net_worth,
    COALESCE(SUM(CASE WHEN b.kind IN ('bank','cash','ewallet')
                      THEN b.balance END), 0)                        AS liquid,
    COALESCE(SUM(CASE WHEN b.kind IN ('savings','investment')
                      THEN b.balance END), 0)                        AS non_liquid,
    SUM(CASE WHEN b.opening_balance <> 0
              OR EXISTS (SELECT 1 FROM transactions t
                          WHERE t.account_id = b.id OR t.to_account_id = b.id)
             THEN 1 ELSE 0 END)                                      AS account_count,
    COUNT(*)                                                         AS account_count_all
FROM v_account_balances b
WHERE b.is_active = 1;
