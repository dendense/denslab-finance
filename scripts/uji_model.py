#!/usr/bin/env python3
"""Uji banding model parser — cari mana yang paling akurat untuk chat-entry.

Dijalankan sekali untuk memutuskan model; bukan bagian dari aplikasi.

Yang diuji bukan cuma "apakah JSON-nya valid" — parser yang selalu membalas
JSON rapi tapi salah menebak arah transaksi tetap merusak laporan. Jadi setiap
kasus punya jawaban yang diharapkan.

Jalankan:  python3 uji_model.py
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import model_config  # noqa: E402

BASE = model_config._base_url()  # ponytail: env dibaca saat impor; upgrade ke panggil-per-request kalau skrip jadi long-running

KATEGORI = ["Makan", "Transport", "Belanja", "Hiburan", "Tagihan",
            "Kesehatan", "Pendidikan", "Gaji", "Bonus", "Lainnya"]

SYS = """Kamu parser transaksi keuangan berbahasa Indonesia. Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.

Format:
{"transactions": [
  {"direction": "in"|"out"|"transfer", "amount": number,
   "category": string|null, "note": string,
   "occurred_on": "YYYY-MM-DD"|null, "account_hint": string|null,
   "assumed_date": bool}
], "question": string|null}

Aturan WAJIB:
- Kalau satu pesan berisi LEBIH DARI SATU transaksi, keluarkan SEMUA sebagai elemen terpisah di "transactions".
- amount SELALU positif. Arah disimpan di "direction", bukan di tanda angka.
- "transfer"/"pindah"/"masukin ke tabungan" -> "transfer".
- "terima"/"gaji"/"masuk"/"dapat"/"bonus"/"dibayar" -> "in". Sisanya "out".
- category HARUS salah satu dari: %s
- Kalau user tidak menyebut tanggal, isi null dan set "assumed_date": true. Hari ini = %s.
- "note": deskripsi singkat dari user, jangan tambah sendiri.
- Kalau pesan BUKAN transaksi (sapaan, pertanyaan), transactions = [] dan isi "question".""" % (
    ", ".join(KATEGORI), date.today().isoformat())

# (kalimat, jumlah transaksi, arah yang diharapkan, jumlah rupiah yang diharapkan)
KASUS = [
    ("makan malam 45000",                      1, ["out"],      [45000]),
    ("makan siang 25rb sama parkir 5rb",       2, ["out","out"],[25000, 5000]),
    ("terima gaji 4226000",                    1, ["in"],       [4226000]),
    ("bayar tagihan listrik 250000",           1, ["out"],      [250000]),
    ("pindah 500000 ke tabungan",              1, ["transfer"], [500000]),
    ("kemarin belanja bulanan 350000",         1, ["out"],      [350000]),
    ("dapat bonus 3870600",                    1, ["in"],       [3870600]),
    ("top up gopay 100000",                    1, ["out","transfer"], [100000]),
    ("beli obat 75000 sama vitamin 30000",     2, ["out","out"],[75000, 30000]),
    ("transfer 1000000 ke bca",                1, ["transfer"], [1000000]),
    ("isi bensin 200000",                      1, ["out"],      [200000]),
    ("bayar kos 1500000",                      1, ["out"],      [1500000]),
]

TIDAK_TRANSAKSI = ["halo", "apa kabar", "makasih ya"]


def panggil(model, teks):
    key = os.environ.get("KENARI_API_KEY", "").strip()
    body = {
        "model": model, "max_tokens": 900, "stream": True, "temperature": 0,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": teks}],
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read().decode()

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
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def nilai(model):
    benar = total = 0
    gagal_json = 0
    kosong = 0
    rincian = []

    for teks, n_harap, arah_harap, jumlah_harap in KASUS:
        total += 1
        try:
            d = panggil(model, teks)
        except Exception as e:
            rincian.append((teks, "ERROR %s" % type(e).__name__))
            continue
        if d is None:
            gagal_json += 1
            rincian.append((teks, "JSON rusak / kosong"))
            continue
        txs = d.get("transactions") or []
        if not txs:
            kosong += 1
            rincian.append((teks, "tidak menemukan transaksi"))
            continue

        ok = True
        pesan = []
        if len(txs) != n_harap:
            ok = False
            pesan.append("jumlah %d!=%d" % (len(txs), n_harap))
        arah_dapat = [t.get("direction") for t in txs]
        if arah_dapat != arah_harap:
            ok = False
            pesan.append("arah %s!=%s" % (arah_dapat, arah_harap))
        jumlah_dapat = []
        for t in txs:
            try:
                jumlah_dapat.append(int(float(t.get("amount") or 0)))
            except Exception:
                jumlah_dapat.append(None)
        if jumlah_dapat != jumlah_harap:
            ok = False
            pesan.append("jumlah %s!=%s" % (jumlah_dapat, jumlah_harap))

        if ok:
            benar += 1
        else:
            rincian.append((teks, "; ".join(pesan)))

    # pesan yang bukan transaksi: harus mengembalikan transactions kosong
    for teks in TIDAK_TRANSAKSI:
        total += 1
        try:
            d = panggil(model, teks)
        except Exception:
            continue
        if d is not None and not (d.get("transactions") or []):
            benar += 1
        else:
            rincian.append((teks, "mengarang transaksi dari sapaan"))

    return benar, total, gagal_json, kosong, rincian


def main():
    kandidat = sys.argv[1:] or [
        "kenari/glm-5-3-flash",
        "kenari/agnes-2-0-flash:free",
        "kenari/agnes-2-5-flash:free",
        "kenari/agnes-3-0-flash:free",
        "kenari/glm-4-7-flash:free",
    ]
    hasil = []
    for m in kandidat:
        print("menguji %s ..." % m, flush=True)
        try:
            benar, total, gj, kos, rincian = nilai(m)
        except Exception as e:
            print("  model tidak bisa dipakai: %s" % e)
            hasil.append((m, -1, 0, 0, 0, []))
            continue
        hasil.append((m, benar, total, gj, kos, rincian))
        print("  %d/%d benar (%d JSON rusak, %d kosong)"
              % (benar, total, gj, kos), flush=True)

    print("\n" + "=" * 72)
    print("%-32s %8s %8s %8s" % ("MODEL", "BENAR", "RUSAK", "KOSONG"))
    print("-" * 72)
    for m, benar, total, gj, kos, _ in sorted(hasil, key=lambda x: -x[1]):
        if benar < 0:
            print("%-32s %8s" % (m, "MATI"))
        else:
            print("%-32s %5d/%-3d %8d %8d" % (m, benar, total, gj, kos))

    print("\nKegagalan terbesar (per model):")
    for m, benar, total, gj, kos, rincian in hasil:
        if benar < 0 or not rincian:
            continue
        print("\n  %s:" % m)
        for teks, sebab in rincian[:5]:
            print("    %-42s %s" % (teks[:42], sebab[:60]))


if __name__ == "__main__":
    main()
