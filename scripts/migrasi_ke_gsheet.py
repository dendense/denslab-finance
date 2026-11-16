#!/usr/bin/env python3
"""Pindahkan data finance (SQLite + jadwal hutang) ke backend Google Sheet.

Pakai:
    python3 scripts/migrasi_ke_gsheet.py --url <URL Web App> --token <ADMIN_TOKEN>
    python3 scripts/migrasi_ke_gsheet.py --url ... --token ... --password   # pasang password saja
    python3 scripts/migrasi_ke_gsheet.py --ekspor keluar.json                # tanpa kirim, untuk diperiksa

Yang dibaca (READ-ONLY, tidak ada yang diubah):
    Data/finance/finance.db          semua tabel kecuali `sesi`
    Data/finance/LIST-HUTANG.md      jadwal cicilan  -> tab jadwal_hutang
    Data/finance/HUTANG-LUNAS.json   status lunas    -> tab hutang_lunas
    Data/finance/terhapus.log        jejak hapus     -> tab terhapus

Database dibuka dengan `mode=ro`: skrip ini tidak bisa menulis ke finance.db
walaupun ada bug di dalamnya.

Kalau tab transactions di Sheet sudah berisi, impor DITOLAK kecuali --timpa.
Itu disengaja: setelah mulai mencatat dari HP, impor ulang dari Mac akan
menghapus transaksi yang dicatat dari HP.
"""
import argparse
import getpass
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABEL_DB = ("accounts", "categories", "transactions", "analyses", "savings_goals")


def _data_dir(arg):
    if arg:
        return Path(arg)
    return Path(os.environ.get("FINANCE_DATA") or (ROOT.parent / "Data" / "finance"))


def ekspor(data_dir):
    """Kembalikan {"data": {tabel: [baris]}, "seq": {tabel: n}, "peringatan": [...]}."""
    data_dir = Path(data_dir)
    db_path = data_dir / "finance.db"
    if not db_path.is_file():
        raise SystemExit("finance.db tidak ditemukan di %s" % data_dir)
    peringatan = []
    data = {}
    conn = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for t in TABEL_DB:
            data[t] = [dict(r) for r in conn.execute("SELECT * FROM %s ORDER BY id" % t)]
        seq = {r["name"]: r["seq"] for r in conn.execute("SELECT name, seq FROM sqlite_sequence")}
    finally:
        conn.close()

    # Jadwal + lunas: pakai pembaca server.py sendiri, supaya aturan format
    # (dan pesan galatnya) sama persis dengan yang selama ini dipakai panel.
    os.environ["FINANCE_DATA"] = str(data_dir)
    sys.path.insert(0, str(ROOT / "src"))
    import server  # noqa: E402

    data["jadwal_hutang"] = []
    data["hutang_lunas"] = []
    if (data_dir / "LIST-HUTANG.md").is_file():
        try:
            hutang = server._baca_hutang()
            for u in hutang["utang"]:
                for r in u["baris"]:
                    data["jadwal_hutang"].append({
                        "nama_utang": u["nama"], "nomor": r["nomor"], "nominal": r["nominal"],
                        "jatuh_tempo": r["jatuh_tempo"], "jatuh_tempo_teks": r["jatuh_tempo_teks"]})
        except server._GagalHutang as e:
            peringatan.append("Jadwal hutang tidak dibaca: %s" % e.pesan)
        try:
            for e in server._baca_lunas():
                data["hutang_lunas"].append({k: e.get(k) for k in (
                    "nama_utang", "jatuh_tempo", "nomor", "nominal", "ditandai_pada",
                    "transaksi_id", "transaksi_nominal", "transaksi_tanggal")})
        except server._GagalHutang as e:
            peringatan.append("Status lunas tidak dibaca: %s" % e.pesan)
    else:
        peringatan.append("LIST-HUTANG.md tidak ada — tab jadwal_hutang dibiarkan kosong.")

    data["terhapus"] = []
    log = data_dir / "terhapus.log"
    if log.is_file():
        for i, baris in enumerate(log.read_text(encoding="utf-8").splitlines(), 1):
            if not baris.strip():
                continue
            try:
                d = json.loads(baris)
            except json.JSONDecodeError:
                peringatan.append("terhapus.log baris %d bukan JSON, dilewati." % i)
                continue
            data["terhapus"].append({
                "dihapus_pada": d.get("dihapus_pada"),
                "transaksi": json.dumps(d.get("transaksi"), ensure_ascii=False)})
    return {"data": data, "seq": seq, "peringatan": peringatan}


def kirim(url, amplop):
    """POST amplop ke Web App. Redirect 302 Google diikuti urllib sebagai GET — itu yang benar."""
    req = urllib.request.Request(
        url, data=json.dumps(amplop).encode("utf-8"),
        headers={"Content-Type": "text/plain;charset=utf-8"})
    with urllib.request.urlopen(req, timeout=300) as r:
        teks = r.read().decode("utf-8")
    try:
        return json.loads(teks)
    except json.JSONDecodeError:
        raise SystemExit("Balasan bukan JSON (URL Web App benar? akses 'Anyone'?):\n%s" % teks[:400])


def _admin(url, token, path, body=None):
    body = dict(body or {})
    body["admin_token"] = token
    return kirim(url, {"method": "POST", "path": path, "body": body})


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", help="URL Web App (…/exec)")
    ap.add_argument("--token", help="ADMIN_TOKEN dari log siapkan()")
    ap.add_argument("--data", help="folder data (bawaan: FINANCE_DATA atau ../Data/finance)")
    ap.add_argument("--timpa", action="store_true", help="timpa data yang sudah ada di Sheet")
    ap.add_argument("--password", action="store_true", help="hanya pasang/ganti password")
    ap.add_argument("--ekspor", metavar="BERKAS", help="tulis hasil ekspor ke berkas, tanpa kirim")
    a = ap.parse_args()

    if a.ekspor:
        hasil = ekspor(_data_dir(a.data))
        Path(a.ekspor).write_text(json.dumps(hasil, ensure_ascii=False, indent=1), encoding="utf-8")
        for p in hasil["peringatan"]:
            print("! " + p)
        print("Ditulis ke %s: %s" % (a.ekspor, {k: len(v) for k, v in hasil["data"].items()}))
        return 0

    if not a.url or not a.token:
        ap.error("--url dan --token wajib (kecuali --ekspor)")

    if not a.password:
        hasil = ekspor(_data_dir(a.data))
        for p in hasil["peringatan"]:
            print("! " + p)
        print("Mengirim: %s" % {k: len(v) for k, v in hasil["data"].items()})
        r = _admin(a.url, a.token, "/api/admin/impor",
                   {"data": hasil["data"], "seq": hasil["seq"], "timpa": a.timpa})
        b = r.get("body") or {}
        if not b.get("ok"):
            print("GAGAL: %s" % (b.get("message") or b))
            return 1
        print("Impor selesai: %s" % b.get("diimpor"))

    st = _admin(a.url, a.token, "/api/admin/status").get("body") or {}
    if a.password or not st.get("sudah_ada_password"):
        pw = getpass.getpass("Password aplikasi (min 6 karakter): ")
        if pw != getpass.getpass("Ulangi password: "):
            print("Dua password berbeda. Password TIDAK dipasang.")
            return 1
        b = _admin(a.url, a.token, "/api/admin/password", {"password": pw}).get("body") or {}
        print("Password dipasang." if b.get("ok") else "GAGAL: %s" % b.get("message"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
