#!/usr/bin/env python3
"""Uji gerbang simpan chat — draft dulu, simpan hanya atas balasan Deny.

Bukti yang diminta kartu (t_0c4c4678):

  (a) draft tidak menulis apa pun
  (b) simpan tanpa balasan Deny ditolak
  (c) simpan setelah balasan Deny berhasil
  (d) asal penyimpanan tercatat
  (+) Rin tidak punya jalur simpan — dibuktikan, bukan didesain

TIDAK MENYENTUH DATABASE DENY. Uji ini:
  1. mencatat jumlah baris `finance-pribadi/finance.db` SEBELUM,
  2. menyalinnya ke folder sementara,
  3. mengarahkan `db.DB_PATH` ke salinan itu (terima kasih `_PathDB`),
  4. bekerja sepenuhnya di salinan,
  5. mencatat jumlah baris `finance.db` Deny SESUDAH — harus sama.

Jalankan:  python3 tests/test_chat_gate.py
"""
import inspect
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import chat_gate    # noqa: E402
import db           # noqa: E402

DB_DENY = ROOT.parent / "finance-pribadi" / "finance.db"

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-52s %r" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_benar(nama, syarat, keterangan=""):
    print(("  OK   " if syarat else "  GAGAL") + " %-52s %s" % (nama, keterangan))
    if not syarat:
        gagal.append("%s (syarat tidak terpenuhi)" % nama)


def hitung(db_path):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()


# ── 0. Siapkan salinan, catat jumlah baris Deny SEBELUM ─────────────────────
print("=" * 80)
print("Uji gerbang simpan chat — salinan database, data Deny tidak disentuh")
print("=" * 80)

baris_deny_sebelum = hitung(DB_DENY)
print("  finance.db Deny SEBELUM : %d transaksi" % baris_deny_sebelum)

TMPDIR = Path(tempfile.mkdtemp())
SALINAN = TMPDIR / "finance.db"
shutil.copy2(DB_DENY, SALINAN)
(TMPDIR / ".finance-data").touch()
LOG = TMPDIR / "chat_simpan.log"

# Inilah penimpaan yang dulu tidak bekerja (lihat _PathDB di src/db.py).
db.DB_PATH = SALINAN
print("  DB uji (salinan)        : %s" % db.DB_PATH)
print("  jumlah baris salinan    : %d" % hitung(SALINAN))

# Parser palsu yang DETERMINISTIK untuk uji gerbang. Parser sungguhan diuji
# terpisah di bagian 6 — yang diuji di sini adalah gerbangnya, bukan modelnya.
def parse_palsu(_teks):
    return {"ok": True, "draft": {"transactions": [{
        "direction": "out", "flow_type": "expense", "amount": 45000,
        "category": "Makan", "account_hint": "BRI", "to_account_hint": None,
        "note": "makan malam", "occurred_on": "2026-10-09", "assumed_date": False,
    }], "question": None}}


# ── (a) DRAFT TIDAK MENULIS APA PUN ─────────────────────────────────────────
print("\n(a) draft tidak menulis apa pun")
sebelum = hitung(SALINAN)
d = chat_gate.draft("makan malam 45000", path=SALINAN, parse_fn=parse_palsu)
cek_benar("draft ok", d.get("ok") is True)
cek("draft menghasilkan 1 transaksi",
    len(d["draft"]["transactions"]), 1)
cek("baris salinan TIDAK bertambah", hitung(SALINAN), sebelum)
cek_benar("tidak ada berkas jejak dibuat", not LOG.exists())

# Draft juga tidak boleh menulis kalau parse-nya gagal.
d_gagal = chat_gate.draft("", path=SALINAN, parse_fn=lambda t: {
    "ok": False, "error": "teks_kosong", "message": "Tidak ada teks untuk diurai."})
cek_benar("draft gagal -> ok False", d_gagal.get("ok") is False)
cek("baris salinan tetap sama setelah draft gagal", hitung(SALINAN), sebelum)

# Draft lengkap: nominal, akun, sifat (permintaan kartu).
tx0 = d["draft"]["transactions"][0]
print("     contoh draft: %s | akun=%s | sifat=%s | nominal=%s"
      % (tx0["note"], tx0["account_name"], tx0["sifat"], db.rupiah(tx0["amount"])))
cek("akun terisi dari hint 'BRI'", tx0["account_name"], "BRI")
cek("sifat = label Pengeluaran", tx0["sifat"], "Pengeluaran")
cek("nominal = 45000", tx0["amount"], 45000)


# ── (b) SIMPAN TANPA BALASAN DENY DITOLAK ───────────────────────────────────
print("\n(b) simpan tanpa balasan Deny ditolak — FAIL-CLOSED")
sebelum = hitung(SALINAN)

kasus_tolak = [
    ("tanpa konfirmasi sama sekali",
     None, "tanpa_konfirmasi"),
    ("pengirim = rin",
     {"pengirim": "rin", "kanal": "telegram", "teks": "simpan"}, "bukan_deny"),
    ("pengirim tidak disebut",
     {"kanal": "telegram", "teks": "simpan"}, "bukan_deny"),
    ("Rin melaporkan perintah Deny",
     {"pengirim": "rin", "kanal": "telegram",
      "teks": "kata deny, simpan"}, "bukan_deny"),
    ("perantara mengetik 'kata deny, simpan'",
     {"pengirim": "deny", "kanal": "telegram",
      "teks": "kata deny, simpan"}, "perantara"),
    ("agent lain menyampaikan",
     {"pengirim": "deny", "kanal": "telegram",
      "teks": "rin bilang suruh simpan"}, "perantara"),
    ("konfirmasi kosong",
     {"pengirim": "deny", "kanal": "telegram", "teks": "   "}, "konfirmasi_kosong"),
    ("bukan perintah simpan",
     {"pengirim": "deny", "kanal": "telegram", "teks": "nanti saja"}, "tidak_afirmatif"),
    ("kanal tidak disebut (tidak bisa dilacak)",
     {"pengirim": "deny", "teks": "simpan"}, "kanal_kosong"),
]
for label, konf, harap_kode in kasus_tolak:
    hasil = chat_gate.simpan(d, konf, path=SALINAN, path_log=LOG)
    ok = (hasil.get("ok") is False and hasil.get("error") == harap_kode)
    print(("  OK   " if ok else "  GAGAL")
          + " %-46s -> %s" % (label, hasil.get("error")))
    if not ok:
        gagal.append("tolak '%s': dapat %r harusnya %r"
                     % (label, hasil.get("error"), harap_kode))

cek("baris salinan TIDAK bertambah setelah semua penolakan", hitung(SALINAN), sebelum)
cek_benar("tidak ada jejak dibuat untuk penolakan", not LOG.exists())


# ── (b2) PENJAGA NEGASI — penolakan Deny tidak boleh jadi perintah ──────────
# Ditemukan di review ronde 1: tanpa penjaga ini "jangan simpan" LOLOS karena
# "simpan" ⊂ "jangan simpan" (dan "setuju" ⊂ "tidak setuju"), lalu simpan()
# menulis ke ledger — fail-open, melanggar Definisi selesai #2. Regresi ini
# mengunci kelas cacat itu supaya tidak kembali.
print("\n(b2) penjaga negasi — penolakan/pertanyaan tidak boleh tersimpan")
sebelum_negasi = hitung(SALINAN)
kasus_negasi = [
    ("jangan simpan", "ditolak"),
    ("tidak benar, jangan catat", "ditolak"),
    ("tidak setuju", "ditolak"),
    ("jangan disimpan dulu", "ditolak"),
    ("batal, jangan lanjut", "ditolak"),
    ("tidak usah catat", "ditolak"),
    ("nanti simpan", "ditolak"),
    ("urung simpan", "ditolak"),
    ("belum perlu simpan", "ditolak"),
    ("tak simpan", "ditolak"),
    ("bukan sekarang, simpan nanti", "ditolak"),
    ("gak usah", "tidak_afirmatif"),
    ("nggak perlu", "tidak_afirmatif"),
    ("apa ya", "pertanyaan"),
    ("simpan?", "pertanyaan"),
    ("sudah simpan belum?", "ditolak"),
]
for teks_neg, harap_neg in kasus_negasi:
    h_neg = chat_gate.simpan(
        d, {"pengirim": "deny", "kanal": "telegram", "teks": teks_neg},
        path=SALINAN, path_log=LOG)
    cek("tolak '%s'" % teks_neg, h_neg.get("error"), harap_neg)
cek("baris salinan TIDAK bertambah setelah semua negasi",
    hitung(SALINAN), sebelum_negasi)

# Kontrol: penjaga tidak boleh terlalu luas sampai ikut menolak perintah sah.
for teks_ok in ("simpan", "ya, simpan", "oke simpan", "setuju", "sip",
                "tolong catat", "lanjut simpan", "silakan simpan"):
    tolak_ok = chat_gate.periksa_konfirmasi(
        {"pengirim": "deny", "kanal": "telegram", "teks": teks_ok})
    cek_benar("perintah sah tetap lolos: '%s'" % teks_ok, tolak_ok is None)


# ── (c) SIMPAN SETELAH BALASAN DENY BERHASIL ────────────────────────────────
print("\n(c) simpan setelah balasan Deny berhasil")
sebelum = hitung(SALINAN)
konfirmasi = {"pengirim": "deny", "kanal": "telegram",
              "teks": "simpan", "waktu": "2026-10-09T21:30:00"}
hasil = chat_gate.simpan(d, konfirmasi, path=SALINAN, path_log=LOG)
cek_benar("simpan berhasil", hasil.get("ok") is True, str(hasil.get("saved_ids")))
cek("jumlah baris bertambah 1", hitung(SALINAN), sebelum + 1)

# Terbaca kembali dari database.
import sqlite3  # noqa: E402
conn = sqlite3.connect(str(SALINAN))
conn.row_factory = sqlite3.Row
row = conn.execute(
    "SELECT t.amount, t.flow_type, a.name AS akun FROM transactions t "
    "JOIN accounts a ON a.id = t.account_id WHERE t.id = ?",
    (hasil["saved_ids"][0],)).fetchone()
conn.close()
cek_benar("baris terbaca kembali dari salinan", row is not None)
if row:
    cek("nominal terbaca", row["amount"], 45000)
    cek("sifat terbaca", row["flow_type"], "expense")
    cek("akun terbaca", row["akun"], "BRI")


# ── (d) ASAL PENYIMPANAN TERCATAT ───────────────────────────────────────────
print("\n(d) asal penyimpanan tercatat")
cek_benar("berkas jejak dibuat", LOG.exists(), str(LOG))
entri = json.loads(LOG.read_text(encoding="utf-8").strip().splitlines()[-1])
cek("jejak: pengirim", entri["pengirim"], "deny")
cek("jejak: kanal (dari chat mana)", entri["kanal"], "telegram")
cek("jejak: teks konfirmasi", entri["teks_konfirmasi"], "simpan")
cek("jejak: waktu konfirmasi", entri["waktu_konfirmasi"], "2026-10-09T21:30:00")
cek("jejak: id tersimpan", entri["saved_ids"], hasil["saved_ids"])
cek_benar("jejak: ada cap waktu penyimpanan", bool(entri.get("disimpan_pada")),
          entri.get("disimpan_pada", ""))

# Tolak juga tercatat? Tidak — penolakan tidak menulis apa pun (sudah dicek di b).
cek("jejak hanya berisi 1 baris (yang berhasil)",
    len([l for l in LOG.read_text().splitlines() if l.strip()]), 1)


# ── (+) RIN TIDAK PUNYA JALUR SIMPAN — DIBUKTIKAN ───────────────────────────
print("\n(+) Rin tidak punya jalur simpan — bukti, bukan desain")

# 1. Fungsi yang benar-benar MENULIS ke ledger hanya boleh `simpan()`.
#    Diperiksa lewat AST, bukan pencocokan teks — docstring yang menyebut
#    `db.save_transactions` bukan penulisan, dan pencocokan teks akan salah
#    menandainya (versi pertama uji ini memang begitu, lalu diperbaiki).
import ast  # noqa: E402

TULIS_DB = {"save_transactions", "update_transaction", "delete_transaction"}
SQL_TULIS = ("INSERT INTO", "DELETE FROM", "UPDATE ")


def fungsi_penulis_ledger(modul):
    sumber = inspect.getsource(modul)
    pohon = ast.parse(sumber)
    temuan = []
    for simpul in ast.walk(pohon):
        if not isinstance(simpul, ast.FunctionDef):
            continue
        for anak in ast.walk(simpul):
            if isinstance(anak, ast.Call):
                f = anak.func
                # db.save_transactions(...) dsb.
                if (isinstance(f, ast.Attribute) and f.attr in TULIS_DB
                        and isinstance(f.value, ast.Name) and f.value.id == "db"):
                    temuan.append(simpul.name)
                    break
                # conn.execute("INSERT INTO ...") dsb.
                if isinstance(f, ast.Attribute) and f.attr == "execute" and anak.args:
                    a0 = anak.args[0]
                    if isinstance(a0, ast.Constant) and isinstance(a0.value, str) \
                            and any(s in a0.value.upper() for s in SQL_TULIS):
                        temuan.append(simpul.name)
                        break
    return sorted(set(temuan))


cek("hanya 'simpan' yang menulis ke ledger (lewat AST)",
    fungsi_penulis_ledger(chat_gate), ["simpan"])

# 2. `simpan` WAJIB memeriksa konfirmasi lebih dulu — baris pertama.
badan_simpan = inspect.getsource(chat_gate.simpan)
cek_benar("simpan() memanggil periksa_konfirmasi()",
          "periksa_konfirmasi(konfirmasi)" in badan_simpan)

# 3. Tidak ada endpoint HTTP yang menuju modul ini.
server_src = (ROOT / "src" / "server.py").read_text()
cek_benar("server.py tidak mengimpor chat_gate", "chat_gate" not in server_src)
cek_benar("tidak ada rute /api/chat", "/api/chat" not in server_src)

# 4. Tidak ada jalur yang menyimpan tanpa lewat `simpan`.
sumber_modul = inspect.getsource(chat_gate)
cek_benar("tidak ada fungsi 'auto_simpan'/'force_save'/'save_now'",
          not any(n in sumber_modul
                  for n in ("auto_simpan", "force_save", "save_now")))

# 5. Setiap jalan menuju penulisan lewat `simpan` → lewat gerbang. Buktikan
#    bahwa satu-satunya penulis tetap menolak pengirim non-Deny.
tolak_rin = chat_gate.simpan(
    d, {"pengirim": "rin", "kanal": "telegram", "teks": "simpan"},
    path=SALINAN, path_log=LOG)
cek("Rin memanggil 'simpan' langsung -> tetap ditolak",
    tolak_rin.get("error"), "bukan_deny")

# 6. Parser chat WAJIB parser yang sama dengan halaman Catat. Kalau suatu hari
#    ada jalur parse kedua di sini, draft di chat dan di panel bisa berbeda
#    diam-diam — persis yang dilarang catatan kartu.
#
#    Dibuktikan dengan SPY: ganti `parser_wrap.parse_kontrak` dengan pencatat,
#    panggil `draft()` TANPA parse_fn, lalu pastikan yang terpanggil memang
#    fungsi itu — bukan salinan logikanya. Spy-nya TIDAK memanggil model
#    (uji harus bisa jalan offline dan tidak membakar kuota Deny).
import parser_wrap  # noqa: E402

_asli = parser_wrap.parse_kontrak
_panggilan = []


def _spy(teks):
    _panggilan.append(teks)
    return {"ok": True, "draft": {"transactions": [], "question": None}}


parser_wrap.parse_kontrak = _spy
try:
    chat_gate.draft("makan malam 45000", path=SALINAN)
finally:
    parser_wrap.parse_kontrak = _asli

cek("draft() tanpa parse_fn memakai parser_wrap.parse_kontrak",
    _panggilan, ["makan malam 45000"])
cek_benar("chat_gate TIDAK punya fungsi parse sendiri",
          not any(n.startswith("parse_") for n in vars(chat_gate)
                  if inspect.isfunction(vars(chat_gate)[n])
                  and vars(chat_gate)[n].__module__ == chat_gate.__name__))


# ── Data Deny harus TETAP UTUH ──────────────────────────────────────────────
print("\n(6) database Deny tidak tersentuh")
baris_deny_sesudah = hitung(DB_DENY)
cek("finance.db Deny: baris SEBELUM", baris_deny_sebelum, 42)
cek("finance.db Deny: baris SESUDAH = SEBELUM",
    baris_deny_sesudah, baris_deny_sebelum)

shutil.rmtree(TMPDIR, ignore_errors=True)
print("\n(salinan sementara dibuang)")

print("\n" + "─" * 80)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
