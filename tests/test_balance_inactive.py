#!/usr/bin/env python3
"""Uji: apakah `/api/summary` melaporkan uang di akun NONAKTIF bersaldo?

Ini kasus yang diminta yuki: kalau ada akun dinonaktifkan tapi masih bersaldo,
panel harus bisa memberi tahu Deny — kalau tidak, `total` naik tanpa akun yang
menjelaskan dari mana.

SEJAK PANEL DIKUNCI PASSWORD, uji ini butuh sesi login. Kalau belum ada password,
skrip ini memasangnya sendiri (password uji) dan MENGHAPUSNYA lagi di akhir —
supaya tidak ada password yang tertinggal di database Deny.

Jalankan SERVER dulu (python3 src/server.py --port 8791), lalu skrip ini.

Jalankan:  python3 tests/test_balance_inactive.py
"""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
import db    # noqa: E402
import auth  # noqa: E402

BASE = "http://localhost:8791"
URL = BASE + "/api/summary?month=2026-10"
NAMA_UJI = "UJI-NonaktifBersaldo"
SALDO = 777000
PASSWORD_UJI = "uji-sementara-123"

gagal = []
_ada_password_sebelum = auth.sudah_ada_password()


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-46s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def login():
    """Dapatkan cookie sesi. Pasang password uji kalau belum ada."""
    if not _ada_password_sebelum:
        auth.pasang_password(PASSWORD_UJI)
    body = json.dumps({"password": PASSWORD_UJI}).encode()
    req = urllib.request.Request(
        BASE + "/api/auth", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            cookie = r.headers.get("Set-Cookie") or ""
    except urllib.error.HTTPError as e:
        if e.code == 401 and _ada_password_sebelum:
            raise SystemExit(
                "Sudah ada password milik Deny, dan uji ini tidak tahu passwordnya.\n"
                "Lewati uji ini, atau jalankan ulang tanpa password terpasang.")
        raise
    return cookie.split(";")[0]


_COOKIE = None


def ringkas():
    req = urllib.request.Request(URL, headers={"Cookie": _COOKIE})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())["net_worth"]


# Bersihkan sisa kalau skrip sebelumnya terhenti di tengah
with db.connect() as conn:
    conn.execute("DELETE FROM accounts WHERE name = ?", (NAMA_UJI,))

# Login dulu — semua endpoint butuh sesi sejak panel dikunci password
_COOKIE = login()
print("  (login berhasil, sesi dipakai untuk semua panggilan)")

try:
    print("\n1. Keadaan awal")
    awal = ringkas()
    for f in ("total", "liquid", "non_liquid", "account_count",
              "account_count_all", "balance_inactive"):
        if f not in awal:
            gagal.append("field '%s' tidak ada di /api/summary" % f)
    cek("enam field lengkap", all(f in awal for f in (
        "total", "liquid", "non_liquid", "account_count",
        "account_count_all", "balance_inactive")), True)
    total_awal = awal["total"]
    print("     total=%s  balance_inactive=%s" % (total_awal, awal["balance_inactive"]))

    print("\n2. Buat akun bersaldo Rp 777.000, lalu NONAKTIFKAN")
    a = db.create_account(NAMA_UJI, "bank", SALDO)
    db.update_account(a["id"], is_active=0)

    sesudah = ringkas()
    cek("balance_inactive melaporkan saldo akun nonaktif",
        sesudah["balance_inactive"], SALDO)
    # Saldo awal akun BARU menambah kekayaan (memang begitu seharusnya).
    # Yang diuji di sini: menonaktifkannya TIDAK menghapus uang itu dari total.
    # Kalau bug lama (WHERE is_active = 1) masih ada, `total` akan kembali
    # ke angka semula dan uang Rp 777.000 lenyap tanpa penjelasan.
    cek("total menambahkan saldo akun nonaktif",
        sesudah["total"], total_awal + SALDO)
    cek("uang tidak hilang saat akun dinonaktifkan",
        sesudah["total"] > total_awal, True)
    cek("account_count_all tidak menghitung akun nonaktif",
        sesudah["account_count_all"], awal["account_count_all"])

    print("\n3. Aktifkan lagi — balance_inactive harus kembali 0")
    db.update_account(a["id"], is_active=1)
    aktif_lagi = ringkas()
    cek("balance_inactive kembali 0", aktif_lagi["balance_inactive"], 0)
    cek("total tetap termasuk saldo akun itu",
        aktif_lagi["total"], total_awal + SALDO)

finally:
    with db.connect() as conn:
        conn.execute("DELETE FROM accounts WHERE name = ?", (NAMA_UJI,))
    print("\n(akun uji dibersihkan)")
    # Kalau password dipasang oleh uji ini, hapus lagi supaya tidak tertinggal
    # di database Deny. Password Deny sendiri tidak pernah disentuh.
    if not _ada_password_sebelum:
        try:
            auth.KREDENSIAL.unlink()
            print("(password uji dihapus — Deny belum memasang password)")
        except OSError:
            pass

print("\n" + "─" * 68)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
