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
AFIRMASI_KATA = ("ya", "iya", "ok", "oke", "sip")

# Kata PENYANGKAL. Kalau salah satu muncul, teksnya bukan perintah simpan —
# bisa jadi penolakan ("jangan simpan") atau penundaan ("nanti simpan").
# Tanpa penjaga ini, "simpan" ⊂ "jangan simpan" dan "setuju" ⊂ "tidak setuju",
# jadi kalimat PENOLAKAN Deny lolos gerbang dan tertulis ke ledger — fail-open,
# persis yang dilarang Definisi selesai #2 ("ragu → berhenti").
#
# PENTING (review ronde 3): daftar ini BUKAN gerbangnya. Daftar hitam bahasa
# Indonesia informal tidak pernah selesai — 'ndak', 'kagak', 'mbok', 'udah',
# 'no' semuanya pernah lolos. Yang benar-benar menjaga adalah DAFTAR PUTIH di
# `perintah_diizinkan()`: hanya bentuk perintah yang diakui yang lolos, sisanya
# berhenti. Daftar penyangkal ini sekarang hanya memilih kode pesan yang lebih
# tepat (`ditolak` vs `tidak_afirmatif`).
NEGASI_SUB = ("jangan", "jgn", "tidak", "tdk", "batal", "urung", "belum",
              "belom", "nggak", "enggan", "engga", "enggak", "gausah", "bukan")
NEGASI_KATA = ("tak", "gak", "gk", "ga", "g", "nanti")

# Kata tanya. Kalimat yang bertanya bukan perintah, walau memuat kata
# afirmatif ("apa ya" memuat kata utuh "ya"). Dicocokkan sebagai kata utuh
# supaya "siapa" tidak tertangkap oleh "apa".
KATA_TANYA = ("apa", "apakah", "kah", "gimana", "bagaimana", "kok", "kenapa",
              "mengapa", "kapan", "siapa")

# ── Daftar PUTIH perintah simpan — ini GERBANG SEBENARNYA ────────────────────
# Perbaikan review ronde 3 (9 Okt 2026). Penjaga negasi di atas memakai DAFTAR
# HITAM penyangkal, dan daftar hitam bahasa Indonesia informal tidak pernah
# selesai: 'ndak', 'kagak', 'mbok', 'udah', 'no', 'udah', 'sudah' ... setiap
# kata baru yang lolos adalah satu angka yang bisa masuk tanpa perintah Deny —
# kelas cacat yang sama dengan ronde 1 (penolakan diperlakukan sebagai
# perintah). Karena itu arah kegagalannya DIBALIK: bukan "kecualikan penolakan
# yang kita kenali", melainkan "izinkan hanya perintah yang kita akui, sisanya
# berhenti". Daftar hitam di atas tetap ada, tapi sekarang hanya untuk memilih
# kode pesan yang lebih tepat — yang menjaga adalah daftar putih ini.
#
# Bentuk sah, setelah normalisasi (huruf kecil, pemisah netral -> spasi, spasi
# dirapatkan):
#   * satu kata afirmatif:  ya · iya · ok · oke · sip · setuju · benar
#   * satu kata perintah:   simpan · catat
#   * prefiks + perintah:   "ya simpan" · "oke simpan" · "tolong catat" ·
#                           "lanjut simpan" · "silakan simpan" ...
# Di luar itu DITOLAK fail-closed. "simpan aja" ikut ditolak — Deny cukup
# mengetik "simpan" sekali lagi, dan itu jauh lebih baik daripada satu angka
# masuk tanpa perintahnya.
#
# ── Karakter asing juga DITOLAK (perbaikan review ronde 4, 9 Okt 2026) ──────
# Normalisasi versi lama membuang SEMUA karakter non-huruf/angka tanpa syarat
# (`re.sub(r"[^\w\s]+", " ", ...)`). Akibatnya penanda penolakan yang lazim di
# chat ikut hilang SEBELUM gerbang memutuskan: '❌ simpan', '⛔ simpan',
# '🚫 simpan', 'simpan ❌' semuanya menormalisasi jadi 'simpan' dan LOLOS —
# masing-masing benar-benar tertulis ke ledger. Itu kelas cacat yang sama
# dengan ronde 1 & 3 (penolakan Deny diperlakukan sebagai perintah).
# Sekarang hanya PEMISAH NETRAL (`,` `.` `!`) yang dipetakan ke spasi. Kalau
# teks masih memuat karakter di luar huruf/angka/spasi, `perintah_diizinkan()`
# mengembalikan False — jadi 'ya, simpan' tetap lolos, tapi '❌ simpan',
# 'simpan🔥', 'si-mpan' berhenti. Sebuah penanda penolakan tidak boleh bisa
# hilang sebelum gerbang memutuskan.
PERINTAH_KATA = ("simpan", "catat")
AFIRMASI_TUNGGAL = ("ya", "iya", "ok", "oke", "sip", "setuju", "benar")
PREFIKS_PERINTAH = ("ya", "iya", "ok", "oke", "sip", "silakan", "tolong",
                    "lanjut", "setuju", "benar", "gas", "ayo")

# Satu-satunya tanda baca yang netral — ia tidak membawa makna perintah maupun
# penolakan, jadi boleh dipetakan ke spasi. Selain ini: tolak.
PEMISAH_NETRAL = (",", ".", "!")
_POLA_ASING = re.compile(r"[^a-z0-9\s]")


def _normalisasi_perintah(teks):
    """Huruf kecil, PEMISAH NETRAL -> spasi, spasi dirapatkan.

    'ya, simpan' -> 'ya simpan'. Karakter di luar pemisah netral TIDAK dibuang
    di sini — pembuangan buta adalah cacat ronde 4 (penanda penolakan hilang).
    Pemeriksaannya ada di `perintah_diizinkan()`.

    Penjaga tipe (perbaikan ronde 6): fungsi ini juga dipanggil dari luar jalur
    `perintah_diizinkan()`, jadi non-teks dikembalikan sebagai string kosong —
    yang artinya "tidak ada perintah yang diakui", bukan exception.
    """
    if not isinstance(teks, str):
        return ""
    t = teks.lower()
    for p in PEMISAH_NETRAL:
        t = t.replace(p, " ")
    return re.sub(r"\s+", " ", t).strip()


def perintah_diizinkan(teks):
    """True HANYA kalau teks cocok persis salah satu bentuk perintah sah.

    Fail-closed dua lapis:
      1. karakter asing — apa pun di luar huruf/angka/spasi (setelah pemisah
         netral dipetakan) -> False. '❌ simpan', 'simpan🔥', 'si-mpan' berhenti.
      2. daftar putih bentuk perintah.
    """
    if not isinstance(teks, str):
        return False
    bersih = _normalisasi_perintah(teks)
    if _POLA_ASING.search(bersih):
        return False
    kata = bersih.split()
    if len(kata) == 1:
        return kata[0] in AFIRMASI_TUNGGAL or kata[0] in PERINTAH_KATA
    if len(kata) == 2:
        return kata[0] in PREFIKS_PERINTAH and kata[1] in PERINTAH_KATA
    return False


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

    Penjaga tipe (perbaikan review ronde 5, 9 Okt 2026): `hint` datang dari
    keluaran model, jadi bisa berupa angka, list, atau bool. Sebelum ini
    `hint.strip()` melempar AttributeError lewat `draft()` dan CLI untuk
    keluaran seperti itu. Hint non-string diperlakukan **seperti hint kosong**
    — tidak ditebak, tapi juga tidak meledak.
    """
    if isinstance(hint, str) and hint.strip():
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
    # Penjaga jalur parser (perbaikan review ronde 6): `draft()` adalah pintu
    # masuk jalur chat. Kalau parser yang disuntikkan melempar (bukan
    # mengembalikan kode), pemanggil chat menerima stack trace — padahal
    # prinsip modul ini adalah mengembalikan KODE. `parser_wrap.parse_kontrak`
    # sendiri sudah menangkap exception; ini menjaga jalur yang sama kalau
    # parser diganti.
    try:
        hasil = parse_fn(text)
    except Exception as e:
        return {"ok": False, "error": "parser_melempar",
                "message": "Parser gagal saat mengurai kalimat itu (%s). "
                           "Coba tulis lebih sederhana, atau isi manual."
                           % type(e).__name__}
    # Penjaga bentuk (kelas cacat sama dengan penjaga tipe di `simpan()`):
    # parser yang mengembalikan bentuk salah dulu melempar AttributeError/
    # TypeError ke pemanggil. Modul ini selalu memakai KODE, bukan exception —
    # supaya pemanggil chat bisa menampilkan alasan, bukan stack trace.
    if not isinstance(hasil, dict):
        return {"ok": False, "error": "hasil_parser_rusak",
                "message": "Parser tidak mengembalikan hasil yang dikenal."}
    if not hasil.get("ok"):
        return hasil

    d = hasil.get("draft") or {}
    if not isinstance(d, dict):
        return {"ok": False, "error": "hasil_parser_rusak",
                "message": "Isi draft dari parser bukan bentuk yang dikenal."}
    txs = d.get("transactions") or []
    if not isinstance(txs, list):
        return {"ok": False, "error": "hasil_parser_rusak",
                "message": "Daftar transaksi dari parser bukan daftar."}
    if not txs:
        return hasil

    akun = _akun_aktif(path)
    nama_akun = [a["name"] for a in akun]

    untuk_tampil = []
    for tx in txs:
        if not isinstance(tx, dict):
            return {"ok": False, "error": "hasil_parser_rusak",
                    "message": "Ada transaksi dari parser yang bukan bentuk yang dikenal."}
        aid, anama = _cocokkan_akun(tx.get("account_hint"), akun)
        tid, tnama = _cocokkan_akun(tx.get("to_account_hint"), akun)
        butuh_akun = aid is None and len(akun) != 1
        # Transfer butuh DUA akun: `src/schema.sql:68-74` mewajibkan
        # `to_account_id` terisi untuk direction='transfer'. Kalau akun tujuan
        # belum jelas, itu harus dikatakan di draft — bukan baru ketahuan saat
        # simpan dengan pesan yang salah (bug 22 Okt 2026).
        butuh_tujuan = tx.get("direction") == "transfer" and tid is None
        # `flow_type` non-string (mis. list) tidak boleh jadi kunci dict —
        # itu TypeError di jalur yang seharusnya mengembalikan kode.
        ftype = tx.get("flow_type")
        sifat = LABEL_SIFAT.get(ftype, ftype) if isinstance(ftype, str) else None
        untuk_tampil.append({
            **tx,
            "account_id": aid,
            "account_name": anama,
            "to_account_id": tid,
            "to_account_name": tnama,
            "butuh_akun": butuh_akun,
            "butuh_akun_tujuan": butuh_tujuan,
            "sifat": sifat,
        })

    return {"ok": True, "draft": {
        "transactions": untuk_tampil,
        "question": d.get("question"),
        "akun_kandidat": nama_akun,
        "perlu_akun": any(t["butuh_akun"] for t in untuk_tampil),
        "perlu_akun_tujuan": any(t["butuh_akun_tujuan"] for t in untuk_tampil),
    }}


def render_draft(hasil):
    """Draft -> teks untuk ditampilkan di chat. Tidak menyimpan apa pun.

    Penjaga bentuk (perbaikan review ronde 6, 9 Okt 2026): kelas yang sama
    dengan penjaga `draft()`/`simpan()` — pemanggil yang menyerahkan hasil
    berbentuk salah (`None`, teks, dict tanpa `draft` yang benar) dulu menerima
    `AttributeError` alih-alih teks. Fungsi ini yang menampilkan pesan ke chat,
    jadi ia tidak boleh jadi tempat exception muncul.
    """
    if not isinstance(hasil, dict):
        return "Gagal mengurai: hasil parser tidak dikenal."
    if not hasil.get("ok"):
        return "Gagal mengurai: %s" % hasil.get("message", "sebab tidak diketahui")

    d = hasil.get("draft") or {}
    if not isinstance(d, dict):
        return "Gagal mengurai: isi draft bukan bentuk yang dikenal."
    txs = d.get("transactions") or []
    if not isinstance(txs, list):
        return "Gagal mengurai: daftar transaksi bukan daftar."
    if not txs:
        return d.get("question") or "Aku tidak menemukan transaksi di pesan itu."

    baris = []
    for i, tx in enumerate(txs, 1):
        if not isinstance(tx, dict):
            return "Gagal mengurai: ada transaksi yang bukan bentuk yang dikenal."
        akun = tx.get("account_name") or "(akun belum jelas)"
        tujuan = ""
        if tx.get("flow_type") == "transfer":
            tujuan = " -> %s" % (tx.get("to_account_name") or "(akun tujuan belum jelas)")
        tgl = tx.get("occurred_on", "-")
        # Penjaga tipe (perbaikan review ronde 5): `occurred_on` dari model bisa
        # bukan teks (mis. angka). Sebelum ini `tgl += "..."` melempar TypeError
        # saat `assumed_date` truthy. Modul ini selalu memakai KODE/nilai yang
        # bisa ditampilkan, bukan exception.
        if not isinstance(tgl, str):
            tgl = str(tgl) if tgl is not None else "-"
        if tx.get("assumed_date"):
            tgl += " (dianggap hari ini)"
        baris.append("  %d. %s  %s  %s%s  %s" % (
            i, db.rupiah(tx.get("amount")), tx.get("sifat", "?"), akun, tujuan, tgl))
        if tx.get("note"):
            baris.append("     catatan: %s" % tx["note"])

    ada_transfer = any(isinstance(t, dict) and t.get("flow_type") == "transfer"
                       for t in txs)
    ekor = []
    if d.get("perlu_akun"):
        # Untuk transfer, yang belum jelas adalah akun ASAL — bukan "akun"
        # tanpa keterangan. Pesan lama menyebut "akun tidak disebutkan" padahal
        # akun tujuan sudah disebut Deny (bug 22 Okt 2026).
        ekor.append("  %s belum jelas. Pilih salah satu: %s"
                    % ("Akun asal" if ada_transfer else "Akun",
                       ", ".join(d.get("akun_kandidat") or [])))
    if d.get("perlu_akun_tujuan"):
        ekor.append("  Akun tujuan belum jelas. Pilih salah satu: %s"
                    % ", ".join(d.get("akun_kandidat") or []))
    if ada_transfer and (d.get("perlu_akun") or d.get("perlu_akun_tujuan")):
        ekor.append("  Tulis lengkap: 'pindah dana 100000 dari Mandiri ke Tabungan'.")
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

    # Penjaga tipe field (perbaikan review ronde 4, 9 Okt 2026). Sebelum ini
    # field konfirmasi non-string (`{"pengirim": 1}`, `{"teks": ["simpan"]}`,
    # `{"kanal": 99}`) membuat `.strip()` melempar AttributeError ke pemanggil —
    # padahal docstring `simpan()` berjanji "tidak pernah melempar exception
    # untuk penolakan", dan `periksa_konfirmasi()` sudah memakai pola ini di
    # tingkat atas (`isinstance(konfirmasi, dict)` -> `konfirmasi_rusak`).
    # Field yang HILANG tetap bukan `konfirmasi_rusak`: ia punya kode sendiri
    # (`bukan_deny` / `konfirmasi_kosong` / `kanal_kosong`). Yang ditolak di
    # sini hanya field yang ADA tapi bukan teks — fail-closed, bukan exception.
    pengirim_mentah = konfirmasi.get("pengirim")
    if pengirim_mentah is not None and not isinstance(pengirim_mentah, str):
        return ("konfirmasi_rusak",
                "Field 'pengirim' bukan teks. Draft belum disimpan.")
    pengirim = (pengirim_mentah or "").strip().lower()
    if pengirim != MANUSIA:
        return ("bukan_deny",
                "Perintah simpan hanya sah kalau datang dari Deny sendiri. "
                "Yang mengirim ini '%s', bukan Deny. Draft belum disimpan."
                % (pengirim or "tidak disebutkan"))

    teks_mentah = konfirmasi.get("teks")
    if teks_mentah is not None and not isinstance(teks_mentah, str):
        return ("konfirmasi_rusak",
                "Field 'teks' bukan teks. Draft belum disimpan.")
    teks = (teks_mentah or "").strip()
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

    # Penjaga negasi — diperiksa SETELAH kita tahu ada kata afirmatif.
    # Urutannya penting: "jangan simpan" memuat kata afirmatif "simpan", jadi
    # tanpa penjaga ini ia lolos dan tertulis ke ledger. Fail-closed berarti
    # penyangkal menang. Ditaruh setelah cek afirmatif supaya teks tanpa
    # perintah sama sekali ("nanti saja") tetap diberi kode `tidak_afirmatif`
    # yang lebih tepat, bukan `ditolak`.
    #
    # CATATAN (ronde 3): penjaga ini sekarang HANYA memilih kode pesan yang
    # lebih tepat. Yang benar-benar menjaga adalah daftar putih di bawah —
    # lihat `perintah_diizinkan()`. Daftar hitam penyangkal tidak pernah
    # lengkap ('ndak', 'kagak', 'udah', 'no' ...), jadi ia tidak boleh jadi
    # gerbang; kalau ia yang jadi gerbang, bentuk yang tidak terdaftar lolos.
    if (any(k in rendah for k in NEGASI_SUB)
            or any(re.search(r"\b%s\b" % re.escape(k), rendah)
                   for k in NEGASI_KATA)):
        return ("ditolak",
                "Kalimat itu memuat kata penyangkalan ('jangan', 'tidak', "
                "'batal', 'nanti', dan sejenisnya), jadi bunyinya seperti "
                "penolakan atau penundaan — bukan perintah simpan. Aku "
                "berhenti. Balas \"simpan\" kalau memang mau disimpan.")

    # Pertanyaan bukan perintah. "simpan?" / "apa ya" mengandung kata afirmatif
    # (kata utuh "ya") tapi sedang bertanya, bukan menyuruh — fail-closed:
    # berhenti. Kata tanya dicocokkan sebagai kata utuh supaya "siapa" tidak
    # ikut tertangkap oleh "apa".
    if "?" in teks or any(re.search(r"\b%s\b" % k, rendah) for k in KATA_TANYA):
        return ("pertanyaan",
                "Kalimat itu berbentuk pertanyaan, bukan perintah simpan. "
                "Aku berhenti. Balas \"simpan\" kalau memang mau disimpan.")

    # ── GERBANG SEBENARNYA: daftar putih ────────────────────────────────────
    # Sampai sini teks sudah memuat kata afirmatif, tidak memuat penyangkal
    # yang kita kenal, dan bukan pertanyaan. Itu BELUM cukup: daftar hitam di
    # atas selalu bisa bocor ('ndak usah simpan', 'no simpan', 'sudah saya
    # simpan' — semuanya memuat "simpan" dan tidak memuat penyangkal
    # terdaftar). Jadi keputusan akhirnya bukan "bukan penolakan", melainkan
    # "bentuk perintah yang diakui". Apa pun di luar daftar putih berhenti.
    if not perintah_diizinkan(teks):
        return ("ditolak",
                "Kalimat itu bukan salah satu bentuk perintah simpan yang "
                "diakui (mis. \"simpan\", \"ya simpan\", \"tolong catat\"). "
                "Aku berhenti — ragu berarti berhenti. Balas \"simpan\" kalau "
                "memang mau disimpan.")

    kanal_mentah = konfirmasi.get("kanal")
    if kanal_mentah is not None and not isinstance(kanal_mentah, str):
        return ("konfirmasi_rusak",
                "Field 'kanal' bukan teks. Draft belum disimpan.")
    kanal = (kanal_mentah or "").strip()
    if not kanal:
        return ("kanal_kosong",
                "Asal chat konfirmasi tidak disebutkan — tidak bisa dilacak. "
                "Draft belum disimpan.")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. SIMPAN — satu-satunya jalur tulis, dan ia menuntut konfirmasi
# ─────────────────────────────────────────────────────────────────────────────
def _teks_aman(nilai):
    """Nilai apa pun -> nilai yang PASTI bisa ditulis ke JSON, atau None.

    Perbaikan review ronde 6 (9 Okt 2026): `waktu` di konfirmasi tidak pernah
    dijaga tipenya, padahal ia masuk ke jejak asal lewat `json.dumps`. Pemanggil
    chat yang wajar mengirim `datetime` (bukan teks) — dan `json.dumps` melempar
    `TypeError: Object of type datetime is not JSON serializable` **sesudah**
    `db.save_transactions` berhasil. Akibatnya: baris ledger sudah TERTULIS,
    tapi jejak asalnya hilang dan pemanggil menerima stack trace. Kartu ini
    menuntut sebaliknya — setiap penyimpanan harus bisa dilacak.

    Semua nilai dinormalkan SEBELUM penyimpanan, jadi tidak ada lagi langkah
    yang bisa gagal setelah ledger tersentuh. Jejak selalu berisi TEKS supaya
    bentuknya seragam untuk siapa pun yang membacanya.
    """
    if nilai is None or isinstance(nilai, str):
        return nilai
    if isinstance(nilai, datetime):
        return nilai.isoformat(timespec="seconds")
    try:
        return json.dumps(nilai, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(nilai)


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
    # Serialisasi diperiksa SEBELUM berkas dibuka: kalau nilainya tidak bisa
    # ditulis, jangan tinggalkan berkas kosong yang terlihat seperti jejak.
    baris = json.dumps(entri, ensure_ascii=False)
    with open(p, "a", encoding="utf-8") as f:
        f.write(baris + "\n")
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

    # Penjaga bentuk draft (kelas cacat sama dengan penjaga tipe konfirmasi di
    # atas, dan sengaja ditutup di ronde yang sama). `draft_hasil` yang bukan
    # dict — atau `draft`/`transactions` yang berbentuk salah — dulu melempar
    # AttributeError/TypeError ke pemanggil, padahal docstring di atas berjanji
    # tidak melempar untuk penolakan. Fail-closed: kembalikan kode.
    if not draft_hasil or not isinstance(draft_hasil, dict) \
            or not draft_hasil.get("ok"):
        return {"ok": False, "error": "draft_tidak_sah",
                "message": "Draftnya tidak sah atau gagal diurai.", "tersimpan": 0}

    isi_draft = draft_hasil.get("draft")
    if isi_draft is not None and not isinstance(isi_draft, dict):
        return {"ok": False, "error": "draft_tidak_sah",
                "message": "Isi draft bukan bentuk yang dikenal.", "tersimpan": 0}

    txs = (isi_draft or {}).get("transactions") or []
    if not isinstance(txs, list):
        return {"ok": False, "error": "draft_tidak_sah",
                "message": "Daftar transaksi di draft bukan daftar.", "tersimpan": 0}
    if not txs:
        return {"ok": False, "error": "draft_kosong",
                "message": "Tidak ada transaksi di draft itu.", "tersimpan": 0}

    items = []
    for i, tx in enumerate(txs, 1):
        if not isinstance(tx, dict):
            return {"ok": False, "error": "draft_tidak_sah",
                    "message": "Transaksi ke-%d bukan bentuk yang dikenal." % i,
                    "tersimpan": 0}
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

    # Jejak asal dibangun & dinormalkan SEBELUM ledger tersentuh (perbaikan
    # review ronde 6). Sebelum ini `waktu` mentah dari konfirmasi langsung
    # masuk `json.dumps` SETELAH `db.save_transactions` berhasil: pemanggil
    # chat yang mengirim `datetime` (wajar) membuat baris ledger tertulis
    # sementara jejak asalnya hilang dan exception naik ke pemanggil. Kartu
    # ini menuntut setiap penyimpanan bisa dilacak, jadi tidak boleh ada
    # langkah yang masih bisa gagal sesudah baris masuk.
    asal = {
        "pengirim": _teks_aman(konfirmasi.get("pengirim")),
        "kanal": _teks_aman(konfirmasi.get("kanal")),
        "waktu": _teks_aman(konfirmasi.get("waktu"))
                 or datetime.now().isoformat(timespec="seconds"),
        "teks": _teks_aman(konfirmasi.get("teks")),
    }

    try:
        ids = db.save_transactions(items, path=path)
    except Exception as e:
        # Pesan dari db.py sudah spesifik (akun tidak ada, flow_type tidak
        # cocok arah). Teruskan apa adanya — itu yang menolong Deny memperbaiki.
        return {"ok": False, "error": "gagal_simpan", "message": str(e),
                "tersimpan": 0}

    try:
        berkas = _catat_asal(asal, ids, path_log=path_log)
    except OSError as e:
        # Baris ledger SUDAH masuk; gagal menulis berkas jejak bukan alasan
        # untuk melempar exception ke pemanggil — tapi juga tidak boleh
        # dilaporkan sebagai "beres". Kembalikan apa adanya supaya pemanggil
        # bisa menampilkan bahwa asalnya tidak terekam.
        return {"ok": True, "saved_ids": ids, "count": len(ids), "asal": asal,
                "jejak": None, "jejak_error": "gagal_catat_jejak: %s" % e}
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
