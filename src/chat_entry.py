#!/usr/bin/env python3
"""Prototipe parser chat-entry keuangan — TANPA database.

Tujuan: Deny bisa mencoba sendiri dan menilai apakah cara input ini nyaman sebelum
investasi ke aplikasi penuh.

Yang diuji di sini adalah bagian yang paling rawan: mengurai kalimat Indonesia jadi
transaksi terstruktur. Bagian UI dan database belum ada.

Jalankan:  python3 chat_entry.py
Atau:      python3 chat_entry.py "makan malam 45000"

Model dibaca dari model_config.py — jangan hardcode di sini, supaya mengganti
model tidak perlu menyentuh dua berkas.
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime

import model_config

MODEL = model_config.MODEL
BASE = model_config.BASE

KATEGORI = ["Makan", "Transport", "Belanja", "Hiburan", "Tagihan",
            "Kesehatan", "Pendidikan", "Gaji", "Lainnya"]

SYS = """Kamu parser transaksi keuangan berbahasa Indonesia. Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.

Format:
{"transactions": [
  {"direction": "in"|"out"|"transfer", "amount": number,
   "category": string|null, "note": string,
   "occurred_on": "YYYY-MM-DD"|null, "account_hint": string|null,
   "assumed_date": bool}
], "question": string|null}

Aturan WAJIB:
- Kalau satu pesan berisi LEBIH DARI SATU transaksi, keluarkan SEMUA sebagai elemen
  terpisah di "transactions". Contoh: "makan siang 25rb sama parkir 5rb" ->
  DUA transaksi: 25000 Makan, dan 5000 Transport. Jangan pernah gabungkan jadi satu,
  dan jangan pernah buang salah satunya.
- amount SELALU positif. Arah disimpan di "direction", bukan di tanda angka.
- "transfer"/"pindah"/"masukin ke tabungan" -> "transfer".
- "terima"/"gaji"/"masuk"/"dapat"/"bonus"/"dibayar" -> "in". Sisanya "out".
- category HARUS salah satu dari: %s
  Category adalah JENIS transaksi, BUKAN arah. Untuk direction "transfer", category = null.
- "occurred_on": kalau user tidak menyebut tanggal, isi null dan set "assumed_date": true.
  Kalau menyebut ("kemarin", "tadi pagi", "3 hari lalu"), hitung dari hari ini = %s.
- "note": deskripsi singkat dari user, jangan tambah sendiri.
- Kalau pesan BUKAN transaksi (sapaan, pertanyaan), transactions = [] dan isi "question".
- Kalau ada angka tapi arah/kategori benar-benar tidak bisa ditentukan, tetap keluarkan
  transaksinya dengan category "Lainnya" dan sebutkan keraguanmu di "note".""" % (
    ", ".join(KATEGORI), date.today().isoformat())


def parse(text):
    """Kirim ke model, kembalikan dict hasil parse.

    stream WAJIB true. Alasannya: ROUTER membalas HTTP 200 dengan content
    KOSONG saat stream=false untuk model-model ini (bug yang sama dengan jalur
    visi). Default sekarang Kenari LANGSUNG (lihat `model_config.BASE`), tapi
    NINE_ROUTER_BASE bisa menunjuk router lokal — dan router apa pun yang
    dipakai tetap punya sifat ini. Jadi jangan set stream=false.
    """
    key = os.environ.get("NINE_ROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("NINE_ROUTER_API_KEY tidak ada di environment")

    body = {
        "model": MODEL,
        "max_tokens": 1200,
        "stream": True,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content": text},
        ],
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=model_config.TIMEOUT) as r:
            raw = r.read().decode()
    except Exception as e:
        # Model utama tidak bisa dihubungi (kuota habis, provider mati, model
        # dicabut). Coba cadangan supaya pencatatan tidak ikut mati.
        if model_config.MODEL_CADANGAN and model_config.MODEL_CADANGAN != MODEL:
            body["model"] = model_config.MODEL_CADANGAN
            req = urllib.request.Request(
                BASE, data=json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + key,
                         "Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=model_config.TIMEOUT) as r:
                    raw = r.read().decode()
            except Exception as e2:
                # `e2` WAJIB ditangkap di sini: tanpa itu, `e` di bawah merujuk
                # kegagalan model UTAMA — sebab kegagalan CADANGAN hilang, dan
                # itu justru informasi yang paling dibutuhkan saat mendiagnosa.
                raise RuntimeError(
                    "Model utama dan cadangan dua-duanya gagal. "
                    "Utama: %s · Cadangan: %s" % (e, e2))
        else:
            raise

    chunks = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if p == "[DONE]":
            break
        try:
            d = json.loads(p)
            ch = d.get("choices") or []
            if ch and (ch[0].get("delta") or {}).get("content"):
                chunks.append(ch[0]["delta"]["content"])
        except Exception:
            pass

    txt = "".join(chunks).strip().replace("```json", "").replace("```", "").strip()
    if not txt:
        return {"transactions": [], "question": "Model tidak membalas (content kosong)."}
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        return {"transactions": [],
                "question": "Jawaban model bukan JSON valid. Coba tulis ulang pesanmu."}

    # Tanggal null -> isi hari ini dan tandai diasumsikan. Kalau dibiarkan null,
    # transaksinya tidak akan muncul di laporan bulan mana pun.
    today = date.today().isoformat()
    for tx in data.get("transactions") or []:
        if not tx.get("occurred_on"):
            tx["occurred_on"] = today
            tx["assumed_date"] = True
        if tx.get("direction") == "transfer":
            tx["category"] = None
    return data


def rupiah(n):
    try:
        return "Rp " + format(int(round(float(n))), ",d").replace(",", ".")
    except Exception:
        return "Rp ?"


def render(text, hasil):
    txs = hasil.get("transactions") or []
    print("\n" + "─" * 62)
    print("KAMU :", text)

    if not txs:
        # Jangan pakai hasil["question"] apa adanya: model kadang memantulkan pesan
        # user atau membalas dengan kalimat yang tidak menjelaskan apa-apa. Pesan
        # cadangan dipakai kalau balasannya terlalu pendek, tidak memakai kata tanya,
        # atau isinya persis pesan user.
        q = (hasil.get("question") or "").strip()
        layak = (
            q
            and q.lower() != text.strip().lower()
            and len(q) > 12
            and any(k in q for k in ("?", "tidak", "bukan", "belum", "mohon", "coba", "maksud", "transaksi", "catat"))
        )
        print("MONICA:", q if layak else "Aku tidak menemukan transaksi di pesan itu.")
        print("─" * 62)
        return

    if len(txs) > 1:
        print("\nMONICA: Pesanmu berisi %d transaksi. Cek satu-satu:\n" % len(txs))
    else:
        print()

    arah_label = {"in": "MASUK   ", "out": "KELUAR  ", "transfer": "PINDAH  "}
    for i, tx in enumerate(txs, 1):
        d = tx.get("direction", "?")
        cat = tx.get("category") or ("—" if d == "transfer" else "Lainnya")
        tgl = tx.get("occurred_on", "-")
        tanda = "  (tanggal diasumsikan hari ini)" if tx.get("assumed_date") else ""
        print("  %d. %s %-12s %-11s %s" % (
            i, arah_label.get(d, d.ljust(8)), rupiah(tx.get("amount")), cat, tgl + tanda))
        if tx.get("note"):
            print("     catatan: %s" % tx["note"])
        if tx.get("account_hint"):
            print("     akun   : %s" % tx["account_hint"])

    print("\n  [Simpan semua]  [Koreksi]  [Batal]     ← di prototipe ini belum aktif")
    print("─" * 62)


def main():
    if len(sys.argv) > 1:
        teks = " ".join(sys.argv[1:])
        try:
            render(teks, parse(teks))
        except Exception as e:
            print("GAGAL:", e)
        return

    print("Prototipe pencatatan lewat chat — monica")
    print("Ketik transaksi seperti: Membeli makan malam 45000")
    print("Ketik 'keluar' untuk berhenti.\n")
    while True:
        try:
            teks = input("KAMU : ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not teks:
            continue
        if teks.lower() in {"keluar", "exit", "quit", "q"}:
            break
        try:
            render(teks, parse(teks))
        except Exception as e:
            print("GAGAL:", e)


if __name__ == "__main__":
    main()
