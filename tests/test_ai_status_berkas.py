#!/usr/bin/env python3
"""Uji `/api/ai-status` membaca kunci dari `DATA_DIR/secrets.env`.

Latar belakang — 23 Okt 2026:

`model_config.api_key()` sudah punya fallback berkas (kartu t_45cccacd), tapi
`src/server.py:904` masih membaca `os.environ` langsung. Akibatnya, saat app
dibuka dari Dock (tanpa shell yang me-`source` env.sh) dan kuncinya hanya ada
di `secrets.env`:

  - catat pintar (`chat_entry`)  -> JALAN
  - analisa bulanan              -> JALAN
  - panel cek-kesehatan AI       -> "Kunci API belum diatur"

Itu yang membuat app terbaca rusak padahal fiturnya hidup. Uji ini menjaga dua
arah sekaligus:

  1. Kunci dari berkas -> panel melaporkan hidup (dan kuncinya benar-benar
     dipakai sebagai Bearer, bukan cuma "tidak kosong").
  2. Kunci kosong di mana pun -> panel TETAP melaporkan "belum diatur".
     Jangan sampai perbaikan ini melonggarkan cek kosong.

Model TIDAK dipanggil sungguhan: `model_config.BASE` diarahkan ke HTTP server
palsu di 127.0.0.1, jadi nol kuota terpakai dan hasilnya deterministik.

Jalankan:  python3 tests/test_ai_status_berkas.py
"""
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TMP = Path(tempfile.mkdtemp())

# FINANCE_DATA harus diset SEBELUM `db`/`server` diimpor: DATA_DIR dibaca saat
# import. Uji ini memakai folder sementara, folder data Deny tidak disentuh.
os.environ["FINANCE_DATA"] = str(TMP)
os.environ.pop("KENARI_API_KEY", None)
os.environ.pop("KENARI_BASE", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import model_config  # noqa: E402
import server        # noqa: E402

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


# ── Model palsu ─────────────────────────────────────────────────────────────
# Mencatat header Authorization supaya bisa dibuktikan kunci dari BERKAS yang
# benar-benar dipakai, bukan sekadar "tidak kosong".
dilihat = []


class Palsu(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        panjang = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(panjang)
        dilihat.append({"auth": self.headers.get("Authorization"),
                        "path": self.path})
        body = json.dumps({"model": "palsu-1", "choices": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        pass  # jangan cemari keluaran uji


srv = HTTPServer(("127.0.0.1", 0), Palsu)
threading.Thread(target=srv.serve_forever, daemon=True).start()
model_config.BASE = "http://127.0.0.1:%d/v1/chat/completions" % srv.server_port


def folder(nama, isi=None):
    d = TMP / nama
    d.mkdir()
    if isi is not None:
        (d / "secrets.env").write_text(isi, encoding="utf-8")
    return d


def pakai(d):
    os.environ["FINANCE_DATA"] = str(d)
    model_config._sudah_lapor = False


def tanpa_env():
    os.environ.pop("KENARI_API_KEY", None)


print("\n1. Env kosong + kunci HANYA di secrets.env -> panel melaporkan HIDUP")
tanpa_env()
pakai(folder("ada_berkas", "KENARI_API_KEY=kunci-dari-berkas\n"))
dilihat.clear()
hasil = server.api_ai_status({})
cek("ok", hasil.get("ok"), True)
cek("keadaan", hasil.get("keadaan"), "ok")
cek_benar("pesan bukan 'belum diatur'",
          "belum diatur" not in (hasil.get("pesan") or "").lower())
cek("kunci dipakai sebagai Bearer", dilihat[0]["auth"] if dilihat else None,
    "Bearer kunci-dari-berkas")
cek_benar("kunci tidak ikut di balasan",
          "kunci-dari-berkas" not in json.dumps(hasil))

print("\n2. Env diset -> env menang, berkas tidak dipakai (perilaku lama)")
pakai(folder("env_menang", "KENARI_API_KEY=kunci-dari-berkas\n"))
os.environ["KENARI_API_KEY"] = "kunci-dari-env"
dilihat.clear()
hasil = server.api_ai_status({})
cek("ok", hasil.get("ok"), True)
cek("kunci dipakai sebagai Bearer", dilihat[0]["auth"] if dilihat else None,
    "Bearer kunci-dari-env")
tanpa_env()

print("\n3. Env kosong + TANPA secrets.env -> TETAP 'belum diatur', tanpa panggilan")
pakai(folder("tanpa_berkas"))
dilihat.clear()
hasil = server.api_ai_status({})
cek("ok", hasil.get("ok"), False)
cek("keadaan", hasil.get("keadaan"), "gagal")
cek("latensi_ms", hasil.get("latensi_ms"), None)
cek_benar("pesan menyebut 'belum diatur'",
          "belum diatur" in (hasil.get("pesan") or "").lower())
cek("model tidak dihubungi", len(dilihat), 0)

print("\n4. Berkas ada tapi nilainya KOSONG -> tetap 'belum diatur'")
pakai(folder("kosong", "KENARI_API_KEY=\n"))
dilihat.clear()
hasil = server.api_ai_status({})
cek("ok", hasil.get("ok"), False)
cek_benar("pesan menyebut 'belum diatur'",
          "belum diatur" in (hasil.get("pesan") or "").lower())
cek("model tidak dihubungi", len(dilihat), 0)

print("\n5. Berkas berisi spasi saja -> tetap 'belum diatur'")
pakai(folder("spasi", "KENARI_API_KEY=   \n"))
cek("api_key", model_config.api_key(), "")
hasil = server.api_ai_status({})
cek("ok", hasil.get("ok"), False)

print("\n6. §1 CONTRACT: nama variabel environment tidak disebut ke UI")
pakai(folder("tanpa_berkas_2"))
pesan = server.api_ai_status({}).get("pesan") or ""
cek_benar("pesan tanpa 'KENARI_API_KEY'", "KENARI_API_KEY" not in pesan)
cek_benar("pesan tanpa 'os.environ'", "environ" not in pesan.lower())

srv.shutdown()
print("")
if gagal:
    print("GAGAL %d cek:" % len(gagal))
    for g in gagal:
        print("  - " + g)
    sys.exit(1)
print("SEMUA LULUS")
