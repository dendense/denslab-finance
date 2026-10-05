#!/usr/bin/env python3
"""Konfigurasi model untuk parser chat-entry.

Satu tempat untuk mengganti model. `chat_entry.py` dan `parser_wrap.py`
membaca dari sini, jadi mengganti model tidak berarti mengedit dua berkas.

Cara ganti model: ubah MODEL di bawah, lalu jalankan
    python3 uji_model.py <nama-model>
untuk memastikan model barunya benar-benar akurat, bukan cuma hidup.
"""
import os

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
# Kalau ingin lewat router lokal, set NINE_ROUTER_BASE=http://localhost:20128/v1/chat/completions
BASE = os.environ.get("NINE_ROUTER_BASE", "https://kenari.id/v1/chat/completions")
TIMEOUT = 90
