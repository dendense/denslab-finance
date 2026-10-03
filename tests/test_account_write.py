#!/usr/bin/env python3
"""Uji jalur tulis akun — `create_account` dan `update_account`.

Dijalankan di database SEMENTARA. `finance.db` berisi data keuangan sungguhan
dan tidak boleh dipakai untuk menguji pembuatan akun.

Jalankan:  python3 test_account_write.py
"""
import tempfile
from pathlib import Path
import sys

# Kode ada di src/, satu tingkat di atas tests/ atau scripts/
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import db  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji_akun.db"
db.init_db(TMP)

# seed.sql SENGAJA tidak menyisipkan akun (akun bawaan yang muncul kembali
# setiap restart pernah membuat akun Deny hidup lagi). Jadi uji ini membuat
# akun keduanya sendiri untuk menguji nama duplikat.
with db.connect(TMP) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('Tunai','cash')")

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-48s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_gagal(nama, fn):
    try:
        fn()
        print("  GAGAL %-48s seharusnya ditolak" % nama)
        gagal.append(nama)
    except ValueError as e:
        print("  OK    %-48s ditolak: %s" % (nama, str(e)[:44]))


print("\n1. Tambah akun")
a = db.create_account("Mandiri", "bank", 1500000, TMP)
cek("nama", a["name"], "Mandiri")
cek("jenis", a["kind"], "bank")
cek("saldo awal", a["opening_balance"], 1500000)

print("\n2. Saldo awal ikut terhitung di net_worth")
# akun seed: Tunai/BCA/Tabungan (0) + Mandiri (1.400.000)
cek("net_worth", db.net_worth(TMP)["net_worth"], 1500000)
cek("likuid (bank masuk likuid)", db.net_worth(TMP)["liquid"], 1500000)

print("\n3. Nama duplikat ditolak (beda huruf besar/kecil sekalipun)")
cek_gagal("tambah 'Mandiri' lagi", lambda: db.create_account("Mandiri", "bank", 0, TMP))
cek_gagal("tambah 'MANDIRI'", lambda: db.create_account("MANDIRI", "bank", 0, TMP))
cek_gagal("tambah '  mandiri  '", lambda: db.create_account("  mandiri  ", "bank", 0, TMP))

print("\n4. Nama kosong ditolak")
cek_gagal("tambah nama kosong", lambda: db.create_account("", "bank", 0, TMP))
cek_gagal("tambah nama spasi", lambda: db.create_account("   ", "bank", 0, TMP))

print("\n5. Ubah nama")
h = db.update_account(a["id"], name="Mandiri Syariah", path=TMP)
cek("nama baru", h["name"], "Mandiri Syariah")
cek("jenis tidak berubah", h["kind"], "bank")
cek("saldo awal tidak berubah", h["opening_balance"], 1500000)
cek("net_worth tidak berubah oleh ganti nama", db.net_worth(TMP)["net_worth"], 1500000)

print("\n6. Ganti nama ke nama yang sudah dipakai ditolak")
cek_gagal("rename ke 'Tunai'",
          lambda: db.update_account(a["id"], name="Tunai", path=TMP))

print("\n7. Nonaktifkan akun — saldo & riwayat tetap, hilang dari daftar")
NAMA_AKHIR = "Mandiri Syariah"   # sudah di-rename di §5
db.update_account(a["id"], is_active=0, path=TMP)
aktif = [x["name"] for x in db.account_balances(path=TMP)]
cek("akun nonaktif tidak muncul di daftar", NAMA_AKHIR in aktif, False)
cek("net_worth TIDAK berubah saat dinonaktifkan",
    db.net_worth(TMP)["net_worth"], 1500000)
cek("saldo akun nonaktif tetap terhitung di balance_inactive",
    db.net_worth(TMP)["balance_inactive"], 1500000)
cek("account_count_all menurun setelah dinonaktifkan",
    db.net_worth(TMP)["account_count_all"], 1)   # 2 akun - Mandiri nonaktif
semua = [x["name"] for x in db.account_balances(include_inactive=True, path=TMP)]
cek("masih ada kalau diminta termasuk nonaktif", NAMA_AKHIR in semua, True)

print("\n8. Aktifkan lagi")
db.update_account(a["id"], is_active=1, path=TMP)
aktif = [x["name"] for x in db.account_balances(path=TMP)]
cek("kembali muncul", NAMA_AKHIR in aktif, True)
cek("balance_inactive kembali 0", db.net_worth(TMP)["balance_inactive"], 0)

print("\n9. Akun tidak ada ditolak")
cek_gagal("patch id 9999", lambda: db.update_account(9999, name="X", path=TMP))

print("\n10. Transaksi tetap bisa disimpan ke akun baru")
ids = db.save_transactions([{
    "occurred_on": "2026-10-03", "direction": "out", "amount": 25000,
    "account_hint": "Mandiri", "category": "Makan", "note": "uji",
    "flow_type": "expense"}], TMP)
cek("tersimpan", len(ids), 1)
saldo = {x["name"]: x["balance"] for x in db.account_balances(path=TMP)}
cek("saldo berkurang 25.000", saldo[NAMA_AKHIR], 1500000 - 25000)

print("\n11. AKUN TIDAK BOLEH DITEBAK — ini bug yang ditemukan yuki")
cek_gagal("transaksi tanpa akun (2 akun aktif)",
          lambda: db.save_transactions([{
              "occurred_on": "2026-10-03", "direction": "out", "amount": 1000,
              "category": "Makan", "note": "tanpa akun"}], TMP))
cek_gagal("transaksi dengan akun yang tidak ada",
          lambda: db.save_transactions([{
              "occurred_on": "2026-10-03", "direction": "out", "amount": 1000,
              "account_hint": "gopay", "category": "Makan", "note": "x"}], TMP))

print("\n12. Kalau HANYA ada satu akun aktif, boleh tanpa petunjuk")
TMP2 = Path(tempfile.mkdtemp()) / "uji_satu_akun.db"
db.init_db(TMP2)
with db.connect(TMP2) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('Satu-satunya','cash')")
ids = db.save_transactions([{
    "occurred_on": "2026-10-03", "direction": "out", "amount": 5000,
    "category": "Makan", "note": "tanpa akun, cuma 1 akun aktif"}], TMP2)
cek("tersimpan ke satu-satunya akun aktif", len(ids), 1)

print("\n" + "─" * 72)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
