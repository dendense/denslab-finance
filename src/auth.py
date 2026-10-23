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

CARA KERJA SESI — DIUBAH 23 Okt 2026, dan perubahan itu SENGAJA:
  - Login -> server membuat token acak, yang disimpan di DB adalah
    `sha256(token)`-nya (BUKAN token mentah, BUKAN di memori proses).
  - Token mentah hanya dikirim ke browser sebagai cookie httpOnly.
  - Sesi TERIKAT KE BOOT MESIN: tiap baris sesi mencatat `kern.bootsessionuuid`
    saat dibuat. Diperiksa dengan UUID boot sekarang — beda berarti mesin sudah
    restart, dan sesi itu ditolak.
  - Logout menghapus baris sesi; token lama tidak bisa dipakai lagi.
  - Umur sesi 30 hari (BATAS_UMUR_DETIK), dihitung dari saat dibuat.

ATURAN LAMA (dibatalkan 23 Okt 2026, jangan dikembalikan tanpa bertanya ke Deny):
  Sampai 22 Okt 2026 sesi hanya hidup di memori proses, dengan alasan
  "kunci kembali jika di tengah jalan server terputus". Itu bukan kelalaian —
  itu permintaan Deny saat panel masih dibuka lewat browser.

  Yang membatalkan: app Tauri (DESIGN_NEW.md D8) menutup sidecar Python setiap
  kali app ditutup. Kalau sesi tetap di memori, Deny harus login ulang SETIAP
  membuka app — itu yang diminta diubah. Aturan baru: sesi bertahan melewati
  tutup-buka app, tapi mati tepat saat laptop restart. Karena itu ikatannya
  boot UUID, bukan umur proses: server boleh mati berkali-kali, sesi tetap sah;
  mesin restart sekali, semua sesi mati.

  Jadi: sesi yang selamat dari restart server = benar. Sesi yang selamat dari
  restart LAPTOP = bug. Kalau ada yang mengubah ini kembali ke memori, itu
  membatalkan keputusan D8, bukan memperbaiki bug.
"""
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import time
from pathlib import Path

import db   # koneksi + DB_PATH; sesi hidup di tabel `sesi`, bukan di memori

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent

# Berkas kredensial hidup DI FOLDER DATA, bukan di dalam repo.
# Alasannya sama dengan database keuangan (lihat catatan di `db.py`): begitu
# hash password masuk satu commit, menghapusnya tidak cukup — git menyimpan
# riwayat. Pemisahan fisik mencegahnya, .gitignore hanya mengingatkan.
DATA_DIR = Path(os.environ.get("FINANCE_DATA")
                or (ROOT_DIR.parent / "Data" / "finance"))
KREDENSIAL = DATA_DIR / "kredensial.json"

# Sesi TIDAK lagi di memori. Disimpan di tabel `sesi` (lihat `schema.sql`),
# supaya app Tauri boleh menutup sidecar Python tanpa memaksa login ulang.
# Umur sesi: 30 hari. Lebih lama dari jarak restart normal, tapi tidak abadi.
BATAS_UMUR_DETIK = 30 * 24 * 60 * 60

# Identitas boot mesin ini. Dibaca sekali saat modul dimuat: nilainya tidak bisa
# berubah selama proses hidup, dan `sysctl` dipanggil ~1 ms.
# Dipakai untuk mengikat sesi: UUID beda = laptop sudah restart = sesi mati.
def _baca_boot_uuid():
    try:
        hasil = subprocess.run(["sysctl", "-n", "kern.bootsessionuuid"],
                               capture_output=True, text=True, timeout=5)
        uuid = hasil.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        uuid = ""
    # Kalau gagal dibaca, jangan pernah mengembalikan nilai yang membuat semua
    # sesi dianggap sah. "tidak-diketahui" hanya cocok dengan dirinya sendiri,
    # jadi sesi lama tetap ditolak begitu pembacaan mulai bekerja lagi.
    return uuid or "tidak-diketahui"


BOOT_UUID = _baca_boot_uuid()

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
def _hash_token(token):
    """sha256(token) — INI yang disimpan di DB, bukan token mentahnya.

    DB ini di-backup dan bisa dibaca siapa pun yang punya akses ke Mac ini.
    Token mentah di disk sama berbahayanya dengan password mentah: siapa pun
    yang membacanya bisa memakai sesi yang sedang hidup. Hash tidak bisa dipakai
    untuk login — hanya untuk mencocokkan token yang dikirim browser.
    """
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _waktu(t=None):
    """Waktu sebagai teks kolom DB. Detik epoch, 6 desimal — mudah dibaca mesin."""
    return "%.6f" % (time.time() if t is None else t)


def buat_sesi(umur_detik=None):
    """Buat token sesi baru. Yang disimpan: sha256(token) + boot_uuid + waktu.

    Mengembalikan token MENTAH — pemanggil mengirimnya ke browser sebagai cookie.
    Itu satu-satunya tempat token mentah ada, dan ia tidak ditulis ke disk.

    `umur_detik=None` berarti umur bawaan 30 hari.
    `umur_detik=0` berarti sesi langsung kedaluwarsa — itu dipakai di uji.
    Nol dan None BEDA di sini, dan bedanya diwujudkan dengan memundurkan
    `dibuat_pada`: umur 0 = dibuat 30 hari lalu = sudah lewat batas.
    """
    token = secrets.token_urlsafe(32)
    sekarang = time.time()
    dibuat = sekarang
    if umur_detik is not None:
        dibuat = sekarang - max(0, BATAS_UMUR_DETIK - umur_detik)
    _bersihkan()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO sesi (token_hash, dibuat_pada, boot_uuid, terakhir)"
            " VALUES (?, ?, ?, ?)",
            (_hash_token(token), _waktu(dibuat), BOOT_UUID, _waktu(sekarang)))
    return token


def sesi_sah(token, perbarui=True):
    """True kalau token masih berlaku untuk boot mesin ini."""
    if not token:
        return False
    _bersihkan()
    kunci = _hash_token(token)
    with db.connect() as conn:
        baris = conn.execute(
            "SELECT dibuat_pada, boot_uuid FROM sesi WHERE token_hash = ?",
            (kunci,)).fetchone()
        if not baris:
            return False
        # Mesin sudah restart sejak sesi ini dibuat -> sesi tidak berlaku.
        # Barisnya dihapus, bukan cuma ditolak: sesi dari boot lama tidak akan
        # pernah sah lagi, dan menyimpannya hanya menumpuk sampah.
        if baris["boot_uuid"] != BOOT_UUID:
            conn.execute("DELETE FROM sesi WHERE token_hash = ?", (kunci,))
            return False
        if time.time() - float(baris["dibuat_pada"]) > BATAS_UMUR_DETIK:
            conn.execute("DELETE FROM sesi WHERE token_hash = ?", (kunci,))
            return False
        if perbarui:
            conn.execute("UPDATE sesi SET terakhir = ? WHERE token_hash = ?",
                         (_waktu(), kunci))
    return True


def akhiri_sesi(token):
    """Logout. Token langsung tidak berlaku; tidak bisa dipakai ulang."""
    if not token:
        return False
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM sesi WHERE token_hash = ?",
                           (_hash_token(token),))
        return cur.rowcount > 0


def akhiri_semua_sesi():
    """Kunci semuanya. Dipakai kalau password diganti — sesi lama jadi tidak sah."""
    with db.connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]
        conn.execute("DELETE FROM sesi")
    return n


def jumlah_sesi():
    _bersihkan()
    with db.connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM sesi").fetchone()[0]


def _bersihkan():
    """Buang sesi dari boot lain dan sesi yang lewat umur."""
    batas = time.time() - BATAS_UMUR_DETIK
    with db.connect() as conn:
        cur = conn.execute(
            "DELETE FROM sesi WHERE boot_uuid != ? OR CAST(dibuat_pada AS REAL) < ?",
            (BOOT_UUID, batas))
        return cur.rowcount