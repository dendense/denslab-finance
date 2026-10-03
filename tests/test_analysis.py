#!/usr/bin/env python3
"""Uji analisa bulanan — hitungan, aturan bulan, dan PENYARINGAN ANGKA AI.

Yang paling penting diuji di sini: apakah narasi AI bisa menyelundupkan angka
yang tidak ada di data. Kalau bisa lolos, satu angka karangan di halaman analisa
merusak kepercayaan pada semua angka lain di halaman itu — dan Deny tidak punya
cara tahu mana yang karangan.

Jalankan:  python3 tests/test_analysis.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db  # noqa: E402
import monthly_analysis as ma  # noqa: E402

TMP = Path(tempfile.mkdtemp()) / "uji_analisa.db"
db.init_db(TMP)
gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-50s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


# ── Siapkan data dua bulan ───────────────────────────────────────────────────
with db.connect(TMP) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('BRI','bank')")
acc = {a["name"]: a["id"] for a in db.account_balances(include_inactive=True, path=TMP)}
BRI = acc["BRI"]

def tx(tgl, arah, jumlah, kategori, flow="expense", catatan="uji"):
    return {"occurred_on": tgl, "direction": arah, "amount": jumlah,
            "account_id": BRI, "category": kategori, "note": catatan,
            "flow_type": flow}

# September (bulan pembanding)
db.save_transactions([
    tx("2026-09-05", "in",  8000000, "Gaji", "income"),
    tx("2026-09-10", "out",  400000, "Makan"),
    tx("2026-09-15", "out",  200000, "Transport"),   # wajib
    tx("2026-09-20", "out",  150000, "Tagihan"),     # wajib
], TMP)

# Oktober (bulan yang dianalisa)
db.save_transactions([
    tx("2026-10-05", "in",  8000000, "Gaji", "income"),
    tx("2026-10-10", "out",  600000, "Makan"),        # naik 50%
    tx("2026-10-15", "out",  250000, "Transport"),    # naik, tapi WAJIB
    tx("2026-10-20", "out",  300000, "Tagihan"),      # naik, tapi WAJIB
    tx("2026-10-22", "out",  100000, "Hiburan"),      # kategori baru, tanpa pembanding
    tx("2026-10-25", "out",  500000, "Tagihan", "debt_payment", "bayar utang"),
    tx("2026-10-26", "out",  200000, "Tagihan", "receivable", "talangan project"),
], TMP)

print("\n1. Ringkasan bulan")
r = db.ringkasan_bulan("2026-10", TMP)
cek("ada data", r["ada_data"], True)
cek("jumlah transaksi", r["tx_count"], 7)
cek("masuk", r["masuk"], 8000000)
cek("keluar semua", r["keluar_semua"], 600000 + 250000 + 300000 + 100000 + 500000 + 200000)
cek("konsumsi (hanya expense)", r["konsumsi"], 600000 + 250000 + 300000 + 100000)
cek("pelunasan utang", r["pelunasan_utang"], 500000)
cek("talangan piutang", r["talangan_piutang"], 200000)
cek("sisa kas", r["sisa_kas"], 8000000 - 1950000)
cek("sisa bebas", r["sisa_bebas"], 8000000 - 1250000)

print("\n2. Sisa bebas HARUS lebih besar dari sisa kas — ini yang mencegah sesat")
cek("sisa_bebas > sisa_kas", r["sisa_bebas"] > r["sisa_kas"], True)

print("\n3. Rincian kategori + pembanding bulan lalu")
kat = {k["category"]: k for k in r["kategori"]}
cek("Makan ada", "Makan" in kat, True)
cek("Makan total", kat["Makan"]["total"], 600000)
cek("Makan bulan lalu", kat["Makan"]["total_bulan_lalu"], 400000)
cek("Makan naik (%)", kat["Makan"]["perubahan_persen"], 50)
cek("Makan wajib?", kat["Makan"]["wajib"], False)
cek("Transport wajib?", kat["Transport"]["wajib"], True)
cek("Tagihan wajib?", kat["Tagihan"]["wajib"], True)
cek("konsumsi TIDAK menghitung utang/talangan", kat["Tagihan"]["total"],
    300000)  # hanya expense, bukan 500k+200k

print("\n4. Saran hemat — kategori wajib tidak disarankan dipotong")
s = db.saran_hemat("2026-10", TMP)
per = {k["kategori"]: k for k in s["kategori"]}
cek("ada pembanding", s["ada_pembanding"], True)
cek("Makan jenis 'naik'", per["Makan"]["jenis"], "naik")
cek("Makan potensi hemat = selisih", per["Makan"]["potensi_hemat"], 200000)
cek("Transport ditandai wajib", per["Transport"]["wajib"], True)
cek("Transport TIDAK disarankan potong", per["Transport"]["potensi_hemat"], None)
cek("Tagihan TIDAK disarankan potong", per["Tagihan"]["potensi_hemat"], None)
cek("Hiburan tanpa pembanding", per["Hiburan"]["jenis"], "tanpa_pembanding")
cek("Hiburan potensi hemat None (bukan 0)", per["Hiburan"]["potensi_hemat"], None)
cek("total potensi hemat", s["total_potensi_hemat"], 200000)

print("\n5. Aturan bulan: hanya bulan yang SUDAH SELESAI")
hari_ini = db.bulan_berjalan(TMP)
cek("bulan berjalan tidak boleh dianalisa", db.bulan_sudah_selesai(hari_ini, TMP), False)
cek("bulan depan tidak boleh dianalisa", db.bulan_sudah_selesai("2099-01", TMP), False)
cek("bulan lalu boleh", db.bulan_sudah_selesai("2026-09", TMP), True)
cek("nama bulan", db.nama_bulan("2026-10"), "Oktober 2026")

print("\n6. PENYARINGAN ANGKA AI — ini inti berkas ini")
fakta = ma._ringkas_untuk_model(db.analisa_lengkap("2026-10", TMP))
sah = ma._fakta_angka(fakta)
print("     angka sah yang dikenali: %d" % len(sah))

# CATATAN: nilai yang "ada di fakta" MEMANG boleh disebut — itu bukan karangan.
# Yang diuji di sini adalah angka yang TIDAK ada di fakta.
kasus = [
    ("Makan naik dari Rp 400.000 ke Rp 600.000",
     True,  "kedua angka ADA di fakta (bulan lalu & bulan ini)"),
    ("Total pengeluaran Rp 600.000 untuk Makan",
     True,  "600.000 ADA di fakta"),
    ("Tidak ada pembanding bulan lalu",
     True,  "tanpa angka"),
    ("Kamu bisa menghemat Rp 9.000.000",
     False, "9.000.000 tidak ada di fakta"),
    ("Kalau kamu menabung Rp 123.456",
     False, "123.456 tidak ada di fakta"),
    ("Pengeluaranmu Rp 3.200.000",
     False, "3.200.000 tidak ada di fakta"),
    # Persentase DILARANG, walaupun angkanya kebetulan ada di data.
    ("Pengeluaranmu naik 50%",
     False, "persentase tidak bisa diverifikasi"),
    ("Turun 30% dari bulan lalu",
     False, "angka 30 tidak ada di fakta"),
    ("Turun 4 persen dari bulan lalu",
     False, "menyebut 'persen'"),
]
for kalimat, harus_aman, alasan in kasus:
    aman = ma._kalimat_aman(kalimat, sah, fakta)
    ok = aman == harus_aman
    print(("  OK   " if ok else "  GAGAL") + " %-42s aman=%-5s (%s)"
          % (kalimat[:42], aman, alasan))
    if not ok:
        gagal.append("penyaringan: %r dapat %s harusnya %s" % (kalimat, aman, harus_aman))

print("\n6b. Angka kecil TIDAK dianggap angka keuangan")
for teks, harus_kosong in [("turun 30%", True), ("7 transaksi", True),
                           ("naik 50 persen", True), ("Rp 600.000", False)]:
    d = ma._angka_dalam(teks)
    ok = (len(d) == 0) == harus_kosong
    print(("  OK   " if ok else "  GAGAL") + " %-24s -> %s" % (teks, sorted(d)))
    if not ok:
        gagal.append("angka kecil: %r -> %s" % (teks, sorted(d)))

print("\n7. Narasi karangan harus DIBUANG, tapi kategori tetap terisi")
# Tiru hasil model yang menyelundupkan angka karangan DAN persen.
asli_panggil = ma._panggil_model
ma._panggil_model = lambda f: {
    "ringkasan": "Bulan ini kamu menghemat Rp 123.456 dari bulan lalu.",   # KARANGAN
    "per_kategori": {
        "Makan": "Makan naik 50 persen dari Rp 400.000 ke Rp 600.000.",    # persen -> dipotong
        "Hiburan": "Kamu menghabiskan Rp 777.777 di sini.",                # KARANGAN
    },
    "penutup": "Sisa bebasmu Rp 6750000.",                                 # sah, tanpa format
}
hasil = ma.buat_narasi(db.analisa_lengkap("2026-10", TMP))
ma._panggil_model = asli_panggil

cek("ringkasan karangan dibuang", hasil["ringkasan"], None)
cek("kategori persen DIPOTONG, bukan dibuang",
    "Makan" in hasil["per_kategori"], True)
cek("persen hilang dari kalimat Makan",
    "persen" in (hasil["per_kategori"].get("Makan") or "").lower(), False)
cek("angka Makan tetap ada",
    "400.000" in (hasil["per_kategori"].get("Makan") or ""), True)
cek("kategori karangan pakai kalimat bawaan (tidak kosong)",
    "Hiburan" in hasil["per_kategori"], True)
cek("kategori karangan masuk daftar diganti",
    "Hiburan" in hasil["kategori_diganti"], True)
cek("penutup terformat jadi 'Rp 6.750.000'",
    "Rp 6.750.000" in (hasil["penutup"] or ""), True)
cek("ada catatan kenapa", bool(hasil["catatan"]), True)
print("     catatan   : %s" % hasil["catatan"])
print("     dipotong  : %d" % len(hasil["persen_dipotong"]))
print("     dibuang   : %d" % len(hasil["dibuang"]))
print("     diganti   : %s" % hasil["kategori_diganti"])

print("\n7b. Kalau MODEL MATI, semua kategori tetap terisi kalimat bawaan")
asli = ma._panggil_model
ma._panggil_model = lambda f: (_ for _ in ()).throw(RuntimeError("model mati"))
mati = ma.buat_narasi(db.analisa_lengkap("2026-10", TMP))
ma._panggil_model = asli
cek("per_kategori tetap terisi", len(mati["per_kategori"]) > 0, True)
cek("semua kategori terisi", all(v for v in mati["per_kategori"].values()), True)
cek("ada catatan model mati", "tidak bisa dihubungi" in (mati["catatan"] or ""), True)
print("     contoh kalimat bawaan: %s"
      % list(mati["per_kategori"].values())[0][:66])

print("\n8. Simpan & baca analisa")
hasil = db.simpan_analisa("2026-10", narasi={"ringkasan": "contoh"},
                          snapshot={"masuk": 8000000}, model="model-uji", path=TMP)
cek("tersimpan", hasil["ada_analisa"], True)
cek("bulan tersimpan", hasil["month"], "2026-10")
cek("narasi terbaca", hasil["narasi"]["ringkasan"], "contoh")
cek("model tercatat", hasil["model"], "model-uji")
cek("narasi belum basi", hasil["narasi_basi"], False)

print("\n9. Narasi ditandai BASI setelah data berubah")
# Tambah transaksi baru -> tx_terakhir lebih baru dari dibuat_pada
import time
time.sleep(1.1)
db.save_transactions([tx("2026-10-28", "out", 30000, "Makan", "expense", "tambahan")], TMP)
hasil2 = db.analisa_lengkap("2026-10", TMP)
cek("narasi ditandai basi", hasil2["narasi_basi"], True)
cek("angka tetap dihitung ulang (konsumsi naik)",
    hasil2["angka"]["konsumsi"], 1250000 + 30000)
cek("narasi lama tetap ada (tidak dihapus)", hasil2["narasi"]["ringkasan"], "contoh")

print("\n10. Hapus analisa")
cek("dihapus", db.hapus_analisa("2026-10", TMP), True)
hasil3 = db.analisa_lengkap("2026-10", TMP)
cek("ada_analisa jadi False", hasil3["ada_analisa"], False)
cek("angka tetap ada (tidak ikut terhapus)", hasil3["angka"]["ada_data"], True)
cek("hapus lagi ditolak", db.hapus_analisa("2026-10", TMP), False)

print("\n11. Bulan tanpa data")
kosong = db.analisa_lengkap("2026-01", TMP)
cek("ada_data False", kosong["angka"]["ada_data"], False)
cek("boleh dianalisa (bulan lampau)", kosong["boleh_dianalisa"], True)
cek("saran kosong", len(kosong["saran"]["kategori"]), 0)

print("\n" + "─" * 74)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
