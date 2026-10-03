#!/usr/bin/env python3
"""Uji ubah & hapus transaksi.

Dijalankan di database SEMENTARA. database keuangan Deny berisi data
sungguhan dan tidak boleh dipakai untuk menguji penghapusan.

Yang paling penting diuji di sini: perubahan `flow_type` HARUS menarik
`direction` ikut berubah, dan penghapusan HARUS meninggalkan jejak sebelum
barisnya dibuang.

Jalankan:  python3 tests/test_transaction_edit.py
"""
import json
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import db  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji_edit.db"
db.init_db(TMP)
LOG = TMP.parent / "terhapus.log"
gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-50s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_gagal(nama, fn):
    try:
        fn()
        print("  GAGAL %-50s seharusnya ditolak" % nama)
        gagal.append(nama)
    except ValueError as e:
        print("  OK    %-50s ditolak: %s" % (nama, str(e)[:42]))


# Siapkan: dua akun + transaksi
with db.connect(TMP) as conn:
    conn.execute("UPDATE accounts SET is_active = 0")
    conn.execute("INSERT INTO accounts (name, kind, is_active) VALUES ('BRI','bank',1)")
    conn.execute("INSERT INTO accounts (name, kind, is_active) VALUES ('Dompet','cash',1)")

acc = {a["name"]: a["id"] for a in db.account_balances(TMP, include_inactive=True)}
ids = db.save_transactions([{
    "occurred_on": "2026-10-03", "direction": "out", "amount": 45000,
    "account_id": acc["BRI"], "category": "Makan", "note": "makan malam",
    "flow_type": "expense"}], TMP)
TX = ids[0]

print("\n1. Baca satu transaksi")
t = db.get_transaction(TX, TMP)
cek("id", t["id"], TX)
cek("nominal", t["amount"], 45000)
cek("akun", t["account_name"], "BRI")
cek("kategori", t["category_name"], "Makan")
cek("source", t["source"], "manual")
cek("transaksi tidak ada -> None", db.get_transaction(9999, TMP), None)

print("\n2. Ubah nominal & catatan")
h = db.update_transaction(TX, {"amount": 450000, "note": "makan malam keluarga"}, TMP)
cek("nominal baru", h["amount"], 450000)
cek("catatan baru", h["note"], "makan malam keluarga")
cek("kategori tidak berubah", h["category_name"], "Makan")
cek("akun tidak berubah", h["account_name"], "BRI")

print("\n3. Ubah kategori")
h = db.update_transaction(TX, {"category": "Belanja"}, TMP)
cek("kategori baru", h["category_name"], "Belanja")
cek("nominal tetap", h["amount"], 450000)

print("\n4. Ubah tanggal")
h = db.update_transaction(TX, {"occurred_on": "2026-10-05"}, TMP)
cek("tanggal baru", h["occurred_on"], "2026-10-05")

print("\n5. Ubah akun")
h = db.update_transaction(TX, {"account_hint": "Dompet"}, TMP)
cek("akun baru", h["account_name"], "Dompet")

print("\n6. direction TIDAK boleh diubah langsung — ini inti aturannya")
cek_gagal("kirim direction", lambda: db.update_transaction(TX, {"direction": "in"}, TMP))
cek_gagal("kirim id", lambda: db.update_transaction(TX, {"id": 5}, TMP))
cek_gagal("kirim source", lambda: db.update_transaction(TX, {"source": "statement"}, TMP))

print("\n7. flow_type mengubah direction ikut — INI YANG PALING PENTING")
h = db.update_transaction(TX, {"flow_type": "receivable"}, TMP)
cek("flow_type", h["flow_type"], "receivable")
cek("direction ikut jadi out", h["direction"], "out")
h = db.update_transaction(TX, {"flow_type": "income", "category": "Gaji"}, TMP)
cek("flow_type income", h["flow_type"], "income")
cek("direction ikut jadi in", h["direction"], "in")
cek("kategori ikut arah in", h["category_name"], "Gaji")

print("\n8. Ubah ke transfer tanpa akun tujuan harus DITOLAK")
cek_gagal("flow_type=transfer tanpa tujuan",
          lambda: db.update_transaction(TX, {"flow_type": "transfer"}, TMP))

print("\n9. Ubah ke transfer DENGAN akun tujuan")
h = db.update_transaction(TX, {"flow_type": "transfer",
                               "to_account_hint": "BRI"}, TMP)
cek("flow_type", h["flow_type"], "transfer")
cek("direction", h["direction"], "transfer")
cek("akun tujuan", h["to_account_name"], "BRI")
cek("kategori jadi kosong (transfer tidak berkategori)", h["category_name"], None)

print("\n10. transfer ke akun yang sama ditolak")
cek_gagal("transfer ke akun sendiri",
          lambda: db.update_transaction(TX, {"account_hint": "BRI",
                                             "to_account_hint": "BRI"}, TMP))

print("\n11. Kembali ke expense — akun tujuan harus dilepas")
h = db.update_transaction(TX, {"flow_type": "expense", "category": "Makan"}, TMP)
cek("flow_type", h["flow_type"], "expense")
cek("direction", h["direction"], "out")
cek("akun tujuan dilepas", h["to_account_name"], None)

print("\n12. Kirim to_account_id ke transaksi non-transfer ditolak")
cek_gagal("to_account_id pada expense",
          lambda: db.update_transaction(TX, {"to_account_id": acc["BRI"]}, TMP))

print("\n13. Nilai tidak sah ditolak")
cek_gagal("nominal bukan angka", lambda: db.update_transaction(TX, {"amount": "abc"}, TMP))
cek_gagal("nominal nol", lambda: db.update_transaction(TX, {"amount": 0}, TMP))
cek_gagal("nominal negatif", lambda: db.update_transaction(TX, {"amount": -5000}, TMP))
cek_gagal("tanggal ngawur", lambda: db.update_transaction(TX, {"occurred_on": "2026-13-99"}, TMP))
cek_gagal("flow_type ngawur", lambda: db.update_transaction(TX, {"flow_type": "hibah"}, TMP))
cek_gagal("akun tidak ada", lambda: db.update_transaction(TX, {"account_hint": "gopay"}, TMP))
cek_gagal("transaksi tidak ada", lambda: db.update_transaction(9999, {"amount": 1}, TMP))

print("\n14. Gagal TIDAK boleh mengubah apa pun")
sebelum = db.get_transaction(TX, TMP)
try:
    db.update_transaction(TX, {"amount": 999, "flow_type": "ngawur"}, TMP)
except ValueError:
    pass
sesudah = db.get_transaction(TX, TMP)
cek("nominal tidak berubah setelah gagal", sesudah["amount"], sebelum["amount"])
cek("flow_type tidak berubah setelah gagal", sesudah["flow_type"], sebelum["flow_type"])

print("\n15. HAPUS — jejak harus tertulis SEBELUM barisnya dibuang")
n_sebelum = len(db.list_transactions(path=TMP))
dihapus = db.delete_transaction(TX, TMP, log_path=LOG)
n_sesudah = len(db.list_transactions(path=TMP))
cek("jumlah berkurang 1", n_sesudah, n_sebelum - 1)
cek("transaksi benar-benar hilang", db.get_transaction(TX, TMP), None)
cek("berkas jejak dibuat", LOG.exists(), True)

isi_log = [json.loads(l) for l in LOG.read_text().strip().splitlines()]
cek("satu baris tercatat di jejak", len(isi_log), 1)
cek("id di jejak", isi_log[0]["transaksi"]["id"], TX)
cek("nominal di jejak", isi_log[0]["transaksi"]["amount"], dihapus["amount"])
cek("akun di jejak", isi_log[0]["transaksi"]["account_name"], "Dompet")
cek("ada waktu penghapusan", "dihapus_pada" in isi_log[0], True)

print("\n16. Hapus transaksi yang tidak ada ditolak")
cek_gagal("hapus id 9999", lambda: db.delete_transaction(9999, TMP, log_path=LOG))

print("\n17. Saldo ikut menyesuaikan setelah hapus")
acc2 = {a["name"]: a["balance"] for a in db.account_balances(TMP, include_inactive=True)}
cek("saldo Dompet kembali 0", acc2["Dompet"], 0)

print("\n18. seed.sql tidak lagi menyisipkan akun")
teks_seed = (SRC / "seed.sql").read_text()
# Periksa pernyataan INSERT-nya, bukan komentar penjelasan (komentar memang
# menyebut 'Tunai'/'BCA' untuk menceritakan kenapa keduanya dihapus).
insert_akun = [b for b in teks_seed.split(";")
               if "INSERT" in b.upper() and "INTO accounts" in b]
cek("tidak ada INSERT INTO accounts", len(insert_akun), 0)
cek("kategori tetap disisipkan", "INSERT OR IGNORE INTO categories" in teks_seed, True)

print("\n19. init_db() TIDAK membuat akun apa pun di database baru")
TMP2 = Path(tempfile.mkdtemp()) / "kosong.db"
db.init_db(TMP2)
cek("jumlah akun", len(db.get_accounts(include_inactive=True, path=TMP2)), 0)
cek("jumlah kategori", len(db.get_categories(path=TMP2)), 11)

print("\n" + "─" * 74)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
