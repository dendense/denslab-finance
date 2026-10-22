#!/usr/bin/env python3
"""Uji: apakah `/api/summary` melaporkan uang di akun NONAKTIF bersaldo?

Kasus yang diminta yuki: kalau ada akun dinonaktifkan tapi masih bersaldo, panel
harus bisa memberi tahu Deny — kalau tidak, `total` naik tanpa akun yang
menjelaskan dari mana.

Jalankan:  python3 tests/test_balance_inactive.py

TIDAK BUTUH SERVER, TIDAK BUTUH PASSWORD, TIDAK MENYENTUH DATA DENY.

Cara kerjanya: `api_summary` dipanggil LANGSUNG dari proses ini, dengan
db.DB_PATH diarahkan ke database sementara. Tidak ada HTTP, tidak ada sesi
login, dan tidak satu byte pun ditulis ke Data/finance/.

Mengapa tidak lewat HTTP seperti versi sebelumnya — uji versi lama menuntut
server yang jalan, dan server itu membaca database Deny:

  1. Ia MENULIS akun uji ke database keuangan Deny (walau dihapus lagi di akhir;
     kalau skripnya terhenti di tengah, akunnya tertinggal).
  2. Ia gagal dengan "no such table: accounts" kalau dijalankan tanpa server,
     karena database yang dihubunginya kosong.
  3. Ia butuh password Deny — versi lama memasang password uji sendiri, dan
     kalau Deny sudah punya password, uji itu mati dengan 401.
  4. Ia satu-satunya uji di repo yang begitu; yang lain memakai database
     sementara lewat argumen `path` (lihat tests/test_analysis_live.py).

Uji yang gagal karena desainnya sendiri akan diabaikan orang, dan begitu satu
uji diabaikan, yang lain menyusul. Karena itu ia diperbaiki, bukan dilewati.

JEBAKAN YANG SUDAH DITEMUKAN — jangan ulangi:

  * Menimpa `db.DB_PATH` SEBELUM 7 Okt 2026 TIDAK BEKERJA. Semua fungsi db
    bertanda tangan `path=DB_PATH`, dan default argumen di Python dievaluasi
    saat import — jadi path sudah terkunci sebelum uji sempat menimpanya. Uji
    ini membaca database keuangan Deny sambil mencetak path /tmp ke layar.
    Diperbaiki di `db.py` lewat `_PathDB`, dan uji ini memverifikasi hasilnya:
    langkah 1 mewajibkan "database kosong" benar-benar kosong.
  * `account_count_all` BUKAN jumlah semua akun. Namanya menyesatkan. Menurut
    `schema.sql` (dikonfirmasi migrations/003, 004, 005) ia menghitung akun
    AKTIF dengan aturan mentah — tanpa syarat saldo/transaksi yang dipakai
    `account_count`. Jadi akun nonaktif tidak dihitung di sini; jumlahnya cuma
    terlihat dari `balance_inactive`.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db        # noqa: E402
import server    # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji-balance-inactive.db"

# Nama akun uji HARUS unik per jalannya. Versi lama memakai nama tetap, dan
# karena uji itu dulu menulis ke database Deny, akun bernama "BRI-Uji" sudah
# tertinggal di sana. Nama tetap akan langsung bentrok ("sudah ada akun bernama
# ...") di database mana pun yang pernah tersentuh uji lama.
import os        # noqa: E402
AKHIR = os.getpid()
NAMA_LATAR = "UJI-Latar-%d" % AKHIR
NAMA_UJI = "UJI-NonaktifBersaldo-%d" % AKHIR
SALDO = 777000
SALDO_LATAR = 1000000

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-48s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


# ── Arahkan database ke /tmp ────────────────────────────────────────────────
# `db.DB_PATH` adalah default argumen `path=DB_PATH` di 30 fungsi db, dan
# `server.api_summary` memanggil lewat default itu. Sejak `_PathDB` dipasang,
# penimpaan di sini benar-benar berlaku. Langkah 1 di bawah membuktikannya.
DB_DENY = str(ROOT.parent / "Data" / "finance" / "finance.db")
db.DB_PATH = TMP
db.init_db(TMP)

print("=" * 78)
print("Uji balance_inactive — database sementara, tanpa server")
print("=" * 78)
print("  DB uji    : %s" % db.DB_PATH)
print("  DB Deny   : %s" % DB_DENY)
print("              (uji ini hanya MEMBACA nilai ini untuk dicetak; tidak ada")
print("               penulisan ke sana — langkah 1 memverifikasi isolasinya)")

# Enam field ini hidup di dalam `net_worth`, BUKAN di akar balasan.
# Versi lama uji ini memeriksanya di akar, dan pada database kosong pemeriksaan
# `f in awal` gagal senyap. Baca bentuknya dari kode (`src/server.py`), jangan
# dari kebiasaan.
FIELD = ("total", "liquid", "non_liquid", "account_count",
         "account_count_all", "balance_inactive")


def ringkas():
    """Bagian `net_worth` dari /api/summary, seperti yang dibaca UI."""
    return server.api_summary({})["net_worth"]


try:
    print("\n1. Isolasi database — prasyarat mutlak")
    awal = ringkas()
    # Kalau isolasi gagal, uji ini membaca database keuangan Deny dan SEMUA
    # angka di bawahnya tidak bermakna. Diperiksa paling awal supaya kegagalan
    # jenis itu ketahuan di sini, bukan tersamar sebagai "uji lulus".
    cek("database uji benar-benar KOSONG (total = 0)", awal["total"], 0)
    cek("database uji kosong: account_count_all = 0",
        awal["account_count_all"], 0)
    if awal["total"] != 0:
        print("\n  HENTI: isolasi database gagal.")
        print("  Uji ini sedang membaca database lain (kemungkinan milik Deny).")
        print("  Angka-angka selanjutnya tidak akan bermakna, jadi tidak")
        print("  diteruskan. Periksa `_PathDB` / `_path_aktif` di src/db.py.")
        sys.exit(2)

    for f in FIELD:
        cek("field '%s' ada di net_worth" % f, f in awal, True)
    cek("database kosong: balance_inactive = 0", awal["balance_inactive"], 0)
    total_awal = awal["total"]
    print("     total=%s  balance_inactive=%s"
          % (total_awal, awal["balance_inactive"]))

    print("\n2. Buat akun AKTIF bersaldo Rp %s (latar)" % f"{SALDO_LATAR:,}")
    db.create_account(NAMA_LATAR, "bank", SALDO_LATAR)
    aktif = ringkas()
    cek("total naik sebesar saldo akun baru",
        aktif["total"], total_awal + SALDO_LATAR)
    cek("account_count menghitung akun aktif", aktif["account_count"], 1)
    cek("account_count_all menghitung akun aktif", aktif["account_count_all"], 1)
    cek("balance_inactive masih 0 (akunnya aktif)",
        aktif["balance_inactive"], 0)
    total_awal = aktif["total"]

    print("\n3. Tambah akun bersaldo Rp 777.000, lalu NONAKTIFKAN")
    a = db.create_account(NAMA_UJI, "bank", SALDO)
    db.update_account(a["id"], is_active=0)

    sesudah = ringkas()
    # Inti uji: menonaktifkan akun TIDAK boleh menghapus uangnya dari total.
    # Kalau v_net_worth memakai `WHERE is_active = 1`, total akan kembali ke
    # angka semula dan Rp 777.000 lenyap tanpa error apa pun.
    cek("total TETAP memasukkan saldo akun nonaktif",
        sesudah["total"], total_awal + SALDO)
    cek("uang tidak hilang saat akun dinonaktifkan",
        sesudah["total"] > total_awal, True)
    # Inilah yang dipakai UI untuk memberi tahu Deny di mana uang itu berada.
    cek("balance_inactive melaporkan saldo akun nonaktif",
        sesudah["balance_inactive"], SALDO)
    cek("akun nonaktif tidak dihitung di account_count",
        sesudah["account_count"], 1)
    # `account_count_all` menghitung akun AKTIF dengan aturan mentah
    # (tanpa syarat saldo/transaksi). Akun nonaktif tidak ikut — lihat schema.sql:229.
    cek("account_count_all hanya menghitung akun aktif",
        sesudah["account_count_all"], 1)

    print("\n4. Aktifkan lagi — akun itu kembali ke hitungan normal")
    db.update_account(a["id"], is_active=1)
    aktif_lagi = ringkas()
    cek("total tetap termasuk saldo akun itu",
        aktif_lagi["total"], total_awal + SALDO)
    cek("kini dua akun aktif", aktif_lagi["account_count"], 2)
    cek("balance_inactive kembali 0", aktif_lagi["balance_inactive"], 0)

finally:
    print("\n(database sementara dibuang; data Deny tidak tersentuh)")

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
