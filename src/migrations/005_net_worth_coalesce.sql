-- finance — migrasi 005: jumlah akun tidak lagi NULL di database kosong
--
-- BUG YANG DIPERBAIKI:
-- v_net_worth memakai SUM(...) tanpa COALESCE untuk `account_count` dan
-- `account_count_all`. SQLite mengembalikan NULL — bukan 0 — saat SUM dijalankan
-- atas NOL baris. Jadi di database yang benar-benar kosong (belum ada akun),
-- kedua kolom itu bernilai NULL.
--
-- Akibatnya untuk UI: `net_worth.account_count` jadi null, dan pengecekan
-- seperti `account_count > 0` akan gagal dengan cara yang aneh — atau panel
-- menampilkan "null akun".
--
-- Sebelumnya tidak terasa karena seed.sql selalu menyisipkan tiga akun bawaan,
-- sehingga view ini tidak pernah dijumlahkan atas nol baris. Setelah akun
-- bawaan dihapus dari seed.sql (karena muncul kembali setiap restart), database
-- kosong jadi keadaan yang nyata — dan bug ini muncul.
--
-- Jalankan:  sqlite3 data/finance.db < src/migrations/005_net_worth_coalesce.sql

DROP VIEW IF EXISTS v_net_worth;
CREATE VIEW v_net_worth AS
SELECT
    COALESCE(SUM(b.balance), 0)                                      AS net_worth,
    COALESCE(SUM(CASE WHEN b.kind IN ('bank','cash','ewallet')
                      THEN b.balance END), 0)                        AS liquid,
    COALESCE(SUM(CASE WHEN b.kind IN ('savings','investment')
                      THEN b.balance END), 0)                        AS non_liquid,
    COALESCE(SUM(CASE WHEN b.is_active = 1
              AND (b.opening_balance <> 0
                   OR EXISTS (SELECT 1 FROM transactions t
                               WHERE t.account_id = b.id OR t.to_account_id = b.id))
             THEN 1 ELSE 0 END), 0)                                  AS account_count,
    COALESCE(SUM(CASE WHEN b.is_active = 1 THEN 1 ELSE 0 END), 0)    AS account_count_all,
    COALESCE(SUM(CASE WHEN b.is_active = 0 THEN b.balance END), 0)   AS balance_inactive
FROM v_account_balances b;
