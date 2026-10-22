#!/usr/bin/env python3
"""Uji SAMBUNGAN `POST /api/analysis` — dari handler sampai baris tersimpan.

Kenapa berkas ini ada, terpisah dari test_analysis.py:
test_analysis.py menguji `db.analisa_lengkap()` dan `buat_narasi()` secara
TERPISAH, dan keduanya lulus. Yang gagal adalah **sambungannya**: di
`api_analysis_create`, setelah narasi berhasil dibuat, baris terakhir memakai
`model_config` yang tidak diimpor -> NameError.

Akibatnya mahal dan senyap: model sudah dipanggil (3-7 detik + kuota terpakai),
narasinya sudah jadi, lalu dibuang. Yang lebih buruk, exception keluar sebelum
`_send()` sehingga koneksi ditutup tanpa balasan HTTP — dari UI terlihat seperti
server mati.

Ditemukan yuki, 3 Okt 2026. Berkas uji ini menutup celah itu.

Jalankan:  python3 tests/test_analysis_handler.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import db                # noqa: E402
import monthly_analysis as ma   # noqa: E402
import server            # noqa: E402

gagal = []


def cek(nama, dapat, harap):
    ok = dapat == harap
    print(("  OK   " if ok else "  GAGAL") + " %-52s %s" % (nama, dapat))
    if not ok:
        gagal.append("%s: dapat %r harusnya %r" % (nama, dapat, harap))


def cek_benar(nama, kondisi):
    print(("  OK   " if kondisi else "  GAGAL") + " %s" % nama)
    if not kondisi:
        gagal.append(nama)


# ── Data uji: dua bulan, supaya ada pembanding ───────────────────────────────
TMP = Path(tempfile.mkdtemp()) / "handler.db"
db.init_db(TMP)
with db.connect(TMP) as conn:
    conn.execute("INSERT INTO accounts (name, kind) VALUES ('BRI','bank')")
BRI = db.account_balances(include_inactive=True, path=TMP)[0]["id"]


def tx(tgl, arah, jumlah, kategori, flow="expense"):
    return {"occurred_on": tgl, "direction": arah, "amount": jumlah,
            "account_id": BRI, "category": kategori, "note": "uji", "flow_type": flow}


db.save_transactions([
    tx("2026-09-01", "in", 8000000, "Gaji", "income"),
    tx("2026-09-10", "out", 400000, "Makan"),
], TMP)
db.save_transactions([
    tx("2026-10-01", "in", 8000000, "Gaji", "income"),
    tx("2026-10-10", "out", 600000, "Makan"),
    tx("2026-10-15", "out", 250000, "Transport"),
], TMP)

# Semua panggilan handler diarahkan ke database uji, dan "bulan berjalan"
# dibuat November supaya Oktober boleh dianalisa.
#
# PENTING: mengganti `db.DB_PATH` SAJA TIDAK CUKUP. Argumen default
# (`path=DB_PATH`) diikat saat fungsi DIDEFINISIKAN, bukan saat dipanggil —
# jadi `simpan_analisa(month, ...)` tetap menulis ke database asli. Itu
# kesalahan yang sudah terjadi sekali di berkas ini: satu baris uji sempat
# masuk ke database Deny dan harus dihapus manual.
#
# Cara yang benar: ganti DB_PATH **dan** panggil handler dengan path eksplisit
# lewat pembungkus di bawah.
_asli_db_path = db.DB_PATH
_asli_bulan = db.bulan_berjalan
db.DB_PATH = TMP
db.bulan_berjalan = lambda path=None: "2026-11"


def buat_analisa(month):
    """Panggil handler dengan SEMUA fungsi db yang menerima path diarahkan ke uji.

    Membungkus di sini, bukan mengganti DB_PATH diam-diam, supaya kalau ada
    fungsi db baru yang lupa diarahkan, kegagalannya terlihat (uji gagal),
    bukan menulis ke database Deny tanpa ada yang tahu.
    """
    asli = {}
    for nama in ("analisa_lengkap", "simpan_analisa", "hapus_analisa",
                 "bulan_sudah_selesai", "nama_bulan"):
        if hasattr(db, nama):
            asli[nama] = getattr(db, nama)
    try:
        db.analisa_lengkap = lambda m, path=None: asli["analisa_lengkap"](m, TMP)
        db.simpan_analisa = (lambda m, **kw:
                             asli["simpan_analisa"](m, path=TMP, **kw))
        db.bulan_sudah_selesai = (lambda m, path=None:
                                  asli["bulan_sudah_selesai"](m, TMP))
        return server.api_analysis_create({"month": month})
    finally:
        for nama, fn in asli.items():
            setattr(db, nama, fn)

# Mock model: TIDAK memanggil provider sungguhan (lambat + biaya), tapi
# mengembalikan bentuk yang sama seperti aslinya.
_asli_narasi = ma.buat_narasi


def narasi_palsu(analisa):
    return {
        "ringkasan": "Ringkasan uji untuk %s." % analisa["nama_bulan"],
        "per_kategori": {k["kategori"]: "Catatan %s." % k["kategori"]
                         for k in analisa["saran"]["kategori"]},
        "penutup": "Penutup uji.",
        "catatan": None,
        "dibuang": [], "persen_dipotong": [], "kategori_diganti": [],
    }


ma.buat_narasi = narasi_palsu

try:
    print("\n1. POST /api/analysis untuk bulan yang SUDAH SELESAI — harus berhasil")
    # Inilah panggilan yang gagal dengan NameError sebelum diperbaiki.
    hasil = buat_analisa("2026-10")
    cek("ok", hasil.get("ok"), True)
    cek_benar("tidak ada error '%s'" % hasil.get("error"),
              hasil.get("error") is None)
    print("     error: %s" % hasil.get("error"))
    print("     message: %s" % hasil.get("message"))

    print("\n2. Baris benar-benar TERSIMPAN di tabel analyses")
    cek("ada_analisa", hasil.get("ada_analisa"), True)
    cek("bulan", hasil.get("month"), "2026-10")
    with db.connect(TMP) as conn:
        n = conn.execute("SELECT COUNT(*) c FROM analyses").fetchone()["c"]
    cek("jumlah baris di tabel analyses", n, 1)

    print("\n3. Model dicatat — bukti baris 346 dijalankan")
    # Sebelum perbaikan, baris ini tidak pernah tercapai. Sekarang harus terisi.
    cek("model tercatat", hasil.get("model"), ma.MODEL)

    print("\n4. Narasi tersimpan dan bisa dibaca lagi")
    cek("ringkasan ada", bool(hasil["narasi"]["ringkasan"]), True)
    cek_benar("per_kategori terisi",
              len(hasil["narasi"]["per_kategori"]) == 2)
    lagi = db.analisa_lengkap("2026-10", TMP)
    cek("terbaca dari query terpisah",
        lagi["narasi"]["ringkasan"], hasil["narasi"]["ringkasan"])

    print("\n5. Penjaga bulan berjalan tetap bekerja")
    d = buat_analisa("2026-11")
    cek("ok", d.get("ok"), False)
    cek("error", d.get("error"), "bulan_belum_selesai")

    print("\n6. Penjaga bulan tanpa data tetap bekerja")
    d = buat_analisa("2026-05")
    cek("error", d.get("error"), "tidak_ada_data")

    print("\n7. Format bulan tidak sah")
    d = buat_analisa("Oktober")
    cek("error", d.get("error"), "bulan_tidak_sah")

    print("\n8. Gagal di tengah: handler melempar, `_jalankan` yang menangkap")
    # `api_analysis_create` SENGAJA tidak menangkap exception dari model —
    # itu tugas `_jalankan` di lapisan HTTP. Diuji dalam dua langkah:
    # (a) exception memang keluar dari handler, (b) `_jalankan` mengubahnya.
    ma.buat_narasi = lambda a: (_ for _ in ()).throw(RuntimeError("model meledak"))
    keluar = False
    try:
        buat_analisa("2026-10")
    except RuntimeError as e:
        keluar = "model meledak" in str(e)
    cek("exception keluar dari handler (bukan ditelan)", keluar, True)
    ma.buat_narasi = narasi_palsu

    print("\n9. `_jalankan` mengubah exception jadi balasan JSON yang bisa dibaca")
    class Palsu(server.Handler):
        def __init__(self):
            pass

    h = Palsu()
    hasil_j = h._jalankan(lambda: (_ for _ in ()).throw(RuntimeError("uji ledakan")))
    cek("ok", hasil_j.get("ok"), False)
    cek("error", hasil_j.get("error"), "gagal_server")
    cek_benar("message menyebut jenis exception",
              "RuntimeError" in (hasil_j.get("message") or ""))
    cek_benar("message menyebut penyebabnya",
              "uji ledakan" in (hasil_j.get("message") or ""))
    print("     message: %s" % hasil_j.get("message"))

    print("\n9b. Database ASLI tidak tersentuh oleh uji ini")
    # Ambil lokasi asli SEBELUM db.DB_PATH diganti (lihat #9b di bawah).
    #
    # Catatan kenapa `db.DB_PATH` tidak bisa dipakai di sini: ujinya sendiri
    # menimpanya dengan TMP di bagian awal, jadi memeriksa `db.DB_PATH` sama
    # dengan memeriksa database UJI — dan pasti terisi. Pemeriksaan yang salah
    # sasaran lebih buruk daripada tidak ada: ia lulus/gagal karena alasan yang
    # tidak berhubungan dengan yang mau dijaga.
    import os
    data_dir = Path(os.environ.get("FINANCE_DATA")
                    or (Path(__file__).resolve().parent.parent.parent
                        / "Data" / "finance"))
    asli = data_dir / "finance.db"
    if not asli.exists():
        print("  LEWATI  database Deny tidak ada di %s" % asli)
    else:
        with db.connect(asli) as conn:
            n_asli = conn.execute(
                "SELECT COUNT(*) c FROM analyses").fetchone()["c"]
        cek("tidak ada baris uji di database Deny", n_asli, 0)
        if n_asli:
            print("     (uji ini MENULIS ke database Deny — periksa sekarang)")

    print("\n10. `_jalankan` meneruskan hasil normal apa adanya")
    hasil_n = h._jalankan(lambda x: {"ok": True, "nilai": x}, 42)
    cek("hasil diteruskan", hasil_n, {"ok": True, "nilai": 42})

finally:
    ma.buat_narasi = _asli_narasi
    db.bulan_berjalan = _asli_bulan
    db.DB_PATH = _asli_db_path

print("\n" + "─" * 78)
if gagal:
    print("HASIL: %d UJI GAGAL" % len(gagal))
    for g in gagal:
        print("  -", g)
    sys.exit(1)
print("HASIL: semua uji lulus")
