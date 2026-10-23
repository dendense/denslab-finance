#!/usr/bin/env python3
"""Uji sesi persisten: token ter-hash di SQLite + ikat `kern.bootsessionuuid`.

Aturan yang diuji (D8, 23 Okt 2026): sesi login BERTAHAN melewati tutup-buka
app / restart server, tapi MATI tepat saat laptop restart.

Yang diuji di sini, dan kenapa masing-masing penting:
  1. Token yang dibuat langsung sah — dasar, kalau ini gagal semuanya gagal
  2. Token salah/kosong ditolak — jangan sampai salah ketik jadi pintu masuk
  3. Yang tersimpan di DB adalah sha256(token), BUKAN token mentah — DB ini
     di-backup; token mentah di disk = kunci yang ikut tersalin
  4. boot_uuid berbeda -> sesi ditolak — INI inti kartunya: tanpa ini,
     "mati saat restart laptop" hanya klaim, bukan perilaku
  5. TTL 30 hari berlaku — persist bukan berarti abadi
  6. Logout & kunci-semua benar-benar menghapus baris
  7. Sesi selamat dari "restart server" (modul dimuat ulang) — sisi lain D8
  8. `init_db` pada DB lama tanpa tabel `sesi` menambah tabel, data lama utuh

Semua uji memakai DB sementara (FINANCE_DATA), BUKAN `Data/finance/finance.db`.

Jalankan:  python3 tests/test_sesi_persisten.py
"""
import hashlib
import importlib
import os
import sys
import tempfile
import time
from pathlib import Path

# FINANCE_DATA HARUS di-set SEBELUM `db` dan `auth` diimpor: keduanya membaca
# env ini saat modul dimuat. Kalau urutannya terbalik, uji ini akan menulis
# sesi ke database keuangan Deny — persis kesalahan yang pernah terjadi
# (lihat catatan `_PathDB` di `src/db.py`).
TMPDIR = Path(tempfile.mkdtemp(prefix="uji-sesi-"))
os.environ["FINANCE_DATA"] = str(TMPDIR)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import db     # noqa: E402
import auth   # noqa: E402

db.init_db()  # skema + seed ke DB sementara

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-56s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def _baris_sesi():
    with db.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM sesi")]


print("\n0. DB uji, bukan DB Deny")
cek("DB yang dipakai di folder sementara", str(TMPDIR) in str(db.DB_PATH), True)
with db.connect() as conn:
    tabel = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
cek("tabel sesi ada", "sesi" in tabel, True)

print("\n1. Sesi dibuat -> langsung sah")
t1 = auth.buat_sesi()
cek("token baru sah", auth.sesi_sah(t1), True)
cek("boot_uuid tercatat", bool(_baris_sesi()[0]["boot_uuid"]), True)
cek("boot_uuid = boot sekarang", _baris_sesi()[0]["boot_uuid"], auth.BOOT_UUID)

print("\n2. Token salah / kosong ditolak")
cek("token ngawur tidak sah", auth.sesi_sah("token-palsu"), False)
cek("token kosong tidak sah", auth.sesi_sah(""), False)
cek("token None tidak sah", auth.sesi_sah(None), False)

print("\n3. Yang tersimpan HASH, bukan token mentah")
isi = _baris_sesi()
hash_tersimpan = [b["token_hash"] for b in isi]
cek("token mentah TIDAK ada di DB", t1 in hash_tersimpan, False)
cek("sha256(token) ADA di DB", hashlib.sha256(t1.encode()).hexdigest() in hash_tersimpan, True)
cek("semua token_hash panjang 64 (sha256)", [len(h) for h in hash_tersimpan], [64])

print("\n4. boot_uuid berbeda -> sesi DITOLAK (simulasi laptop restart)")
# 4a: periksa perbandingan di `sesi_sah` sendiri, tanpa bantuan `_bersihkan`
asli_bersihkan = auth._bersihkan
asli_boot = auth.BOOT_UUID
auth._bersihkan = lambda: 0
auth.BOOT_UUID = "boot-lain-setelah-restart"
cek("boot beda -> sesi_sah False", auth.sesi_sah(t1), False)
auth._bersihkan = asli_bersihkan
auth.BOOT_UUID = asli_boot

# 4b: perilaku penuh — sesi dari boot lama dibuang, bukan cuma ditolak
t_boot = auth.buat_sesi()
auth.BOOT_UUID = "boot-lain-setelah-restart"
cek("boot beda -> sesi_sah False (dengan pembersihan)", auth.sesi_sah(t_boot), False)
auth.BOOT_UUID = asli_boot
cek("sesi boot lama tidak hidup lagi setelah UUID benar", auth.sesi_sah(t_boot), False)
cek("barisnya sudah dibuang", len([b for b in _baris_sesi()
                                   if b["token_hash"] == auth._hash_token(t_boot)]), 0)

print("\n5. TTL 30 hari berlaku")
t_ttl = auth.buat_sesi()
cek("umur bawaan 30 hari", auth.BATAS_UMUR_DETIK, 30 * 24 * 60 * 60)
# Suntik: seolah dibuat 31 hari lalu.
with db.connect() as conn:
    conn.execute("UPDATE sesi SET dibuat_pada = ? WHERE token_hash = ?",
                 ("%.6f" % (time.time() - 31 * 24 * 60 * 60), auth._hash_token(t_ttl)))
cek("sesi 31 hari -> tidak sah", auth.sesi_sah(t_ttl), False)
# Dan yang 29 hari masih sah — batasnya harus benar di dua sisi.
t_muda = auth.buat_sesi()
with db.connect() as conn:
    conn.execute("UPDATE sesi SET dibuat_pada = ? WHERE token_hash = ?",
                 ("%.6f" % (time.time() - 29 * 24 * 60 * 60), auth._hash_token(t_muda)))
cek("sesi 29 hari -> masih sah", auth.sesi_sah(t_muda), True)
cek("umur_detik=0 langsung mati", auth.sesi_sah(auth.buat_sesi(umur_detik=0)), False)

print("\n6. Logout & kunci-semua")
t2 = auth.buat_sesi()
cek("logout berhasil", auth.akhiri_sesi(t2), True)
cek("token setelah logout TIDAK sah", auth.sesi_sah(t2), False)
cek("logout token yang sama dua kali ditolak", auth.akhiri_sesi(t2), False)
cek("logout token kosong ditolak", auth.akhiri_sesi(""), False)

ta = auth.buat_sesi()
tb = auth.buat_sesi()
n = auth.akhiri_semua_sesi()
cek("semua dikunci", n >= 2, True)
cek("jumlah sesi jadi 0", auth.jumlah_sesi(), 0)
cek("token a tidak sah", auth.sesi_sah(ta), False)
cek("token b tidak sah", auth.sesi_sah(tb), False)

print("\n7. Sesi SELAMAT dari restart server (modul dimuat ulang, boot sama)")
t3 = auth.buat_sesi()
importlib.reload(auth)   # proses baru: semua variabel modul hilang
cek("jumlah sesi setelah 'restart server'", auth.jumlah_sesi() >= 1, True)
cek("token lama masih sah setelah 'restart server'", auth.sesi_sah(t3), True)

print("\n8. DB lama tanpa tabel `sesi` -> init_db menambah tabel, data lama utuh")
lama = Path(tempfile.mkdtemp(prefix="uji-sesi-lama-")) / "finance.db"
with db.connect(lama) as conn:
    conn.execute("CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, note TEXT)")
    conn.execute("INSERT INTO accounts (name, note) VALUES ('akun-lama', 'harus selamat')")
with db.connect(lama) as conn:
    tabel_awal = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
cek("sebelum init_db: tabel sesi belum ada", "sesi" in tabel_awal, False)
db.init_db(lama)
with db.connect(lama) as conn:
    tabel_akhir = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    baris_lama = conn.execute(
        "SELECT note FROM accounts WHERE name = 'akun-lama'").fetchone()
cek("sesudah init_db: tabel sesi ada", "sesi" in tabel_akhir, True)
cek("data lama utuh", baris_lama["note"] if baris_lama else None, "harus selamat")
db.init_db(lama)   # harus aman diulang
with db.connect(lama) as conn:
    tabel_ulang = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")]
    baris_ulang = conn.execute(
        "SELECT note FROM accounts WHERE name = 'akun-lama'").fetchone()
cek("init_db dua kali: tabel sesi tetap ada", "sesi" in tabel_ulang, True)
cek("init_db dua kali: data lama tetap utuh",
    baris_ulang["note"] if baris_ulang else None, "harus selamat")

print("\n" + "─" * 74)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
