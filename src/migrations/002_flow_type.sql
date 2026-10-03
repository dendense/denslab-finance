-- finance — migrasi 002: pemisahan sifat transaksi
--
-- Alasan: statement BRI 1-3 Okt 2026 menunjukkan uang keluar Rp 2.100.000,
-- tapi yang benar-benar konsumsi pribadi hanya Rp 539.572. Sisanya:
--   - Rp 285.458 talangan ke project studio-contoh (ProyekAlpha + ProyekBeta)
--   - Rp 1.400.000 pelunasan utang (PinjamanOnline + DompetDigitalLater)
--   - Rp 190.000 transfer ke rekening sendiri
-- Tanpa kolom ini, laporan bulanan akan melaporkan pengeluaran 4x lipat
-- dari yang sebenarnya.
--
-- Tanpa tabel terpisah: ini pemisahan sifat, bukan sistem piutang penuh.
-- Deny belum bisa melihat "total piutang belum dibayar" sebagai angka —
-- itu keterbatasan yang diketahui dan diterima.
--
-- Jalankan:  sqlite3 finance.db < migrations/002_flow_type.sql
--
-- CATATAN: SQLite tidak punya "ADD COLUMN IF NOT EXISTS". Menjalankan ulang
-- file ini akan gagal di baris ALTER dengan "duplicate column name" — itu
-- normal dan aman: bagian ALTER dilewati, bagian view tetap diperbarui.
-- Untuk memeriksa kolomnya sudah ada:
--   sqlite3 finance.db "PRAGMA table_info(transactions);"

-- >>> ALTER (gagal dengan wajar kalau kolomnya sudah ada) <<<
ALTER TABLE transactions ADD COLUMN flow_type TEXT NOT NULL DEFAULT 'expense';

-- expense     : konsumsi / uang hilang (termasuk bantuan yang tidak kembali)
-- income      : uang masuk
-- receivable  : talangan, diharapkan kembali (topup project)
-- debt_payment: melunasi utang lama; bukan konsumsi baru
-- transfer    : berpindah antar akun sendiri; tidak mengubah kekayaan
--
-- CHECK tidak bisa ditambahkan lewat ALTER TABLE di SQLite, jadi validasi
-- ditangani lapisan aplikasi (db.py). Ini trade-off yang diterima.

CREATE INDEX IF NOT EXISTS idx_tx_flow_type ON transactions(flow_type);

-- ─────────────────────────────────────────────────────────────────────────────
-- View ringkasan diperbarui: keluarkan angka konsumsi yang sebenarnya.
-- v_monthly_flow lama hanya menjumlahkan in/out dan mencampur konsumsi
-- dengan pelunasan utang — itu angka yang menyesatkan.
-- ─────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_monthly_flow;
CREATE VIEW v_monthly_flow AS
SELECT
    substr(occurred_on, 1, 7) AS month,

    -- pemasukan & pengeluaran apa adanya (semua yang bergerak)
    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount END), 0)  AS total_in,
    COALESCE(SUM(CASE WHEN direction = 'out' THEN amount END), 0)  AS total_out,

    -- yang benar-benar konsumsi pribadi
    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'expense'
                      THEN amount END), 0)                          AS expense_real,
    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'receivable'
                      THEN amount END), 0)                          AS receivable_out,
    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'debt_payment'
                      THEN amount END), 0)                          AS debt_payment_out,

    -- selisih: masuk dikurangi keluar, apa adanya
    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount
                      WHEN direction = 'out' THEN -amount END), 0)  AS net,

    -- selisih yang mencerminkan perubahan kekayaan sebenarnya:
    -- talangan piutang dihitung netral (keluar uang, dapat piutang),
    -- pelunasan utang dihitung netral (keluar uang, hilang utang).
    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount
                      WHEN direction = 'out' AND flow_type = 'expense'
                      THEN -amount END), 0)                          AS net_real,

    COUNT(*)                                                        AS tx_count,
    SUM(CASE WHEN direction = 'in'  THEN 1 ELSE 0 END)              AS in_count,
    SUM(CASE WHEN direction = 'out' THEN 1 ELSE 0 END)              AS out_count,
    SUM(CASE WHEN direction = 'transfer' THEN 1 ELSE 0 END)         AS transfer_count
FROM transactions
GROUP BY substr(occurred_on, 1, 7);
