#!/usr/bin/env python3
"""Uji format rupiah pada narasi analisa.

Fungsi ini kelihatan sepele, tapi sudah dua kali salah:
  1. "Rp 9.000.000" (angka karangan) sempat lolos penyaring
  2. "Oktober 2026" berubah jadi "Oktober Rp 2.026" — tahun diformat sebagai uang

Karena itu diuji terpisah, dengan kasus yang benar-benar pernah gagal.

Jalankan:  python3 tests/test_format_rupiah.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import monthly_analysis as ma  # noqa: E402

# (teks, harus MENGANDUNG, harus TIDAK mengandung)
KASUS = [
    # Tahun jangan diformat sebagai uang — bug nyata
    ("Di Oktober 2026 ada 8 transaksi",  "Oktober 2026",  "Rp 2.026"),
    ("Pada 2026-10-05 belanja",          "2026-10-05",    "Rp 2.026"),
    ("tahun 2025 pengeluaran 1830000",   "2025",          "Rp 2.025"),
    ("tahun 2025 pengeluaran 1830000",   "Rp 1.830.000",  None),
    ("Oktober 2026 mencatat 8 transaksi", "Oktober 2026",  "Rp 2.026"),

    # Format yang benar: sudah rapi, jangan diubah
    ("uang masuk Rp 8250000",            "Rp 8.250.000",  None),
    ("naik Rp 330.000 dari Rp 450.000",  "Rp 330.000",    None),
    ("naik Rp 330.000 dari Rp 450.000",  "Rp 450.000",    None),

    # Format yang perlu diperbaiki
    ("uang masuk 8250000",               "Rp 8.250.000",  None),
    ("Rp 6750000.",                      "Rp 6.750.000",  None),
    ("Rp8250000",                        "Rp 8.250.000",  None),
    ("Rp 450.000 ke 780000",             "Rp 780.000",    None),
    ("Rp 1250000 dan Rp 6750000",        "Rp 1.250.000",  None),
    ("Rp 1250000 dan Rp 6750000",        "Rp 6.750.000",  None),

    # Angka kecil bukan uang
    ("ada 8 transaksi",                  "ada 8 transaksi", None),
    ("Nominal 500",                      "Nominal 500",   None),
]

gagal = []
for teks, harus_ada, harus_tidak in KASUS:
    hasil = ma._format_rupiah(teks)
    ok = ((harus_ada is None or harus_ada in hasil)
          and (harus_tidak is None or harus_tidak not in hasil))
    print(("  OK   " if ok else "  GAGAL") + " %-40s -> %s" % (teks[:40], hasil))
    if not ok:
        gagal.append("%r -> %r (harus ada %r, harus tidak ada %r)"
                     % (teks, hasil, harus_ada, harus_tidak))

print("\n" + "─" * 76)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua %d uji lulus" % len(KASUS))
