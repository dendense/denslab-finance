#!/usr/bin/env python3
"""Autentikasi panel finance — pengamanan standar, BUKAN enkripsi data.

APA YANG DILINDUNGI:
  Menghalangi orang yang lewat / memakai Mac ini sebentar dari melihat angka
  keuangan lewat panel. Layar terkunci = tidak ada angka yang tampil.

APA YANG TIDAK DILINDUNGI (penting, dan sengaja ditulis di sini):
  - `Data/finance/finance.db` tetap terbaca langsung dengan SQLite oleh siapa pun yang
    punya akses ke Mac ini. Password di sini TIDAK menyentuh database.
  - Berkas berkas proyek ini juga terbaca lewat Finder.
  - Siapa pun yang bisa membuka terminal bisa mereset password (lihat
    scripts/reset_password.py) — itu memang disengaja, supaya Deny tidak
    terkunci dari datanya sendiri.
  Kalau nanti yang dibutuhkan adalah perlindungan data yang sebenarnya,
  itu enkripsi database (SQLCipher) — pekerjaan berbeda, bukan file ini.

CARA KERJA SESI:
  - Login -> server membuat token acak, disimpan di memori (BUKAN di berkas).
  - Token dikirim ke browser sebagai cookie httpOnly.
  - Karena token hanya ada di memori, MEMATIKAN SERVER = SEMUA SESI MATI.
    Ini yang diminta Deny: "kunci kembali jika di tengah jalan server terputus".
  - Logout menghapus token itu dari memori; token lama tidak bisa dipakai lagi.

Kenapa token di memori dan bukan di berkas: token di berkas akan bertahan
melewati restart, dan itu bertentangan dengan permintaan "kunci kalau server
terputus". Efek sampingnya: setiap kali kamu menyalakan ulang server, kamu
perlu login lagi — itu perilaku yang diinginkan, bukan bug.
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent

# Berkas kredensial hidup DI FOLDER DATA, bukan di dalam repo.
# Alasannya sama dengan database keuangan (lihat catatan di `db.py`): begitu
# hash password masuk satu commit, menghapusnya tidak cukup — git menyimpan
# riwayat. Pemisahan fisik mencegahnya, .gitignore hanya mengingatkan.
DATA_DIR = Path(os.environ.get("FINANCE_DATA")
                or (ROOT_DIR.parent / "Data" / "finance"))
KREDENSIAL = DATA_DIR / "kredensial.json"

# Sesi hidup di memori saja. Restart server = semua sesi hilang.
_SESI = {}

# Sesi tanpa aktivitas selama ini otomatis mati, walaupun server tetap hidup.
# 12 jam: cukup untuk dipakai seharian, tapi tidak menggantung berhari-hari.
BATAS_DIAM_DETIK = 12 * 60 * 60

# Iterasi PBKDF2. Nilai tinggi = lebih lambat ditebak, tapi login juga lambat.
# 200.000 masih di bawah 0,2 detik di Mac ini.
ITERASI = 200_000

PANJANG_MIN_PASSWORD = 6


# ─────────────────────────────────────────────────────────────────────────────
# Password
# ─────────────────────────────────────────────────────────────────────────────
def _hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERASI).hex()


def sudah_ada_password(path=None):
    """True kalau password sudah pernah dipasang."""
    p = Path(path or KREDENSIAL)
    # Tandai folder data kalau belum bertanda.
    #
    # KENAPA INI PERLU — kejadian nyata, 3 Okt 2026: `init_db()` menandai folder
    # data, tapi `/api/auth` memanggil fungsi ini LEBIH DULU, dan `/api/auth`
    # adalah rute PUBLIK — jadi ia jalan bahkan saat server belum selesai
    # menyiapkan apa pun. Tanpa penanda, `periksa_lokasi_data` menganggap folder
    # yang sah sebagai mencurigakan. Penanda di sini memastikan folder KREDENSIAL
    # (tempat data memang berada) dikenali, bukan folder lain yang kebetulan
    # disentuh.
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.parent / ".finance-data").touch(exist_ok=True)
    if not p.exists():
        return False
    try:
        isi = json.loads(p.read_text())
        return bool(isi.get("hash") and isi.get("salt"))
    except (json.JSONDecodeError, OSError):
        return False


def pasang_password(password, path=None):
    """Pasang password pertama kali, atau ganti yang ada.

    Dipakai saat setup awal (dari panel) dan oleh scripts/reset_password.py.
    Mengembalikan True kalau berhasil.
    """
    p = Path(path or KREDENSIAL)
    if not password or len(password) < PANJANG_MIN_PASSWORD:
        raise ValueError("password minimal %d karakter" % PANJANG_MIN_PASSWORD)

    salt = secrets.token_hex(16)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "algo": "pbkdf2_sha256",
        "iterasi": ITERASI,
        "salt": salt,
        "hash": _hash(password, salt),
        "dibuat": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, indent=2))
    # Izin ketat: hanya pemilik berkas yang bisa membacanya.
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return True


def cek_password(password, path=None):
    """Bandingkan password dengan hash tersimpan. Pakai perbandingan konstan-waktu."""
    p = Path(path or KREDENSIAL)
    if not p.exists():
        return False
    try:
        isi = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    if not isi.get("hash") or not isi.get("salt"):
        return False
    return hmac.compare_digest(_hash(password or "", isi["salt"]), isi["hash"])


# ─────────────────────────────────────────────────────────────────────────────
# Sesi
# ─────────────────────────────────────────────────────────────────────────────
def buat_sesi(umur_detik=None):
    """Buat token sesi baru. Disimpan DI MEMORI saja.

    `umur_detik=None` berarti tanpa batas umur (selain batas diam 12 jam).
    `umur_detik=0` berarti sesi langsung kedaluwarsa — itu dipakai di uji.
    Perhatikan: nol dan None BEDA di sini. Memakai `if s["umur"]` membuat
    umur 0 diperlakukan sebagai "tanpa batas", dan itu bug.
    """
    token = secrets.token_urlsafe(32)
    _SESI[token] = {
        "dibuat": time.time(),
        "terakhir": time.time(),
        "umur": umur_detik,
    }
    _bersihkan()
    return token


def sesi_sah(token, perbarui=True):
    """True kalau token masih berlaku. Sekaligus memperpanjang masa aktifnya."""
    if not token:
        return False
    _bersihkan()
    s = _SESI.get(token)
    if not s:
        return False
    # `is not None`, bukan truthy: umur 0 harus berarti kedaluwarsa sekarang.
    if s["umur"] is not None and time.time() - s["dibuat"] > s["umur"]:
        _SESI.pop(token, None)
        return False
    if perbarui:
        s["terakhir"] = time.time()
    return True


def akhiri_sesi(token):
    """Logout. Token langsung tidak berlaku; tidak bisa dipakai ulang."""
    return _SESI.pop(token, None) is not None


def akhiri_semua_sesi():
    """Kunci semuanya. Dipakai kalau password diganti — sesi lama jadi tidak sah."""
    n = len(_SESI)
    _SESI.clear()
    return n


def jumlah_sesi():
    _bersihkan()
    return len(_SESI)


def _bersihkan():
    """Buang sesi yang sudah diam terlalu lama."""
    batas = time.time() - BATAS_DIAM_DETIK
    mati = [t for t, s in _SESI.items() if s["terakhir"] < batas]
    for t in mati:
        _SESI.pop(t, None)
    return len(mati)