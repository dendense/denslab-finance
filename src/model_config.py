#!/usr/bin/env python3
"""Konfigurasi model untuk parser chat-entry.

Satu tempat untuk mengganti model. `chat_entry.py` dan `parser_wrap.py`
membaca dari sini, jadi mengganti model tidak berarti mengedit dua berkas.

Cara ganti model: ubah MODEL di bawah, lalu jalankan
    python3 uji_model.py <nama-model>
untuk memastikan model barunya benar-benar akurat, bukan cuma hidup.
"""
import os
import sys
from pathlib import Path

# Model yang dipakai parser. Dipilih Deny 1 Okt 2026.
#
# Riwayat pemilihan (hasil uji_model.py, 15 kasus):
#   kenari/glm-5-3-flash        14/15  versi lama; TIDAK muncul di /v1/models
#                                      lagi -> bisa dicabut sewaktu-waktu
#   kenari/agnes-2-0-flash:free 14/15  gratis, akurat, tapi kuota gratis
#                                      bisa berubah perilaku tanpa kabar
#   kenari/agnes-2-5-flash:free  0/15  request gagal semua
#   kenari/agnes-3-0-flash:free  0/15  request gagal semua
#   kenari/glm-4-7-flash:free    0/15  request gagal semua
#   kenari/deepseek-v4-1-flash  14/15  DIPAKAI -> kuota masih cukup
#
# Satu-satunya kasus yang gagal di semua model: "top up gopay 100000" —
# kalimatnya memang ambigu (pindah ke saldo, atau pengeluaran?). Bukan cacat
# model; ini alasan layar konfirmasi punya chip koreksi flow_type.
# PENTING: nama model TIDAK memakai awalan "kenari/". Awalan itu konvensi
# router omniroute, bukan nama asli di API kenari.id. Lewat kenari.id langsung,
# modelnya cuma "deepseek-v4-1-flash" — memakai awalan menghasilkan
# HTTP 400 "no price for model 'kenari/deepseek-v4-1-flash'".
MODEL = "deepseek-v4-1-flash"

# Cadangan kalau model utama mati. Yang gratis, supaya pencatatan tidak
# pernah benar-benar berhenti walaupun kuota habis.
MODEL_CADANGAN = "agnes-2-0-flash:free"

# Bawaan: kenari.id langsung. Tidak perlu omniroute.
# Kalau ingin lewat router lokal, set KENARI_BASE=http://localhost:20128/v1/chat/completions
_BASE_BAWAAN = "https://kenari.id/v1/chat/completions"

# ── Rahasia dari berkas ─────────────────────────────────────────────────────
# Launcher `.command` me-`source` env.sh, tapi app Tauri yang dibuka dari Dock
# tidak mewarisi shell apa pun. Tanpa fallback ini server tetap hidup tapi
# fitur AI menjawab "Kunci API belum diatur" — terbaca seperti app rusak.
# Berkasnya di folder data (di luar repo, gitignored), bukan di config.json.
# Env TETAP menang: kalau env menyetel nilainya, berkas tidak dibuka sama sekali.
_sudah_lapor = False


def _data_dir():
    """Sama dengan `db.DATA_DIR` (`db.py:44-45`), tapi dibaca saat dipanggil.

    Dibaca saat dipanggil supaya uji bisa mengarahkan FINANCE_DATA ke folder
    sementara tanpa meng-import ulang modul.
    """
    return Path(os.environ.get("FINANCE_DATA")
                or (Path(__file__).resolve().parent.parent.parent / "Data" / "finance"))


def _dari_berkas(nama):
    """Baca satu variabel dari DATA_DIR/secrets.env kalau env tidak menyetelnya.

    Berkas TIDAK di-`source`/`eval`: isi seperti `$(whoami)` atau `` `id` ``
    tersimpan apa adanya dan tidak pernah dijalankan. `os.environ` juga tidak
    diubah — kunci yang ditulis balik ke environment proses terlihat di
    `ps eww` dan bisa diwarisi proses anak.
    """
    global _sudah_lapor
    path = _data_dir() / "secrets.env"
    try:
        teks = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None  # wajar: banyak instalasi memang tanpa berkas ini
    except OSError as e:
        if not _sudah_lapor:  # sekali saja, bukan tiap panggilan
            _sudah_lapor = True
            print("finance: %s tidak bisa dibaca (%s); kunci dari berkas dilewati."
                  % (path, e), file=sys.stderr)
        return None
    for baris in teks.splitlines():
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        kunci, _, nilai = baris.partition("=")  # pisah di `=` PERTAMA
        # `export NAMA=nilai` wajar ditulis manusia. Lepas HANYA di awal baris
        # dan HANYA kalau diikuti spasi: `exportNAMA=nilai` bukan `export NAMA`.
        if kunci.startswith("export") and kunci[6:7].isspace():
            kunci = kunci[6:].lstrip()
        if kunci.strip() != nama:
            continue
        nilai = nilai.strip()
        if len(nilai) >= 2 and nilai[0] == nilai[-1] and nilai[0] in "\"'":
            nilai = nilai[1:-1]  # `KENARI_API_KEY="abc"` tetap abc
        return nilai or None
    return None


def _base_url():
    """KENARI_BASE boleh menunjuk root API (`.../v1`) atau endpoint penuh.

    Kode mem-POST langsung ke nilai ini, jadi `.../v1` saja = 404. Bentuk
    yang diterima: kosong -> bawaan, berakhir `/chat/completions` -> apa
    adanya, berakhir `/v1` -> ditambah `chat/completions`.
    """
    url = (os.environ.get("KENARI_BASE") or _dari_berkas("KENARI_BASE")
           or "").strip().rstrip("/")
    if not url:
        return _BASE_BAWAAN
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return url + "/chat/completions"
    return url  # ponytail: bentuk lain dipakai apa adanya; upgrade ke parser URL kalau ternyata salah bentuk


BASE = _base_url()


def api_key():
    """Nama dibaca dari satu tempat, supaya tidak tersebar di empat berkas.

    Urutan sumber: env dulu (perilaku lama, tidak berubah), baru
    `DATA_DIR/secrets.env`. Env kosong/tidak ada -> berkas. Tanpa berkas ->
    `""`, sama seperti sebelumnya (pemanggil sudah menangani string kosong).
    """
    return (os.environ.get("KENARI_API_KEY") or _dari_berkas("KENARI_API_KEY")
            or "").strip()


TIMEOUT = 90
