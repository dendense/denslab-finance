#!/usr/bin/env python3
"""Gerbang simpan pencatatan lewat chat — draft dulu, simpan hanya atas Deny.

KEPUTUSAN DENY (9 Okt 2026, dijawab langsung, bukan lewat perantara):

  1. Boleh mencatat lewat chat atas perintah yang disampaikan Rin -> YA
  2. Konfirmasi tetap dua langkah                                   -> YA, wajib
  3. Rin boleh menyimpan sendiri                                    -> TIDAK

Aturan yang mengikat modul ini:

  * Draft dulu, selalu. Nol baris tersimpan sebelum Deny membalas.
  * Simpan hanya atas balasan Deny SENDIRI. Balasan Rin *tentang* Deny
    bukan perintah. Ragu -> berhenti -> tanya Deny. Fail-closed.
  * Rin tidak punya jalur simpan.
  * Setiap penyimpanan tercatat asalnya: siapa, kapan, dari chat mana.
  * Postur jaringan tidak berubah: tanpa port baru, tanpa kunci API baru,
    server tetap 127.0.0.1. Modul ini membaca `finance.db` langsung sebagai
    proses di Mac yang sama, dan TIDAK membuka jaringan apa pun sendiri.

────────────────────────────────────────────────────────────────────────────
BATAS YANG JUJUR — baca sebelum menganggap ini "aman"

Modul ini TIDAK bisa memverifikasi identitas. Tidak ada kriptografi di sini,
dan memang tidak ditambahkan: keputusan Deny melarang kunci API baru. Yang
bisa ditegakkan hanya STRUKTUR perintahnya:

  * ada dua langkah (draft, lalu simpan),
  * perintah simpan harus berbentuk orang-pertama dari Deny — bukan kalimat
    yang menceritakan bahwa Deny menyuruh,
  * setiap penyimpanan meninggalkan jejak asalnya.

Yang TIDAK ditegakkan: kalau seseorang mengetik `pengirim: "deny"` padahal
bukan Deny, gerbang ini tidak tahu. Itu sebabnya aturan "Rin tidak punya
jalur simpan" tidak dipenuhi oleh gerbang ini, melainkan oleh kenyataan
bahwa **tidak ada** fungsi, endpoint, atau perintah yang bisa dipanggil Rin
untuk mencapai `simpan()` tanpa melewati satu langkah yang dipegang manusia.
Buktinya di `tests/test_chat_gate.py` (bagian "Rin tidak punya jalur simpan").
────────────────────────────────────────────────────────────────────────────
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import db            # noqa: E402
import parser_wrap   # noqa: E402

# Siapa yang boleh memerintahkan penyimpanan. HANYA manusia pemilik buku.
# Rin tidak ada di sini, dan tidak akan pernah ditambahkan.
MANUSIA = "deny"

# Nama agent lain. Kalau salah satu muncul DI SAMPING kata pelaporan
# ("rin bilang simpan"), pesannya sedang menceritakan perintah orang lain —
# bukan perintah itu sendiri.
NAMA_AGENT = ("rin", "steve", "yuki", "hana")

# Kata pelaporan: menandakan kalimat TENTANG orang lain, bukan ucapan orang itu.
KATA_LAPOR = ("bilang", "berkata", "kata ", "suruh", "menyuruh", "menyampaikan",
              "titip", "mewakili", "atas nama", "menurut")

# Kata afirmatif yang sah sebagai perintah simpan. Yang panjang dicocokkan
# sebagai substring ("disimpan" ikut), yang pendek wajib kata utuh — supaya
# "yang" tidak lolos hanya karena memuat "ya".
AFIRMASI_SUB = ("simpan", "catat", "benar", "setuju", "lanjut")
AFIRMASI_KATA = ("ya", "ok", "oke", "sip")

LABEL_SIFAT = {
    "expense": "Pengeluaran",
    "income": "Pemasukan",
    "receivable": "Talangan",
    "debt_payment": "Bayar utang",
    "transfer": "Pindah akun",
}

ARAH_SIFAT = {
    "expense": "out", "receivable": "out", "debt_payment": "out",
    "income": "in", "transfer": "transfer",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. DRAFT — membaca saja, TIDAK PERNAH menulis
# ─────────────────────────────────────────────────────────────────────────────
def _akun_aktif(path=None):
    return db.get_accounts(path=path)


def _cocokkan_akun(hint, akun):
    """Cocokkan petunjuk akun ke daftar akun, TANPA menebak.

    Mengembalikan (id, nama) kalau pas, atau (None, None). Kalau petunjuknya
    tidak ada dan cuma satu akun aktif, akun itu yang dipakai — sama seperti
    `db._resolve_account`. Kalau lebih dari satu, tidak ditebak.
    """
    if hint and hint.strip():
        h = hint.strip().lower()
        for a in akun:
            if a["name"].lower() == h:
                return a["id"], a["name"]
        for a in akun:
            if h in a["name"].lower():
                return a["id"], a["name"]
        return None, None
    if len(akun) == 1:
        return akun[0]["id"], akun[0]["name"]
    return None, None


def draft(text, path=None, parse_fn=None):
    """Urai kalimat jadi draft lengkap. NOL baris tersimpan.

    `parse_fn` bisa diganti di uji supaya tidak memanggil model. Di pemakaian
    sungguhan ia adalah `parser_wrap.parse_kontrak` — parser YANG SAMA dengan
    halaman Catat. Tidak ada jalur parse kedua di sini; kalau ada, draft di
    chat dan di panel bisa berbeda diam-diam.
    """
    parse_fn = parse_fn or parser_wrap.parse_kontrak
    hasil = parse_fn(text)
    if not hasil.get("ok"):
        return hasil

    d = hasil.get("draft") or {}
    txs = d.get("transactions") or []
    if not txs:
        return hasil

    akun = _akun_aktif(path)
    nama_akun = [a["name"] for a in akun]

    untuk_tampil = []
    for tx in txs:
        aid, anama = _cocokkan_akun(tx.get("account_hint"), akun)
        tid, tnama = _cocokkan_akun(tx.get("to_account_hint"), akun)
        butuh_akun = aid is None and len(akun) != 1
        untuk_tampil.append({
            **tx,
            "account_id": aid,
            "account_name": anama,
            "to_account_id": tid,
            "to_account_name": tnama,
            "butuh_akun": butuh_akun,
            "sifat": LABEL_SIFAT.get(tx.get("flow_type"), tx.get("flow_type")),
        })

    return {"ok": True, "draft": {
        "transactions": untuk_tampil,
        "question": d.get("question"),
        "akun_kandidat": nama_akun,
        "perlu_akun": any(t["butuh_akun"] for t in untuk_tampil),
    }}


def render_draft(hasil):
    """Draft -> teks untuk ditampilkan di chat. Tidak menyimpan apa pun."""
    if not hasil.get("ok"):
        return "Gagal mengurai: %s" % hasil.get("message", "sebab tidak diketahui")

    d = hasil.get("draft") or {}
    txs = d.get("transactions") or []
    if not txs:
        return d.get("question") or "Aku tidak menemukan transaksi di pesan itu."

    baris = []
    for i, tx in enumerate(txs, 1):
        akun = tx.get("account_name") or "(akun belum jelas)"
        tujuan = ""
        if tx.get("flow_type") == "transfer":
            tujuan = " -> %s" % (tx.get("to_account_name") or "(akun tujuan belum jelas)")
        tgl = tx.get("occurred_on", "-")
        if tx.get("assumed_date"):
            tgl += " (dianggap hari ini)"
        baris.append("  %d. %s  %s  %s%s  %s" % (
            i, db.rupiah(tx.get("amount")), tx.get("sifat", "?"), akun, tujuan, tgl))
        if tx.get("note"):
            baris.append("     catatan: %s" % tx["note"])

    ekor = []
    if d.get("perlu_akun"):
        ekor.append("  Akun belum jelas. Pilih salah satu: %s"
                    % ", ".join(d.get("akun_kandidat") or []))
    ekor.append("  Belum ada yang tersimpan. Balas \"simpan\" untuk menyimpan.")

    return "\n".join(baris + [""] + ekor)


# ─────────────────────────────────────────────────────────────────────────────
# 2. KONFIRMASI — fail-closed, semua yang tidak jelas DITOLAK
# ─────────────────────────────────────────────────────────────────────────────
def periksa_konfirmasi(konfirmasi):
    """Kembalikan None kalau sah, atau (kode, pesan) kalau ditolak.

    FAIL-CLOSED: keraguan selalu berarti berhenti. Tidak ada jalur "mungkin
    benar" — lebih baik Deny mengetik "simpan" sekali lagi daripada satu
    angka masuk tanpa perintah.
    """
    if not konfirmasi:
        return ("tanpa_konfirmasi",
                "Belum ada konfirmasi dari Deny. Draft belum disimpan.")
    if not isinstance(konfirmasi, dict):
        return ("konfirmasi_rusak",
                "Bentuk konfirmasi tidak dikenal. Draft belum disimpan.")

    pengirim = (konfirmasi.get("pengirim") or "").strip().lower()
    if pengirim != MANUSIA:
        return ("bukan_deny",
                "Perintah simpan hanya sah kalau datang dari Deny sendiri. "
                "Yang mengirim ini '%s', bukan Deny. Draft belum disimpan."
                % (pengirim or "tidak disebutkan"))

    teks = (konfirmasi.get("teks") or "").strip()
    if not teks:
        return ("konfirmasi_kosong",
                "Konfirmasi tidak berisi kata apa pun. Draft belum disimpan.")

    rendah = teks.lower()

    # Perantara: kalimat yang MENYEBUT nama Deny berarti pesannya tentang
    # Deny, bukan ucapan Deny. Orang yang memerintah tidak menyebut namanya
    # sendiri. Ini yang menangkap "kata deny, simpan".
    if re.search(r"\b%s\b" % re.escape(MANUSIA), rendah):
        return ("perantara",
                "Kalimat itu menyebut nama Deny, jadi bunyinya seperti "
                "laporan orang lain, bukan perintah Deny. Aku berhenti dan "
                "tunggu Deny sendiri yang bilang \"simpan\".")

    # "rin bilang simpan" — agent lain + kata pelaporan.
    if any(re.search(r"\b%s\b" % re.escape(n), rendah) for n in NAMA_AGENT) \
            and any(k in rendah for k in KATA_LAPOR):
        return ("perantara",
                "Kalimat itu menyebut agent lain yang menyampaikan perintah. "
                "Perantara bukan perintah. Aku berhenti dan tanya Deny.")

    afirmatif = (any(k in rendah for k in AFIRMASI_SUB)
                 or any(re.search(r"\b%s\b" % re.escape(k), rendah)
                        for k in AFIRMASI_KATA))
    if not afirmatif:
        return ("tidak_afirmatif",
                "Konfirmasi itu tidak berisi perintah simpan yang jelas. "
                "Balas \"simpan\" kalau memang mau disimpan.")

    kanal = (konfirmasi.get("kanal") or "").strip()
    if not kanal:
        return ("kanal_kosong",
                "Asal chat konfirmasi tidak disebutkan — tidak bisa dilacak. "
                "Draft belum disimpan.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. SIMPAN — satu-satunya jalur tulis, dan ia menuntut konfirmasi
# ─────────────────────────────────────────────────────────────────────────────
def _catat_asal(asal, ids, path_log=None):
    """Tulis jejak asal penyimpanan ke berkas JSON-per-baris di folder data.

    Ditulis SETELAH `db.save_transactions` berhasil. Aman: penyimpanan itu
    satu transaksi database (semua-atau-tidak-sama-sekali), jadi tidak ada
    keadaan setengah jadi yang perlu dilacak lebih dulu. Kalau prosesnya mati
    di tengah, transaksinya di-rollback — dan tidak ada yang tersimpan untuk
    dilacak.

    Bawaannya di samping database AKTIF, bukan `db.DATA_DIR` — supaya uji
    yang mengarahkan `db.DB_PATH` ke salinan tidak menulis jejak ke folder
    data Deny.
    """
    if path_log is None:
        path_log = Path(str(db.DB_PATH)).parent / "chat_simpan.log"
    p = Path(path_log)
    p.parent.mkdir(parents=True, exist_ok=True)
    entri = {
        "disimpan_pada": datetime.now().isoformat(timespec="seconds"),
        "pengirim": asal.get("pengirim"),
        "kanal": asal.get("kanal"),
        "waktu_konfirmasi": asal.get("waktu"),
        "teks_konfirmasi": asal.get("teks"),
        "jumlah": len(ids),
        "saved_ids": list(ids),
    }
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entri, ensure_ascii=False) + "\n")
    return str(p)


def simpan(draft_hasil, konfirmasi, path=None, path_log=None):
    """Simpan draft. Menuntut konfirmasi Deny yang sah — tanpa itu, menolak.

    Mengembalikan {"ok": True, "saved_ids": [...], "asal": {...}} atau
    {"ok": False, "error": ..., "message": ...}. Tidak pernah melempar
    exception untuk penolakan: pemanggil harus bisa menampilkan alasannya.
    """
    tolak = periksa_konfirmasi(konfirmasi)
    if tolak:
        kode, pesan = tolak
        return {"ok": False, "error": kode, "message": pesan, "tersimpan": 0}

    if not draft_hasil or not draft_hasil.get("ok"):
        return {"ok": False, "error": "draft_tidak_sah",
                "message": "Draftnya tidak sah atau gagal diurai.", "tersimpan": 0}

    txs = (draft_hasil.get("draft") or {}).get("transactions") or []
    if not txs:
        return {"ok": False, "error": "draft_kosong",
                "message": "Tidak ada transaksi di draft itu.", "tersimpan": 0}

    items = []
    for i, tx in enumerate(txs, 1):
        for f in ("occurred_on", "direction", "amount"):
            if not tx.get(f):
                return {"ok": False, "error": "field_kurang",
                        "message": "Transaksi ke-%d tidak punya '%s'." % (i, f),
                        "tersimpan": 0}
        items.append({
            "occurred_on": tx["occurred_on"],
            "direction": tx["direction"],
            "amount": tx["amount"],
            "flow_type": tx.get("flow_type"),
            "account_id": tx.get("account_id"),
            "account_hint": tx.get("account_hint"),
            "to_account_id": tx.get("to_account_id"),
            "to_account_hint": tx.get("to_account_hint"),
            "category": tx.get("category"),
            "note": tx.get("note"),
        })

    try:
        ids = db.save_transactions(items, path=path)
    except Exception as e:
        # Pesan dari db.py sudah spesifik (akun tidak ada, flow_type tidak
        # cocok arah). Teruskan apa adanya — itu yang menolong Deny memperbaiki.
        return {"ok": False, "error": "gagal_simpan", "message": str(e),
                "tersimpan": 0}

    asal = {
        "pengirim": konfirmasi.get("pengirim"),
        "kanal": konfirmasi.get("kanal"),
        "waktu": konfirmasi.get("waktu") or datetime.now().isoformat(timespec="seconds"),
        "teks": konfirmasi.get("teks"),
    }
    berkas = _catat_asal(asal, ids, path_log=path_log)
    return {"ok": True, "saved_ids": ids, "count": len(ids),
            "asal": asal, "jejak": berkas}


# ─────────────────────────────────────────────────────────────────────────────
# 4. CLI — untuk Deny di Mac yang sama. Bukan jalur chat.
# ─────────────────────────────────────────────────────────────────────────────
def main(argv=None):
    """Pemakaian:
        python3 src/chat_gate.py "makan malam 45000"            # draft saja
        python3 src/chat_gate.py "..." --simpan --kanal telegram --teks "simpan"
    """
    import argparse
    ap = argparse.ArgumentParser(description="Draft & simpan lewat chat (dua langkah).")
    ap.add_argument("kalimat", help="kalimat transaksi, mis. 'makan malam 45000'")
    ap.add_argument("--simpan", action="store_true",
                    help="simpan draft. Menuntut --kanal dan --teks (kata Deny).")
    ap.add_argument("--kanal", help="dari chat mana perintah itu datang")
    ap.add_argument("--teks", help="kata-kata Deny yang memerintahkan simpan")
    ap.add_argument("--pengirim", default=MANUSIA,
                    help="siapa yang memerintah (bawaan: deny)")
    args = ap.parse_args(argv)

    hasil = draft(args.kalimat)
    print(render_draft(hasil))
    if not args.simpan:
        return 0

    konfirmasi = {"pengirim": args.pengirim, "kanal": args.kanal, "teks": args.teks}
    keluar = simpan(hasil, konfirmasi)
    if keluar["ok"]:
        print("\nTERSIMPAN: %d transaksi, id %s" % (keluar["count"], keluar["saved_ids"]))
        print("jejak asal: %s" % keluar["jejak"])
        return 0
    print("\nDITOLAK (%s): %s" % (keluar["error"], keluar["message"]))
    return 1


if __name__ == "__main__":
    sys.exit(main())
