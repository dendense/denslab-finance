#!/usr/bin/env python3
"""Uji deklarasi batas versi Python — tanpa memasang interpreter lain.

`cek()` menentukan apakah app boleh jalan. Kalau ambangnya salah, dua-duanya
buruk: interpreter tua lolos lalu gagal di tengah jalan, atau interpreter yang
sah ditolak. Karena itu PENOLAKAN harus dibuktikan, bukan diasumsikan.

Versi tua disimulasikan dengan mengganti `sys.version_info` — deterministik,
dan tidak butuh Python 3.8 sungguhan di mesin ini.

Jalankan:  python3 tests/test_versi_python.py
"""
import io
import sys
from pathlib import Path

# Kode ada di src/, satu tingkat di atas tests/ atau scripts/
SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import versi_python as vp  # noqa: E402

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-46s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r, harusnya %r" % (nama, dapat, harap))


def panggil_dengan_versi(versi):
    """Panggil vp.cek() dengan sys.version_info palsu.

    -> (exit code atau None, isi stderr). sys asli selalu dipulihkan.
    """
    asli_vi, asli_err = sys.version_info, sys.stderr
    buf = io.StringIO()
    kode = None
    try:
        sys.version_info = versi
        sys.stderr = buf
        vp.cek()
    except SystemExit as e:
        kode = e.code
    finally:
        sys.version_info, sys.stderr = asli_vi, asli_err
    return kode, buf.getvalue()


print("\n1. Interpreter sekarang (%s) — harus lolos diam-diam"
      % sys.version.split()[0])
kode, pesan = panggil_dengan_versi(sys.version_info)
cek("tidak exit", kode, None)
cek("tidak mencetak apa pun", pesan, "")

print("\n2. Versi di bawah minimum — harus DITOLAK")
# 3.8, bukan 3.9.6: MINIMUM = 3.9, jadi 3.9.6 memang SAH dan tidak boleh ditolak.
kode, pesan = panggil_dengan_versi((3, 8, 10))
cek("exit code", kode, 1)
cek("mencetak pesan", pesan != "", True)

print("\n3. Pesan penolakan menyebut tiga hal")
cek("path interpreter", sys.executable in pesan, True)
cek("versi yang ditemukan", "3.8.10" in pesan, True)
cek("versi minimum", vp.MINIMUM_TEKS in pesan, True)
print("     pesan yang dilihat orang:")
for baris in pesan.splitlines():
    print("       " + baris)

print("\n4. Tepat di batas minimum (%s) — lolos, bukan ditolak" % vp.MINIMUM_TEKS)
kode, pesan = panggil_dengan_versi(vp.MINIMUM + (0,))
cek("tidak exit", kode, None)
cek("tidak mencetak apa pun", pesan, "")

print("\n5. server.py memanggil cek() sebelum impor modul lokal")
# Kalau urutannya terbalik, interpreter tua crash SyntaxError di dalam modul
# lokal sebelum sempat mencetak pesan — deklarasinya jadi tidak berguna.
sumber = (SRC / "server.py").read_text(encoding="utf-8")
i_cek = sumber.find("versi_python.cek()")
i_db = sumber.find("\nimport db")
cek("cek() dipanggil", i_cek != -1, True)
cek("cek() sebelum 'import db'", -1 < i_cek < i_db, True)

print("\n6. Peringatan() di bawah rekomendasi — teks, bukan penolakan")
# MINIMUM tetap 3.9 (lantai sintaks). 3.9.6 SAH jalan, tapi harus memberi tahu
# bahwa Python sistem Apple deprecated. Peringatan yang tidak pernah diuji sama
# saja dengan tidak ada peringatan.
def panggil_peringatan(versi):
    """-> (hasil, SystemExit atau None). sys asli selalu dipulihkan."""
    asli_vi = sys.version_info
    keluar = None
    try:
        sys.version_info = versi
        hasil = vp.peringatan()
    except SystemExit as e:      # tidak boleh terjadi, tapi harus dibuktikan
        keluar, hasil = e, None
    finally:
        sys.version_info = asli_vi
    return hasil, keluar


print("\n   a. %s (rekomendasi) — harus DIAM" % vp.REKOMENDASI_TEKS)
hasil, keluar = panggil_peringatan(vp.REKOMENDASI + (0,))
cek("return None", hasil, None)
cek("tidak SystemExit", keluar, None)

print("\n   b. 3.9.6 — harus memperingatkan")
hasil, keluar = panggil_peringatan((3, 9, 6))
cek("tidak SystemExit", keluar, None)
cek("mengembalikan teks", isinstance(hasil, str) and hasil != "", True)
cek("menyebut versi dipakai", "3.9.6" in (hasil or ""), True)
cek("menyebut path interpreter", sys.executable in (hasil or ""), True)
cek("menyebut rekomendasi", vp.REKOMENDASI_TEKS in (hasil or ""), True)
cek("satu baris", len((hasil or "").splitlines()) <= 1, True)
print("     pesan yang dilihat orang:")
print("       " + (hasil or ""))

print("\n7. cek() di 3.9.6 — SAH, tidak boleh exit")
kode, pesan = panggil_dengan_versi((3, 9, 6))
cek("tidak exit", kode, None)
cek("tidak mencetak apa pun", pesan, "")

print("\n8. Konstanta tidak berubah arti")
cek("MINIMUM tetap 3.9", vp.MINIMUM, (3, 9))
cek("REKOMENDASI 3.11", vp.REKOMENDASI, (3, 11))

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
