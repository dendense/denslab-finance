#!/usr/bin/env python3
"""Server lokal finance — panel + chat.

Jalankan:  python3 src/server.py            (lalu buka http://localhost:8765)
           python3 src/server.py --port 8791

Struktur: kode di src/, data di folder terpisah (FINANCE_DATA), panel di web/. Path dihitung dari letak
berkas ini, jadi perintah di atas bisa dijalankan dari folder mana pun.

Ini HANYA jalan di Mac ini. Tidak bisa diakses dari HP — konsekuensi keputusan
"lokal murni". Kalau suatu saat Deny mau akses mobile, ini harus pindah ke hosting.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))
import db        # noqa: E402
import auth      # noqa: E402
import model_config  # noqa: E402

STATIC = ROOT_DIR / "web"

# Berkas yang boleh dibuka TANPA login. Selain ini, semua butuh sesi sah.
# Sengaja sesempit mungkin: hanya halaman login dan gaya/ikonnya.
PUBLIK = {"/login", "/login.html", "/masuk"}


def _cookie_sesi(token):
    """Cookie sesi: httpOnly (JavaScript tidak bisa membacanya), SameSite=Lax.

    Tanpa Max-Age: ini cookie SESI browser — hilang saat browser ditutup.
    Umur sebenarnya ditentukan oleh server (token di memori), bukan cookie.
    """
    return "sesi=%s; Path=/; HttpOnly; SameSite=Lax" % token


def api_summary(params):
    month = (params.get("month") or [None])[0]
    ms = db.monthly_summary(month)
    nw = db.net_worth()
    return {
        "month": ms["month"],
        "ada_data": ms["_ada_data"],
        "tx_count": ms["tx_count"],
        "net_worth": {
            "total": nw["net_worth"],
            "liquid": nw["liquid"],
            "non_liquid": nw["non_liquid"],
            "account_count": nw["account_count"],
            # account_count_all & balance_inactive WAJIB ikut. Ui memakainya
            # untuk memberi tahu Deny kalau ada uang di akun yang dinonaktifkan.
            # Tanpa ini, `total` naik tanpa akun yang menjelaskan dari mana —
            # persis kebingungan yang ingin dicegah oleh perbaikan v_net_worth.
            "account_count_all": nw["account_count_all"],
            "balance_inactive": nw["balance_inactive"],
        },
        "flow": {
            "total_in": ms["total_in"],
            "total_out": ms["total_out"],
            "expense_real": ms["expense_real"],
            "receivable_out": ms["receivable_out"],
            "debt_payment_out": ms["debt_payment_out"],
            "net": ms["net"],
            "net_real": ms["net_real"],
        },
        "accounts": [
            {"id": a["id"], "name": a["name"], "kind": a["kind"],
             "balance": a["balance"], "is_active": a["is_active"]}
            for a in db.account_balances()
        ],
    }


def api_transactions(params):
    month = (params.get("month") or [None])[0]
    direction = (params.get("direction") or [None])[0]
    limit_raw = (params.get("limit") or [None])[0]
    limit = int(limit_raw) if limit_raw else None
    rows = db.list_transactions(month=month, limit=limit, direction=direction)
    return {"month": month, "count": len(rows), "items": rows}


def api_transaction_patch(tx_id, body):
    """Ubah sebagian field transaksi.

    `direction` ditolak — arah mengikuti `flow_type`, karena FLOW_DIRECTION di
    db.py yang jadi satu-satunya penentu pasangan arah/sifat. Kalau arah bisa
    diubah sendiri, akan ada baris dengan flow_type='income' tapi
    direction='out' dan tidak ada yang tahu.
    """
    if not body:
        return {"ok": False, "error": "tidak_ada_perubahan",
                "message": "Tidak ada field yang dikirim."}
    if "direction" in body:
        return {"ok": False, "error": "field_terkunci",
                "message": "Kolom 'direction' tidak bisa diubah langsung — "
                           "ubah 'flow_type', arahnya mengikuti."}
    try:
        hasil = db.update_transaction(tx_id, body)
    except ValueError as e:
        pesan = str(e)
        if "tidak ada transaksi" in pesan:
            kode = "transaksi_tidak_ada"
        elif "flow_type" in pesan and "dikenal" in pesan:
            kode = "pasangan_tidak_sah"
        elif "kategori" in pesan:
            kode = "kategori_tidak_dikenal"
        elif "nominal" in pesan:
            kode = "amount_bukan_angka"
        elif "akun" in pesan:
            kode = "akun_tidak_ditemukan"
        elif "terkunci" in pesan:
            kode = "field_terkunci"
        else:
            kode = "gagal_ubah"
        return {"ok": False, "error": kode, "message": pesan}
    # Sertakan `source` supaya UI bisa menandai transaksi impor.
    hasil.setdefault("source", "manual")
    return {"ok": True, **hasil}


def api_transaction_delete(tx_id):
    """Hapus transaksi. KERAS, tapi barisnya lebih dulu dicatat ke berkas
    pemulihan `finance-pribadi/terhapus.log` — data keuangan tidak bisa dikembalikan,
    jadi jejaknya harus ada sebelum barisnya dibuang."""
    try:
        hasil = db.delete_transaction(tx_id)
    except ValueError as e:
        return {"ok": False, "error": "transaksi_tidak_ada", "message": str(e)}
    return {"ok": True, "id": tx_id, "dihapus": True,
            "pemulihan": "finance-pribadi/terhapus.log", "transaksi": hasil}


def api_parse(body):
    """Parse kalimat jadi draft. TIDAK menyimpan apa pun.

    Logika di parser_wrap.py; di sini cuma memanggil dan menyerahkan hasilnya.
    """
    import parser_wrap
    return parser_wrap.parse_kontrak(body.get("text"))


def api_save(body):
    """Simpan draft yang sudah dikonfirmasi Deny. Semua-atau-tidak-sama-sekali."""
    items = body.get("transactions") or []
    if not items:
        return {"ok": False, "error": "kosong", "message": "Tidak ada yang disimpan."}
    wajib = ("occurred_on", "direction", "amount")
    for i, it in enumerate(items, 1):
        for f in wajib:
            if not it.get(f):
                return {"ok": False, "error": "field_kurang",
                        "message": "Transaksi ke-%d tidak punya '%s'." % (i, f)}
    try:
        ids = db.save_transactions(items)
    except Exception as e:
        return {"ok": False, "error": "gagal_simpan", "message": str(e)}

    # Transaksi SUDAH pasti tersimpan (save_transactions all-or-nothing).
    # Cocokkan nominal ke jadwal hutang & tandai cicilan yang cocok LUNAS.
    # Dibungkus try/except: kegagalan APA PUN di sini TIDAK boleh merusak
    # penyimpanan transaksi — transaksi tetap tersimpan, fitur ini hanya bonus.
    lunas_baru = []
    try:
        lunas_baru = _tandai_lunas_untuk(items, ids)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("[hutang-lunas] penandaan otomatis dilewati: %s: %s"
              % (type(e).__name__, e), flush=True)

    hasil = {"ok": True, "saved_ids": ids, "count": len(ids)}
    if lunas_baru:
        hasil["hutang_lunas"] = lunas_baru
    return hasil


def api_categories(params):
    """Daftar kategori untuk chip di UI. Dipisah per arah."""
    direction = (params.get("direction") or [None])[0]
    items = db.get_categories(direction)
    return {"count": len(items), "items": items}


def api_accounts(params):
    """Daftar akun + saldo. Dipakai UI untuk chip akun di kartu draft.

    `balance` ikut dikirim supaya UI bisa memilih akun yang masuk akal tanpa
    menebak, dan supaya Deny melihat akibatnya sebelum menyimpan.
    """
    include_inactive = (params.get("all") or ["0"])[0] in ("1", "true", "ya")
    items = db.account_balances(include_inactive=include_inactive)
    return {"count": len(items), "items": items}


# ── tulis akun ───────────────────────────────────────────────────────────────
KIND_SAH = ("bank", "cash", "ewallet", "savings", "investment")


def api_account_create(body):
    """Tambah akun baru.

    `opening_balance` HANYA boleh diisi di sini — setelah akun dibuat, angkanya
    terkunci. Alasannya: v_account_balances dihitung dari opening_balance +
    semua transaksi, jadi mengubahnya setelah ada transaksi akan menggeser
    SEMUA saldo lama, termasuk bulan yang laporannya sudah ditunjukkan ke Deny.
    """
    name = (body.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "nama_kosong",
                "message": "Nama akun tidak boleh kosong."}

    kind = (body.get("kind") or "").strip().lower()
    if kind not in KIND_SAH:
        return {"ok": False, "error": "jenis_tidak_dikenal",
                "message": "Jenis '%s' tidak dikenal. Pilihan: %s."
                           % (kind or "-", ", ".join(KIND_SAH))}

    saldo = body.get("opening_balance", 0)
    if isinstance(saldo, bool) or not isinstance(saldo, (int, float, str)):
        return {"ok": False, "error": "saldo_awal_bukan_angka",
                "message": "Saldo awal harus angka bulat rupiah."}
    try:
        saldo = int(round(float(saldo)))
    except (TypeError, ValueError):
        return {"ok": False, "error": "saldo_awal_bukan_angka",
                "message": "Saldo awal harus angka bulat rupiah."}

    try:
        hasil = db.create_account(name, kind, saldo)
    except ValueError as e:
        pesan = str(e)
        kode = "nama_sudah_ada" if "sudah ada" in pesan.lower() else "gagal_simpan"
        return {"ok": False, "error": kode, "message": pesan}
    return {"ok": True, **hasil}


def api_account_patch(account_id, body):
    """Ubah nama atau aktif/nonaktifkan akun.

    `kind` dan `opening_balance` SENGAJA ditolak — keduanya mengubah angka di
    v_net_worth tanpa satu pun transaksi, dan perubahan seperti itu harus lewat
    migrasi yang tercatat, bukan satu tap di UI.
    """
    terkunci = []
    if "kind" in body:
        terkunci.append("kind")
    if "opening_balance" in body:
        terkunci.append("opening_balance")
    if terkunci:
        return {"ok": False, "error": "field_terkunci",
                "message": ("Kolom %s tidak bisa diubah setelah akun dibuat — "
                            "keduanya mengubah angka kekayaan tanpa transaksi. "
                            "Perbaikannya lewat migrasi yang tercatat."
                            % " dan ".join("'%s'" % f for f in terkunci))}

    name = body.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            return {"ok": False, "error": "nama_kosong",
                    "message": "Nama akun tidak boleh kosong."}

    is_active = body.get("is_active")
    if is_active is not None:
        is_active = 1 if is_active in (1, True, "1", "true", "ya") else 0

    if name is None and is_active is None:
        return {"ok": False, "error": "tidak_ada_perubahan",
                "message": "Tidak ada field yang bisa diubah. Kirim 'name' atau 'is_active'."}

    try:
        hasil = db.update_account(account_id, name=name, is_active=is_active)
    except ValueError as e:
        pesan = str(e)
        kode = "akun_tidak_ada" if "tidak ada akun" in pesan.lower() else (
            "nama_sudah_ada" if "sudah ada" in pesan.lower() else "gagal_simpan")
        return {"ok": False, "error": kode, "message": pesan}
    return {"ok": True, **hasil}


def api_trend(params):
    """Tren N bulan untuk grafik. Satu panggilan, bukan enam."""
    try:
        months = int((params.get("months") or ["6"])[0])
    except ValueError:
        months = 6
    months = max(1, min(months, 24))
    return db.monthly_trend(months)


def api_categories_spending(params):
    """Pengeluaran per kategori (hanya `expense`, bukan utang/talangan)."""
    month = (params.get("month") or [None])[0]
    direction = (params.get("direction") or ["out"])[0]
    return db.spending_by_category(month, direction)


def api_suggestions(params):
    """Saran hemat. Setiap saran WAJIB membawa asumsinya."""
    month = (params.get("month") or [None])[0]
    return db.saving_suggestions(month)


# ── analisa bulanan ──────────────────────────────────────────────────────────
def api_analysis(params):
    """Analisa satu bulan: angka (selalu dihitung ulang) + narasi tersimpan.

    Tanpa `?month=`, dipakai bulan lalu — karena analisa dibuat untuk bulan
    yang sudah selesai.
    """
    month = (params.get("month") or [None])[0]
    if not month:
        month = db._bulan_sebelum(db.bulan_berjalan())
    return db.analisa_lengkap(month)


def api_analysis_create(body):
    """Buat/segarkan narasi analisa. Angkanya tetap dihitung ulang.

    Hanya boleh untuk bulan yang SUDAH SELESAI. Menganalisa bulan berjalan
    menghasilkan kesimpulan yang bisa terbalik keesokan harinya.
    """
    month = (body.get("month") or "").strip()
    if not month:
        return {"ok": False, "error": "bulan_kosong",
                "message": "Sebutkan bulan yang mau dianalisa, format YYYY-MM."}
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return {"ok": False, "error": "bulan_tidak_sah",
                "message": "Format bulan harus YYYY-MM, contoh: 2026-10."}
    if not db.bulan_sudah_selesai(month):
        return {"ok": False, "error": "bulan_belum_selesai",
                "message": ("Bulan %s belum selesai, jadi belum bisa dianalisa. "
                            "Angkanya masih bisa berubah."
                            % db.nama_bulan(month))}

    analisa = db.analisa_lengkap(month)
    if not analisa["angka"]["ada_data"]:
        return {"ok": False, "error": "tidak_ada_data",
                "message": "Tidak ada transaksi di %s, tidak ada yang bisa dianalisa."
                           % db.nama_bulan(month)}

    import monthly_analysis
    narasi = monthly_analysis.buat_narasi(analisa)

    # Snapshot disimpan sebagai PEMBANDING saja. Yang ditampilkan ke Deny
    # selalu hasil hitung ulang, jadi koreksi transaksi tetap terbaca benar.
    snapshot = {
        "masuk": analisa["angka"]["masuk"],
        "keluar_semua": analisa["angka"]["keluar_semua"],
        "konsumsi": analisa["angka"]["konsumsi"],
        "sisa_bebas": analisa["angka"]["sisa_bebas"],
        "tx_count": analisa["angka"]["tx_count"],
    }
    hasil = db.simpan_analisa(
        month, narasi=narasi, snapshot=snapshot,
        model=None if narasi.get("catatan") else model_config.MODEL,
        catatan=narasi.get("catatan"))
    return {"ok": True, **hasil}


def api_analysis_delete(month):
    """Hapus narasi analisa satu bulan. Angkanya tetap ada (dihitung ulang)."""
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return {"ok": False, "error": "bulan_tidak_sah",
                "message": "Format bulan harus YYYY-MM."}
    dihapus = db.hapus_analisa(month)
    if not dihapus:
        return {"ok": False, "error": "tidak_ada_analisa",
                "message": "Belum ada analisa untuk bulan itu."}
    return {"ok": True, "month": month, "dihapus": True}


# ── target tabungan ──────────────────────────────────────────────────────────
def api_months(params):
    """Bulan yang punya transaksi + status analisanya. Untuk pemilih bulan."""
    return db.daftar_bulan()


def api_savings(params):
    """Target tabungan aktif + progresnya. Progres selalu dihitung ulang."""
    t = db.target_aktif()
    akun = db.account_balances(include_inactive=True)
    akun_savings = [a for a in akun if a["kind"] in ("savings", "investment")]
    return {
        "ada_target": t is not None,
        "target": t,
        # Dipakai UI kalau belum ada target: menawarkan akun mana yang masuk akal
        # dipakai untuk menabung, tanpa harus menebak dari daftar semua akun.
        "akun_bisa_dipakai": [
            {"id": a["id"], "name": a["name"], "kind": a["kind"],
             "balance": a["balance"]} for a in akun_savings],
        "catatan": "Progres dihitung dari SALDO AKUN target, bukan dari total "
                   "kekayaan. Uang yang disimpan di akun lain tidak ikut terhitung.",
    }


def api_savings_set(body):
    """Pasang atau ubah target tabungan."""
    name = (body.get("name") or "").strip()
    if not name:
        return {"ok": False, "error": "nama_kosong",
                "message": "Nama target tidak boleh kosong."}

    jumlah = body.get("target_amount")
    if jumlah is None:
        return {"ok": False, "error": "target_kosong",
                "message": "Target harus diisi, angka bulat rupiah."}

    try:
        hasil = db.set_target(
            name=name, target_amount=jumlah,
            account_id=body.get("account_id"),
            account_hint=body.get("account_hint"),
            target_date=body.get("target_date"))
    except ValueError as e:
        pesan = str(e)
        if "akun" in pesan:
            kode = "akun_tidak_ditemukan"
        elif "tanggal" in pesan:
            kode = "tanggal_tidak_sah"
        else:
            kode = "target_tidak_sah"
        return {"ok": False, "error": kode, "message": pesan}

    return {"ok": True, "target": hasil}


def api_savings_delete():
    """Arsipkan target aktif. Datanya tidak dihapus."""
    if not db.hapus_target():
        return {"ok": False, "error": "tidak_ada_target",
                "message": "Belum ada target tabungan yang aktif."}
    return {"ok": True, "diarsipkan": True}


# ── jadwal cicilan per utang (baca LIST-HUTANG.md, READ-ONLY) ────────────────
class _GagalHutang(Exception):
    """Kegagalan yang bisa dibaca UI: kode + pesan Bahasa Indonesia."""

    def __init__(self, kode, pesan):
        super().__init__(pesan)
        self.kode = kode
        self.pesan = pesan


# Bulan Indonesia -> angka. Memuat `Ags` (bentuk yang dipakai berkas) DAN
# `Agu` (singkatan app.js MONTH_SHORT) supaya berkas yang memakai salah satu
# tetap terbaca; bulan di luar daftar ini = error format, bukan ditebak Januari.
BULAN_ID = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "ags": 8, "agu": 8, "sep": 9, "okt": 10, "nov": 11, "des": 12,
}
BARIS_CICILAN = re.compile(
    r"^\s*(\d+)\.\s+(\d+)\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})\s*$")


# ── status LUNAS: berkas TERPISAH finance-pribadi/HUTANG-LUNAS.json ──────────
# Kenapa berkas terpisah: LIST-HUTANG.md adalah jadwal asli Deny dan TIDAK
# boleh disentuh (nol tulis). Status lunas adalah LAPISAN di atasnya, jadi
# disimpan di berkas sendiri. LIST-HUTANG.md tidak punya id utang, maka kunci
# unik = (nama_utang, jatuh_tempo) — tanggal = identitas alami cicilan.
#
# Skema: {"versi":1,"diperbarui":ISO,"lunas":[{nama_utang,jatuh_tempo,nomor,
#         nominal,ditandai_pada,transaksi_id,transaksi_nominal,
#         transaksi_tanggal}, ...]}
VERSI_LUNAS = 1


def _kunci_lunas(nama_utang, jatuh_tempo):
    """Kunci unik satu cicilan: (nama_utang, jatuh_tempo)."""
    return (nama_utang, jatuh_tempo)


def _berkas_lunas():
    return Path(str(db.DATA_DIR)) / "HUTANG-LUNAS.json"


def _baca_lunas():
    """Baca HUTANG-LUNAS.json. Kembalikan daftar entri `lunas` (list of dict).

    Belum ada berkas -> dianggap KOSONG (semua belum lunas) — BUKAN "semua
    lunas". Rusak / bentuk salah -> `_GagalHutang("hutang_lunas_rusak", ...)`
    supaya pemanggil gagal dengan pesan jelas, tidak menampilkan total salah.
    """
    berkas = _berkas_lunas()
    if not berkas.is_file():
        return []
    try:
        isi = berkas.read_text(encoding="utf-8")
    except OSError as e:
        raise _GagalHutang(
            "hutang_lunas_rusak",
            "Berkas status lunas tidak bisa dibaca (%s: %s). Perbaiki atau "
            "hapus berkas itu supaya jadwal bisa ditampilkan."
            % (type(e).__name__, e))
    if not isi.strip():
        # Berkas kosong = belum ada penandaan. Aman, bukan "semua lunas".
        return []
    try:
        data = json.loads(isi)
    except json.JSONDecodeError as e:
        raise _GagalHutang(
            "hutang_lunas_rusak",
            "Berkas status lunas rusak (JSON tidak valid: %s). Penandaan "
            "otomatis dilewati; perbaiki atau hapus berkas itu." % e)
    if not isinstance(data, dict) or not isinstance(data.get("lunas"), list):
        raise _GagalHutang(
            "hutang_lunas_rusak",
            "Berkas status lunas bentuknya tidak dikenal (harus punya kunci "
            "'lunas' berisi daftar). Penandaan otomatis dilewati.")
    entri = []
    for i, e in enumerate(data["lunas"], 1):
        if not isinstance(e, dict) or not e.get("nama_utang") \
                or not e.get("jatuh_tempo"):
            raise _GagalHutang(
                "hutang_lunas_rusak",
                "Berkas status lunas rusak: entri ke-%d tidak punya "
                "'nama_utang'/'jatuh_tempo'. Penandaan otomatis dilewati." % i)
        entri.append(e)
    return entri


def _tulis_lunas(entri):
    """Tulis HUTANG-LUNAS.json secara ATOMIK (*.tmp + os.replace).

    Atomik supaya berkas tidak pernah setengah tertulis kalau proses berhenti
    di tengah. Nol sentuh LIST-HUTANG.md / finance.db.
    """
    berkas = _berkas_lunas()
    berkas.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "versi": VERSI_LUNAS,
        "diperbarui": _sekarang_iso(),
        "lunas": entri,
    }
    sementara = berkas.with_suffix(berkas.suffix + ".tmp")
    sementara.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    os.replace(sementara, berkas)
    return data


def _sekarang_iso():
    from datetime import datetime as _dt
    return _dt.now().replace(microsecond=0).isoformat()


def _tandai_lunas_untuk(items, ids):
    """Cocokkan transaksi yang BARU disimpan ke cicilan; tandai yang cocok LUNAS.

    Aturan (keputusan Deny):
    - HANYA transaksi `flow_type='debt_payment'` yang memicu.
    - Nominal PERSIS (`amount` integer, toleransi NOL).
    - Kandidat = cicilan yang `nominal == amount` DAN belum lunas.
    - Pilih yang JATUH TEMPO paling awal (tie: nama_utang, lalu nomor).
    - Satu transaksi -> satu cicilan.
    - Tak ada cocok -> tidak terjadi apa-apa.
    - Sudah lunas sebelumnya -> bukan kandidat.

    Mengembalikan daftar penandaan baru: [{nama_utang,jatuh_tempo,nomor,
    nominal,transaksi_id,transaksi_nominal,transaksi_tanggal}, ...].

    Kalau HUTANG-LUNAS.json rusak -> `_GagalHutang` (pemanggil menangkapnya dan
    melewati penandaan; transaksi tetap tersimpan). Pemanggil WAJIB membungkus
    ini dengan try/except supaya kegagalan apa pun tidak merusak penyimpanan.
    """
    hasil = _baca_hutang()          # jadwal dari LIST-HUTANG.md (read-only)
    entri = _baca_lunas()           # status lunas yang sudah ada
    sudah = {_kunci_lunas(e["nama_utang"], e["jatuh_tempo"]) for e in entri}

    # Kandidat belum-lunas, urut jatuh tempo -> nama -> nomor.
    kandidat = []
    for u in hasil["utang"]:
        for r in u["baris"]:
            if _kunci_lunas(u["nama"], r["jatuh_tempo"]) in sudah:
                continue
            kandidat.append({
                "nama_utang": u["nama"],
                "jatuh_tempo": r["jatuh_tempo"],
                "nomor": r["nomor"],
                "nominal": r["nominal"],
            })
    kandidat.sort(key=lambda c: (c["jatuh_tempo"], c["nama_utang"], c["nomor"]))

    baru = []
    for it, tx_id in zip(items, ids):
        if (it.get("flow_type") or "") != "debt_payment":
            continue
        try:
            amount = int(it.get("amount"))
        except (TypeError, ValueError):
            continue
        # Cari kandidat pertama (paling awal) yang nominalnya persis & belum
        # dipakai di iterasi ini.
        terpakai = {_kunci_lunas(b["nama_utang"], b["jatuh_tempo"]) for b in baru}
        pilih = None
        for c in kandidat:
            k = _kunci_lunas(c["nama_utang"], c["jatuh_tempo"])
            if k in terpakai:
                continue
            if c["nominal"] == amount:
                pilih = c
                break
        if pilih is None:
            continue
        baru.append({
            "nama_utang": pilih["nama_utang"],
            "jatuh_tempo": pilih["jatuh_tempo"],
            "nomor": pilih["nomor"],
            "nominal": pilih["nominal"],
            "ditandai_pada": _sekarang_iso(),
            "transaksi_id": tx_id,
            "transaksi_nominal": amount,
            "transaksi_tanggal": it.get("occurred_on"),
        })

    if baru:
        _tulis_lunas(entri + baru)
    return baru


def api_debts_batalkan(body):
    """POST /api/debts/batalkan — batalkan (unmark) satu cicilan yang ditandai lunas.

    Body: {"nama_utang": <str>, "jatuh_tempo": <ISO 'YYYY-MM-DD'>}.
    Balasan sukses: {"ok": true, "dibatalkan": {...}}.
    Tak ada yang ditandai untuk kunci itu: {"ok": false, "error": "tidak_ditandai"}.
    Berkas rusak: {"ok": false, "error": "hutang_lunas_rusak", ...}.
    """
    nama_utang = (body.get("nama_utang") or "").strip()
    jatuh_tempo = (body.get("jatuh_tempo") or "").strip()
    if not nama_utang or not jatuh_tempo:
        return {"ok": False, "error": "field_kurang",
                "message": "Butuh 'nama_utang' dan 'jatuh_tempo'."}
    try:
        entri = _baca_lunas()
    except _GagalHutang as e:
        return {"ok": False, "error": e.kode, "message": e.pesan}

    kunci = _kunci_lunas(nama_utang, jatuh_tempo)
    sisa, dibatalkan = [], None
    for e in entri:
        if _kunci_lunas(e["nama_utang"], e["jatuh_tempo"]) == kunci:
            dibatalkan = e
        else:
            sisa.append(e)
    if dibatalkan is None:
        return {"ok": False, "error": "tidak_ditandai",
                "message": "Cicilan itu tidak sedang ditandai lunas."}
    _tulis_lunas(sisa)
    return {"ok": True, "dibatalkan": {
        "nama_utang": dibatalkan.get("nama_utang"),
        "jatuh_tempo": dibatalkan.get("jatuh_tempo"),
        "nomor": dibatalkan.get("nomor"),
        "nominal": dibatalkan.get("nominal"),
    }}


def _baca_hutang():
    """Baca LIST-HUTANG.md read-only, kembalikan jadwal cicilan terstruktur.

    SEMUA angka (total per utang, jumlah cicilan, total semua, cicilan
    berikutnya) dihitung DI SINI, bukan di UI — CONTRACT.md: UI tidak pernah
    menghitung angka keuangan. UI hanya memformat yang sudah jadi.

    Gagal KERAS dengan pesan jelas kalau berkas hilang atau formatnya berubah:
    halaman kosong tanpa keterangan persis yang dilarang kartu ini.

    Nol tulis ke berkas sumber, nol SQL, nol tabel baru.
    """
    from datetime import date as _date

    berkas = Path(str(db.DATA_DIR)) / "LIST-HUTANG.md"
    if not berkas.is_file():
        raise _GagalHutang(
            "berkas_tidak_ada",
            "Berkas jadwal hutang tidak ditemukan di %s. Tidak ada yang bisa "
            "ditampilkan." % berkas)
    try:
        isi = berkas.read_text(encoding="utf-8")
    except OSError as e:
        raise _GagalHutang(
            "berkas_tidak_terbaca",
            "Berkas jadwal hutang tidak bisa dibaca (%s: %s)."
            % (type(e).__name__, e))

    hari_ini = _date.today()
    utang = []
    bagian = None            # bagian yang sedang diisi
    ada_judul = False
    nomor_baris = 0

    for baris in isi.splitlines():
        nomor_baris += 1
        if baris.startswith("## "):
            nama = baris[3:].strip()
            if not nama:
                continue
            bagian = {"nama": nama, "baris": []}
            utang.append(bagian)
            ada_judul = True
            continue
        if baris.startswith("#"):
            continue          # judul berkas (satu '#')
        if not baris.strip():
            continue

        m = BARIS_CICILAN.match(baris)
        if not m:
            # Baris non-kosong di dalam bagian yang tidak cocok = format berubah.
            if bagian is not None:
                raise _GagalHutang(
                    "format_berubah",
                    "Baris %d tidak bisa dibaca sebagai cicilan "
                    "(contoh: '1. 1803272 11 Nov 2026'): %r"
                    % (nomor_baris, baris.strip()[:60]))
            continue

        if bagian is None:
            raise _GagalHutang(
                "format_berubah",
                "Baris %d berisi cicilan tapi belum ada judul '## <nama "
                "utang>' di atasnya." % nomor_baris)

        nomor, nominal, hari, bulan_teks, tahun = m.groups()
        bulan = BULAN_ID.get(bulan_teks.lower())
        if bulan is None:
            raise _GagalHutang(
                "format_berubah",
                "Baris %d: bulan '%s' tidak dikenal (harus Jan..Des / "
                "Ags / Okt)." % (nomor_baris, bulan_teks))
        try:
            jatuh = _date(int(tahun), bulan, int(hari))
        except ValueError as e:
            raise _GagalHutang(
                "format_berubah",
                "Baris %d: tanggal tidak sah (%s)." % (nomor_baris, e))

        bagian["baris"].append({
            "nomor": int(nomor),
            "nominal": int(nominal),
            "jatuh_tempo": jatuh.isoformat(),
            "jatuh_tempo_teks": "%d %s %d" % (int(hari), bulan_teks, int(tahun)),
            "_tanggal": jatuh,
        })

    if not ada_judul:
        raise _GagalHutang(
            "format_berubah",
            "Format LIST-HUTANG.md berubah: tidak ada satu pun judul "
            "'## <nama utang>'. Halaman tidak dibangun dari format yang tidak "
            "dikenal.")

    hasil = []
    total_semua = 0
    for b in utang:
        if not b["baris"]:
            raise _GagalHutang(
                "format_berubah",
                "Bagian '%s' tidak punya baris cicilan yang bisa dibaca."
                % b["nama"])
        baris_urut = sorted(b["baris"], key=lambda r: (r["_tanggal"], r["nomor"]))
        total = sum(r["nominal"] for r in baris_urut)
        total_semua += total
        hasil.append({
            "nama": b["nama"],
            "jumlah_cicilan": len(baris_urut),
            "total": total,
            "jatuh_tempo_terakhir": baris_urut[-1]["jatuh_tempo"],
            "baris": [{k: v for k, v in r.items() if k != "_tanggal"}
                      for r in baris_urut],
        })

    # ── campur status LUNAS (dari HUTANG-LUNAS.json, berkas TERPISAH) ────────
    # Dicampur DI SINI supaya UI hanya memformat (CONTRACT.md). Kalau berkas
    # lunas rusak, `_baca_lunas()` melempar `_GagalHutang` -> `api_debts()`
    # membalas error yang jelas, BUKAN total yang salah.
    entri_lunas = _baca_lunas()
    kunci_lunas = {_kunci_lunas(e["nama_utang"], e["jatuh_tempo"]): e
                   for e in entri_lunas}
    peta_cicilan = {}
    for u in hasil:
        for r in u["baris"]:
            peta_cicilan[_kunci_lunas(u["nama"], r["jatuh_tempo"])] = r
    # Entri "yatim": ditandai lunas tapi tidak ada lagi di jadwal (mis. Deny
    # menyunting LIST-HUTANG.md). Dilaporkan, TIDAK dihitung ke total mana pun.
    yatim = sorted(k for k in kunci_lunas if k not in peta_cicilan)

    hari_ini_teks = hari_ini.isoformat()
    total_lunas_semua = 0
    for u in hasil:
        jumlah_lunas = 0
        total_lunas = 0
        for r in u["baris"]:
            e = kunci_lunas.get(_kunci_lunas(u["nama"], r["jatuh_tempo"]))
            r["lunas"] = e is not None
            if e is not None:
                r["lunas_pada"] = e.get("ditandai_pada")
                r["lunas_transaksi_id"] = e.get("transaksi_id")
                jumlah_lunas += 1
                total_lunas += r["nominal"]
        u["jumlah_lunas"] = jumlah_lunas
        u["total_sisa"] = u["total"] - total_lunas
        total_lunas_semua += total_lunas
        # `cicilan_berikutnya` = cicilan BELUM LUNAS paling dekat (keputusan
        # Deny #2: "berikutnya" melewati yang sudah lunas). Nama & bentuk field
        # TIDAK berubah supaya UI yuki tidak perlu ikut berubah.
        berikutnya = None
        for r in u["baris"]:
            if r["lunas"]:
                continue
            if r["jatuh_tempo"] >= hari_ini_teks:
                berikutnya = {
                    "nomor": r["nomor"], "nominal": r["nominal"],
                    "jatuh_tempo": r["jatuh_tempo"],
                    "jatuh_tempo_teks": r["jatuh_tempo_teks"],
                }
                break
        u["cicilan_berikutnya"] = berikutnya

    return {
        "ok": True,
        "sumber": "finance-pribadi/LIST-HUTANG.md",
        "hari_ini": hari_ini_teks,
        "jumlah_utang": len(hasil),
        "total_semua": total_semua,
        "total_lunas_semua": total_lunas_semua,
        "total_sisa_semua": total_semua - total_lunas_semua,
        "yatim": yatim,
        "utang": hasil,
    }


def api_debts(params):
    """GET /api/debts — jadwal cicilan per utang dari LIST-HUTANG.md.

    Baca-saja: nol tulis ke berkas sumber, nol SQL, nol tabel baru. Semua
    agregat dihitung di server; UI hanya memformat. Kalau berkas hilang atau
    formatnya berubah, balas `{"ok": false, ...}` dengan pesan jelas supaya UI
    menampilkan keterangan, bukan layar kosong.
    """
    try:
        return _baca_hutang()
    except _GagalHutang as e:
        return {"ok": False, "error": e.kode, "message": e.pesan}


# ── autentikasi ──────────────────────────────────────────────────────────────
def api_ai_status(params):
    """Cek apakah AI untuk kolom catat bisa dipakai. Dipakai panel `#ai-host`.

    KENAPA endpoint ini ada: sebelumnya satu-satunya cara mengetahui AI hidup
    adalah dengan MENGIRIM kalimat ke model — dan itu membakar kuota Deny setiap
    kali halaman dimuat. Endpoint ini hanya mengirim satu pesan satu kata, dan
    dipanggil ketika Deny menekan "Periksa", bukan otomatis.

    Bentuk balasan mengikuti kontrak yang diminta yuki di
    requests/CATATAN-BELUM-SELESAI.md §5c:
        ok, model, endpoint, latensi_ms, pesan

    ATURAN: endpoint dan model dibaca dari server, TIDAK BISA diubah dari UI.
    Kunci API tidak pernah ikut terkirim ke browser — UI hanya perlu tahu
    "hidup atau tidak", bukan alamat atau kuncinya (CONTRACT.md §1).
    """
    import time
    import urllib.request
    import urllib.error

    model = model_config.MODEL
    endpoint = model_config.BASE

    key = os.environ.get("NINE_ROUTER_API_KEY", "").strip()
    if not key:
        # Jangan sebut nama variabel environment ke UI — itu bocoran yang tidak
        # perlu diketahui browser. Cukup katakan belum diatur.
        return {
            "ok": False, "model": model, "endpoint": endpoint,
            "latensi_ms": None, "keadaan": "gagal",
            "pesan": "Kunci API belum diatur di server. Minta pemiliknya "
                     "mengisinya pada berkas env, lalu jalankan ulang peluncurnya.",
        }

    body = json.dumps({
        "model": model,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "ok"}],
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})

    mulai = time.time()
    try:
        with urllib.request.urlopen(req, timeout=model_config.TIMEOUT) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        latensi = int((time.time() - mulai) * 1000)

        # Model yang menjawab bisa berbeda dari yang diminta (router mengalihkan
        # ke model cadangan). Laporkan yang BENAR-BENAR menjawab, bukan yang
        # kita minta — kalau tidak, panel akan menampilkan model yang salah.
        menjawab = d.get("model") or model

        # Ambang "lambat": 5 detik. Di bawah itu terasa biasa; di atasnya Deny
        # akan mengira panelnya menggantung.
        if latensi > 5000:
            keadaan, pesan = "lambat", "AI menjawab tapi lambat."
        else:
            keadaan, pesan = "ok", "AI siap dipakai."

        return {"ok": True, "model": menjawab, "endpoint": endpoint,
                "latensi_ms": latensi, "keadaan": keadaan, "pesan": pesan}

    except urllib.error.HTTPError as e:
        latensi = int((time.time() - mulai) * 1000)
        try:
            detail = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            detail = ""
        return {
            "ok": False, "model": model, "endpoint": endpoint,
            "latensi_ms": latensi, "keadaan": "gagal",
            "pesan": "AI tidak menjawab (HTTP %d). %s" % (e.code, detail.strip()),
        }
    except Exception as e:
        latensi = int((time.time() - mulai) * 1000)
        return {
            "ok": False, "model": model, "endpoint": endpoint,
            "latensi_ms": latensi, "keadaan": "gagal",
            "pesan": "AI tidak bisa dihubungi (%s)." % type(e).__name__,
        }


def api_auth_status(params):
    """Status login. Dipakai halaman login untuk tahu form mana yang ditampilkan.

    SENGAJA publik (tanpa sesi) — halaman login butuh ini SEBELUM ada sesi.
    Tanpa ini, halaman login tidak tahu password sudah ada atau belum, dan
    formnya salah: password yang diketik justru terpasang. Lihat `_butuh_login`
    di server.py.

    Yang dikirim HANYA ini:
      - `sudah_ada_password`: satu bit, tidak sensitif, dan memang dibutuhkan
      - `panjang_min_password`: supaya halaman login bisa memberi tahu batasnya
        tanpa menebak

    Yang TIDAK dikirim: jumlah sesi aktif (berapa orang sedang memakai panel),
    waktu sesi terakhir, atau apa pun tentang pemakaian. Informasi itu hanya
    berguna untuk yang sudah login.
    """
    return {
        "sudah_ada_password": auth.sudah_ada_password(),
        "panjang_min_password": auth.PANJANG_MIN_PASSWORD,
    }


def api_auth_status_lengkap(params):
    """Status lengkap — HANYA untuk yang sudah login."""
    return {
        "sudah_ada_password": auth.sudah_ada_password(),
        "jumlah_sesi": auth.jumlah_sesi(),
        "batas_diam_jam": auth.BATAS_DIAM_DETIK // 3600,
        "catatan": "Sesi hilang kalau server dimatikan — itu memang disengaja.",
    }


def api_auth_login(body):
    """Masuk dengan password, atau pasang password pertama kali.

    Belum ada password -> ini pemasangan pertama (setup).
    Sudah ada password -> ini login biasa.
    """
    password = body.get("password") or ""

    if not auth.sudah_ada_password():
        # Setup pertama: password dipasang, lalu sesi langsung dibuat.
        if len(password) < auth.PANJANG_MIN_PASSWORD:
            return {"ok": False, "error": "password_terlalu_pendek",
                    "message": "Password minimal %d karakter."
                               % auth.PANJANG_MIN_PASSWORD}
        konfirmasi = body.get("konfirmasi")
        if konfirmasi is not None and konfirmasi != password:
            return {"ok": False, "error": "konfirmasi_beda",
                    "message": "Dua password yang dimasukkan berbeda."}
        try:
            auth.pasang_password(password)
        except ValueError as e:
            return {"ok": False, "error": "password_tidak_sah", "message": str(e)}
        return {"ok": True, "baru_dipasang": True}

    if not auth.cek_password(password):
        return {"ok": False, "error": "password_salah",
                "message": "Password salah."}

    return {"ok": True, "siap_dibuat_sesi": True}


def api_auth_logout(handler):
    """Keluar: hapus sesi dan cookie."""
    token = handler._token()
    auth.akhiri_sesi(token)
    return handler._send(200, {"ok": True, "keluar": True},
                         cookie="sesi=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    # ── sesi ─────────────────────────────────────────────────────────────────
    def _token(self):
        """Ambil token sesi dari cookie."""
        cookie = self.headers.get("Cookie") or ""
        for bagian in cookie.split(";"):
            nama, _, nilai = bagian.strip().partition("=")
            if nama == "sesi":
                return nilai
        return None

    def _sudah_login(self):
        return auth.sesi_sah(self._token())

    def _butuh_login(self, path, method):
        """Tentukan apakah request ini boleh dilanjutkan.

        Semua API butuh sesi, KECUALI:
          - halaman login itu sendiri (`/login`)
          - `/api/auth` untuk GET **dan** POST

        Kenapa GET /api/auth juga publik: endpoint itu mengirim
        `sudah_ada_password`, dan itu satu-satunya cara halaman login tahu
        apakah harus menampilkan form "pasang password" atau form "masuk".

        Kalau GET-nya diblokir, halaman login TIDAK PERNAH tahu bahwa password
        belum dipasang — jadi ia selalu menampilkan form masuk, dan password
        yang diketik di situ justru TERPASANG. Artinya: siapa pun yang membuka
        panel lebih dulu bisa memasang passwordnya sendiri dan mengunci Deny
        keluar dari panelnya.

        Celah ini ditemukan yuki 3 Okt 2026 saat menguji halaman login; ia
        mengalaminya sendiri tanpa sengaja.
        """
        if path in PUBLIK:
            return True
        if path == "/api/auth":
            return True          # GET (status) maupun POST (login)
        return self._sudah_login()

    def _tolak(self):
        """Balasan untuk yang belum login.

        Untuk /api/*: JSON, supaya UI bisa menampilkan pesan yang benar.
        Untuk halaman: alihkan ke halaman login.
        """
        if self.path.startswith("/api/"):
            return self._send(401, {"ok": False, "error": "belum_login",
                                    "message": "Sesi tidak berlaku. Masuk dulu."})
        self.send_response(302)
        self.send_header("Location", "/login")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _send(self, code, payload, ctype="application/json", cookie=None):
        body = (json.dumps(payload, ensure_ascii=False).encode()
                if ctype == "application/json" else payload)
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def _jalankan(self, fn, *a, **kw):
        """Jalankan handler rute; kalau ada exception, kirim balasan yang bisa dibaca.

        Kenapa ini ada: tanpa penjagaan ini, exception apa pun di dalam handler
        keluar SEBELUM `_send()` dipanggil, jadi socket-nya ditutup tanpa
        balasan HTTP. Dari sisi browser/curl, itu terlihat seperti **koneksi
        putus / server mati** — bukan seperti bug di server.

        Kejadian nyata: `api_analysis_create` memakai `model_config` yang tidak
        diimpor (3 Okt 2026). Modelnya sudah dipanggil, narasinya sudah jadi,
        lalu `NameError` — dan Deny melihat "HTTP 000, 0 byte" tanpa keterangan
        apa pun. Bug yang seharusnya berteriak malah terdengar seperti koneksi
        bermasalah. yuki yang menemukannya.

        Dengan ini, kegagalan server selalu menghasilkan balasan JSON yang bisa
        ditampilkan UI — walau isinya cuma "server gagal, ini jejaknya di log".
        """
        try:
            return fn(*a, **kw)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"ok": False, "error": "gagal_server",
                    "message": "Server gagal memproses permintaan (%s: %s). "
                               "Lihat log server." % (type(e).__name__, e)}

    def _send_401(self, payload):
        return self._send(401, payload)

    def _auth_login(self, body):
        """Login: verifikasi password, lalu buat sesi dan kirim cookie.

        Pemisahan ini penting: `api_auth_login` hanya memutuskan SAH atau TIDAK.
        Pembuatan sesi + cookie ada di sini karena itu urusan lapisan HTTP.
        """
        hasil = api_auth_login(body)

        if not hasil.get("ok"):
            # Password pertama kali dipasang -> langsung buat sesi, jangan
            # menyuruh Deny mengetik ulang password yang baru saja ia tentukan.
            return self._send(401, hasil)

        if hasil.get("baru_dipasang") and body.get("langsung_masuk", True):
            token = auth.buat_sesi()
            return self._send(200, {"ok": True, "baru_dipasang": True, "masuk": True},
                              cookie=_cookie_sesi(token))

        if hasil.get("siap_dibuat_sesi"):
            token = auth.buat_sesi()
            return self._send(200, {"ok": True, "masuk": True},
                              cookie=_cookie_sesi(token))

        return self._send(200, hasil)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        if not self._butuh_login(path, "GET"):
            return self._tolak()

        # Halaman login: disajikan walau belum masuk
        if path in PUBLIK and path in ("/login", "/login.html", "/masuk"):
            berkas = STATIC / "login.html"
            if berkas.is_file():
                return self._send(200, berkas.read_bytes(), "text/html")
            return self._send(200,
                              b"<h1>Halaman login belum dibuat</h1>"
                              b"<p>web/login.html belum ada.</p>", "text/html")

        rute = {
            "/api/summary": api_summary,
            "/api/transactions": api_transactions,
            "/api/categories": api_categories,
            "/api/accounts": api_accounts,
            "/api/trend": api_trend,
            "/api/spending-by-category": api_categories_spending,
            "/api/suggestions": api_suggestions,
            "/api/analysis": api_analysis,
            "/api/savings": api_savings,
            "/api/debts": api_debts,
            "/api/months": api_months,
            "/api/ai-status": api_ai_status,
            "/api/auth": api_auth_status,
            "/api/auth/status": api_auth_status_lengkap,
        }
        if path in rute:
            return self._send(200, self._jalankan(rute[path], params))

        # berkas statis
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())):
            return self._send(403, {"error": "dilarang"})
        if target.is_file():
            ctype = ("text/html" if target.suffix == ".html" else
                     "text/css" if target.suffix == ".css" else
                     "application/javascript" if target.suffix == ".js" else
                     "text/plain")
            return self._send(200, target.read_bytes(), ctype)
        return self._send(404, {"error": "tidak_ditemukan"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else "{}"
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "json_rusak",
                                    "message": "Body bukan JSON valid."})

        if not self._butuh_login(parsed.path, "POST"):
            return self._tolak()

        if parsed.path == "/api/parse":
            return self._send(200, self._jalankan(api_parse, body))
        if parsed.path == "/api/save":
            return self._send(200, self._jalankan(api_save, body))
        if parsed.path == "/api/debts/batalkan":
            return self._send(200, self._jalankan(api_debts_batalkan, body))
        if parsed.path == "/api/accounts":
            return self._send(200, self._jalankan(api_account_create, body))
        if parsed.path == "/api/analysis":
            return self._send(200, self._jalankan(api_analysis_create, body))
        if parsed.path == "/api/savings":
            return self._send(200, self._jalankan(api_savings_set, body))
        if parsed.path == "/api/auth":
            return self._jalankan(self._auth_login, body)
        if parsed.path == "/api/auth/keluar":
            return api_auth_logout(self)
        return self._send(404, {"ok": False, "error": "tidak_ditemukan"})

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode() if length else "{}"
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return self._send(400, {"ok": False, "error": "json_rusak",
                                    "message": "Body bukan JSON valid."})

        if not self._butuh_login(parsed.path, "PATCH"):
            return self._tolak()

        m = re.fullmatch(r"/api/accounts/(\d+)", parsed.path)
        if m:
            return self._send(200, self._jalankan(api_account_patch, int(m.group(1)), body))
        m = re.fullmatch(r"/api/transactions/(\d+)", parsed.path)
        if m:
            return self._send(200, self._jalankan(api_transaction_patch, int(m.group(1)), body))
        return self._send(404, {"ok": False, "error": "tidak_ditemukan"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)

        if not self._butuh_login(parsed.path, "DELETE"):
            return self._tolak()

        m = re.fullmatch(r"/api/transactions/(\d+)", parsed.path)
        if m:
            return self._send(200, self._jalankan(api_transaction_delete, int(m.group(1))))
        m = re.fullmatch(r"/api/analysis/(\d{4}-\d{2})", parsed.path)
        if m:
            return self._send(200, self._jalankan(api_analysis_delete, m.group(1)))
        if parsed.path == "/api/savings":
            return self._send(200, self._jalankan(api_savings_delete))
        return self._send(404, {"ok": False, "error": "tidak_ditemukan"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    # Periksa dulu apakah sudah ada server yang jalan di port ini.
    #
    # KENAPA: kalau server dijalankan dari shortcut (ikon yang diklik), Deny bisa
    # mengkliknya dua kali — atau mengkliknya padahal server dari sesi sebelumnya
    # masih hidup. Tanpa pemeriksaan ini, yang muncul adalah traceback Python
    # `OSError: [Errno 48] Address already in use`, dan itu tidak memberi tahu
    # apa yang harus dilakukan.
    #
    # Yang benar: katakan bahwa panelnya SUDAH jalan, dan buka browser ke sana.
    # Itu yang sebenarnya dia mau ketika mengklik ikonnya.
    def sudah_ada_server(port):
        """True kalau ada yang menjawab di port itu (server finance kita)."""
        import urllib.request
        try:
            with urllib.request.urlopen(
                    "http://127.0.0.1:%d/api/auth" % port, timeout=2) as r:
                body = r.read().decode("utf-8", "ignore")
            # Pastikan itu memang server finance, bukan aplikasi lain yang
            # kebetulan memakai port yang sama.
            return '"panjang_min_password"' in body
        except Exception:
            return False

    if sudah_ada_server(args.port):
        print("Panel finance SUDAH jalan di http://localhost:%d" % args.port)
        print("Membuka browser ke sana. Tidak menjalankan server kedua.")
        try:
            import subprocess
            subprocess.run(["open", "http://localhost:%d" % args.port],
                           check=False)
        except Exception:
            pass
        print("(Kalau ingin memaksa server baru: matikan yang lama dulu dengan")
        print(" pkill -f 'src/server.py', lalu jalankan lagi.)")
        return 0

    db.init_db()
    try:
        srv = HTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        # Port terpakai aplikasi LAIN (bukan server finance kita). Katakan
        # dengan jelas, jangan biarkan traceback Python yang membingungkan.
        print("Gagal membuka port %d: %s" % (args.port, e))
        print("Kemungkinan port itu dipakai aplikasi lain.")
        print("Coba port lain, misalnya:  python3 src/server.py --port 8792")
        return 1

    print("Server finance jalan di http://localhost:%d" % args.port)
    print("Database: %s" % db.DB_PATH)
    print("Hanya bisa diakses dari Mac ini. Ctrl+C untuk berhenti.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("Berhenti.")
    return 0


if __name__ == "__main__":
    main()
