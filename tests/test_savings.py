#!/usr/bin/env python3
"""Uji target tabungan.

Yang paling penting diuji: progres dihitung dari SALDO AKUN, bukan dari angka
yang disimpan. Kalau progres disimpan, koreksi transaksi akan membuatnya basi
tanpa ada yang tahu.

Jalankan:  python3 tests/test_savings.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "tabungan.db"
db.init_db(TMP)
gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-52s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_gagal(nama, fn):
    try:
        fn()
        print("  GAGAL %-52s seharusnya ditolak" % nama)
        gagal.append(nama)
    except ValueError as e:
        print("  OK    %-52s ditolak: %s" % (nama, str(e)[:34]))


# seed.sql tidak menyediakan akun — uji ini membuatnya sendiri
BRI = db.create_account("BRI", "bank", 5000000, TMP)["id"]
TAB = db.create_account("Tabungan", "savings", 0, TMP)["id"]
REK = db.create_account("Reksadana", "investment", 0, TMP)["id"]

print("\n1. Sebelum ada target")
cek("target_aktif None", db.target_aktif(TMP), None)

print("\n2. Pasang target 'Dana Darurat' Rp 20 juta")
t = db.set_target("Dana Darurat", 20000000, account_id=TAB, path=TMP)
cek("nama", t["name"], "Dana Darurat")
cek("target", t["target_amount"], 20000000)
cek("akun", t["account_name"], "Tabungan")
cek("terkumpul", t["terkumpul"], 0)
cek("sisa", t["sisa"], 20000000)
cek("persen", t["persen"], 0)
cek("status", t["status"], "belum_mulai")
cek("riwayat setoran kosong", t["riwayat_setoran"], [])
cek("rata setoran None (bukan 0)", t["rata_setoran_bulanan"], None)
cek("perkiraan bulan None (tidak dikarang)", t["perkiraan_bulan_lagi"], None)

print("\n3. Setor Rp 2 juta dari BRI ke Tabungan")
db.save_transactions([{
    "occurred_on": "2026-11-05", "direction": "transfer", "amount": 2000000,
    "account_id": BRI, "to_account_id": TAB, "note": "nabung November",
    "flow_type": "transfer"}], TMP)

t = db.target_aktif(TMP)
cek("terkumpul", t["terkumpul"], 2000000)
cek("sisa", t["sisa"], 18000000)
cek("persen", t["persen"], 10)
cek("status", t["status"], "berjalan")
cek("riwayat setoran 1 bulan", len(t["riwayat_setoran"]), 1)
cek("setoran bulan itu", t["riwayat_setoran"][0]["total"], 2000000)
cek("rata setoran bulanan", t["rata_setoran_bulanan"], 2000000)
cek("perkiraan bulan lagi", t["perkiraan_bulan_lagi"], 9)

print("\n4. Progres DIHITUNG ULANG — hapus transaksinya, angka ikut turun")
with db.connect(TMP) as conn:
    conn.execute("DELETE FROM transactions WHERE note = 'nabung November'")
t = db.target_aktif(TMP)
cek("terkumpul kembali 0", t["terkumpul"], 0)
cek("persen kembali 0", t["persen"], 0)
cek("status kembali belum_mulai", t["status"], "belum_mulai")
cek("riwayat ikut bersih", t["riwayat_setoran"], [])

print("\n5. Setor beberapa bulan — rata-rata dihitung dari bulan yang ADA setoran")
db.save_transactions([
    {"occurred_on": "2026-11-05", "direction": "transfer", "amount": 2000000,
     "account_id": BRI, "to_account_id": TAB, "note": "nov", "flow_type": "transfer"},
    {"occurred_on": "2026-12-05", "direction": "transfer", "amount": 3000000,
     "account_id": BRI, "to_account_id": TAB, "note": "des", "flow_type": "transfer"},
], TMP)
t = db.target_aktif(TMP)
cek("terkumpul", t["terkumpul"], 5000000)
cek("persen", t["persen"], 25)
cek("bulan ada setoran", t["bulan_ada_setoran"], 2)
cek("rata setoran (2,5 juta)", t["rata_setoran_bulanan"], 2500000)
cek("perkiraan bulan lagi", t["perkiraan_bulan_lagi"], 6)
cek("riwayat urut terbaru dulu", t["riwayat_setoran"][0]["month"], "2026-12")

print("\n6. Tarik dari tabungan — progres ikut turun")
db.save_transactions([{
    "occurred_on": "2026-12-20", "direction": "transfer", "amount": 1000000,
    "account_id": TAB, "to_account_id": BRI, "note": "tarik", "flow_type": "transfer"}], TMP)
t = db.target_aktif(TMP)
cek("terkumpul turun jadi 4 juta", t["terkumpul"], 4000000)
cek("ada catatan penarikan", len(t["riwayat_penarikan"]), 1)
cek("jumlah penarikan", t["riwayat_penarikan"][0]["total"], 1000000)

print("\n7. Uang di AKUN LAIN tidak dihitung — ini konsekuensi yang harus jelas")
# Nol-kan Tabungan supaya keadaan awalnya jelas, tidak bergantung langkah
# sebelumnya. (Uji sebelumnya sudah mengubah saldonya.)
with db.connect(TMP) as conn:
    conn.execute("UPDATE accounts SET opening_balance = 0 WHERE id = ?", (TAB,))
    conn.execute("DELETE FROM transactions WHERE account_id = ? OR to_account_id = ?",
                 (TAB, TAB))
cek("Tabungan mulai dari 0", db.target_aktif(TMP)["terkumpul"], 0)

db.save_transactions([{
    "occurred_on": "2026-12-25", "direction": "transfer", "amount": 5000000,
    "account_id": BRI, "to_account_id": REK, "note": "ke reksadana",
    "flow_type": "transfer"}], TMP)
cek("terkumpul TIDAK berubah oleh setoran ke akun lain",
    db.target_aktif(TMP)["terkumpul"], 0)

print("\n8. Target terlampaui — status 'tercapai', persen bisa > 100")
# Target saat ini Rp 20 juta (Dana Darurat masih aktif setelah langkah 7?
# Tidak — target masih 'Dana Darurat' 20 juta). Isi Tabungan jadi 25 juta.
with db.connect(TMP) as conn:
    conn.execute("UPDATE accounts SET opening_balance = 25000000 WHERE id = ?", (TAB,))
t = db.target_aktif(TMP)
cek("target yang diuji", t["target_amount"], 20000000)
cek("terkumpul", t["terkumpul"], 25000000)
cek("status", t["status"], "tercapai")
cek("persen", t["persen"], 125)
cek("sisa negatif (kelebihan)", t["sisa"], -5000000)

print("\n9. Ganti target — yang lama diarsipkan, bukan dihapus")
t2 = db.set_target("Motor", 15000000, account_id=TAB, path=TMP)
cek("target baru", t2["name"], "Motor")
cek("target aktif cuma satu", db.target_aktif(TMP)["name"], "Motor")
with db.connect(TMP) as conn:
    n = conn.execute("SELECT COUNT(*) c FROM savings_goals").fetchone()["c"]
    arsip = conn.execute("SELECT COUNT(*) c FROM savings_goals WHERE is_archived=1").fetchone()["c"]
cek("total baris target (jejak tersimpan)", n, 2)
cek("yang diarsipkan", arsip, 1)

print("\n10. Nilai tidak sah ditolak")
cek_gagal("nama kosong", lambda: db.set_target("", 1000, account_id=TAB, path=TMP))
cek_gagal("target nol", lambda: db.set_target("X", 0, account_id=TAB, path=TMP))
cek_gagal("target negatif", lambda: db.set_target("X", -100, account_id=TAB, path=TMP))
cek_gagal("target bukan angka", lambda: db.set_target("X", "abc", account_id=TAB, path=TMP))
cek_gagal("akun tidak ada", lambda: db.set_target("X", 1000, account_hint="gopay", path=TMP))
cek_gagal("tanggal ngawur", lambda: db.set_target("X", 1000, account_id=TAB,
                                                  target_date="2026-13-99", path=TMP))

print("\n11. Arsipkan target")
cek("berhasil diarsipkan", db.hapus_target(TMP), True)
cek("target aktif jadi None", db.target_aktif(TMP), None)
cek("arsip ulang ditolak", db.hapus_target(TMP), False)
with db.connect(TMP) as conn:
    n = conn.execute("SELECT COUNT(*) c FROM savings_goals").fetchone()["c"]
cek("data target TIDAK dihapus", n, 2)

print("\n11b. Gagal pasang target BARU tidak boleh menghilangkan target LAMA")
# Cacat yang ditemukan yuki: kalau arsip-dulu-lalu-insert dipisah, ada jendela
# di mana target lama sudah terarsip tapi yang baru belum masuk. Kalau insert
# gagal di jendela itu, Deny kehilangan targetnya tanpa dapat gantinya.
db.set_target("Target Lama", 10000000, account_id=TAB, path=TMP)
cek("target lama aktif", db.target_aktif(TMP)["name"], "Target Lama")
try:
    # Tanggal tidak sah -> gagal SETELAH validasi lolos, tepat di tengah
    db.set_target("Target Baru", 5000000, account_id=TAB,
                  target_date="bukan-tanggal", path=TMP)
    gagal.append("set_target dengan tanggal ngawur seharusnya ditolak")
    print("  GAGAL seharusnya ditolak")
except ValueError:
    print("  OK    set_target gagal seperti seharusnya (tanggal tidak sah)")
cek("target LAMA masih aktif setelah kegagalan",
    db.target_aktif(TMP)["name"], "Target Lama")
with db.connect(TMP) as conn:
    n_arsip = conn.execute(
        "SELECT COUNT(*) c FROM savings_goals WHERE is_archived=1").fetchone()["c"]
cek("target lama TIDAK ikut terarsip", n_arsip, 2)   # 2 arsip dari langkah 9

print("\n12. Target dengan tenggat")
t = db.set_target("Liburan", 5000000, account_id=TAB, target_date="2027-06-30", path=TMP)
cek("tanggal tersimpan", t["target_date"], "2027-06-30")

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
