#!/usr/bin/env python3
"""Uji lapisan data — hitung dengan tangan, bandingkan dengan hasil db.py.

Dijalankan di database sementara supaya finance.db Deny tidak tersentuh.
Kalau ada satu saja yang tidak cocok, skrip ini berhenti dengan exit code 1.
"""
import sys
import tempfile
from pathlib import Path

# Kode ada di src/, satu tingkat di atas tests/ atau scripts/
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import db  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji.db"
db.init_db(TMP)

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-46s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r, harusnya %r" % (nama, dapat, harap))


print("\n1. Database kosong — angka harus nol, bukan error")
nw = db.net_worth(TMP)
cek("net_worth kosong", nw["net_worth"], 0)
# seed.sql sengaja TIDAK menyisipkan akun apa pun (akun bawaan yang muncul
# kembali setiap restart pernah menghapus akun Deny). Jadi database baru
# dimulai tanpa akun, dan uji ini yang membuatnya sendiri.
cek("belum ada akun", nw["account_count"], 0)
cek("account_count_all juga 0", nw["account_count_all"], 0)

print("\n2. Akun dibuat sendiri oleh uji (seed.sql tidak menyediakannya)")
for nama, jenis, saldo in [("BCA", "bank", 1500000), ("Tunai", "cash", 200000),
                           ("Tabungan", "savings", 5000000)]:
    with db.connect(TMP) as conn:
        conn.execute("INSERT INTO accounts (name, kind, opening_balance) VALUES (?,?,?)",
                     (nama, jenis, saldo))

bal = {b["name"]: b["balance"] for b in db.account_balances(TMP)}
cek("saldo BCA", bal["BCA"], 1500000)
cek("saldo Tunai", bal["Tunai"], 200000)
cek("saldo Tabungan", bal["Tabungan"], 5000000)
cek("net_worth", db.net_worth(TMP)["net_worth"], 1500000 + 200000 + 5000000)
cek("likuid", db.net_worth(TMP)["liquid"], 1500000 + 200000)
cek("tidak likuid", db.net_worth(TMP)["non_liquid"], 5000000)

print("\n3. Transaksi masuk & keluar")
# Gaji 7.000.000 ke BCA, makan 45.000 dari Tunai, transport 25.000 dari Tunai
db.save_transactions([
    {"occurred_on": "2026-10-01", "direction": "in",  "amount": 8000000,
     "account_hint": "BCA",   "category": "Gaji",    "note": "gaji Oktober"},
    {"occurred_on": "2026-10-01", "direction": "out", "amount": 45000,
     "account_hint": "Tunai", "category": "Makan",   "note": "makan malam"},
    {"occurred_on": "2026-10-01", "direction": "out", "amount": 25000,
     "account_hint": "Tunai", "category": "Transport", "note": "parkir"},
], TMP)

bal = {b["name"]: b["balance"] for b in db.account_balances(TMP)}
cek("BCA setelah gaji", bal["BCA"], 1500000 + 8000000)
cek("Tunai setelah 2 pengeluaran", bal["Tunai"], 200000 - 45000 - 25000)

print("\n4. Transfer TIDAK mengubah total kekayaan (pindah, bukan berubah)")
sebelum = db.net_worth(TMP)["net_worth"]
db.save_transactions([
    {"occurred_on": "2026-10-01", "direction": "transfer", "amount": 1000000,
     "account_hint": "BCA", "to_account_hint": "Tabungan", "note": "nabung"},
], TMP)
sesudah = db.net_worth(TMP)["net_worth"]
cek("net_worth sebelum transfer", sebelum, 1500000 + 8000000 + 200000 - 45000 - 25000 + 5000000)
cek("net_worth setelah transfer (harus SAMA)", sesudah, sebelum)

bal = {b["name"]: b["balance"] for b in db.account_balances(TMP)}
cek("BCA berkurang 1 juta", bal["BCA"], 1500000 + 8000000 - 1000000)
cek("Tabungan bertambah 1 juta", bal["Tabungan"], 5000000 + 1000000)

print("\n5. Ringkasan bulanan — tx_count harus ikut")
ms = db.monthly_summary("2026-10", TMP)
cek("total masuk", ms["total_in"], 8000000)
cek("total keluar", ms["total_out"], 45000 + 25000)
cek("selisih", ms["net"], 8000000 - 70000)
cek("jumlah transaksi", ms["tx_count"], 4)
cek("jumlah transfer", ms["transfer_count"], 1)
cek("transfer tidak dihitung sebagai masuk", ms["total_in"], 8000000)

print("\n6. Bulan tanpa data — harus jelas 'tidak ada data', bukan nol palsu")
kosong = db.monthly_summary("2026-09", TMP)
cek("tx_count bulan kosong", kosong["tx_count"], 0)
cek("tanda ada_data", kosong["_ada_data"], False)

print("\n7. Multi-transaksi bersifat semua-atau-tidak-sama-sekali")
sebelum_count = len(db.list_transactions(path=TMP))
try:
    db.save_transactions([
        {"occurred_on": "2026-10-02", "direction": "out", "amount": 30000,
         "account_hint": "Tunai", "category": "Makan", "note": "ini harusnya masuk"},
        {"occurred_on": "2026-10-02", "direction": "out", "amount": 50000,
         "account_hint": "Tunai", "category": "Transport",
         "account_id": 999999, "note": "akun ngawur -> harus bikin semua batal"},
    ], TMP)
    cek("seharusnya gagal", "tidak gagal", "gagal")
except Exception as e:
    print("  OK   gagal seperti seharusnya: %s" % type(e).__name__)
sesudah_count = len(db.list_transactions(path=TMP))
cek("tidak ada yang tersimpan setengah jadi", sesudah_count, sebelum_count)

print("\n8. Constraint — transfer tanpa tujuan harus ditolak")
import sqlite3  # noqa: E402
try:
    with db.connect(TMP) as conn:
        conn.execute(
            """INSERT INTO transactions
               (occurred_on, direction, amount, account_id, to_account_id, category_id)
               VALUES ('2026-10-03','transfer',10000,1,NULL,NULL)""")
    cek("transfer tanpa tujuan", "diterima", "ditolak")
except sqlite3.IntegrityError:
    print("  OK   transfer tanpa tujuan ditolak database")

print("\n9. Kategori di luar 'in'/'out' ditolak")
try:
    with db.connect(TMP) as conn:
        conn.execute("INSERT INTO transactions (occurred_on,direction,amount,account_id,category_id)"
                     " VALUES ('2026-10-03','out',5000,1,NULL)")
    cek("out tanpa kategori", "diterima", "ditolak")
except sqlite3.IntegrityError:
    print("  OK   'out' tanpa kategori ditolak database")

print("\n10. Format rupiah")
cek("format", db.rupiah(1250000), "Rp 1.250.000")
cek("format nol", db.rupiah(0), "Rp 0")

print("\n" + "─" * 62)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
print("Database uji:", TMP)
