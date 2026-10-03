#!/usr/bin/env python3
"""Uji saldo per tanggal / saldo akhir bulan.

Yang diuji: apakah saldo pada tanggal tertentu benar-benar berbeda dari saldo
hari ini, dan apakah `null` dipakai dengan benar untuk keadaan yang tidak punya
arti (bulan berjalan, bulan tanpa data).

Permintaan yuki, 3 Okt 2026: panel "sisa saldo akhir bulan sebelumnya" tidak
bisa dibangun karena tidak ada endpoint yang menerima tanggal — semua sumber
yang ada selalu mengembalikan saldo HARI INI.

Jalankan:  python3 tests/test_saldo_akhir_bulan.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "saldo.db"
db.init_db(TMP)
gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-54s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


# ── Data: satu akun dengan saldo awal, lalu transaksi lintas bulan ───────────
BRI = db.create_account("BRI", "bank", 1000000, TMP)["id"]
TAB = db.create_account("Tabungan", "savings", 0, TMP)["id"]


def tx(tgl, arah, jumlah, kategori, flow, ke=None):
    d = {"occurred_on": tgl, "direction": arah, "amount": jumlah,
         "account_id": BRI, "category": kategori, "note": "uji", "flow_type": flow}
    if ke:
        d["to_account_id"] = ke
    return d


db.save_transactions([
    tx("2026-09-05", "in", 5000000, "Gaji", "income"),
    tx("2026-09-10", "out", 500000, "Makan", "expense"),
    tx("2026-09-20", "transfer", 1000000, "Tagihan", "transfer", ke=TAB),
], TMP)

db.save_transactions([
    tx("2026-10-05", "in", 8000000, "Gaji", "income"),
    tx("2026-10-10", "out", 750000, "Makan", "expense"),
], TMP)

print("\n1. Saldo akhir September vs saldo hari ini HARUS berbeda")
akhir_sep = db.saldo_per_tanggal("2026-09-30", TMP)
hari_ini = db.net_worth(TMP)
print("     saldo per 2026-09-30 : %s" % db.rupiah(akhir_sep["net_worth"]))
print("     saldo hari ini       : %s" % db.rupiah(hari_ini["net_worth"]))
# 950.000 + 4.500.000 - 500.000 = 5.200.000 (transfer tidak mengubah total)
cek("saldo akhir September", akhir_sep["net_worth"], 5500000)
# + 7.000.000 - 750.000 = 9.500.000
cek("saldo hari ini", hari_ini["net_worth"], 12750000)
print("     -> keduanya BERBEDA: inilah yang tidak bisa dilakukan endpoint lama")

print("\n2. Saldo per tanggal di tengah bulan")
tengah = db.saldo_per_tanggal("2026-09-15", TMP)
# 950.000 + 4.500.000 - 500.000 = 5.200.000 (transaksi 20 Sep belum masuk)
cek("saldo per 2026-09-15", tengah["net_worth"], 5500000)
awal_sep = db.saldo_per_tanggal("2026-09-01", TMP)
cek("saldo per 2026-09-01 (belum ada transaksi)", awal_sep["net_worth"], 1000000)

print("\n3. Saldo per akun juga benar, bukan cuma total")
per_akun = {a["name"]: a["balance"] for a in akhir_sep["accounts"]}
cek("BRI per 30 Sep", per_akun["BRI"], 4500000)     # 1jt + 5jt - 500rb - 1jt
cek("Tabungan per 30 Sep", per_akun["Tabungan"], 1000000)
cek("total = jumlah akun", akhir_sep["net_worth"],
    per_akun["BRI"] + per_akun["Tabungan"])

print("\n4. Likuid vs tidak likuid")
cek("likuid (BRI)", akhir_sep["liquid"], 4500000)
cek("tidak likuid (Tabungan)", akhir_sep["non_liquid"], 1000000)
cek("jumlahnya = total", akhir_sep["liquid"] + akhir_sep["non_liquid"],
    akhir_sep["net_worth"])

print("\n5. Akhir bulan: tanggalnya benar untuk bulan berbeda")
cek("September (30 hari)", db.akhir_bulan("2026-09"), "2026-09-30")
cek("Oktober (31 hari)", db.akhir_bulan("2026-10"), "2026-10-31")
cek("Februari 2026 (28 hari)", db.akhir_bulan("2026-02"), "2026-02-28")
cek("Februari 2028 kabisat (29)", db.akhir_bulan("2028-02"), "2028-02-29")
cek("Desember", db.akhir_bulan("2026-12"), "2026-12-31")

print("\n6. `ringkasan_bulan`: net_worth_akhir untuk bulan yang SUDAH SELESAI")
# Paksa "bulan berjalan" jadi November supaya Sep & Okt dianggap selesai
asli = db.bulan_berjalan
db.bulan_berjalan = lambda path=None: "2026-11"

r_sep = db.ringkasan_bulan("2026-09", TMP)
cek("September: per_tanggal", r_sep["per_tanggal"], "2026-09-30")
cek("September: net_worth_akhir", r_sep["net_worth_akhir"], 5500000)
cek("September: net_worth (hari ini)", r_sep["net_worth"], 12750000)

r_okt = db.ringkasan_bulan("2026-10", TMP)
cek("Oktober: per_tanggal", r_okt["per_tanggal"], "2026-10-31")
cek("Oktober: net_worth_akhir", r_okt["net_worth_akhir"], 12750000)

print("\n7. Bulan BERJALAN: net_worth_akhir harus None, bukan saldo hari ini")
db.bulan_berjalan = lambda path=None: "2026-10"
r = db.ringkasan_bulan("2026-10", TMP)
cek("per_tanggal None", r["per_tanggal"], None)
cek("net_worth_akhir None", r["net_worth_akhir"], None)
cek("net_worth_akhir_liquid None", r["net_worth_akhir_liquid"], None)
cek("tapi net_worth hari ini tetap ada", r["net_worth"], 12750000)
print("     -> kalau ini mengirim saldo hari ini dengan label 'akhir bulan',")
print("        panel akan menampilkan angka yang berubah besok.")

print("\n8. Bulan TANPA data: net_worth_akhir None, bukan saldo bulan sebelumnya")
r_kosong = db.ringkasan_bulan("2026-08", TMP)
cek("ada_data", r_kosong["ada_data"], False)
cek("per_tanggal None", r_kosong["per_tanggal"], None)
cek("net_worth_akhir None", r_kosong["net_worth_akhir"], None)
print("     -> Agustus tidak punya transaksi; saldonya SAMA dengan Juli.")
print("        Mengirim angkanya akan membuat Deny mengira ada aktivitas.")

print("\n9. Bulan depan juga None")
r_depan = db.ringkasan_bulan("2027-01", TMP)
cek("net_worth_akhir None", r_depan["net_worth_akhir"], None)

print("\n10. Rumusnya COCOK dengan v_account_balances")
# Ini pemeriksaan paling penting: kalau rumus Python dan SQL menyimpang,
# "saldo hari ini" dan "saldo akhir bulan" tidak akan nyambung.
hari_ini_akun = {a["name"]: a["balance"]
                 for a in db.account_balances(include_inactive=True, path=TMP)}
per_tgl_skrg = {a["name"]: a["balance"]
                for a in db.saldo_per_tanggal("2099-12-31", TMP)["accounts"]}
cek("BRI sama", per_tgl_skrg["BRI"], hari_ini_akun["BRI"])
cek("Tabungan sama", per_tgl_skrg["Tabungan"], hari_ini_akun["Tabungan"])
print("     -> saldo 'per tanggal jauh di depan' = saldo hari ini, seperti seharusnya")

db.bulan_berjalan = asli

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
