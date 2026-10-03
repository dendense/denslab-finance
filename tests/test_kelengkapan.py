#!/usr/bin/env python3
"""Uji peringatan kelengkapan data bulan.

Yang diuji: apakah sistem memberi tahu Deny bahwa angkanya berdasar data tipis.

Kasus nyata yang memicunya: Oktober 2026 baru 3 dari 31 hari, tapi "sisa bebas"
menghasilkan Rp 7.800.000 — angka yang benar sebagai hitungan, menyesatkan
sebagai gambaran. Tanpa peringatan, Deny akan mengira itu uang bebas.

Jalankan:  python3 tests/test_kelengkapan.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-52s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_benar(nama, kondisi):
    print(("  OK   " if kondisi else "  GAGAL") + " %s" % nama)
    if not kondisi:
        gagal.append(nama)


# ── Data: bulan penuh (September, 31 hari terisi) vs 3 hari (Oktober) ────────
TMP = Path(tempfile.mkdtemp()) / "kelengkapan.db"
db.init_db(TMP)
with db.connect(TMP) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('BRI','bank')")
BRI = db.account_balances(include_inactive=True, path=TMP)[0]["id"]


def tx(tgl, jumlah, kategori="Makan", flow="expense", arah="out"):
    return {"occurred_on": tgl, "direction": arah, "amount": jumlah,
            "account_id": BRI, "category": kategori, "note": "uji", "flow_type": flow}


# September: terisi hampir tiap hari
sep = [tx("2026-09-01", 8000000, "Gaji", "income", "in")]
for d in range(2, 31):
    sep.append(tx("2026-09-%02d" % d, 100000, "Makan"))
db.save_transactions(sep, TMP)

# Oktober: hanya 3 hari
db.save_transactions([
    tx("2026-10-01", 8496600, "Gaji", "income", "in"),
    tx("2026-10-01", 45000, "Makan"),
    tx("2026-10-02", 84000, "Makan"),
    tx("2026-10-03", 301250, "Transport"),
], TMP)

print("\n1. Bulan penuh (September, 30 dari 30 hari)")
k = db.kelengkapan_bulan("2026-09", TMP)
cek("jumlah hari bulan", k["jumlah_hari_bulan"], 30)
cek("hari tercatat", k["hari_tercatat"], 30)
cek("dianggap lengkap", k["lengkap"], True)
cek("peringatan None", k["peringatan"], None)

print("\n2. Bulan baru 3 hari (Oktober) — INI KASUS YANG MEMICU FITUR INI")
k = db.kelengkapan_bulan("2026-10", TMP)
cek("jumlah hari bulan", k["jumlah_hari_bulan"], 31)
cek("hari tercatat", k["hari_tercatat"], 3)
cek("TIDAK dianggap lengkap", k["lengkap"], False)
cek_benar("peringatan terisi", bool(k["peringatan"]))
print("     peringatan: %s" % k["peringatan"])

print("\n3. Peringatan menyebut angka yang benar")
cek_benar("menyebut 3 hari", "3" in (k["peringatan"] or ""))
cek_benar("menyebut 31 hari", "31" in (k["peringatan"] or ""))
cek_benar("menyebut rentang tanggal",
          "2026-10-01" in (k["peringatan"] or "") and "2026-10-03" in (k["peringatan"] or ""))

print("\n4. Bulan tanpa data sama sekali")
k = db.kelengkapan_bulan("2026-06", TMP)
cek("hari tercatat", k["hari_tercatat"], 0)
cek("tidak lengkap", k["lengkap"], False)
cek_benar("peringatan menyebut belum ada transaksi",
          "Belum ada transaksi" in (k["peringatan"] or ""))

print("\n5. Ambang batas: bulan harus terisi >= 60% hari")
# 31 hari -> ambang 18 hari
k = db.kelengkapan_bulan("2026-10", TMP)
cek("ambang untuk Oktober", k["ambang_hari"], 18)
cek("30 hari -> lengkap", db.kelengkapan_bulan("2026-09", TMP)["lengkap"], True)

print("\n6. Terpasang di analisa_lengkap")
# Bulan September lengkap -> tanpa peringatan
a = db.analisa_lengkap("2026-09", TMP)
cek("kelengkapan ada di balasan", "kelengkapan" in a, True)
cek("September lengkap", a["kelengkapan"]["lengkap"], True)
cek("Oktober tidak lengkap",
    db.analisa_lengkap("2026-10", TMP)["kelengkapan"]["lengkap"], False)

print("\n7. Fakta untuk model ikut membawa status kelengkapan")
import monthly_analysis as ma  # noqa: E402
fakta = ma._ringkas_untuk_model(db.analisa_lengkap("2026-10", TMP))
cek_benar("ada bagian kelengkapan_data", "kelengkapan_data" in fakta)
cek("data_lengkap di fakta", fakta["kelengkapan_data"]["data_lengkap"], False)
cek("hari tercatat di fakta", fakta["kelengkapan_data"]["hari_tercatat"], 3)
cek("jumlah hari di fakta", fakta["kelengkapan_data"]["jumlah_hari_bulan"], 31)

print("\n8. Sisa bebas yang menyesatkan tetap dilaporkan — tapi dengan peringatan")
a = db.analisa_lengkap("2026-10", TMP)
print("     sisa_bebas : %s" % db.rupiah(a["angka"]["sisa_bebas"]))
print("     peringatan : %s" % a["kelengkapan"]["peringatan"])
cek_benar("angka tetap ada (tidak disembunyikan)",
          a["angka"]["sisa_bebas"] > 0)
cek_benar("peringatan mendampinginya", bool(a["kelengkapan"]["peringatan"]))

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
