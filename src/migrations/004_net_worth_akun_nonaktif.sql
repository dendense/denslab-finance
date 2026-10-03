-- finance — migrasi 004: akun nonaktif tetap dihitung di total kekayaan
--
-- BUG YANG DIPERBAIKI:
-- v_net_worth sebelumnya memakai `WHERE b.is_active = 1`. Akibatnya
-- menonaktifkan akun akan MENGHAPUS saldonya dari total kekayaan — seolah
-- uangnya lenyap. Tidak ada error, tidak ada peringatan, angka cuma berubah.
--
-- Untuk akun yang saldonya 0 efeknya tidak terasa. Tapi begitu ada akun
-- bersaldo yang dinonaktifkan (mis. akun bank lama yang masih ada isinya),
-- net_worth langsung salah besar.
--
-- Sekarang: SEMUA akun dijumlahkan. `is_active` cuma menentukan apakah akun
-- muncul di daftar. Saldo akun nonaktif dipisah ke kolom `balance_inactive`
-- supaya bisa ditampilkan terpisah kalau perlu.
--
-- Ditemukan oleh test_account_write.py saat menguji jalur tulis akun.
--
-- Jalankan:  sqlite3 finance.db < migrations/004_net_worth_akun_nonaktif.sql

DROP VIEW IF EXISTS v_net_worth;
CREATE VIEW v_net_worth AS
SELECT
    COALESCE(SUM(b.balance), 0)                                      AS net_worth,
    COALESCE(SUM(CASE WHEN b.kind IN ('bank','cash','ewallet')
                      THEN b.balance END), 0)                        AS liquid,
    COALESCE(SUM(CASE WHEN b.kind IN ('savings','investment')
                      THEN b.balance END), 0)                        AS non_liquid,
    SUM(CASE WHEN b.is_active = 1
              AND (b.opening_balance <> 0
                   OR EXISTS (SELECT 1 FROM transactions t
                               WHERE t.account_id = b.id OR t.to_account_id = b.id))
             THEN 1 ELSE 0 END)                                      AS account_count,
    SUM(CASE WHEN b.is_active = 1 THEN 1 ELSE 0 END)                 AS account_count_all,
    COALESCE(SUM(CASE WHEN b.is_active = 0 THEN b.balance END), 0)   AS balance_inactive
FROM v_account_balances b;
