#!/usr/bin/env python3
"""Uji ujung-ke-ujung analisa bulanan dengan MODEL AI SUNGGUHAN.

Berbeda dari tests/test_analysis.py (yang memalsukan model), skrip ini
memanggil model betulan lewat model_config, untuk memastikan:
  1. Narasi benar-benar terbentuk dari data nyata
  2. Penyaring angka tetap bekerja pada keluaran model sungguhan
  3. Hasilnya tersimpan dan bisa dibaca lagi

Dijalankan di database SEMENTARA — data keuangan Deny tidak tersentuh.

Jalankan:  python3 tests/test_analysis_live.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402
import monthly_analysis as ma  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "live.db"
db.init_db(TMP)

with db.connect(TMP) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('BRI','bank')")
BRI = {a["name"]: a["id"] for a in db.account_balances(include_inactive=True, path=TMP)}["BRI"]


def tx(tgl, arah, jumlah, kategori, flow="expense", catatan="contoh"):
    return {"occurred_on": tgl, "direction": arah, "amount": jumlah,
            "account_id": BRI, "category": kategori, "note": catatan,
            "flow_type": flow}


# September — pembanding
db.save_transactions([
    tx("2026-09-01", "in", 4226000, "Gaji", "income", "Gaji pokok"),
    tx("2026-09-02", "in", 3870600, "Bonus", "income", "Tunjangan kinerja"),
    tx("2026-09-05", "out", 450000, "Makan", "expense", "makan sebulan"),
    tx("2026-09-08", "out", 300000, "Transport", "expense", "bensin"),
    tx("2026-09-10", "out", 250000, "Tagihan", "expense", "listrik"),
    tx("2026-09-15", "out", 180000, "Hiburan", "expense", "nonton"),
], TMP)

# Oktober — yang dianalisa
db.save_transactions([
    tx("2026-10-01", "in", 4226000, "Gaji", "income", "Gaji pokok"),
    tx("2026-10-02", "in", 3870600, "Bonus", "income", "Tunjangan kinerja"),
    tx("2026-10-05", "out", 780000, "Makan", "expense", "makan sebulan"),
    tx("2026-10-08", "out", 350000, "Transport", "expense", "bensin dan tol"),
    tx("2026-10-10", "out", 280000, "Tagihan", "expense", "listrik dan air"),
    tx("2026-10-12", "out", 420000, "Hiburan", "expense", "langganan dan nonton"),
    tx("2026-10-20", "out", 1378666, "Tagihan", "debt_payment", "pelunasan PinjamanOnline"),
    tx("2026-10-22", "out", 285458, "Tagihan", "receivable", "topup ProyekAlpha & ProyekBeta"),
], TMP)

print("Data uji disiapkan: 6 transaksi September, 8 transaksi Oktober\n")

print("=" * 74)
print("ANGKA (dihitung db.py — bukan dari AI)")
print("=" * 74)
analisa = db.analisa_lengkap("2026-10", TMP)
a = analisa["angka"]
print(f"  masuk              : {db.rupiah(a['masuk'])}")
print(f"  keluar semua       : {db.rupiah(a['keluar_semua'])}")
print(f"  konsumsi sungguhan : {db.rupiah(a['konsumsi'])}")
print(f"  pelunasan utang    : {db.rupiah(a['pelunasan_utang'])}")
print(f"  talangan project   : {db.rupiah(a['talangan_piutang'])}")
print(f"  sisa kas           : {db.rupiah(a['sisa_kas'])}")
print(f"  SISA BEBAS         : {db.rupiah(a['sisa_bebas'])}   <- yang bisa ditabung")

print("\n" + "=" * 74)
print("KATEGORI (konsumsi saja — utang & talangan tidak ikut)")
print("=" * 74)
for k in a["kategori"]:
    tanda = " [WAJIB]" if k["wajib"] else ""
    naik = f" ({k['perubahan_persen']:+d}%)" if k["perubahan_persen"] is not None else ""
    print(f"  {k['category']:<12} {db.rupiah(k['total']):>16}{naik}{tanda}")

print("\n" + "=" * 74)
print("SARAN (angka dari hitungan)")
print("=" * 74)
for s in analisa["saran"]["kategori"]:
    ph = db.rupiah(s["potensi_hemat"]) if s["potensi_hemat"] else "—"
    print(f"  [{s['jenis']:<16}] {s['kategori']:<12} potensi hemat: {ph}")
    print(f"      {s['asumsi']}")

print("\n" + "=" * 74)
print("NARASI AI (memanggil model sungguhan...)")
print("=" * 74)
narasi = ma.buat_narasi(analisa)

print(f"\nmodel  : {ma.MODEL}")
print(f"catatan: {narasi.get('catatan') or 'narasi lengkap, tidak ada yang dibuang'}")

if narasi.get("angka_dibuang"):
    print(f"\n!! {len(narasi['angka_dibuang'])} kalimat DIBUANG karena angka karangan:")
    for d in narasi["angka_dibuang"]:
        print(f"   [{d['tempat']}] {d['kalimat']}")

print("\n--- ringkasan ---")
print(narasi.get("ringkasan") or "(tidak ada)")
print("\n--- per kategori ---")
for nama, kalimat in (narasi.get("per_kategori") or {}).items():
    print(f"  {nama}: {kalimat}")
print("\n--- penutup ---")
print(narasi.get("penutup") or "(tidak ada)")

print("\n" + "=" * 74)
print("SIMPAN & BACA LAGI")
print("=" * 74)
hasil = db.simpan_analisa("2026-10", narasi=narasi,
                          snapshot={"masuk": a["masuk"], "konsumsi": a["konsumsi"]},
                          model=ma.MODEL if not narasi.get("catatan") else None,
                          catatan=narasi.get("catatan"), path=TMP)
print(f"  ada_analisa     : {hasil['ada_analisa']}")
print(f"  dibuat_pada     : {hasil['dibuat_pada']}")
print(f"  model tercatat  : {hasil['model']}")
print(f"  narasi_basi     : {hasil['narasi_basi']}")
print(f"  ringkasan tersimpan: {hasil['narasi']['ringkasan'][:70] if hasil['narasi'].get('ringkasan') else '(kosong)'}...")

print("\nDatabase uji:", TMP)
