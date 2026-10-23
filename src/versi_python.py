#!/usr/bin/env python3
"""Batas versi Python — satu sumber kebenaran.

`MINIMUM` adalah LANTAI SINTAKS, bukan kebijakan. Angka ini ditentukan dari kode
yang ADA, bukan dari dokumen:

  * Fitur sintaks termodern yang dipakai seluruh `src/`, `scripts/`, `tests/`:
    `subprocess.run(capture_output=True, text=True)` di `src/auth.py:77` -> 3.7.
    Tidak ada `match`/`case`, tidak ada `X | Y` di anotasi tipe, tidak ada
    `dataclass(slots=True)`, tidak ada `:=`, tidak ada `list[...]` di anotasi.
  * Ke-30 berkas .py kompilasi bersih di `/usr/bin/python3` (3.9.6), dan seluruh
    suite lulus di 3.9.6 persis seperti di 3.11.15.

Jadi 3.10 BUKAN syarat kode ini. 3.9 dipilih sebagai angka deklarasi karena itu
versi terendah yang benar-benar DIJALANKAN (bukan cuma disimpulkan dari sintaks);
3.7/3.8 hanya inferensi dan tidak pernah diuji. Lihat kartu t_26b9eb05.

Keputusan Deny, 23 Okt 2026: `MINIMUM` tetap (3, 9) karena sudah terbukti — suite
hijau di 3.9.6 dan `py_compile` 30/30. Yang berubah hanyalah KEBIASAAN: launcher
wajib memilih Python 3.11 lebih dulu (`REKOMENDASI`). Kalau harus jatuh ke Python
sistem Apple (3.9.6) itu boleh — TAPI dengan peringatan yang terlihat, karena
Python bawaan sistem deprecated sejak macOS 12.3 dan akan dihapus. Jadi:

  * di bawah `MINIMUM` -> `cek()` MENOLAK (exit 1), sama seperti sebelumnya.
  * di antara `MINIMUM` dan `REKOMENDASI` -> `peringatan()` mengembalikan teks,
    TIDAK pernah exit. Ini bukan penolakan, ini pemberitahuan.
"""
import sys

MINIMUM = (3, 9)
MINIMUM_TEKS = ".".join(map(str, MINIMUM))

REKOMENDASI = (3, 11)   # versi yang seharusnya dipakai; MINIMUM cuma lantai sintaks
REKOMENDASI_TEKS = ".".join(map(str, REKOMENDASI))


def cek():
    """Keluar dengan pesan jelas kalau interpreter terlalu tua.

    Versi yang dilaporkan diambil dari `sys.version_info`, bukan
    `platform.python_version()`: nilainya sama persis di interpreter sungguhan,
    tapi `sys.version_info` bisa di-monkeypatch sehingga ujinya deterministik.
    """
    if sys.version_info[:2] >= MINIMUM:
        return
    ditemukan = ".".join(map(str, sys.version_info[:3]))
    sys.stderr.write(
        "Python terlalu tua: %s = %s, minimum %s.\n"
        "Pasang Python %s+ atau set FINANCE_PYTHON ke interpreter yang benar.\n"
        % (sys.executable, ditemukan, MINIMUM_TEKS, MINIMUM_TEKS))
    sys.exit(1)


def peringatan():
    """Satu baris peringatan kalau interpreter di bawah `REKOMENDASI`, atau None.

    TIDAK pernah `sys.exit`: 3.9-3.10 masih sah dipakai (lihat docstring modul).
    Pemanggil cukup mencetaknya ke `sys.stderr`.

    Versi dibaca dari `sys.version_info` supaya bisa di-monkeypatch di uji.
    """
    if sys.version_info[:2] >= REKOMENDASI:
        return None
    ditemukan = ".".join(map(str, sys.version_info[:3]))
    return (
        "Peringatan: jalan di Python %s (%s) — di bawah %s. "
        "Python bawaan sistem Apple deprecated dan akan dihapus. "
        "Set FINANCE_PYTHON ke %s+."
        % (ditemukan, sys.executable, REKOMENDASI_TEKS, REKOMENDASI_TEKS))


if __name__ == "__main__":
    cek()
    _p = peringatan()
    if _p:
        sys.stderr.write(_p + "\n")
    print("Python %s — memenuhi minimum %s (rekomendasi %s)."
          % (sys.version.split()[0], MINIMUM_TEKS, REKOMENDASI_TEKS))
