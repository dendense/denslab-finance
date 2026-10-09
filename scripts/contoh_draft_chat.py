#!/usr/bin/env python3
"""Contoh keluaran NYATA: draft lewat chat memakai parser yang sama dengan halaman Catat.

Tidak memalsukan parser — memanggil `parser_wrap.parse_kontrak` hidup, lewat
model sungguhan (kuota Deny terpakai, jadi kalimatnya sedikit dan sengaja).

Berjalan di SALINAN database, bukan `finance.db` Deny.

Jalankan:  . finance-pribadi/env.sh && python3 scripts/contoh_draft_chat.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import chat_gate  # noqa: E402
import db         # noqa: E402

DB_DENY = ROOT.parent / "finance-pribadi" / "finance.db"

KALIMAT = [
    "beli makan malam 32000",
    "makan siang 25rb sama parkir 5rb",
    "bayar cicilan pinjaman online 500rb",
]

TMPDIR = Path(tempfile.mkdtemp())
SALINAN = TMPDIR / "finance.db"
shutil.copy2(DB_DENY, SALINAN)
(TMPDIR / ".finance-data").touch()
db.DB_PATH = SALINAN

print("=" * 78)
print("Contoh draft chat — parser hidup, database salinan")
print("  salinan : %s" % SALINAN)
print("  model   : %s" % __import__("model_config").MODEL)
print("=" * 78)

for k in KALIMAT:
    print("\nKAMU : %s" % k)
    try:
        hasil = chat_gate.draft(k, path=SALINAN)
    except Exception as e:
        print("GAGAL memanggil parser: %s: %s" % (type(e).__name__, e))
        continue
    print(chat_gate.render_draft(hasil))

print("\n" + "=" * 78)
print("Tidak ada yang disimpan. Salinan dibuang.")
shutil.rmtree(TMPDIR, ignore_errors=True)
