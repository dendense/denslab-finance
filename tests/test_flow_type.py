#!/usr/bin/env python3
"""Uji tebakan flow_type — tanpa memanggil model, jadi cepat dan bisa diulang.

Fungsi ini adalah lapisan penebak yang paling gampang salah, dan kesalahannya
senyap: transaksi tetap tersimpan, tapi masuk ke kolom yang keliru dan membuat
laporan menyesatkan. Karena itu diuji terpisah.

Jalankan:  python3 test_flow_type.py
"""
import sys
from pathlib import Path

# Kode ada di src/, satu tingkat di atas tests/ atau scripts/
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import parser_wrap as pw  # noqa: E402

# (note, direction, flow_type yang diharapkan)
UJI = [
    # pengeluaran biasa — kata "topup" TIDAK boleh jadi piutang
    ("Topup e-toll via BRI",              "out",      "expense"),
    ("topup gopay 100000",                "out",      "expense"),
    ("topup pulsa 50000",                 "out",      "expense"),
    ("topup dana 200000",                 "out",      "expense"),
    ("isi bensin 200000",                 "out",      "expense"),
    ("makan malam 45000",                 "out",      "expense"),
    ("beli sarapan pagi",                 "out",      "expense"),

    # talangan project — yang benar-benar piutang
    ("topup saldo kenari",                "out",      "receivable"),
    ("topup siray 190000",                "out",      "receivable"),
    ("talangan project studio-contoh",       "out",      "receivable"),
    ("biaya project kenari",              "out",      "receivable"),

    # utang
    ("bayar cicilan spinjam",             "out",      "debt_payment"),
    ("lunas gopaylater",                  "out",      "debt_payment"),
    ("angsuran kredit 500000",            "out",      "debt_payment"),

    # perpindahan antar akun sendiri
    ("pindah ke tabungan",                "transfer", "transfer"),
    ("transfer 500000 ke bca",            "transfer", "transfer"),

    # uang masuk
    ("terima gaji 4226000",               "in",       "income"),
    ("dapat bonus 3870600",               "in",       "income"),
]

gagal = []
for note, direction, harap in UJI:
    tx = {"direction": direction, "note": note, "category": None}
    dapat = pw.tebak_flow_type(tx)
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-34s %-9s -> %-12s (harap %s)"
          % (note, direction, dapat, harap))
    if not ok:
        gagal.append(note)

print("\n" + "─" * 70)
if gagal:
    print("HASIL: %d GAGAL dari %d" % (len(gagal), len(UJI)))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua %d lulus" % len(UJI))
