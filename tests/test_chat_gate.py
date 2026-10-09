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
    ("jgn catat", "ditolak"),
    ("gk usah simpan", "ditolak"),
    ("belom simpan", "ditolak"),
    ("engga simpan", "ditolak"),
    ("gausah simpan", "ditolak"),
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


# ── (b3) DAFTAR PUTIH — arah kegagalan dibalik ──────────────────────────────
# Ditemukan di review ronde 3: penjaga negasi ronde 2 memakai DAFTAR HITAM
# penyangkal, dan daftar hitam bahasa Indonesia informal tidak pernah selesai.
# Bentuk berikut benar-benar TERTULIS ke ledger sebelum perbaikan ini (setiap
# baris ditulis, pengirim "deny"): 'ndak usah simpan', 'ndak simpan',
# 'kagak usah simpan', 'no simpan', 'udah simpan', 'sudah saya simpan'.
# Perbaikan: keputusan akhir bukan "bukan penolakan yang kita kenali", tapi
# "bentuk perintah yang kita akui" — daftar PUTIH. Regresi ini mengunci kelas
# cacat itu supaya tidak kembali lewat kata baru mana pun.
print("\n(b3) daftar putih — bentuk di luar perintah yang diakui DITOLAK")
sebelum_putih = hitung(SALINAN)
kasus_putih = [
    ("ndak usah simpan", "ditolak"),
    ("ndak simpan", "ditolak"),
    ("kagak usah simpan", "ditolak"),
    ("no simpan", "ditolak"),
    ("udah simpan", "ditolak"),
    ("sudah saya simpan", "ditolak"),
    ("mbok simpan", "ditolak"),
    ("simpan aja", "ditolak"),
    ("ya sudah simpan", "ditolak"),
    ("nanti aja simpan", "ditolak"),
    ("ndg simpan", "ditolak"),
    # Kata asing tanpa kata afirmatif sama sekali: sudah ditolak lebih awal
    # sebagai `tidak_afirmatif`. Ditolaknya sama — itu yang penting.
    ("cancel", "tidak_afirmatif"),
    ("stop", "tidak_afirmatif"),
    ("hold", "tidak_afirmatif"),
    ("wait", "tidak_afirmatif"),
    ("tunggu", "tidak_afirmatif"),
    ("skip", "tidak_afirmatif"),
]
for teks_p, harap_p in kasus_putih:
    h_p = chat_gate.simpan(
        d, {"pengirim": "deny", "kanal": "telegram", "teks": teks_p},
        path=SALINAN, path_log=LOG)
    cek("putih tolak '%s'" % teks_p, h_p.get("error"), harap_p)
cek("baris salinan TIDAK bertambah setelah semua bentuk di luar daftar putih",
    hitung(SALINAN), sebelum_putih)

# Unit langsung: daftar putih mengakui HANYA bentuk perintah yang sah.
print("  -- perintah_diizinkan() --")
for teks_sah in ("simpan", "catat", "ya", "iya", "ok", "oke", "sip", "setuju",
                 "benar", "ya simpan", "ya, simpan", "oke simpan", "sip catat",
                 "tolong catat", "lanjut simpan", "silakan simpan", "gas simpan",
                 "ayo catat"):
    cek_benar("diakui: '%s'" % teks_sah, chat_gate.perintah_diizinkan(teks_sah))
for teks_luar in ("ndak usah simpan", "no simpan", "simpan aja", "udah simpan",
                  "sudah saya simpan", "mbok simpan", "simpan dong", "tolong",
                  "ya sudah", "gas", ""):
    cek_benar("di luar daftar putih: '%s'" % teks_luar,
              not chat_gate.perintah_diizinkan(teks_luar))


# ── (b4) KARAKTER ASING — penanda penolakan tidak boleh hilang ──────────────
# Ditemukan di review ronde 4: `_normalisasi_perintah()` versi lama memakai
# `re.sub(r"[^\w\s]+", " ", ...)` dan membuang SEMUA karakter non-huruf/angka
# tanpa syarat. Penanda penolakan lazim di chat ikut terhapus sebelum gerbang
# memutuskan, dan sisa teksnya jadi persis perintah yang diakui daftar putih.
# Bentuk berikut benar-benar TERTULIS ke ledger sebelum perbaikan ini
# (pengirim "deny"): '❌ simpan', '⛔ simpan', '🚫 simpan', '✗ simpan',
# '✖ simpan', 'simpan ❌' — masing-masing baris 42->48 di salinan.
# Perbaikan: hanya pemisah netral (`,` `.` `!`) yang dipetakan ke spasi;
# kalau teks masih memuat karakter di luar huruf/angka/spasi, ditolak.
print("\n(b4) karakter asing — penanda penolakan tidak boleh hilang (fail-closed)")
sebelum_asing = hitung(SALINAN)
kasus_asing = [
    ("\u274c simpan", "ditolak"),
    ("\u26d4 simpan", "ditolak"),
    ("\U0001f6ab simpan", "ditolak"),
    ("\u2717 simpan", "ditolak"),
    ("\u2716 simpan", "ditolak"),
    ("simpan \u274c", "ditolak"),
    ("simpan\U0001f525", "ditolak"),
    # 'si-mpan' tidak memuat kata afirmatif sama sekali, jadi sudah ditolak
    # lebih awal sebagai `tidak_afirmatif`. Ditolaknya sama — itu yang penting.
    ("si-mpan", "tidak_afirmatif"),
]
for teks_a, harap_a in kasus_asing:
    h_a = chat_gate.simpan(
        d, {"pengirim": "deny", "kanal": "telegram", "teks": teks_a},
        path=SALINAN, path_log=LOG)
    cek("asing tolak %r" % teks_a, h_a.get("error"), harap_a)
cek("baris salinan TIDAK bertambah setelah semua bentuk berkarakter asing",
    hitung(SALINAN), sebelum_asing)

# Unit langsung: karakter asing -> False; pemisah netral tetap lolos.
print("  -- perintah_diizinkan() dengan karakter --")
for teks_a in ("\u274c simpan", "\u26d4 simpan", "\U0001f6ab simpan", "\u2717 simpan",
               "\u2716 simpan", "simpan \u274c", "simpan\U0001f525", "si-mpan"):
    cek_benar("berkarakter asing ditolak: %r" % teks_a,
              not chat_gate.perintah_diizinkan(teks_a))
for teks_a in ("ya, simpan", "oke simpan", "tolong catat", "simpan", "ya"):
    cek_benar("pemisah netral tetap lolos: %r" % teks_a,
              chat_gate.perintah_diizinkan(teks_a))


# ── (b5) FIELD NON-STRING — penolakan berbentuk KODE, bukan exception ───────
# Ditemukan di review ronde 4 (lensa Kontrak): `.strip()` dipanggil pada field
# konfirmasi tanpa penjaga tipe, jadi `pengirim=1`, `teks=["simpan"]`, `kanal=99`
# melempar AttributeError — padahal docstring `simpan()` berjanji "tidak pernah
# melempar exception untuk penolakan". Bukan fail-open (nol baris tersimpan),
# tapi cacat kontrak. Regresi ini mengunci: field non-string -> kode
# `konfirmasi_rusak`, bukan exception.
print("\n(b5) field konfirmasi non-string — kode penolakan, bukan exception")
sebelum_tipe = hitung(SALINAN)
kasus_tipe = [
    ("pengirim = 1",          {"pengirim": 1, "kanal": "telegram", "teks": "simpan"}),
    ("pengirim = ['deny']",   {"pengirim": ["deny"], "kanal": "telegram", "teks": "simpan"}),
    ("teks = 12345",          {"pengirim": "deny", "kanal": "telegram", "teks": 12345}),
    ("teks = ['simpan']",     {"pengirim": "deny", "kanal": "telegram", "teks": ["simpan"]}),
    ("kanal = 99",            {"pengirim": "deny", "kanal": 99, "teks": "simpan"}),
    ("kanal = ['telegram']",  {"pengirim": "deny", "kanal": ["telegram"], "teks": "simpan"}),
]
for label_t, konf_t in kasus_tipe:
    try:
        h_t = chat_gate.simpan(d, konf_t, path=SALINAN, path_log=LOG)
        cek("field salah %s -> kode" % label_t, h_t.get("error"), "konfirmasi_rusak")
    except Exception as e:
        cek_benar("field salah %s -> kode (lempar %r)" % (label_t, e), False)
cek("baris salinan TIDAK bertambah setelah semua field salah",
    hitung(SALINAN), sebelum_tipe)

# Field yang HILANG tetap diberi kode sendiri, bukan `konfirmasi_rusak`.
for label_m, konf_m, kode_m in (
        ("pengirim hilang", {"kanal": "telegram", "teks": "simpan"}, "bukan_deny"),
        ("teks hilang", {"pengirim": "deny", "kanal": "telegram"}, "konfirmasi_kosong"),
        ("kanal hilang", {"pengirim": "deny", "teks": "simpan"}, "kanal_kosong")):
    h_m = chat_gate.simpan(d, konf_m, path=SALINAN, path_log=LOG)
    cek("%s -> kode asli" % label_m, h_m.get("error"), kode_m)


# ── (b6) BENTUK SALAH DARI PARSER/DRAFT — kode, bukan exception ─────────────
# Kelas cacat yang sama dengan (b5), tapi di jalur draft: `draft()` dengan
# hasil parser berbentuk salah dan `simpan()` dengan `draft_hasil` berbentuk
# salah dulu melempar AttributeError/TypeError. Ditutup di ronde yang sama
# supaya tidak menyisakan satu pintu lagi untuk kelas yang sama.
print("\n(b6) bentuk salah dari parser/draft — kode, bukan exception")
sebelum_bentuk = hitung(SALINAN)
_konf_sah = {"pengirim": "deny", "kanal": "telegram", "teks": "simpan"}

# draft(): parse_fn mengembalikan bentuk yang tidak dikenal.
for label_b, fn_b in (
        ("parser -> list", lambda t: []),
        ("parser -> str", lambda t: "x"),
        ("parser -> None", lambda t: None),
        ("parser -> draft str", lambda t: {"ok": True, "draft": "x"}),
        ("parser -> tx bukan list", lambda t: {"ok": True, "draft": {"transactions": 5}}),
        ("parser -> tx bukan dict", lambda t: {"ok": True, "draft": {"transactions": ["x"]}})):
    try:
        h_b = chat_gate.draft("makan 1000", path=SALINAN, parse_fn=fn_b)
        cek("draft() %s -> ok False" % label_b, (h_b or {}).get("ok"), False)
    except Exception as e:
        cek_benar("draft() %s -> kode (lempar %r)" % (label_b, e), False)

# simpan(): draft_hasil berbentuk salah.
for label_b, draft_b in (
        ("draft_hasil str", "x"),
        ("draft_hasil int", 123),
        ("draft_hasil draft str", {"ok": True, "draft": "x"}),
        ("draft_hasil tx bukan list", {"ok": True, "draft": {"transactions": 5}}),
        ("draft_hasil tx bukan dict", {"ok": True, "draft": {"transactions": ["x"]}})):
    try:
        h_b = chat_gate.simpan(draft_b, _konf_sah, path=SALINAN, path_log=LOG)
        cek("simpan() %s -> kode" % label_b, h_b.get("error"), "draft_tidak_sah")
    except Exception as e:
        cek_benar("simpan() %s -> kode (lempar %r)" % (label_b, e), False)

cek("baris salinan TIDAK bertambah setelah bentuk salah",
    hitung(SALINAN), sebelum_bentuk)


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
