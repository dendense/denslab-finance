#!/usr/bin/env python3
"""Pembungkus parser — mengubah bentuk keluaran chat_entry.py jadi sesuai CONTRACT.md.

Kenapa dibungkus dan bukan diubah langsung:
`chat_entry.py` adalah prototipe milik Deny yang bisa ia jalankan sendiri dari
terminal. Kalau diubah, prototipe itu berhenti berguna sebagai alat uji. Jadi
logika penguraian tetap di sana; file ini hanya menyesuaikan bentuk datanya.

Yang dikerjakan file ini:
  1. Menebak `flow_type` dari kata kunci (parser asli tidak tahu konsep ini)
  2. Menormalkan tanggal dan menandai tanggal yang diasumsikan
  3. Mengubah kegagalan jadi bentuk {"ok": false, "error": ...} yang bisa
     ditampilkan UI — bukan exception yang menjatuhkan server
"""
from datetime import date

# Kata kunci untuk menebak sifat transaksi. Sengaja pendek dan konservatif:
# lebih baik Deny mengoreksi satu tebakan daripada parser salah menandai
# pelunasan utang sebagai pengeluaran biasa.
KATA_UTANG = ("utang", "hutang", "cicilan", "angsuran", "lunas", "pinjam",
              "paylater", "spaylater", "spinjam", "kredit")

# Nama project/tujuan talangan. Kalau ini muncul, transaksinya bukan
# pengeluaran pribadi biasa.
#
# PENTING: kata "topup" SENDIRI tidak cukup. "Topup e-toll", "topup gopay",
# "topup pulsa" bukan talangan ke project — itu uang Deny sendiri yang
# berpindah bentuk. Kalau "topup" apa saja dianggap piutang, angka piutang
# menggelembung (kejadian nyata: e-toll Rp 301.250 salah masuk piutang) dan
# konsumsi jadi tidak tercatat sama sekali.
KATA_TALANGAN = ("topup project", "top up project", "top-up project",
                 "biaya project", "operasional project", "talangan",
                 "saldo kenari", "topup kenari", "top up kenari",
                 "saldo siray", "topup siray", "top up siray",
                 "kenari", "siray", "studio-contoh", "rin studio")

# Kalau pesan menyebut nama tujuan yang BUKAN akun Deny, ini pengeluaran atau
# talangan — bukan perpindahan antar akun sendiri.
BUKAN_AKUN_SENDIRI = ("kenari", "siray", "openai", "anthropic", "cloud",
                      "hosting", "vercel", "supabase", "domain")

KATEGORI_OUT = {"Makan", "Transport", "Belanja", "Hiburan", "Tagihan",
                "Kesehatan", "Pendidikan", "Lainnya"}
KATEGORI_IN = {"Gaji", "Bonus", "Lainnya"}


def tebak_flow_type(tx):
    """Tebakan awal sifat transaksi. Deny yang mengoreksi di layar konfirmasi.

    Urutan pemeriksaan penting: talangan dicek SEBELUM arah transfer, karena
    "topup saldo kenari" tidak boleh lolos jadi transfer hanya karena ada kata
    "topup".
    """
    text = ("%s %s" % (tx.get("note") or "", tx.get("category") or "")).lower()
    direction = tx.get("direction")

    # Talangan project: menang atas segalanya kecuali uang masuk.
    # Uangnya keluar dari kantong dan tidak kembali sendiri -> piutang.
    if direction != "in" and any(k in text for k in KATA_TALANGAN):
        return "receivable"

    # Utang menang atas transfer: "transfer buat bayar cicilan" itu pembayaran.
    if direction != "in" and any(k in text for k in KATA_UTANG):
        return "debt_payment"

    if direction == "transfer":
        # Kalau tujuannya bukan akun sendiri, ini bukan pindah akun.
        if any(k in text for k in BUKAN_AKUN_SENDIRI):
            return "receivable"
        return "transfer"

    if direction == "in":
        return "income"
    return "expense"


def bersihkan(tx):
    """Satu transaksi mentah -> bentuk kontrak."""
    direction = tx.get("direction")
    if direction not in ("in", "out", "transfer"):
        direction = "out"

    category = tx.get("category")
    if direction == "transfer":
        category = None
    else:
        sah = KATEGORI_IN if direction == "in" else KATEGORI_OUT
        if category not in sah:
            category = "Lainnya"

    try:
        amount = int(round(float(tx.get("amount") or 0)))
    except (TypeError, ValueError):
        amount = 0

    occurred = tx.get("occurred_on") or date.today().isoformat()

    return {
        "direction": direction,
        "flow_type": tebak_flow_type(tx),
        "amount": amount,
        "category": category,
        "account_hint": tx.get("account_hint"),
        "to_account_hint": tx.get("to_account_hint"),
        "note": tx.get("note"),
        "occurred_on": occurred,
        "assumed_date": bool(tx.get("assumed_date")),
    }


def layak_jadi_pertanyaan(q, pesan_asli):
    """Saring balasan model yang tidak berguna.

    Model kadang memantulkan pesan user sendiri, atau membalas dengan kalimat
    yang tidak menjelaskan apa-apa. Kalau itu diteruskan ke UI, Deny melihat
    "MONICA: halo monica apa kabar" — terlihat seperti bot rusak.
    """
    q = (q or "").strip()
    if not q:
        return False
    if q.lower() == (pesan_asli or "").strip().lower():
        return False          # pesan user dipantulkan
    if len(q) <= 12:
        return False          # terlalu pendek untuk menjelaskan apa pun
    penanda = ("?", "tidak", "bukan", "belum", "mohon", "coba", "maksud",
               "transaksi", "catat", "berapa", "nominal", "jumlah")
    return any(k in q.lower() for k in penanda)


def parse_kontrak(text):
    """Urai kalimat -> bentuk sesuai CONTRACT.md bagian 4.

    Selalu mengembalikan dict, tidak pernah melempar exception: server harus
    tetap hidup walaupun model sedang bermasalah.
    """
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "teks_kosong",
                "message": "Tidak ada teks untuk diurai."}

    try:
        import chat_entry
        hasil = chat_entry.parse(text)
    except RuntimeError as e:
        # Kunci API hilang, kuota habis, atau model tidak membalas. `sebab`
        # (teks asli dari Python) TIDAK dikirim ke UI: nama env var dan pesan
        # pustaka tidak bisa ditindaklanjuti Deny, dan menampilkannya membuat
        # layar terbaca seperti rusak. Sebabnya dicatat di server untuk
        # diagnosa; ke Deny cukup apa yang perlu dia lakukan.
        print("[parser] uraian gagal: %s" % e, flush=True)
        return {"ok": False, "error": "model_tidak_membalas",
                "message": "Catat pintar sedang tidak bisa dipakai — model "
                           "tidak menjawab. Kamu tetap bisa mengisi manual."}
    except Exception as e:
        print("[parser] gagal urai: %s" % e, flush=True)
        return {"ok": False, "error": "gagal_parse",
                "message": "Kalimat itu gagal diuraikan. Coba tulis lebih "
                           "sederhana, atau isi manual."}

    txs = hasil.get("transactions") or []
    question = hasil.get("question")

    if not txs:
        if layak_jadi_pertanyaan(question, text):
            pesan = question.strip()
        else:
            pesan = "Aku tidak menemukan transaksi di pesan itu."
        return {"ok": True, "draft": {"transactions": [], "question": pesan}}

    bersih = [bersihkan(tx) for tx in txs]
    # Buang transaksi tanpa jumlah: parser kadang mengeluarkan baris kosong
    # kalau kalimatnya ambigu. Menyimpan 0 akan merusak laporan diam-diam.
    bersih = [tx for tx in bersih if tx["amount"] > 0]

    if not bersih:
        return {"ok": True,
                "draft": {"transactions": [],
                          "question": "Ada angka yang tidak terbaca. Coba tulis ulang, misal: "
                                      "'makan malam 45000'."}}

    return {"ok": True, "draft": {"transactions": bersih, "question": None}}
