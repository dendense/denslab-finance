-- finance — skema SQLite lokal
-- Revisi dari SCHEMA.md: dari Supabase (Postgres + RLS + auth) ke SQLite lokal murni.
-- Keputusan Deny 1 Okt: lokal saja, alasan "masalah teknis + biaya".
-- Konsekuensi yang diterima: tanpa login, tanpa RLS, tanpa user_id, tanpa deploy Vercel.
--
-- Jalankan:  sqlite3 finance.db < schema.sql

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- accounts — tempat uang berada
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT    NOT NULL UNIQUE,
    kind            TEXT    NOT NULL
                    CHECK (kind IN ('bank','cash','ewallet','savings','investment')),
    opening_balance INTEGER NOT NULL DEFAULT 0,   -- IDR penuh, tanpa sen
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- ─────────────────────────────────────────────────────────────────────────────
-- categories — jenis transaksi, BUKAN arah
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    direction   TEXT    NOT NULL CHECK (direction IN ('in','out')),
    is_system   INTEGER NOT NULL DEFAULT 1 CHECK (is_system IN (0,1)),
    sort_order  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (name, direction)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- transactions — satu baris = satu kejadian uang
-- amount SELALU positif; arah disimpan di direction, bukan di tanda angka.
-- occurred_on (tanggal kejadian) dipisah dari created_at (waktu input).
--
-- flow_type: sifat transaksi, terpisah dari arahnya.
--   expense      konsumsi / uang hilang (termasuk bantuan yang tidak kembali)
--   income       uang masuk
--   receivable   talangan, diharapkan kembali (topup project)
--   debt_payment melunasi utang lama; bukan konsumsi baru
--   transfer     berpindah antar akun sendiri; tidak mengubah kekayaan
-- Bedanya bisa 4x lipat: Oktober 2026 uang keluar Rp 2.100.000 tapi konsumsi
-- sebenarnya hanya Rp 284.000. Tanpa kolom ini, laporan menyesatkan.
--
-- source: 'manual' (diketik Deny) atau 'statement' (impor rekening koran).
-- Untuk 'statement', created_at adalah waktu impor — bukan waktu kejadian.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_on   TEXT    NOT NULL,              -- 'YYYY-MM-DD'
    direction     TEXT    NOT NULL CHECK (direction IN ('in','out','transfer')),
    amount        INTEGER NOT NULL CHECK (amount > 0),
    account_id    INTEGER NOT NULL REFERENCES accounts(id),
    to_account_id INTEGER          REFERENCES accounts(id),
    category_id   INTEGER          REFERENCES categories(id),
    note          TEXT,
    flow_type     TEXT    NOT NULL DEFAULT 'expense'
                  CHECK (flow_type IN ('expense','income','receivable',
                                       'debt_payment','transfer')),
    source        TEXT    NOT NULL DEFAULT 'manual'
                  CHECK (source IN ('manual','statement')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now','localtime')),

    -- transfer wajib punya tujuan dan tidak punya kategori;
    -- in/out wajib punya kategori dan tidak punya tujuan.
    CHECK (
        (direction = 'transfer' AND to_account_id IS NOT NULL
                                AND category_id IS NULL
                                AND to_account_id <> account_id)
     OR (direction IN ('in','out') AND to_account_id IS NULL
                                  AND category_id IS NOT NULL)
    ),

    -- flow_type harus cocok dengan direction. Ini mencegah 'income' tersimpan
    -- sebagai pengeluaran (atau sebaliknya) — kesalahan yang membuat laporan
    -- tetap terlihat rapi tapi angkanya terbalik.
    CHECK (
        (flow_type = 'income'       AND direction = 'in')
     OR (flow_type = 'transfer'     AND direction = 'transfer')
     OR (flow_type IN ('expense','receivable','debt_payment') AND direction = 'out')
    )
);

CREATE INDEX IF NOT EXISTS idx_tx_occurred   ON transactions(occurred_on);
CREATE INDEX IF NOT EXISTS idx_tx_account    ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_tx_to_account ON transactions(to_account_id);
CREATE INDEX IF NOT EXISTS idx_tx_direction  ON transactions(direction);
CREATE INDEX IF NOT EXISTS idx_tx_flow_type  ON transactions(flow_type);
CREATE INDEX IF NOT EXISTS idx_tx_source     ON transactions(source);

-- ─────────────────────────────────────────────────────────────────────────────
-- analyses — hasil analisa bulanan (angka + narasi AI)
-- Angka yang ditampilkan ke Deny selalu DIHITUNG ULANG dari transaksi; tabel
-- ini menyimpan narasinya. Lihat src/migrations/006_analyses.sql untuk alasan
-- lengkapnya.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    month         TEXT    NOT NULL UNIQUE,
    dibuat_pada   TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    tx_terakhir   TEXT,
    narasi        TEXT,
    snapshot      TEXT,
    model         TEXT,
    catatan       TEXT
);

CREATE INDEX IF NOT EXISTS idx_analyses_month ON analyses(month);

-- ─────────────────────────────────────────────────────────────────────────────
-- savings_goals — target tabungan
-- Satu target per akun untuk sekarang. Progres TIDAK disimpan; dihitung dari
-- saldo akun lewat v_savings_progress. Lihat src/migrations/007_savings_goal.sql.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS savings_goals (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT    NOT NULL,
    target_amount  INTEGER NOT NULL CHECK (target_amount > 0),
    account_id     INTEGER NOT NULL REFERENCES accounts(id),
    target_date    TEXT,
    is_archived    INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0,1)),
    created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_savings_goals_aktif
    ON savings_goals(is_archived, account_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- v_account_balances — saldo tiap akun
--   saldo = opening_balance
--         + in  yang masuk ke akun
--         - out yang keluar dari akun
--         - transfer yang keluar dari akun
--         + transfer yang masuk ke akun sebagai tujuan
-- ─────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_account_balances;
CREATE VIEW v_account_balances AS
SELECT
    a.id,
    a.name,
    a.kind,
    a.opening_balance,
    a.is_active,
    a.opening_balance
      + COALESCE((SELECT SUM(t.amount) FROM transactions t
                   WHERE t.account_id = a.id AND t.direction = 'in'), 0)
      - COALESCE((SELECT SUM(t.amount) FROM transactions t
                   WHERE t.account_id = a.id AND t.direction = 'out'), 0)
      - COALESCE((SELECT SUM(t.amount) FROM transactions t
                   WHERE t.account_id = a.id AND t.direction = 'transfer'), 0)
      + COALESCE((SELECT SUM(t.amount) FROM transactions t
                   WHERE t.to_account_id = a.id AND t.direction = 'transfer'), 0)
      AS balance
FROM accounts a;

-- ─────────────────────────────────────────────────────────────────────────────
-- v_monthly_flow — per bulan: masuk, keluar, selisih, JUMLAH TRANSAKSI
-- Jumlah transaksi ikut ditampilkan supaya Deny tahu kalau datanya bolong.
-- transfer tidak dihitung sebagai masuk/keluar — hanya berpindah, bukan berubah.
--
-- PENTING: `total_out` adalah SEMUA uang yang keluar dan itu BUKAN pengeluaran
-- pribadi. `expense_real` yang menunjukkan konsumsi. Bedanya bisa 4x lipat
-- kalau ada talangan project atau pelunasan utang (lihat migrations/002).
-- ─────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_monthly_flow;
CREATE VIEW v_monthly_flow AS
SELECT
    substr(occurred_on, 1, 7) AS month,

    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount END), 0)  AS total_in,
    COALESCE(SUM(CASE WHEN direction = 'out' THEN amount END), 0)  AS total_out,

    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'expense'
                      THEN amount END), 0)                          AS expense_real,
    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'receivable'
                      THEN amount END), 0)                          AS receivable_out,
    COALESCE(SUM(CASE WHEN direction = 'out' AND flow_type = 'debt_payment'
                      THEN amount END), 0)                          AS debt_payment_out,

    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount
                      WHEN direction = 'out' THEN -amount END), 0)  AS net,

    -- selisih yang mencerminkan perubahan kekayaan sebenarnya:
    -- talangan piutang netral (keluar uang, dapat piutang),
    -- pelunasan utang netral (keluar uang, hilang utang).
    COALESCE(SUM(CASE WHEN direction = 'in'  THEN amount
                      WHEN direction = 'out' AND flow_type = 'expense'
                      THEN -amount END), 0)                          AS net_real,

    COUNT(*)                                                        AS tx_count,
    SUM(CASE WHEN direction = 'in'     THEN 1 ELSE 0 END)           AS in_count,
    SUM(CASE WHEN direction = 'out'    THEN 1 ELSE 0 END)           AS out_count,
    SUM(CASE WHEN direction = 'transfer' THEN 1 ELSE 0 END)         AS transfer_count
FROM transactions
GROUP BY substr(occurred_on, 1, 7);

-- ─────────────────────────────────────────────────────────────────────────────
-- v_net_worth — total kekayaan = jumlah saldo semua akun AKTIF
-- Akun tabungan & investasi ikut dihitung: itu tetap miliknya, yang membedakan
-- hanya likuiditas — dan itu ditampilkan terpisah, bukan dikeluarkan.
--
-- `account_count` hanya menghitung akun yang BENAR-BENAR dipakai: saldo awal
-- bukan nol, atau punya setidaknya satu transaksi. Akun bawaan yang masih
-- kosong (belum diisi Deny) tidak dihitung — kalau ikut dihitung, panel akan
-- bilang "4 akun" padahal 3 di antaranya kosong dan belum pernah dipakai.
-- ─────────────────────────────────────────────────────────────────────────────
-- PENTING: SEMUA akun ikut dihitung, termasuk yang is_active = 0.
-- Menonaktifkan akun cuma menyembunyikannya dari daftar; uang di dalamnya
-- TETAP milik Deny. Kalau baris nonaktif dikecualikan, menonaktifkan akun akan
-- menghapus saldonya dari total kekayaan seolah uangnya lenyap — kesalahan
-- besar yang tidak menimbulkan error apa pun.
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

-- ─────────────────────────────────────────────────────────────────────────────
-- v_savings_progress — progres target tabungan, DIHITUNG dari saldo akun
-- Tidak ada angka "terkumpul" yang disimpan: kalau disimpan, koreksi transaksi
-- membuatnya basi tanpa ada yang tahu. Saldo selalu benar karena dihitung.
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
    g.target_amount - COALESCE(b.balance, 0) AS sisa,
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
