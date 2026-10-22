#!/usr/bin/env python3
"""Uji pengaman lokasi data.

Latar belakang — kejadian nyata 3 Okt 2026:

Saat menguji "orang baru clone lalu pakai", skrip dijalankan DI FOLDER CLONE
dengan maksud memakai database clone. Ternyata `FINANCE_DATA` tidak di-set,
jadi kode jatuh ke nilai bawaan dan menulis ke database keuangan Deny. Yang
menyelamatkan hanya kebetulan: akun "Tabungan" sudah ada sehingga penambahan
akun ditolak.

Pemisahan fisik folder melindungi dari salah-`git commit`; pengaman ini
melindungi dari salah-`jalankan`.

Jalankan:  python3 tests/test_lokasi_data.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db  # noqa: E402

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-56s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_benar(nama, kondisi):
    print(("  OK   " if kondisi else "  GAGAL") + " %s" % nama)
    if not kondisi:
        gagal.append(nama)


TMP = Path(tempfile.mkdtemp())

print("\n1. Folder BELUM ADA -> diizinkan (pemakaian pertama, wajar)")
kosong = TMP / "belum-ada"
cek("periksa_lokasi_data", db.periksa_lokasi_data(kosong), None)
cek_benar("tidak melempar", True)

print("\n2. Folder ada, ada penanda -> diizinkan")
sah = TMP / "sah"
sah.mkdir()
(sah / db.PENANDA).touch()
(sah / "finance.db").touch()
cek("periksa_lokasi_data", db.periksa_lokasi_data(sah), None)

print("\n3. Folder ada, ADA database, TANPA penanda -> DITOLAK")
# Inilah keadaan yang berbahaya: folder berisi data yang tidak kita kenali.
curiga = TMP / "curiga"
curiga.mkdir()
(curiga / "finance.db").write_bytes(b"SQLite format 3\x00")
pesan = db.periksa_lokasi_data(curiga)
cek_benar("mengembalikan pesan kesalahan", pesan is not None)
cek_benar("pesan menyebut nama folder", "curiga" in (pesan or ""))
cek_benar("pesan menyebut cara menandai", db.PENANDA in (pesan or ""))
cek_benar("pesan menyebut FINANCE_DATA", "FINANCE_DATA" in (pesan or ""))
print("     pesan yang dilihat orang:")
for baris in (pesan or "").splitlines():
    print("       " + baris)

print("\n4. Folder ada, ada penanda TAPI tanpa database -> diizinkan")
# Wajar: penandanya dibuat lebih dulu, database menyusul.
calon = TMP / "calon"
calon.mkdir()
(calon / db.PENANDA).touch()
cek("periksa_lokasi_data", db.periksa_lokasi_data(calon), None)

print("\n5. Folder ada, TANPA penanda, TANPA database -> diizinkan")
# Folder kosong: tidak ada data yang bisa rusak.
kosong2 = TMP / "kosong-bersih"
kosong2.mkdir()
cek("periksa_lokasi_data", db.periksa_lokasi_data(kosong2), None)

print("\n6. `pastikan_lokasi_aman` MELEMPAR pada folder yang mencurigakan")
try:
    db.pastikan_lokasi_aman(curiga)
    cek_benar("melempar RuntimeError", False)
except RuntimeError as e:
    cek_benar("melempar RuntimeError", True)
    cek_benar("pesannya berguna", "FINANCE_DATA" in str(e))

print("\n7. `pastikan_lokasi_aman` TIDAK melempar pada folder yang sah")
try:
    db.pastikan_lokasi_aman(sah)
    cek_benar("tidak melempar", True)
except RuntimeError as e:
    cek_benar("tidak melempar", False)

print("\n8. `init_db` menandai folder baru otomatis")
baru = TMP / "baru" / "finance"
db.init_db(baru / "finance.db")
cek_benar("penanda terbuat", (baru / db.PENANDA).exists())
cek_benar("database terbuat", (baru / "finance.db").exists())
cek("periksa_lokasi_data sesudahnya", db.periksa_lokasi_data(baru), None)
with db.connect(baru / "finance.db") as c:
    n = c.execute("SELECT COUNT(*) c FROM categories").fetchone()["c"]
cek("kategori awal terisi", n, 11)

print("\n9. Uji dengan database SEMENTARA tidak ikut terhenti")
# ini penting: kalau pengamannya terlalu ketat, seluruh uji lain akan mati.
tmp_db = TMP / "uji" / "sementara.db"
tmp_db.parent.mkdir(parents=True, exist_ok=True)
tmp_db.touch()                                    # database tanpa penanda!
try:
    db.init_db(tmp_db)                            # path != DB_PATH -> dilewati
    cek_benar("init_db pada path sementara tetap jalan", True)
except RuntimeError as e:
    cek_benar("init_db pada path sementara tetap jalan", False)
    print("     pesan: %s" % e)

print("\n10. Folder data Deny dikenali sebagai SAH")
# Pemeriksaan paling penting: pengaman tidak boleh menghentikan Deny sendiri.
nyata = Path(os.environ.get("FINANCE_DATA")
             or (Path(__file__).resolve().parent.parent.parent / "Data" / "finance"))
if nyata.exists():
    cek("periksa_lokasi_data(folder Deny)", db.periksa_lokasi_data(nyata), None)
    cek_benar("penanda ada", (nyata / db.PENANDA).exists())
else:
    print("  LEWATI  folder data Deny tidak ada di %s" % nyata)

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
