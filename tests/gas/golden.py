#!/usr/bin/env python3
"""Rekam balasan server Python ASLI sebagai acuan untuk backend Apps Script.

    python3 tests/gas/golden.py <folder-data-SALINAN> <keluaran.json>

Folder data HARUS salinan (skrip ini menulis: transaksi uji, kredensial,
sesi). Skrip menolak jalan kalau foldernya adalah folder data asli.

Alur:
  1. Ekspor tabel lewat scripts/migrasi_ke_gsheet.ekspor() — jalur yang sama
     dengan migrasi sungguhan, jadi uji ikut menguji konversinya.
  2. Nyalakan src/server.py di thread (port acak), pasang password, login.
  3. Jalankan daftar KASUS: GET semua endpoint, lalu serangkaian tulis
     (simpan/ubah/hapus/akun/target/hutang/analisa/parse), lalu GET lagi.
     Model AI dipalsukan (urllib.request.urlopen ditimpa) dengan balasan
     yang juga disimpan ke keluaran, supaya sisi JS memakai teks yang sama.
  4. Simpan {ekspor, kasus:[{method,path,query,body,status,hasil}], ai_palsu, hari_ini}.

tests/gas/banding.test.js memutar ulang kasus yang sama ke backend JS.
"""
import http.client
import http.cookies
import io
import json
import os
import sys
import threading
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(sys.argv[1]).resolve()
KELUAR = Path(sys.argv[2])
ASLI = (ROOT.parent / "Data" / "finance").resolve()
if DATA == ASLI:
    raise SystemExit("Tolak: ini folder data ASLI. Pakai salinan.")

os.environ["FINANCE_DATA"] = str(DATA)
os.environ["KENARI_API_KEY"] = "kunci-uji"
os.environ.pop("KENARI_BASE", None)
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import migrasi_ke_gsheet  # noqa: E402

EKSPOR = migrasi_ke_gsheet.ekspor(DATA)

import urllib.request  # noqa: E402
import server  # noqa: E402
import auth  # noqa: E402
import db  # noqa: E402

# ── AI palsu ────────────────────────────────────────────────────────────────
def _sse(obj_teks):
    potong = [obj_teks[i:i + 37] for i in range(0, len(obj_teks), 37)]
    baris = ["data: " + json.dumps({"choices": [{"delta": {"content": p}}]}) for p in potong]
    return "\n\n".join(baris + ["data: [DONE]"]) + "\n"


PARSER = {
    "makan siang 25rb sama parkir 5rb": json.dumps({"transactions": [
        {"direction": "out", "amount": 25000, "category": "Makan", "note": "makan siang",
         "occurred_on": None, "account_hint": None, "to_account_hint": None, "assumed_date": True},
        {"direction": "out", "amount": "5000", "category": "Parkir", "note": "parkir",
         "occurred_on": "2026-11-01", "account_hint": None, "to_account_hint": None,
         "assumed_date": False}], "question": None}),
    "pindah dana 100000 dari Mandiri ke Tabungan": "Tentu! ```json\n" + json.dumps({"transactions": [
        {"direction": "transfer", "amount": 100000, "category": "Lainnya", "note": "pindah dana",
         "occurred_on": None, "account_hint": "Tabungan", "to_account_hint": None,
         "assumed_date": True}], "question": None}) + "\n```",
    "bayar cicilan spaylater 450000": json.dumps({"transactions": [
        {"direction": "out", "amount": 450000, "category": "Tagihan",
         "note": "bayar cicilan spaylater", "occurred_on": None, "account_hint": None,
         "assumed_date": True}], "question": None}),
    "topup saldo kenari 200rb": json.dumps({"transactions": [
        {"direction": "transfer", "amount": 200000, "category": None,
         "note": "topup saldo kenari", "occurred_on": None, "account_hint": None,
         "assumed_date": True}], "question": None}),
    "halo monica apa kabar": json.dumps({"transactions": [], "question": "halo monica apa kabar"}),
    "berapa ya": json.dumps({"transactions": [], "question": "Maksudnya transaksi apa? Sebutkan nominalnya."}),
    "nol rupiah": json.dumps({"transactions": [{"direction": "out", "amount": 0}], "question": None}),
    "prosa saja": "Maaf, saya tidak bisa membantu itu.",
}
ANALISA = json.dumps({
    "ringkasan": "Bulan ini uang masuk 12345678 dan konsumsi naik 40% dibanding bulan lalu. Oktober 2026 tercatat.",
    "per_kategori": {"Makan": "Makan naik 25 persen dari bulan lalu.",
                     "Transport": "Transport Rp 999.999.999 bulan ini."},
    "penutup": "Sisa bebas bisa ditabung."})
AI_PALSU = {"parser": {k: _sse(v) for k, v in PARSER.items()},
            "analisa": _sse(ANALISA), "status": json.dumps({"model": "model-palsu-menjawab"})}


class _Balas:
    def __init__(self, teks):
        self._b = teks.encode("utf-8")

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _urlopen_palsu(req, timeout=None):
    body = json.loads(req.data.decode("utf-8"))
    if body.get("max_tokens") == 5:
        return _Balas(AI_PALSU["status"])
    sistem = body["messages"][0]["content"]
    if sistem.startswith("Kamu parser"):
        return _Balas(AI_PALSU["parser"][body["messages"][1]["content"]])
    return _Balas(AI_PALSU["analisa"])


urllib.request.urlopen = _urlopen_palsu

# ── server di thread ────────────────────────────────────────────────────────
for f in ("kredensial.json",):
    if (DATA / f).exists():
        (DATA / f).unlink()
srv = server.HTTPServer(("127.0.0.1", 0), server.Handler)
server.Handler.log_message = lambda *a: None
threading.Thread(target=srv.serve_forever, daemon=True).start()
PORT = srv.server_address[1]
auth.pasang_password("rahasia-uji")
COOKIE = {}


def minta(method, path, query="", body=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=30)
    url = path + ("?" + query if query else "")
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json"}
    if COOKIE:
        h["Cookie"] = "; ".join("%s=%s" % kv for kv in COOKIE.items())
    c.request(method, url, body=data, headers=h)
    r = c.getresponse()
    for k, v in r.getheaders():
        if k.lower() == "set-cookie":
            ck = http.cookies.SimpleCookie(v)
            for n, m in ck.items():
                COOKIE[n] = m.value
    teks = r.read().decode("utf-8")
    try:
        return r.status, json.loads(teks)
    except json.JSONDecodeError:
        return r.status, teks


st, _ = minta("POST", "/api/auth", body={"password": "rahasia-uji"})
assert st == 200 and COOKIE.get("sesi"), "login gagal"

KASUS = []


def kasus(method, path, query="", body=None):
    st, hasil = minta(method, path, query, body)
    KASUS.append({"method": method, "path": path, "query": query, "body": body,
                  "status": st, "hasil": hasil})
    return hasil


def semua_get(label):
    bulan = [b["month"] for b in kasus("GET", "/api/months")["bulan"]]
    hari_ini = date.today().strftime("%Y-%m")
    for q in ["", "month=" + hari_ini] + ["month=" + b for b in bulan] + ["month=1999-01"]:
        kasus("GET", "/api/summary", q)
    for q in ["", "limit=5", "direction=out", "direction=transfer&limit=3"] + \
            ["month=" + b for b in bulan]:
        kasus("GET", "/api/transactions", q)
    for q in ["", "direction=in", "direction=out"]:
        kasus("GET", "/api/categories", q)
    for q in ["", "all=1"]:
        kasus("GET", "/api/accounts", q)
    for q in ["", "months=1", "months=12", "months=99", "months=abc"]:
        kasus("GET", "/api/trend", q)
    for b in bulan + [hari_ini]:
        kasus("GET", "/api/spending-by-category", "month=" + b)
        kasus("GET", "/api/suggestions", "month=" + b)
        kasus("GET", "/api/analysis", "month=" + b)
    kasus("GET", "/api/analysis")
    kasus("GET", "/api/savings")
    kasus("GET", "/api/debts")
    return bulan


bulan = semua_get("awal")

# ── tulis ───────────────────────────────────────────────────────────────────
akun = sorted([a for a in EKSPOR["data"]["accounts"] if a["is_active"]], key=lambda a: a["id"])
seq_tx = EKSPOR["seq"].get("transactions", 0)
seq_akun = EKSPOR["seq"].get("accounts", 0)
a0 = akun[0]
today = date.today().isoformat()

kasus("POST", "/api/accounts", body={"name": "Uji Dompet", "kind": "ewallet",
                                     "opening_balance": "150000.6"})
id_akun_baru = seq_akun + 1
kasus("POST", "/api/accounts", body={"name": a0["name"].upper(), "kind": "bank"})
kasus("POST", "/api/accounts", body={"name": "X", "kind": "kripto"})
kasus("POST", "/api/accounts", body={"name": "Y", "kind": "cash", "opening_balance": True})
kasus("POST", "/api/accounts", body={"name": "  ", "kind": "cash"})

kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "amount": 45000, "category": "makan",
     "account_hint": a0["name"].lower(), "note": "makan siang"},
    {"occurred_on": today, "direction": "transfer", "amount": 100000,
     "account_id": a0["id"], "to_account_hint": "uji dom"},
    {"occurred_on": today, "direction": "in", "amount": "2500000", "category": "Gaji",
     "account_id": a0["id"], "note": "gaji"}]})
tx1, tx2, tx3 = seq_tx + 1, seq_tx + 2, seq_tx + 3
next_tx = seq_tx + 4

jadwal = EKSPOR["data"]["jadwal_hutang"]
sudah = {(e["nama_utang"], e["jatuh_tempo"]) for e in EKSPOR["data"]["hutang_lunas"]}
belum = sorted([j for j in jadwal if (j["nama_utang"], j["jatuh_tempo"]) not in sudah],
               key=lambda j: (j["jatuh_tempo"], j["nama_utang"], j["nomor"]))
if belum:
    kasus("POST", "/api/save", body={"transactions": [
        {"occurred_on": today, "direction": "out", "flow_type": "debt_payment",
         "amount": belum[0]["nominal"], "category": "Tagihan", "account_id": a0["id"],
         "note": "bayar cicilan"}]})
    next_tx += 1

kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "flow_type": "income", "amount": 1000,
     "account_id": a0["id"]}]})
kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "amount": 1000, "account_hint": "TidakAdaAkun"}]})
kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "amount": 1000}]})
kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "transfer", "amount": 1000, "to_account_id": a0["id"]}]})
kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "amount": 0, "account_id": a0["id"]}]})
kasus("POST", "/api/save", body={"transactions": []})
kasus("POST", "/api/save", body={"transactions": [
    {"occurred_on": today, "direction": "out", "amount": 5000, "account_id": a0["id"],
     "category": "Makan"},
    {"occurred_on": today, "direction": "out", "amount": 5000, "account_id": 999999}]})

kasus("PATCH", "/api/transactions/%d" % tx1, body={"amount": "47000.4", "note": "makan siang (koreksi)"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "receivable"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "transfer"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "transfer", "to_account_id": id_akun_baru})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "expense", "category": "Belanja"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "expense"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"occurred_on": "2026-02-30"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"occurred_on": "2026-02-28T10:00"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"amount": "abc"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"amount": -5})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"flow_type": "hadiah"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"direction": "in"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={"source": "statement"})
kasus("PATCH", "/api/transactions/%d" % tx1, body={})
kasus("PATCH", "/api/transactions/%d" % tx3, body={"account_hint": "uji"})
kasus("PATCH", "/api/transactions/%d" % tx3, body={"to_account_id": a0["id"]})
kasus("PATCH", "/api/transactions/999999", body={"note": "x"})
kasus("DELETE", "/api/transactions/%d" % tx2)
kasus("DELETE", "/api/transactions/999999")

kasus("PATCH", "/api/accounts/%d" % id_akun_baru, body={"name": "Uji Dompet Ganti"})
kasus("PATCH", "/api/accounts/%d" % id_akun_baru, body={"name": a0["name"]})
kasus("PATCH", "/api/accounts/%d" % id_akun_baru, body={"is_active": False})
kasus("PATCH", "/api/accounts/%d" % a0["id"], body={"kind": "cash", "opening_balance": 1})
kasus("PATCH", "/api/accounts/%d" % a0["id"], body={})
kasus("PATCH", "/api/accounts/999999", body={"name": "Z"})

tabungan = [a for a in akun if a["kind"] in ("savings", "investment")]
kasus("POST", "/api/savings", body={"name": "Dana darurat", "target_amount": "5000000",
                                    "account_hint": (tabungan or akun)[0]["name"],
                                    "target_date": "2027-06-30"})
kasus("POST", "/api/savings", body={"name": "x", "target_amount": 100, "target_date": "2027-02-30"})
kasus("POST", "/api/savings", body={"name": "x", "target_amount": "nol"})
kasus("POST", "/api/savings", body={"name": "x", "target_amount": 100, "account_hint": "TidakAda"})
kasus("POST", "/api/savings", body={"name": "", "target_amount": 100})
kasus("POST", "/api/savings", body={"name": "x"})
kasus("GET", "/api/savings")
kasus("GET", "/api/debts")
if belum:
    kasus("POST", "/api/debts/batalkan", body={"nama_utang": belum[0]["nama_utang"],
                                               "jatuh_tempo": belum[0]["jatuh_tempo"]})
    kasus("POST", "/api/debts/batalkan", body={"nama_utang": belum[0]["nama_utang"],
                                               "jatuh_tempo": belum[0]["jatuh_tempo"]})
kasus("POST", "/api/debts/batalkan", body={"nama_utang": ""})

for teks in PARSER:
    kasus("POST", "/api/parse", body={"text": teks})
kasus("POST", "/api/parse", body={"text": "   "})
kasus("GET", "/api/ai-status")

bulan_selesai = [b for b in bulan if b < date.today().strftime("%Y-%m")]
for b in bulan_selesai[:2]:
    kasus("POST", "/api/analysis", body={"month": b})
kasus("POST", "/api/analysis", body={"month": date.today().strftime("%Y-%m")})
kasus("POST", "/api/analysis", body={"month": "2026-1"})
kasus("POST", "/api/analysis", body={"month": "1999-01"})
kasus("POST", "/api/analysis", body={})
if bulan_selesai:
    kasus("DELETE", "/api/analysis/" + bulan_selesai[0])
kasus("DELETE", "/api/analysis/1999-01")

kasus("DELETE", "/api/savings")
kasus("DELETE", "/api/savings")
kasus("GET", "/api/nggak-ada")

semua_get("akhir")

srv.shutdown()
KELUAR.write_text(json.dumps({"ekspor": EKSPOR, "kasus": KASUS, "ai_palsu": AI_PALSU,
                              "hari_ini": date.today().isoformat()},
                             ensure_ascii=False, indent=1), encoding="utf-8")
print("golden: %d kasus -> %s" % (len(KASUS), KELUAR))
