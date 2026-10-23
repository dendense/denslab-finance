#!/usr/bin/env python3
"""Uji autentikasi panel.

Yang diuji BUKAN "passwordnya benar" saja, tapi:
  1. Tanpa login, tidak ada satu pun endpoint yang membocorkan data
  2. Sesi BERTAHAN melewati restart server, tapi MATI saat laptop restart
     (D8, 23 Okt 2026 — membalik aturan lama "sesi mati saat server restart".
      Alasan: app Tauri menutup sidecar tiap kali app ditutup, jadi sesi di
      memori memaksa login ulang tiap buka app. Batasnya sekarang BOOT mesin,
      diikat ke kern.bootsessionuuid. Uji perilakunya ada di §8.)
  3. Logout benar-benar mencabut token — token lama tidak bisa dipakai lagi
  4. Password tidak pernah tersimpan sebagai teks polos
  5. Reset lewat terminal bekerja (jalur pemulihan yang dipilih Deny)

Jalankan:  python3 tests/test_auth.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Sejak 23 Okt 2026 sesi disimpan di DB, bukan di memori. Folder data uji WAJIB
# di-set SEBELUM `db`/`auth` diimpor — keduanya membaca FINANCE_DATA saat dimuat.
# Tanpa ini uji ini menulis baris `sesi` ke Data/finance/finance.db milik Deny.
DATA_UJI = Path(tempfile.mkdtemp(prefix="uji-auth-"))
os.environ["FINANCE_DATA"] = str(DATA_UJI)

import db    # noqa: E402
import auth  # noqa: E402

db.init_db()   # tabel `sesi` harus ada sebelum ada yang membuat sesi

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-54s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


# Kredensial uji di tempat sementara — jangan sentuh milik Deny
TMP = Path(tempfile.mkdtemp()) / "kredensial.json"

print("\n1. Belum ada password")
cek("sudah_ada_password", auth.sudah_ada_password(path=TMP), False)
cek("cek password apa pun -> False", auth.cek_password("apa saja", path=TMP), False)

print("\n2. Pasang password")
auth.pasang_password("rahasia123", path=TMP)
cek("sudah_ada_password", auth.sudah_ada_password(path=TMP), True)
cek("password benar", auth.cek_password("rahasia123", path=TMP), True)
cek("password salah", auth.cek_password("rahasia124", path=TMP), False)
cek("password kosong", auth.cek_password("", path=TMP), False)
cek("password beda huruf besar", auth.cek_password("Rahasia123", path=TMP), False)

print("\n3. Password TIDAK tersimpan sebagai teks polos")
isi = TMP.read_text()
cek("'rahasia123' tidak ada di berkas", "rahasia123" in isi, False)
data = json.loads(isi)
cek("ada hash", bool(data.get("hash")), True)
cek("ada salt", bool(data.get("salt")), True)
cek("algo tercatat", data.get("algo"), "pbkdf2_sha256")
cek("hash panjang 64 (sha256)", len(data["hash"]), 64)

print("\n4. Password terlalu pendek ditolak")
for pendek in ("", "a", "12345"):
    try:
        auth.pasang_password(pendek, path=TMP)
        gagal.append("password %r seharusnya ditolak" % pendek)
        print("  GAGAL %-54s seharusnya ditolak" % repr(pendek))
    except ValueError:
        print("  OK    %-54s ditolak" % repr(pendek))

print("\n5. Sesi")
t1 = auth.buat_sesi()
cek("token baru sah", auth.sesi_sah(t1), True)
cek("token ngawur tidak sah", auth.sesi_sah("token-palsu"), False)
cek("token kosong tidak sah", auth.sesi_sah(""), False)
cek("token None tidak sah", auth.sesi_sah(None), False)

print("\n6. Logout mencabut token — token lama tidak bisa dipakai lagi")
cek("logout berhasil", auth.akhiri_sesi(t1), True)
cek("token setelah logout TIDAK sah", auth.sesi_sah(t1), False)
cek("logout token yang sama dua kali ditolak", auth.akhiri_sesi(t1), False)

print("\n7. Sesi punya umur — bisa kedaluwarsa")
t2 = auth.buat_sesi(umur_detik=0)          # langsung kedaluwarsa
import time
time.sleep(0.01)
cek("sesi berumur 0 detik sudah mati", auth.sesi_sah(t2), False)

print("\n8. Sesi BERTAHAN melewati restart server (D8, 23 Okt 2026)")
t3 = auth.buat_sesi()
n_sebelum = auth.jumlah_sesi()
cek("ada sesi", n_sebelum > 0, True)
# Tiru restart server: proses baru = modul di-load ulang. Sesi disimpan di DB,
# jadi harus TETAP ada. Sampai 22 Okt 2026 uji ini menuntut sebaliknya ("semua
# sesi hilang"), karena sesi waktu itu hanya di memori — aturan itu dibatalkan
# Deny lewat D8: app Tauri menutup sidecar tiap kali app ditutup, jadi sesi
# memori berarti login ulang tiap buka app. Batasnya sekarang BOOT, bukan proses.
import importlib
importlib.reload(auth)
cek("setelah 'restart server', sesi masih ada", auth.jumlah_sesi() > 0, True)
cek("token lama masih sah setelah 'restart server'", auth.sesi_sah(t3), True)

# Yang membatalkan sesi: mesin restart. Simulasikan dengan UUID boot lain.
_boot_asli = auth.BOOT_UUID
auth.BOOT_UUID = "boot-lain-setelah-restart"
mati = auth.sesi_sah(t3)
auth.BOOT_UUID = _boot_asli
cek("sesi mati kalau boot_uuid beda (laptop restart)", mati, False)

print("\n9. Ganti password mengunci semua sesi")
auth.pasang_password("rahasia123", path=TMP)
ta = auth.buat_sesi()
tb = auth.buat_sesi()
cek("ada 2 sesi", auth.jumlah_sesi(), 2)
n = auth.akhiri_semua_sesi()
cek("semua dikunci", n, 2)
cek("jumlah sesi jadi 0", auth.jumlah_sesi(), 0)
cek("token a tidak sah", auth.sesi_sah(ta), False)
cek("token b tidak sah", auth.sesi_sah(tb), False)

print("\n10. Reset lewat terminal (jalur pemulihan yang dipilih Deny)")
auth.pasang_password("password-baru", path=TMP)
cek("password baru bekerja", auth.cek_password("password-baru", path=TMP), True)
cek("password lama TIDAK bekerja", auth.cek_password("rahasia123", path=TMP), False)

print("\n11. Izin berkas ketat kalau bisa diatur")
try:
    mode = oct(TMP.stat().st_mode & 0o777)
    cek("mode berkas", mode, "0o600")
except OSError:
    print("  (dilewati — tidak bisa membaca mode)")

print("\n12. Dua database kredensial berbeda tidak saling memengaruhi")
TMP2 = Path(tempfile.mkdtemp()) / "lain.json"
auth.pasang_password("punya-si-B", path=TMP2)
cek("kredensial A masih password-baru", auth.cek_password("password-baru", path=TMP), True)
cek("kredensial B", auth.cek_password("punya-si-B", path=TMP2), True)
cek("password B tidak berlaku di A", auth.cek_password("punya-si-B", path=TMP), False)

print("\n13. CELAH yang ditemukan yuki: /api/auth harus publik untuk GET juga")
# Celahnya: kalau GET /api/auth butuh login, halaman login tidak pernah tahu
# password sudah ada atau belum — jadi selalu menampilkan form MASUK. Password
# yang diketik di situ justru TERPASANG, sehingga siapa pun yang membuka panel
# lebih dulu bisa memasang passwordnya sendiri dan mengunci Deny keluar.
#
# Uji ini memeriksa perilaku server.py, bukan auth.py — dan sengaja memeriksa
# KEDUA arah: yang publik harus publik, yang privat harus tetap privat.
import re
teks_server = (Path(__file__).resolve().parent.parent / "src" / "server.py").read_text()

# Ambil isi fungsi _butuh_login
m = re.search(r"def _butuh_login\(self.*?\n(.*?)\n    def ", teks_server, re.S)
isi = m.group(1) if m else ""

cek("_butuh_login menyebut /api/auth", '"/api/auth"' in isi, True)
cek("TIDAK ada syarat method untuk /api/auth",
    'path == "/api/auth" and method' in isi, False)
print("     (kalau uji ini gagal: celah pengambilalihan akun kembali terbuka)")

print("\n14. Status publik tidak membocorkan info pemakaian")
m = re.search(r"def api_auth_status\(params.*?\n(.*?)\n\ndef ", teks_server, re.S)
isi_publik = m.group(1) if m else ""
cek("sudah_ada_password dikirim", "sudah_ada_password" in isi_publik, True)
cek("jumlah_sesi TIDAK dikirim", "jumlah_sesi" in isi_publik, False)
print("     (jumlah sesi = berapa orang sedang memakai panel — hanya untuk yang login)")

print("\n" + "─" * 74)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
