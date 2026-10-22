#!/usr/bin/env python3
"""Uji transfer lewat jalur chat — tanpa memanggil model.

Yang diuji (bug 22 Okt 2026): "Pindah dana 100000 ke Tabungan" ditolak dengan
"akun tidak disebutkan", padahal akun TUJUAN jelas disebut dan yang kurang
adalah akun ASAL. Tiga hal yang harus tetap benar:

  1. "ke Y" dikenali sebagai TUJUAN, "dari X" sebagai ASAL — deterministik,
     dari kalimat asli, tanpa menebak.
  2. Pesan galat menyebut PERAN yang kurang ("akun asal"/"akun tujuan"),
     bukan "akun tidak disebutkan".
  3. Transfer yang benar-benar lengkap tersimpan 1 baris, memindahkan uang
     (saldo dua akun berubah, total tidak).

Jalankan:  python3 tests/test_transfer_chat.py
"""
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import chat_entry    # noqa: E402
import chat_gate     # noqa: E402
import db            # noqa: E402
import parser_wrap   # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji-transfer.db"
db.init_db(TMP)
for nama, jenis, saldo in [("Mandiri", "bank", 1000000),
                           ("Tabungan", "savings", 500000),
                           ("BRI", "bank", 250000)]:
    with db.connect(TMP) as conn:
        conn.execute("INSERT INTO accounts (name, kind, opening_balance) VALUES (?,?,?)",
                     (nama, jenis, saldo))
db.DB_PATH = TMP

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-46s %r" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r, harusnya %r" % (nama, dapat, harap))


def model_bodoh(teks):
    """Tiruan keluaran model LAMA: akun tujuan ditaruh di account_hint,
    dua akun ditempel jadi satu string, to_account_hint tidak pernah diisi."""
    if "dari" in teks.lower():
        hint = "Mandiri -> Tabungan"
    elif "ke" in teks.lower():
        hint = "Tabungan"
    else:
        hint = None
    return {"transactions": [{
        "direction": "transfer", "amount": 100000, "category": None,
        "note": teks, "occurred_on": "2026-10-22", "assumed_date": True,
        "account_hint": hint,
    }], "question": None}


chat_entry.parse = model_bodoh          # nol panggilan model di uji ini

print("\n1. Kalimat Deny: 'Pindah dana 100000 ke Tabungan'")
teks = "Pindah dana 100000 ke Tabungan"
hasil = parser_wrap.parse_kontrak(teks)
tx = hasil["draft"]["transactions"][0]
cek("akun asal tidak dikarang", tx["account_hint"], None)
cek("akun tujuan dari 'ke'", tx["to_account_hint"], "Tabungan")

draf = chat_gate.draft(teks)
tampil = chat_gate.render_draft(draf)
print("     --- tampilan draft ---")
for baris in tampil.splitlines():
    print("     " + baris)
cek("draft: akun asal belum jelas", draf["draft"]["perlu_akun"], True)
cek("draft: akun tujuan SUDAH jelas", draf["draft"]["perlu_akun_tujuan"], False)
cek("tampilan menyebut 'Akun asal'", "Akun asal belum jelas" in tampil, True)
cek("tampilan TIDAK bilang 'akun tidak disebutkan'",
    "akun tidak disebutkan" in tampil, False)

print("\n2. Simpan kalimat Deny harus DITOLAK dengan pesan yang benar")
out = chat_gate.simpan(draf, {"pengirim": "deny", "kanal": "uji", "teks": "simpan"},
                       path=TMP, path_log=Path(TMP).parent / "uji-simpan.log")
print("     pesan:", out["message"])
cek("ditolak", out["ok"], False)
cek("pesan menyebut 'akun asal'", "akun asal tidak disebutkan" in out["message"], True)
cek("pesan TIDAK bilang 'akun tidak disebutkan' (tanpa peran)",
    out["message"].startswith("akun tidak disebutkan"), False)
cek("pesan memberi contoh lengkap", "dari Mandiri ke Tabungan" in out["message"], True)
cek("nol baris tersimpan", out["tersimpan"], 0)

print("\n3. Kalimat lengkap: 'Pindah dana 100000 dari Mandiri ke Tabungan'")
teks = "Pindah dana 100000 dari Mandiri ke Tabungan"
tx = parser_wrap.parse_kontrak(teks)["draft"]["transactions"][0]
cek("akun asal dari 'dari'", tx["account_hint"], "Mandiri")
cek("akun tujuan dari 'ke'", tx["to_account_hint"], "Tabungan")

draf = chat_gate.draft(teks)
tampil = chat_gate.render_draft(draf)
cek("draft: tidak ada akun yang kurang",
    (draf["draft"]["perlu_akun"], draf["draft"]["perlu_akun_tujuan"]), (False, False))

sebelum = {b["name"]: b["balance"] for b in db.account_balances(TMP)}
jumlah_sebelum = sum(sebelum.values())
with db.connect(TMP) as conn:
    n_sebelum = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]

out = chat_gate.simpan(draf, {"pengirim": "deny", "kanal": "uji", "teks": "simpan"},
                       path=TMP, path_log=Path(TMP).parent / "uji-simpan.log")
cek("tersimpan", out["ok"], True)
cek("tepat 1 baris", out.get("count"), 1)

sesudah = {b["name"]: b["balance"] for b in db.account_balances(TMP)}
print("     saldo sebelum:", sebelum)
print("     saldo sesudah:", sesudah)
cek("Mandiri -100000", sesudah["Mandiri"] - sebelum["Mandiri"], -100000)
cek("Tabungan +100000", sesudah["Tabungan"] - sebelum["Tabungan"], 100000)
cek("BRI tidak berubah", sesudah["BRI"] - sebelum["BRI"], 0)
cek("total saldo tidak berubah", sum(sesudah.values()) - jumlah_sebelum, 0)
with db.connect(TMP) as conn:
    n_sesudah = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    baris = conn.execute("SELECT direction, flow_type, account_id, to_account_id, amount,"
                         " category_id FROM transactions ORDER BY id DESC LIMIT 1").fetchone()
cek("jumlah transaksi +1", n_sesudah - n_sebelum, 1)
cek("flow_type transfer", baris["flow_type"], "transfer")
cek("direction transfer", baris["direction"], "transfer")
cek("kategori kosong untuk transfer", baris["category_id"], None)
cek("akun asal = Mandiri (id 1)", baris["account_id"], 1)
cek("akun tujuan = Tabungan (id 2)", baris["to_account_id"], 2)

print("\n4. Aturan pengenalan akun — tanpa tebak")
UJI = [
    # (teks, hint dari model, asal harap, tujuan harap)
    ("pindah 50000 dari BRI ke Tabungan", None, "BRI", "Tabungan"),
    ("pindah dana 100000 ke Tabungan", "Tabungan", None, "Tabungan"),
    ("pindah dana 100000 dari Mandiri ke Tabungan", "Mandiri -> Tabungan",
     "Mandiri", "Tabungan"),
    ("pindah dana 100000", None, None, None),
    ("pindah 25000 ke Bank Mandiri", None, None, "Bank Mandiri"),
]
for teks, hint, asal, tujuan in UJI:
    tx = {"direction": "transfer", "account_hint": hint, "to_account_hint": None}
    hasil = parser_wrap.lengkapi_akun_transfer(dict(tx), teks)
    cek("%-46s" % teks, (hasil["account_hint"], hasil["to_account_hint"]),
        (asal, tujuan))

print("\n5. Non-transfer tidak disentuh")
tx = {"direction": "out", "account_hint": "BRI", "to_account_hint": None}
cek("pengeluaran tetap apa adanya",
    parser_wrap.lengkapi_akun_transfer(dict(tx), "makan 45000 ke warung"),
    {"direction": "out", "account_hint": "BRI", "to_account_hint": None})

print("\n6. Akun tujuan yang tidak ada -> pesan peran, bukan tebakan")
draf = chat_gate.draft("pindah dana 100000 dari Mandiri ke BCA")
out = chat_gate.simpan(draf, {"pengirim": "deny", "kanal": "uji", "teks": "simpan"},
                       path=TMP, path_log=Path(TMP).parent / "uji-simpan.log")
print("     pesan:", out["message"])
cek("ditolak", out["ok"], False)
cek("pesan menyebut 'akun tujuan'", "akun tujuan 'BCA' tidak ditemukan" in out["message"], True)

print("\n7. Database utuh")
with db.connect(TMP) as conn:
    cek("integrity_check", conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")

print("\n" + "─" * 70)
if gagal:
    print("HASIL: %d GAGAL dari %d" % (len(gagal), len(gagal) + 30))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji transfer lulus")
