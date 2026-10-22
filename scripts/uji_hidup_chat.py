#!/usr/bin/env python3
"""Uji HIDUP gerbang chat: draft (parser nyata) -> tolak negasi -> simpan.

Menjalankan alur sungguhan lewat `parser_wrap.parse_kontrak` (model hidup) di
SALINAN database, bukan `finance.db` Deny. Setiap langkah menulis jumlah baris
salinan supaya kelihatan kapan penulisan terjadi (dan kapan TIDAK).

Sengaja memakai kuota model sedikit: dua kalimat saja.

Jalankan:  . Data/finance/env.sh && python3 scripts/uji_hidup_chat.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import chat_gate  # noqa: E402
import db         # noqa: E402

DB_DENY = ROOT.parent / "Data" / "finance" / "finance.db"

TMPDIR = Path(tempfile.mkdtemp())
SALINAN = TMPDIR / "finance.db"
LOG = TMPDIR / "chat_simpan.log"
shutil.copy2(DB_DENY, SALINAN)
(TMPDIR / ".finance-data").touch()
db.DB_PATH = SALINAN


def baris():
    import sqlite3
    conn = sqlite3.connect(str(SALINAN))
    try:
        return conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    finally:
        conn.close()


print("=" * 78)
print("Uji hidup gerbang chat — parser nyata, database salinan")
print("  salinan : %s" % SALINAN)
print("  baris   : %d" % baris())
print("=" * 78)

KALIMAT = "beli makan malam 32000 pakai BRI"

# 1. DRAFT — parser nyata, nol baris tersimpan.
print("\n1. DRAFT (nol baris tersimpan)")
sebelum = baris()
hasil = chat_gate.draft(KALIMAT, path=SALINAN)
print(chat_gate.render_draft(hasil))
print("  baris sebelum=%d sesudah=%d  %s"
      % (sebelum, baris(), "TIDAK bertambah" if baris() == sebelum else "BERTAMBAH!"))

# 2. PENOLAKAN Deny — harus DITOLAK, fail-closed.
#    Termasuk bentuk yang dulu bocor (ronde 3): 'ndak usah simpan', 'no simpan',
#    'sudah saya simpan', 'simpan aja'. Semua ini dulu benar-benar TERTULIS.
#    Dan bentuk bocor ronde 4 (penanda penolakan yang dulu dibuang normalisasi):
#    '❌ simpan', '⛔ simpan', 'simpan ❌'.
print("\n2. Deny membalas PENOLAKAN (harus ditolak, nol baris)")
sebelum = baris()
for teks in ("jangan simpan", "tidak setuju", "batal, jangan lanjut",
             "ndak usah simpan", "no simpan", "udah simpan", "simpan aja",
             "\u274c simpan", "\u26d4 simpan", "simpan \u274c"):
    out = chat_gate.simpan(
        hasil, {"pengirim": "deny", "kanal": "telegram", "teks": teks},
        path=SALINAN, path_log=LOG)
    print("  \"%s\" -> %s: %s" % (teks, out.get("error"), out.get("message")))
print("  baris sebelum=%d sesudah=%d  %s"
      % (sebelum, baris(), "TIDAK bertambah" if baris() == sebelum else "BERTAMBAH!"))
print("  jejak dibuat? %s" % ("ya" if LOG.exists() else "tidak"))

# 3. Rin mencoba menyimpan sendiri — harus ditolak.
print("\n3. Rin mencoba menyimpan sendiri (harus ditolak)")
out = chat_gate.simpan(
    hasil, {"pengirim": "rin", "kanal": "telegram", "teks": "simpan"},
    path=SALINAN, path_log=LOG)
print("  -> %s: %s" % (out.get("error"), out.get("message")))
print("  baris masih %d" % baris())

# 4. Deny memerintahkan simpan — berhasil, jejak asal tercatat.
print("\n4. Deny memerintahkan simpan (berhasil)")
sebelum = baris()
out = chat_gate.simpan(
    hasil, {"pengirim": "deny", "kanal": "telegram", "teks": "simpan",
            "waktu": "2026-10-09T21:30:00"},
    path=SALINAN, path_log=LOG)
print("  -> ok=%s id=%s" % (out.get("ok"), out.get("saved_ids")))
print("  baris sebelum=%d sesudah=%d" % (sebelum, baris()))
if LOG.exists():
    print("  jejak asal: %s" % LOG.read_text(encoding="utf-8").strip())

print("\n" + "=" * 78)
print("Salinan dibuang. finance.db Deny tidak tersentuh.")
shutil.rmtree(TMPDIR, ignore_errors=True)
