#!/usr/bin/env python3
"""Reset password panel finance.

Deny memilih ini (opsi C): kalau lupa password, reset lewat terminal di Mac ini.

PERINGATAN yang perlu disadari: skrip ini berarti **siapa pun yang bisa membuka
terminal di Mac ini bisa mereset password panel**. Jadi password panel BUKAN
perlindungan dari orang yang bisa memakai terminal — dia hanya menghalangi orang
yang lewat / memakai layar sebentar.

Itu pilihan sadar Deny, bukan kelalaian: tanpa jalur ini, lupa password = tidak
bisa membuka datanya sendiri selamanya (tidak ada email pemulihan, database-nya
lokal). Lebih baik bisa dipulihkan dengan konsekuensi itu.

Jalankan:
    python3 scripts/reset_password.py
"""
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import auth  # noqa: E402


def main():
    print("Reset password panel finance")
    print("=" * 48)
    print("Berkas kredensial:", auth.KREDENSIAL)
    print()

    if auth.sudah_ada_password():
        print("Password sudah ada dan akan DIGANTI.")
    else:
        print("Belum ada password. Ini akan memasang yang pertama.")

    print()
    p1 = getpass.getpass("Password baru (min %d karakter): " % auth.PANJANG_MIN_PASSWORD)
    p2 = getpass.getpass("Ulangi password baru: ")

    if p1 != p2:
        print("\nGAGAL: dua password yang dimasukkan berbeda.")
        return 1
    if len(p1) < auth.PANJANG_MIN_PASSWORD:
        print("\nGAGAL: password minimal %d karakter." % auth.PANJANG_MIN_PASSWORD)
        return 1

    auth.pasang_password(p1)
    print()
    print("Password tersimpan sebagai hash (bukan teks polos) di:")
    print(" ", auth.KREDENSIAL)
    print()
    print("Catatan: semua sesi yang sedang berjalan tetap hidup sampai server")
    print("dimatikan. Kalau kamu ingin memaksa logout sekarang, restart server:")
    print("  pkill -f 'src/server.py'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
