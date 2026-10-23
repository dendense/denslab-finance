#!/usr/bin/env python3
"""Uji fallback rahasia dari `DATA_DIR/secrets.env`.

Latar belakang — 23 Okt 2026:

Launcher `.command` me-`source` env.sh, jadi app yang dibuka lewat peluncur
dapat kunci API. App Tauri yang dibuka dari **Dock** tidak mewarisi shell apa
pun: server hidup, `/login` 200, tapi fitur AI menjawab "Kunci API belum
diatur" — terbaca seperti app rusak.

Perbaikannya: `model_config` membaca `DATA_DIR/secrets.env` KALAU env tidak
menyetelnya. Dua hal yang dijaga uji ini:

  1. **Env tetap menang.** Kalau env ada, berkas tidak dibaca sama sekali.
  2. **Parser tidak mengeksekusi apa pun.** Berkas TIDAK di-`source`/`eval`,
     jadi `$(whoami)` tersimpan sebagai teks. Tanpa jaminan ini, berkas
     rahasia berubah jadi jalan eksekusi perintah.

Semua uji memakai folder sementara lewat FINANCE_DATA — folder data Deny
tidak disentuh.

Jalankan:  python3 tests/test_secrets_berkas.py
"""
import io
import os
import stat
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import model_config  # noqa: E402

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-56s %r" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_benar(nama, kondisi):
    print(("  OK   " if kondisi else "  GAGAL") + " %s" % nama)
    if not kondisi:
        gagal.append(nama)


TMP = Path(tempfile.mkdtemp())


def folder(nama, isi=None, mode=None):
    """Folder data sementara; `isi` ditulis ke secrets.env kalau diberikan."""
    d = TMP / nama
    d.mkdir()
    if isi is not None:
        p = d / "secrets.env"
        p.write_text(isi, encoding="utf-8")
        if mode is not None:
            p.chmod(mode)
    return d


def pakai(d):
    os.environ["FINANCE_DATA"] = str(d)
    model_config._sudah_lapor = False


def tanpa_env():
    os.environ.pop("KENARI_API_KEY", None)
    os.environ.pop("KENARI_BASE", None)


print("\n1. Env diset -> nilai env, berkas TIDAK dibaca (berkas berisi nilai lain)")
d = folder("env_menang", "KENARI_API_KEY=dari-berkas-jangan-dipakai\n")
pakai(d)
os.environ["KENARI_API_KEY"] = "dari-env"
cek("api_key", model_config.api_key(), "dari-env")

print("\n2. Env kosong + berkas ada -> nilai dari berkas")
tanpa_env()
os.environ["KENARI_API_KEY"] = ""  # kosong = tidak menyetel
cek("api_key", model_config.api_key(), "dari-berkas-jangan-dipakai")
cek("_dari_berkas langsung", model_config._dari_berkas("KENARI_API_KEY"),
    "dari-berkas-jangan-dipakai")
cek_benar("os.environ tidak diisi balik", "KENARI_API_KEY" not in os.environ
          or os.environ["KENARI_API_KEY"] == "")

print("\n3. Env kosong + berkas TIDAK ada -> string kosong, tanpa exception")
tanpa_env()
pakai(folder("tanpa_berkas"))
try:
    hasil = model_config.api_key()
    cek("api_key", hasil, "")
    cek_benar("tidak melempar", True)
except Exception as e:  # noqa: BLE001
    cek_benar("tidak melempar (%r)" % e, False)

print("\n4. Komentar + baris kosong diabaikan")
tanpa_env()
pakai(folder("komentar", "# komentar di depan\n\n   \n#KENARI_API_KEY=salah\n"
                          "KENARI_API_KEY=benar\n"))
cek("api_key", model_config.api_key(), "benar")

print("\n5. Nilai dengan '=' di dalamnya -> utuh setelah '=' pertama")
tanpa_env()
pakai(folder("sama_dengan", "KENARI_API_KEY=abc=def==ghi\n"))
cek("api_key", model_config.api_key(), "abc=def==ghi")

print("\n6. Berkas tidak bisa dibaca (chmod 000) -> None, lapor SEKALI, tidak crash")
tanpa_env()
d = folder("tak_terbaca", "KENARI_API_KEY=rahasia\n", mode=0o000)
pakai(d)
buf = io.StringIO()
try:
    with redirect_stderr(buf):
        hasil1 = model_config.api_key()
        hasil2 = model_config.api_key()
    cek("api_key pertama", hasil1, "")
    cek("api_key kedua", hasil2, "")
    cek_benar("tidak melempar", True)
    cek("jumlah laporan stderr", buf.getvalue().count("tidak bisa dibaca"), 1)
    cek_benar("laporan menyebut path",
              "secrets.env" in buf.getvalue())
except Exception as e:  # noqa: BLE001
    cek_benar("tidak melempar (%r)" % e, False)

print("\n7. $(whoami) dan `id` TIDAK dieksekusi -> tersimpan literal")
tanpa_env()
pakai(folder("injeksi", "KENARI_API_KEY=$(whoami)\nKENARI_BASE=`id`\n"))
cek("api_key literal", model_config.api_key(), "$(whoami)")
cek("KENARI_BASE literal", model_config._dari_berkas("KENARI_BASE"), "`id`")
cek_benar("tidak ada nama user di nilai", os.environ.get("USER", "\0")
          not in model_config.api_key())

print("\n8. Kutip di sekitar nilai dibuang")
tanpa_env()
pakai(folder("kutip", 'KENARI_API_KEY="abc-123"\n'))
cek("api_key", model_config.api_key(), "abc-123")

print("\n9. KENARI_BASE dari berkas dipakai saat modul diimpor (BASE)")
tanpa_env()
pakai(folder("base", "KENARI_BASE=https://contoh.test/v1\n"))
import importlib  # noqa: E402
importlib.reload(model_config)
cek("BASE", model_config.BASE, "https://contoh.test/v1/chat/completions")
tanpa_env()  # kembalikan supaya uji lain di proses ini tidak terpengaruh

print("\n10. Toleransi format manusia: `export `, spasi sekitar `=`, kutip berpasangan")
tanpa_env()
pakai(folder("toleran", (
    "export KENARI_API_KEY=satu\n"            # awalan export
)))
cek("export NAMA=nilai", model_config.api_key(), "satu")

tanpa_env()
pakai(folder("toleran_spasi_export", "export   KENARI_API_KEY=dua\n"))
cek("export   NAMA=nilai", model_config.api_key(), "dua")

tanpa_env()
pakai(folder("toleran_spasi_eq", "KENARI_API_KEY = tiga\n"))
cek("NAMA = nilai", model_config.api_key(), "tiga")

tanpa_env()
pakai(folder("toleran_spasi_ujung", "KENARI_API_KEY=empat   \n"))
cek("NAMA=nilai (spasi ujung)", model_config.api_key(), "empat")

tanpa_env()
pakai(folder("toleran_kutip_dua", 'KENARI_API_KEY="lima"\n'))
cek('NAMA="nilai"', model_config.api_key(), "lima")

tanpa_env()
pakai(folder("toleran_kutip_tunggal", "KENARI_API_KEY='enam'\n"))
cek("NAMA='nilai'", model_config.api_key(), "enam")

tanpa_env()
pakai(folder("toleran_kutip_spasi", 'KENARI_API_KEY="tujuh"   \n'))
cek('NAMA="nilai" + spasi', model_config.api_key(), "tujuh")

tanpa_env()
pakai(folder("toleran_kutip_tak_berpasangan", 'KENARI_API_KEY="delapan\n'))
cek('NAMA="abc (tak berpasangan)', model_config.api_key(), '"delapan')

tanpa_env()
pakai(folder("toleran_kutip_tengah", 'KENARI_API_KEY=sembilan"x\n'))
cek('NAMA=abc"def (kutip tengah)', model_config.api_key(), 'sembilan"x')

tanpa_env()
pakai(folder("toleran_injeksi_dollar", "KENARI_API_KEY=$(whoami)\n"))
cek("NAMA=$(whoami) literal", model_config.api_key(), "$(whoami)")

tanpa_env()
pakai(folder("toleran_injeksi_backtick", "KENARI_API_KEY=`id`\n"))
cek("NAMA=`id` literal", model_config.api_key(), "`id`")

tanpa_env()
pakai(folder("toleran_injeksi_export", "export KENARI_API_KEY=$(whoami)\n"))
cek("export NAMA=$(whoami) literal", model_config.api_key(), "$(whoami)")
cek_benar("tidak ada nama user di nilai export",
          os.environ.get("USER", "\0") not in (model_config.api_key() or ""))

tanpa_env()
pakai(folder("toleran_sama_dengan", "export KENARI_API_KEY=a=b=c\n"))
cek("nilai berisi '='", model_config.api_key(), "a=b=c")

tanpa_env()
pakai(folder("toleran_export_tanpa_spasi", "exportKENARI_API_KEY=sebelas\n"))
cek("exportNAMA=nilai TIDAK dilepas", model_config.api_key(), "")

print("\n11. `export` di tengah baris bukan awalan -> tidak dilepas")
tanpa_env()
pakai(folder("toleran_export_tengah", "KENARI_API_KEY=x export y\n"))
cek("export di tengah nilai utuh", model_config.api_key(), "x export y")

print("")
if gagal:
    print("GAGAL %d cek:" % len(gagal))
    for g in gagal:
        print("  - " + g)
    sys.exit(1)
print("SEMUA LULUS")
