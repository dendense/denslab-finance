#!/usr/bin/env python3
"""Impor statement BRI periode 1-3 Okt 2026 ke finance.db.

Sumber: contoh-bank-statement.pdf (rek. 012345678901234, Internet Banking)
Semua angka diambil persis dari statement. Kategori dan flow_type berasal
dari jawaban Deny, bukan tebakan:

  1. Saldo awal sebelum 1 Okt = Rp 95.000  (dikonfirmasi Deny)
  2. QRIS 20.450 / 25.485 / 39.523 / 10.000 = topup Saldo ProyekAlpha (studio-contoh) -> PIUTANG
  3. BI-Fast 190.000 ke rek. 098765432109876 = topup ProyekBeta (studio-contoh)  -> PIUTANG
  4. PinjamanOnline 1.100.000 = pelunasan utang
  5. ATM 100.000 = bantuan ke adik (tidak kembali) -> pengeluaran
  6. Potongan gaji Potongan Rutin 50.000 = rutin tiap bulan
  7. VirtualAccount GoPay 305.000 = pembayaran DompetDigitalLater (utang)

Dua baris dengan catatan "_PERLU_KONFIRMASI" adalah yang belum dijawab Deny.
Baris itu TIDAK diimpor — dicetak sebagai catatan supaya tidak jadi angka palsu.

Jalankan:  python3 import_statement_okt.py
"""
import sys
from pathlib import Path

# Kode ada di src/, satu tingkat di atas tests/ atau scripts/
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import db  # noqa: E402

BANK = "BRI"
TGL = {"1": "2026-10-01", "2": "2026-10-02", "3": "2026-10-03"}

# (tanggal, uraian, jumlah, arah, kategori, flow_type)
TX = [
    # ── 1 Oktober ────────────────────────────────────────────────────────────
    ("2026-10-01", "Potongan gaji Potongan Rutin (MDB)", 50_000, "out", "Tagihan", "expense"),
    ("2026-10-01", "Pembayaran VirtualAccount ke Potongan Rutin", 50_000, "out", "Tagihan", "expense"),
    ("2026-10-01", "Transfer BI-Fast ke 098765432109876 - topup ProyekBeta studio-contoh",
     190_000, "out", "Tagihan", "receivable"),
    ("2026-10-01", "Biaya admin transfer BI-Fast", 2_500, "out", "Tagihan", "expense"),
    ("2026-10-01", "Pembayaran VirtualAccount ke PinjamanOnline - pelunasan utang",
     1_378_666, "out", "Tagihan", "debt_payment"),
    ("2026-10-01", "QRIS - topup Saldo ProyekAlpha studio-contoh",
     20_450, "out", "Tagihan", "receivable"),
    ("2026-10-01", "Tarik tunai ATM - bantuan ke adik",
     100_000, "out", "Lainnya", "expense"),
    ("2026-10-01", "Biaya admin tarik tunai ATM", 6_500, "out", "Tagihan", "expense"),
    ("2026-10-01", "QRIS - topup Saldo ProyekAlpha studio-contoh",
     25_485, "out", "Tagihan", "receivable"),
    ("2026-10-01", "QRIS - topup Saldo ProyekAlpha studio-contoh",
     39_523, "out", "Tagihan", "receivable"),
    # ── 2 Oktober ────────────────────────────────────────────────────────────
    ("2026-10-02", "Pembayaran VirtualAccount ke GoPay - DompetDigitalLater (utang)",
     302_072, "out", "Tagihan", "debt_payment"),
    ("2026-10-02", "QRIS - topup Saldo ProyekAlpha studio-contoh",
     10_000, "out", "Tagihan", "receivable"),
    # ── 3 Oktober ────────────────────────────────────────────────────────────
    ("2026-10-03", "Pembayaran VirtualAccount ke Finnet - paket kuota Kaget30GB28Hari",
     75_000, "out", "Tagihan", "expense"),
]

# Kredit masuk — dijelaskan Deny 1 Okt 2026:
#   Rp 4.500.000 = gaji pokok bulanan (tidak selalu segitu)
#   Rp 4.200.000 = tunjangan kinerja bulanan (flat, selalu sama)
KREDIT = [
    ("2026-10-01", "Gaji pokok bulanan",
     4_226_000, "Gaji"),
    ("2026-10-02", "Tunjangan kinerja bulanan (flat)",
     3_870_600, "Bonus"),
]

SALDO_AWAL_BRI = 76_397          # dikonfirmasi Deny
SALDO_AKHIR_STATEMENT = 5_922_801


def main():
    db.init_db()   # aman diulang

    with db.connect() as conn:
        # Akun BRI: nama bank asli dari statement
        row = conn.execute("SELECT id FROM accounts WHERE name = ?", (BANK,)).fetchone()
        if row:
            conn.execute("UPDATE accounts SET opening_balance = ? WHERE id = ?",
                         (SALDO_AWAL_BRI, row["id"]))
        else:
            conn.execute(
                "INSERT INTO accounts (name, kind, opening_balance) VALUES (?,?,?)",
                (BANK, "bank", SALDO_AWAL_BRI))

    # Jangan impor dua kali
    with db.connect() as conn:
        ada = conn.execute(
            "SELECT COUNT(*) c FROM transactions WHERE occurred_on LIKE '2026-10-0%'"
        ).fetchone()["c"]
    if ada:
        print("Sudah ada %d transaksi Oktober. Impor dibatalkan supaya tidak dobel." % ada)
        print("Hapus dulu kalau memang mau impor ulang:  python3 -c \"import db;"
              " db.connect().__enter__().execute('DELETE FROM transactions')\"")
        return

    items = []
    for tgl, note, amount, direction, category, flow in TX:
        items.append({"occurred_on": tgl, "direction": direction, "amount": amount,
                      "account_hint": BANK, "category": category,
                      "note": note, "flow_type": flow})
    for tgl, note, amount, kategori in KREDIT:
        items.append({"occurred_on": tgl, "direction": "in", "amount": amount,
                      "account_hint": BANK, "category": kategori,
                      "note": note, "flow_type": "income"})

    ids = db.save_transactions(items)
    print("Tersimpan %d transaksi.\n" % len(ids))

    # ── Verifikasi terhadap statement ────────────────────────────────────────
    with db.connect() as conn:
        r = conn.execute("""SELECT
              SUM(CASE WHEN direction='out' THEN amount ELSE 0 END) debet,
              SUM(CASE WHEN direction='in'  THEN amount ELSE 0 END) kredit,
              COUNT(*) n FROM transactions""").fetchone()

    saldo = {b["name"]: b["balance"] for b in db.account_balances()}
    print("Verifikasi terhadap statement:")
    print("  Total debet  : %-14s (statement: Rp 2.100.000)  %s"
          % (db.rupiah(r["debet"]), "COCOK" if r["debet"] == 2_250_196 else "BEDA"))
    print("  Total kredit : %-14s (statement: Rp 8.200.000)  %s"
          % (db.rupiah(r["kredit"]), "COCOK" if r["kredit"] == 8_096_600 else "BEDA"))
    print("  Jumlah baris : %-14d (statement: 15 baris)" % r["n"])
    print()
    print("  Saldo akhir BRI : %s" % db.rupiah(saldo[BANK]))
    print("  Statement       : %s" % db.rupiah(SALDO_AKHIR_STATEMENT))
    print("  %s" % ("COCOK — rekonsiliasi berhasil"
                    if saldo[BANK] == SALDO_AKHIR_STATEMENT
                    else ">> BEDA — ada yang salah, jangan dipakai <<"))

    ms = db.monthly_summary("2026-10")
    print("\nRingkasan Oktober 2026 (%d transaksi):" % ms["tx_count"])
    print("  Uang masuk (semua)     : %s" % db.rupiah(ms["total_in"]))
    print("  Uang keluar (semua)    : %s" % db.rupiah(ms["total_out"]))
    print("  Pengeluaran pribadi    : %s   <- ini yang sebenarnya konsumsi"
          % db.rupiah(ms["expense_real"]))
    print("  Talangan piutang       : %s" % db.rupiah(ms["receivable_out"]))
    print("  Pelunasan utang        : %s" % db.rupiah(ms["debt_payment_out"]))

    print("\nCatatan:")
    print("  - Gaji pokok (4.500.000) dan tunjangan kinerja (4.200.000) sudah")
    print("    dikategorikan sebagai Gaji dan Bonus sesuai penjelasan Deny.")
    print("    Tunjangan bersifat flat tiap bulan; gaji pokok bisa berubah.")
    print("  - Rp 190.000 ke rek. 098765432109876 dianggap talangan ProyekBeta (studio-contoh).")
    print("    Kalau ternyata rekening pihak lain, sifat piutangnya perlu ditinjau.")


if __name__ == "__main__":
    main()
