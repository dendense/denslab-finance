#!/usr/bin/env python3
"""Lapisan akses data finance — SQLite lokal.

Semua angka yang keluar ke UI atau laporan HARUS lewat modul ini.
Tidak ada perhitungan saldo yang diulang di tempat lain: kalau rumusnya
ditulis dua kali, cepat atau lambat keduanya berbeda dan tidak ada yang tahu
mana yang benar.

Jumlah uang disimpan sebagai INTEGER rupiah penuh (tanpa sen). Di Indonesia
sen tidak dipakai dalam praktik, dan integer menghindari galat pembulatan
yang khas muncul saat menjumlahkan float.
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

# Struktur folder:
#   finance/          <- repo publik: KODE saja
#     src/            <- berkas ini
#     tests/          <- uji
#   finance-pribadi/  <- DATA: di LUAR repo, tidak akan pernah masuk git
#
# Kenapa data dipisah FISIK, bukan cuma di-.gitignore:
# `.gitignore` hanya mencegah `git add .` menambahkan berkas. Dia tidak
# mencegah `git add -f`, alat yang mengabaikan .gitignore, atau salah ketik.
# Dan begitu data keuangan masuk satu commit, menghapusnya tidak cukup — git
# menyimpan riwayat, dan berkasnya tetap bisa di-checkout siapa pun yang
# meng-clone. Pemisahan fisik mencegahnya; .gitignore hanya mengingatkan.
#
# Lokasi data bisa diganti lewat env FINANCE_DATA, supaya:
#   - Deny bisa memakai datanya dari folder mana pun
#   - arsip lain (mis. komputer kedua) bisa menunjuk ke tempat berbeda
#   - uji bisa mengarahkan ke database sementara tanpa menyentuh data asli
import os
import sys

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
REPO_DIR = ROOT_DIR

# Folder data: dari env, atau default di samping repo.
DATA_DIR = Path(os.environ.get("FINANCE_DATA")
                or (REPO_DIR.parent / "finance-pribadi"))


class _PathDB(str):
    """Path database yang MEMBACA `DB_PATH` terkini setiap kali dipakai.

    Kenapa ini ada — kejadian nyata, 7 Okt 2026:

    Seluruh fungsi di modul ini bertanda tangan `def f(..., path=DB_PATH)`.
    Default argumen di Python dievaluasi **sekali, saat fungsi didefinisikan** —
    jadi `path` sudah terkunci ke database saat import, dan menimpa `db.DB_PATH`
    SETELAH import tidak mengubah apa pun.

    Akibatnya nyata dan berbahaya: `tests/test_balance_inactive.py` mengarahkan
    `db.DB_PATH` ke database sementara di /tmp, MENCETAK path /tmp itu ke layar,
    lalu diam-diam membaca dan menulis ke database keuangan Deny. Ujinya
    berbohong tentang apa yang sedang diujinya — dan itu lebih buruk daripada
    uji yang gagal, karena tidak ada yang tahu ada yang salah.

    Dengan kelas ini, `path=DB_PATH` tetap apa adanya di 30 fungsi, tapi nilainya
    adalah objek yang menanyakan `DB_PATH` global saat dibutuhkan. Menimpa
    `db.DB_PATH = <path baru>` langsung berlaku untuk semua fungsi.
    """

    def __new__(cls, ambil):
        obj = super().__new__(cls, str(ambil()))
        obj._ambil = ambil
        return obj

    def _nilai(self):
        return str(self._ambil())

    # str-nya selalu mengikuti DB_PATH terkini
    def __str__(self):
        return self._nilai()

    def __fspath__(self):
        return self._nilai()

    def __repr__(self):
        return "_PathDB(%r)" % self._nilai()

    # Sifat-sifat Path yang dipakai kode ini (`.parent`, `.name`, `/.exists()`)
    def __getattr__(self, nama):
        n = self._nilai()
        # Path lebih benar untuk atribut seperti .parent (harus Path, bukan str)
        return getattr(Path(n), nama)

    # Operasi path: serahkan ke Path supaya hasilnya juga Path yang benar
    def __truediv__(self, lain):
        return Path(self._nilai()) / lain

    def exists(self):
        return Path(self._nilai()).exists()

    def __eq__(self, lain):
        return self._nilai() == str(lain)

    def __ne__(self, lain):
        return not self.__eq__(lain)

    def __hash__(self):
        return hash(str(self))


# `DB_PATH` adalah `_PathDB` yang menanyakan nilainya SAAT DIPAKAI, bukan saat
# import. Yang ditanyakan adalah atribut `DB_PATH` pada modul ini sendiri —
# kalau uji menimpa `db.DB_PATH = <path>`, ke-30 fungsi `path=DB_PATH` langsung
# ikut berubah.
def _nilai_db_path():
    """Baca `DB_PATH` dari modul ini (bukan dari variabel tertutup).

    Ini penting: kalau `_PathDB` menutup sebuah variabel lokal, menimpa
    `db.DB_PATH` akan mengganti nama di modul tanpa mengubah variabel tersebut —
    dan fungsi-fungsi `path=DB_PATH` akan diam-diam memakai path lama. Persis
    kegagalan yang membuat `tests/test_balance_inactive.py` menulis ke database
    keuangan Deny sambil mencetak path /tmp ke layar.
    """
    modul = sys.modules[__name__]
    v = getattr(modul, "DB_PATH", None)
    # Waspadai rekursi: kalau DB_PATH masih _PathDB (belum ditimpa), pakai default.
    if isinstance(v, _PathDB) or v is None:
        return DATA_DIR / "finance.db"
    return v


DB_PATH = _PathDB(lambda: _nilai_db_path())


def _path_aktif(path=None):
    """Path database yang harus dipakai sekarang.

    SATU-SATUNYA tempat yang menentukan path. Sebelum ini, 30 fungsi menyimpan
    default `path=DB_PATH` yang terkunci saat import — jadi menimpa `db.DB_PATH`
    tidak mengubah apa pun, dan uji yang mengarahkan ke /tmp tetap menulis ke
    database keuangan Deny tanpa ada yang tahu.
    """
    if path is None:
        return Path(str(DB_PATH))
    p = Path(str(path))
    if not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    return p

# Berkas penanda folder data. Fungsinya bukan mengunci apa pun — hanya menandai
# "folder ini memang tempat data finance", supaya kode bisa membedakan folder
# data sungguhan dari folder sembarangan.
PENANDA = ".finance-data"


def periksa_lokasi_data(path=None):
    """Periksa bahwa lokasi data memang tempat yang benar. Mengembalikan pesan
    kesalahan (str) kalau bermasalah, atau None kalau aman.

    Kenapa ini perlu ada — kejadian nyata, 3 Okt 2026:

    Saat menguji "orang baru clone lalu pakai", skrip dijalankan DI FOLDER CLONE
    dengan maksud memakai database clone. Ternyata `FINANCE_DATA` tidak di-set di
    lingkungan skrip itu, jadi `DATA_DIR` jatuh ke nilai bawaan dan kode menulis
    ke database keuangan Deny. Yang menyelamatkan hanya kebetulan: akun bernama
    "Tabungan" sudah ada sehingga `create_account` menolak.

    Pemisahan fisik melindungi dari salah-`git commit`. Ini melindungi dari
    salah-`jalankan` — folder yang salah dengan kode yang benar. Itu jenis
    kesalahan yang tidak bisa dibatalkan: transaksi uji tercampur ke catatan
    keuangan sungguhan, dan tidak ada cara membedakannya lagi.

    Aturannya sengaja sederhana dan tidak menebak-nebak:
      1. Folder belumada        -> izinkan (pemakaian pertama, wajar)
      2. Ada penanda            -> izinkan (folder data yang sah)
      3. Ada database TAPI tanpa penanda -> TOLAK (paling berbahaya: akan
         menulis ke database yang tidak kita kenali)
    """
    d = Path(path or DATA_DIR)
    if not d.exists():
        return None
    if (d / PENANDA).exists():
        return None
    db_ada = (d / "finance.db").exists()
    if db_ada and not (d / PENANDA).exists():
        return (
            "Folder data '%s' berisi database finance.db TAPI tidak punya "
            "berkas penanda '%s'.\n"
            "Ini biasanya berarti kode menunjuk ke folder yang salah — dan "
            "menulis ke sini bisa mencampur data uji ke catatan keuangan "
            "sungguhan.\n"
            "Kalau folder ini memang tempat datamu, tandai dengan:\n"
            "    touch %s\n"
            "Kalau bukan, arahkan ke folder yang benar:\n"
            "    export FINANCE_DATA=/path/ke/finance-pribadi" % (d, PENANDA, d / PENANDA)
        )
    return None


def pastikan_lokasi_aman(path=None):
    """Versi tegas: hentikan program kalau lokasi data bermasalah.

    Dipanggil dari `init_db()` — yaitu sekali saja saat server dinyalakan, bukan
    di setiap koneksi. Kalau dipanggil di setiap koneksi, uji yang memakai
    database sementara akan ikut terhenti tanpa alasan.
    """
    pesan = periksa_lokasi_data(path)
    if pesan:
        raise RuntimeError(pesan)


# ─────────────────────────────────────────────────────────────────────────────
# Koneksi
# ─────────────────────────────────────────────────────────────────────────────
@contextmanager
def connect(path=DB_PATH):
    """Koneksi dengan foreign key aktif. Commit kalau sukses, rollback kalau gagal."""
    conn = sqlite3.connect(str(_path_aktif(path)))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path=DB_PATH):
    """Buat skema dari schema.sql lalu isi data awal dari seed.sql. Aman diulang.

    Ini satu-satunya tempat yang memeriksa lokasi data, dan sengaja dipanggil
    dari sini: `init_db()` jalan sekali saat server dinyalakan, bukan di setiap
    koneksi. Kalau pemeriksaannya di setiap koneksi, uji yang memakai database
    sementara di /tmp akan ikut terhenti tanpa alasan.
    """
    # Hanya periksa folder data sebenarnya, bukan path sementara yang dipakai uji.
    p = _path_aktif(path)
    if str(p) == str(DB_PATH):
        pastikan_lokasi_aman()
    path = p

    # Tandai folder data supaya pemakaian berikutnya dikenali sebagai sah.
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.parent / PENANDA).touch(exist_ok=True)

    here = SRC_DIR
    with connect(path) as conn:
        conn.executescript((here / "schema.sql").read_text())
        conn.executescript((here / "seed.sql").read_text())
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Baca — angka
# ─────────────────────────────────────────────────────────────────────────────
def net_worth(path=DB_PATH):
    """Total kekayaan: total, likuid, tidak likuid, jumlah akun aktif."""
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM v_net_worth").fetchone()
    return dict(row) if row else {"net_worth": 0, "liquid": 0,
                                  "non_liquid": 0, "account_count": 0}


def account_balances(path=DB_PATH, include_inactive=False):
    """Saldo tiap akun, urut dari yang terbesar.

    PERHATIAN: `include_inactive` adalah argumen KETIGA. Selalu panggil dengan
    nama (`include_inactive=True`), jangan positional — urutan argumen di sini
    tidak seperti yang dibaca sekilas.
    """
    sql = "SELECT * FROM v_account_balances"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY balance DESC, name ASC"
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql)]


def monthly_summary(month=None, path=DB_PATH):
    """Ringkasan satu bulan ('YYYY-MM') berikut JUMLAH TRANSAKSI-nya.

    tx_count ikut dikembalikan supaya pemanggil bisa menyatakan berapa
    transaksi yang tercatat — tanpa itu angka terlihat lengkap padahal
    datanya mungkin bolong.

    Catatan penting: `total_out` adalah SEMUA uang yang keluar, dan itu
    BUKAN pengeluaran pribadi. Pakai `expense_real` kalau yang dimaksud
    konsumsi. Selisihnya bisa 4x lipat (lihat migrasi 002).
    """
    month = month or date.today().strftime("%Y-%m")
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM v_monthly_flow WHERE month = ?", (month,)
        ).fetchone()
    if not row:
        return {"month": month, "total_in": 0, "total_out": 0, "net": 0,
                "net_real": 0, "expense_real": 0, "receivable_out": 0,
                "debt_payment_out": 0,
                "tx_count": 0, "in_count": 0, "out_count": 0,
                "transfer_count": 0, "_ada_data": False}
    d = dict(row)
    d["_ada_data"] = True
    return d


def list_transactions(month=None, limit=None, direction=None, path=DB_PATH):
    """Transaksi terbaru dulu, dengan nama akun dan kategori ikut dibaca."""
    where, params = [], []
    if month:
        where.append("substr(t.occurred_on,1,7) = ?")
        params.append(month)
    if direction:
        where.append("t.direction = ?")
        params.append(direction)
    sql = """
        SELECT t.id, t.occurred_on, t.direction, t.flow_type, t.amount,
               t.note, t.source, t.created_at,
               a.name  AS account_name,
               a2.name AS to_account_name,
               c.name  AS category_name,
               c.direction AS category_direction
        FROM transactions t
        JOIN accounts a        ON a.id  = t.account_id
        LEFT JOIN accounts a2  ON a2.id = t.to_account_id
        LEFT JOIN categories c ON c.id  = t.category_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.occurred_on DESC, t.id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def get_categories(direction=None, path=DB_PATH):
    sql = "SELECT * FROM categories"
    params = []
    if direction:
        sql += " WHERE direction = ?"
        params.append(direction)
    sql += " ORDER BY direction, sort_order, name"
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def get_accounts(include_inactive=False, path=DB_PATH):
    sql = "SELECT * FROM accounts"
    if not include_inactive:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY kind, name"
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(sql, )]


def monthly_trend(months=6, path=DB_PATH):
    """Tren beberapa bulan terakhir, LENGKAP dengan bulan yang kosong.

    Bulan tanpa transaksi tetap dikembalikan dengan `ada_data: false` — bukan
    dihilangkan, bukan diisi nol. Bedanya penting untuk grafik: garis yang
    diputus (ada_data=false) jujur, sedangkan titik nol mengarang cerita
    bahwa Deny tidak mengeluarkan uang bulan itu.

    Urutan: lama -> baru, supaya siap digambar kiri ke kanan.
    """
    bulan_ini = date.today().replace(day=1)
    daftar = []
    for i in range(months - 1, -1, -1):
        # mundur i bulan dari bulan ini, tanpa library tanggal tambahan
        y, m = bulan_ini.year, bulan_ini.month - i
        while m <= 0:
            m += 12
            y -= 1
        daftar.append("%04d-%02d" % (y, m))

    with connect(path) as conn:
        rows = {r["month"]: dict(r) for r in conn.execute(
            "SELECT * FROM v_monthly_flow WHERE month >= ?", (daftar[0],))}

    hasil = []
    for b in daftar:
        r = rows.get(b)
        if r:
            hasil.append({
                "month": b, "ada_data": True,
                "total_in": r["total_in"], "total_out": r["total_out"],
                "expense_real": r["expense_real"], "net": r["net"],
                "net_real": r["net_real"], "tx_count": r["tx_count"],
            })
        else:
            hasil.append({"month": b, "ada_data": False, "total_in": None,
                          "total_out": None, "expense_real": None,
                          "net": None, "net_real": None, "tx_count": 0})
    return {"months": months, "items": hasil}


def spending_by_category(month=None, direction="out", path=DB_PATH):
    """Pengeluaran per kategori dalam satu bulan, urut terbesar.

    Hanya menghitung `expense` — talangan dan pelunasan utang BUKAN konsumsi,
    dan mencampurnya membuat kategori 'Tagihan' terlihat raksasa padahal
    isinya pelunasan pinjaman.
    """
    month = month or date.today().strftime("%Y-%m")
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT c.name AS category, SUM(t.amount) AS total, COUNT(*) AS tx_count
            FROM transactions t
            JOIN categories c ON c.id = t.category_id
            WHERE substr(t.occurred_on,1,7) = ?
              AND t.direction = ?
              AND t.flow_type = 'expense'
            GROUP BY c.name
            ORDER BY total DESC
        """, (month, direction)).fetchall()
    return {"month": month, "items": [dict(r) for r in rows]}


def saving_suggestions(month=None, path=DB_PATH):
    """Saran hemat — SETIAP saran membawa asumsinya, dan itu wajib.

    Aturan dari UI-MOBILE.md: "Bisa dihemat Rp 300.000/bulan" tanpa penjelasan
    adalah angka yang tidak bisa dipercaya. Jadi tiap saran mengembalikan
    `asumsi` yang bisa dibaca Deny dan dibantah kalau memang tidak cocok.

    Yang TIDAK dilakukan di sini: mengarang persentase "idealnya". Semua
    perbandingan diambil dari data Deny sendiri atau dari faktanya sendiri.
    """
    month = month or date.today().strftime("%Y-%m")
    bulan_lalu = _bulan_sebelum(month)
    saran = []

    skrg = spending_by_category(month, path=path)["items"]
    lalu = {r["category"]: r["total"]
            for r in spending_by_category(bulan_lalu, path=path)["items"]}

    # 1. Kategori yang naik tajam dibanding bulan sebelumnya
    for r in skrg:
        sebelum = lalu.get(r["category"])
        if sebelum and sebelum > 0 and r["total"] > sebelum * 1.3:
            beda = r["total"] - sebelum
            saran.append({
                "jenis": "kenaikan_kategori",
                "kategori": r["category"],
                "potensi_hemat": beda,
                "asumsi": ("%s naik dari %s (bulan lalu) ke %s bulan ini. "
                           "Angka hemat = selisihnya, kalau kembali ke pola bulan lalu."
                           % (r["category"], rupiah(sebelum), rupiah(r["total"]))),
            })

    # 2. Pengeluaran kecil yang sering — kandidat dipotong
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT c.name AS category, COUNT(*) n, SUM(t.amount) total
            FROM transactions t JOIN categories c ON c.id = t.category_id
            WHERE substr(t.occurred_on,1,7) = ?
              AND t.direction = 'out' AND t.flow_type = 'expense'
            GROUP BY c.name HAVING n >= 5
            ORDER BY n DESC
        """, (month,)).fetchall()
    for r in rows:
        saran.append({
            "jenis": "sering_kecil",
            "kategori": r["category"],
            "potensi_hemat": None,
            "asumsi": ("%s tercatat %d kali bulan ini (total %s, rata-rata %s). "
                       "Banyak transaksi kecil biasanya lebih mudah dipotong "
                       "daripada satu transaksi besar — tapi hanya kamu yang tahu "
                       "mana yang bisa dikurangi."
                       % (r["category"], r["n"], rupiah(r["total"]),
                          rupiah(r["total"] // r["n"] if r["n"] else 0))),
        })

    # 3. Talangan project — bukan konsumsi, tapi mengikat uang
    ms = monthly_summary(month, path=path)
    if ms.get("receivable_out"):
        saran.append({
            "jenis": "talangan_project",
            "kategori": None,
            "potensi_hemat": None,
            "asumsi": ("%s ditalangi ke project bulan ini. Uang ini bukan "
                       "pengeluaran pribadi, tapi selama belum kembali ia tidak "
                       "bisa dipakai untuk hal lain." % rupiah(ms["receivable_out"])),
        })

    # 4. Rasio menabung — dihitung dari data, bukan dari angka ideal karangan
    if ms.get("total_in"):
        rasio = ms["net_real"] / ms["total_in"] * 100
        saran.append({
            "jenis": "rasio_sisa",
            "kategori": None,
            "potensi_hemat": None,
            "asumsi": ("Dari %s yang masuk, %s (%.0f%%) tersisa setelah pengeluaran "
                       "sungguhan. Angka ini belum memperhitungkan pelunasan utang "
                       "dan talangan."
                       % (rupiah(ms["total_in"]), rupiah(ms["net_real"]), rasio)),
        })

    return {"month": month, "items": saran,
            "catatan": "Semua saran menyebut asumsinya. Tidak ada persentase "
                       "'ideal' yang dikarang — perbandingan diambil dari data "
                       "Deny sendiri."}


def kelengkapan_bulan(month, path=DB_PATH):
    """Seberapa lengkap data satu bulan. Dipakai untuk memperingatkan Deny.

    Kenapa ini ada: angka "sisa bebas" dihitung dari pemasukan dikurangi
    konsumsi. Kalau bulan itu baru tercatat 3 hari, sisa bebasnya jadi RATUSAN
    JUTA secara aritmetika — sementara 28 hari pengeluaran belum masuk sama
    sekali. Angkanya benar sebagai hitungan, menyesatkan sebagai gambaran.

    Kasus nyata: Oktober 2026 baru 3 dari 31 hari. "Sisa bebas Rp 7.800.000"
    terlihat seperti uang yang bisa ditabung, padahal itu cuma artinya
    pengeluaran bulan itu belum tercatat.

    Mengembalikan `peringatan` berupa kalimat siap tampil, atau None kalau
    datanya sudah dianggap lengkap.
    """
    from calendar import monthrange

    y, m = int(month[:4]), int(month[5:7])
    jumlah_hari = monthrange(y, m)[1]

    with connect(path) as conn:
        r = conn.execute("""
            SELECT COUNT(*) AS tx,
                   COUNT(DISTINCT occurred_on) AS hari,
                   MIN(occurred_on) AS pertama,
                   MAX(occurred_on) AS terakhir
            FROM transactions WHERE substr(occurred_on,1,7) = ?
        """, (month,)).fetchone()

    tx = r["tx"] or 0
    hari = r["hari"] or 0
    # Ambang: 60% hari terisi. Di bawah itu dianggap belum cukup untuk dinilai.
    ambang = max(1, int(jumlah_hari * 0.6))

    peringatan = None
    if tx == 0:
        peringatan = ("Belum ada transaksi sama sekali di bulan ini, "
                      "jadi belum ada yang bisa dianalisa.")
    elif hari < ambang:
        peringatan = ("Data bulan ini baru mencakup %d dari %d hari "
                      "(%s s/d %s). Angka sisa di bawah dihitung dari data yang "
                      "ada saja — bukan gambaran sebulan penuh."
                      % (hari, jumlah_hari, r["pertama"], r["terakhir"]))

    return {
        "month": month,
        "jumlah_hari_bulan": jumlah_hari,
        "hari_tercatat": hari,
        "tx_count": tx,
        "tanggal_pertama": r["pertama"],
        "tanggal_terakhir": r["terakhir"],
        "ambang_hari": ambang,
        "lengkap": peringatan is None,
        "peringatan": peringatan,
    }


def _bulan_sebelum(month):
    y, m = int(month[:4]), int(month[5:7])
    m -= 1
    if m == 0:
        m, y = 12, y - 1
    return "%04d-%02d" % (y, m)


def _bulan_sesudah(month):
    y, m = int(month[:4]), int(month[5:7])
    m += 1
    if m == 13:
        m, y = 1, y + 1
    return "%04d-%02d" % (y, m)


def daftar_bulan(path=DB_PATH):
    """Bulan yang PUNYA transaksi, urut terbaru dulu.

    Hanya bulan berisi data yang dikembalikan. Bulan kosong tidak dimasukkan:
    menaruhnya di pemilih bulan hanya membuat Deny menekan bulan yang pasti
    menjawab "belum ada data" — pilihan yang tidak berguna.
    """
    with connect(path) as conn:
        rows = conn.execute("""
            SELECT substr(occurred_on,1,7) AS month,
                   COUNT(*) AS tx_count
            FROM transactions
            GROUP BY substr(occurred_on,1,7)
            ORDER BY month DESC
        """).fetchall()
        dianalisa = {r["month"] for r in conn.execute(
            "SELECT month FROM analyses")}

    bulan = []
    for r in rows:
        bulan.append({
            "month": r["month"],
            "nama_bulan": nama_bulan(r["month"]),
            "tx_count": r["tx_count"],
            "ada_analisa": r["month"] in dianalisa,
            # Dipakai UI untuk mematikan tombol "+ Buat analisa"
            "boleh_dianalisa": bulan_sudah_selesai(r["month"], path=path),
        })
    return {
        "bulan": bulan,
        "bulan_berjalan": bulan_berjalan(path=path),
        "catatan": "Hanya bulan yang punya transaksi. Bulan kosong tidak "
                   "dimasukkan karena tidak ada yang bisa ditampilkan.",
    }


def bulan_berjalan(path=DB_PATH):
    return date.today().strftime("%Y-%m")


def bulan_sudah_selesai(month, path=DB_PATH):
    """True kalau bulan itu sudah lewat (bukan bulan berjalan / bulan depan).

    Analisa HANYA untuk bulan yang sudah selesai. Menganalisa bulan yang masih
    berjalan menghasilkan angka yang belum final, dan kesimpulan seperti
    "pengeluaranmu turun" bisa terbalik keesokan harinya.
    """
    return month < bulan_berjalan()


# ─────────────────────────────────────────────────────────────────────────────
# Analisa bulanan
# ─────────────────────────────────────────────────────────────────────────────
# Kategori yang dianggap WAJIB — tidak bisa dipotong, jadi tidak pernah muncul
# sebagai saran hemat. Keputusan Deny 3 Okt 2026: Tagihan + Transport.
#
# Transport masuk daftar karena penggunaannya untuk kerja (bensin, tol, parkir);
# menyarankan memotongnya hanya akan membuat sarannya diabaikan. Mengubah daftar
# ini berarti mengubah isi saran hemat — bukan sekadar tampilan.
KATEGORI_WAJIB = ("Tagihan", "Transport")


def saldo_per_tanggal(tanggal, path=DB_PATH):
    """Saldo tiap akun PADA TANGGAL TERTENTU, bukan hari ini.

    Kenapa ini perlu ada, terpisah dari `account_balances()`:
    `v_account_balances` menjumlahkan SEMUA transaksi tanpa dimensi tanggal —
    hasilnya selalu saldo HARI INI. Untuk menjawab "berapa saldo akhir
    September", transaksi setelah tanggal itu harus dikecualikan.

    Rumusnya sama persis dengan v_account_balances, hanya ditambah saringan
    tanggal:
        saldo = opening_balance
              + in masuk    - out keluar
              - transfer keluar + transfer masuk
        ...dihitung hanya dari transaksi dengan occurred_on <= tanggal.

    Versi Python ini SENGAJA mencerminkan rumus SQL-nya baris per baris, supaya
    kalau rumusnya berubah di satu tempat, yang lain mudah terlihat berbeda.
    Kalau keduanya menyimpang, angka antara "saldo sekarang" dan "saldo akhir
    bulan" akan tidak nyambung dan sulit ditelusuri.
    """
    with connect(path) as conn:
        akun = [dict(r) for r in conn.execute(
            "SELECT id, name, kind, opening_balance, is_active FROM accounts")]
        for a in akun:
            r = conn.execute("""
                SELECT
                  COALESCE(SUM(CASE WHEN account_id = ? AND direction = 'in'
                                    THEN amount END), 0) AS masuk,
                  COALESCE(SUM(CASE WHEN account_id = ? AND direction = 'out'
                                    THEN amount END), 0) AS keluar,
                  COALESCE(SUM(CASE WHEN account_id = ? AND direction = 'transfer'
                                    THEN amount END), 0) AS transfer_keluar,
                  COALESCE(SUM(CASE WHEN to_account_id = ? AND direction = 'transfer'
                                    THEN amount END), 0) AS transfer_masuk
                FROM transactions
                WHERE occurred_on <= ?
            """, (a["id"], a["id"], a["id"], a["id"], tanggal)).fetchone()
            a["balance"] = (a["opening_balance"] + r["masuk"] - r["keluar"]
                            - r["transfer_keluar"] + r["transfer_masuk"])

    aktif = [a for a in akun if a["is_active"]]
    return {
        "per_tanggal": tanggal,
        "accounts": akun,
        "net_worth": sum(a["balance"] for a in akun),
        "liquid": sum(a["balance"] for a in aktif
                      if a["kind"] in ("bank", "cash", "ewallet")),
        "non_liquid": sum(a["balance"] for a in aktif
                          if a["kind"] in ("savings", "investment")),
    }


def akhir_bulan(month):
    """Tanggal terakhir satu bulan: '2026-09' -> '2026-09-30'."""
    from calendar import monthrange
    y, m = int(month[:4]), int(month[5:7])
    return "%04d-%02d-%02d" % (y, m, monthrange(y, m)[1])


def ringkasan_bulan(month, path=DB_PATH):
    """Semua angka satu bulan. Dipakai halaman Analisa.

    Angka di sini SELALU dihitung dari transaksi — tidak pernah dari snapshot
    tersimpan. Jadi kalau transaksi dikoreksi, angka di analisa ikut benar.
    """
    ms = monthly_summary(month, path=path)
    nw = net_worth(path=path)
    kategori = spending_by_category(month, path=path)
    lalu = {r["category"]: r["total"]
            for r in spending_by_category(_bulan_sebelum(month), path=path)["items"]}
    kategori_lalu_ada = bool(lalu)

    rincian = []
    for r in kategori["items"]:
        sebelum = lalu.get(r["category"])
        naik = None
        if sebelum and sebelum > 0:
            naik = round((r["total"] - sebelum) / sebelum * 100)
        rincian.append({
            "category": r["category"],
            "total": r["total"],
            "tx_count": r["tx_count"],
            "total_bulan_lalu": sebelum,
            "perubahan_persen": naik,
            "wajib": r["category"] in KATEGORI_WAJIB,
        })

    # Sisa yang bisa ditabung. INI YANG PALING MUDAH MENYESATKAN.
    #
    # `sisa_kas` = masuk - semua yang keluar. Angka ini BESAR dan kelihatan
    # seperti uang bebas — padahal pelunasan utang dan talangan project bukan
    # konsumsi, dan uangnya sudah tidak ada. Kalau hanya angka ini yang
    # ditampilkan, Deny akan mengira punya tabungan yang tidak pernah ada.
    #
    # Karena itu `sisa_bebas` yang dipakai sebagai "bisa ditabung": hanya
    # pemasukan dikurangi pengeluaran yang benar-benar hilang.
    sisa_kas = ms["total_in"] - ms["total_out"]
    sisa_bebas = ms["total_in"] - ms["expense_real"]

    # Saldo akhir bulan — HANYA untuk bulan yang sudah selesai.
    #
    # Untuk bulan berjalan, "saldo akhir bulan" belum ada artinya. Kalau kita
    # mengirim saldo hari ini dan melabelinya "akhir bulan", panel akan
    # menampilkan angka yang berubah besok dengan label yang bilang "akhir
    # September". Jadi `null`, dan UI menampilkan kalimat.
    #
    # `ada_data` juga jadi syarat: bulan tanpa transaksi sama sekali saldonya
    # SAMA dengan bulan sebelumnya. Mengirim angkanya akan membuat Deny mengira
    # bulan itu punya aktivitas padahal tidak ada. (Diminta yuki, 3 Okt 2026.)
    if bulan_sudah_selesai(month, path=path) and ms["_ada_data"]:
        tgl = akhir_bulan(month)
        akhir = saldo_per_tanggal(tgl, path=path)
        nw_akhir = akhir["net_worth"]
        nw_akhir_liquid = akhir["liquid"]
        nw_akhir_non_liquid = akhir["non_liquid"]
        per_tanggal = tgl
    else:
        nw_akhir = nw_akhir_liquid = nw_akhir_non_liquid = None
        per_tanggal = None

    return {
        "month": month,
        "ada_data": ms["_ada_data"],
        "tx_count": ms["tx_count"],

        "masuk": ms["total_in"],
        "keluar_semua": ms["total_out"],
        "konsumsi": ms["expense_real"],
        "pelunasan_utang": ms["debt_payment_out"],
        "talangan_piutang": ms["receivable_out"],

        "sisa_kas": sisa_kas,
        "sisa_bebas": sisa_bebas,

        "kategori": rincian,
        "kategori_lalu_ada": kategori_lalu_ada,

        # Kekayaan saat ini — bukan bagian bulan itu, tapi konteks yang dicari
        # orang pertama kali.
        "net_worth": nw["net_worth"],
        "saldo_akun": account_balances(path=path),

        # Kekayaan PADA AKHIR bulan itu. None kalau bulan belum selesai atau
        # belum ada datanya — dan None berarti "tidak ada artinya", bukan nol.
        "net_worth_akhir": nw_akhir,
        "net_worth_akhir_liquid": nw_akhir_liquid,
        "net_worth_akhir_non_liquid": nw_akhir_non_liquid,
        "per_tanggal": per_tanggal,

        "kategori_wajib": list(KATEGORI_WAJIB),
    }


def saran_hemat(month, path=DB_PATH):
    """Saran hemat yang BISA DIBUKTIKAN dari data. Tiap saran membawa asumsinya.

    Yang tidak dilakukan di sini: mengarang persentase "ideal", atau
    menyarankan memotong kategori wajib (Tagihan, Transport).

    Mengembalikan dict per kategori:
      jumlah      — rupiah yang bisa dihemat. HANYA terisi kalau ada dasar
                    hitungannya. Kalau tidak ada, None — bukan 0.
      asumsi      — kalimat yang menyebut dari mana angka itu datang.
    """
    bulan_lalu = _bulan_sebelum(month)
    skrg = spending_by_category(month, path=path)["items"]
    lalu = {r["category"]: r["total"]
            for r in spending_by_category(bulan_lalu, path=path)["items"]}
    saran = []

    for r in skrg:
        kategori = r["category"]
        wajib = kategori in KATEGORI_WAJIB
        sebelum = lalu.get(kategori)

        # Kalau tidak ada pembanding (bulan lalu kosong), tidak ada dasar
        # untuk bilang "berlebih". Yang bisa dilakukan hanya mencatat
        # pengeluarannya ada berapa — itu bukan saran, itu laporan.
        if not sebelum:
            saran.append({
                "kategori": kategori,
                "total": r["total"],
                "tx_count": r["tx_count"],
                "wajib": wajib,
                "jenis": "tanpa_pembanding",
                "potensi_hemat": None,
                "asumsi": ("%s %s bulan ini. Belum ada data %s sebagai pembanding, "
                           "jadi tidak bisa dinilai naik atau turun."
                           % (kategori, rupiah(r["total"]),
                              _nama_bulan(bulan_lalu))),
            })
            continue

        beda = r["total"] - sebelum
        if wajib:
            saran.append({
                "kategori": kategori,
                "total": r["total"],
                "tx_count": r["tx_count"],
                "wajib": True,
                "jenis": "wajib",
                "potensi_hemat": None,
                "asumsi": ("%s %s%s. Kategori ini dianggap wajib, jadi tidak "
                           "disarankan dipotong."
                           % (kategori, rupiah(r["total"]),
                              "" if beda == 0 else
                              " (bulan lalu %s)" % rupiah(sebelum))),
            })
        elif beda > 0:
            saran.append({
                "kategori": kategori,
                "total": r["total"],
                "tx_count": r["tx_count"],
                "wajib": False,
                "jenis": "naik",
                "potensi_hemat": beda,
                "asumsi": ("%s naik dari %s (bulan lalu) ke %s — naik %s. "
                           "Angka hemat = selisihnya, kalau kembali ke pola bulan lalu."
                           % (kategori, rupiah(sebelum), rupiah(r["total"]),
                              rupiah(beda))),
            })
        else:
            saran.append({
                "kategori": kategori,
                "total": r["total"],
                "tx_count": r["tx_count"],
                "wajib": False,
                "jenis": "turun_atau_sama",
                "potensi_hemat": None,
                "asumsi": ("%s %s%s — tidak lebih besar dari bulan lalu (%s). "
                           "Tidak ada yang perlu dipotong di sini."
                           % (kategori, rupiah(r["total"]),
                              "" if beda == 0 else
                              ", turun %s" % rupiah(abs(beda)),
                              rupiah(sebelum))),
            })

    total_hemat = sum(s["potensi_hemat"] for s in saran
                      if s["potensi_hemat"]) or 0
    return {
        "month": month,
        "bulan_pembanding": bulan_lalu,
        "ada_pembanding": bool(lalu),
        "kategori": saran,
        "total_potensi_hemat": total_hemat if any(
            s["potensi_hemat"] for s in saran) else None,
        "catatan": "Setiap angka di sini punya dasar hitungan. Yang tidak punya "
                   "dasar dikembalikan sebagai null, bukan 0.",
    }


NAMA_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
              "Juli", "Agustus", "September", "Oktober", "November", "Desember"]


def _nama_bulan(month):
    return "%s %s" % (NAMA_BULAN[int(month[5:7]) - 1], month[:4])


def nama_bulan(month):
    """'2026-10' -> 'Oktober 2026'."""
    return _nama_bulan(month)


def analisa_lengkap(month, path=DB_PATH):
    """Semua yang dibutuhkan halaman Analisa: angka + narasi tersimpan.

    `angka`      selalu dihitung ulang dari transaksi (tidak pernah dari snapshot)
    `analisa`    baris tersimpan — narasi, kapan dibuat, model mana
    `narasi_basi` True kalau ada transaksi di bulan itu yang berubah SETELAH
                  narasi dibuat. UI harus menandainya.
    """
    angka = ringkasan_bulan(month, path=path)
    saran = saran_hemat(month, path=path)

    with connect(path) as conn:
        baris = conn.execute("SELECT * FROM analyses WHERE month = ?",
                             (month,)).fetchone()
        tx_terakhir = conn.execute("""
            SELECT MAX(COALESCE(NULLIF(created_at,''), occurred_on)) AS t
            FROM transactions WHERE substr(occurred_on,1,7) = ?
        """, (month,)).fetchone()["t"]

    tersimpan = dict(baris) if baris else None
    narasi = None
    if tersimpan and tersimpan.get("narasi"):
        try:
            narasi = json.loads(tersimpan["narasi"])
        except json.JSONDecodeError:
            narasi = None

    basi = False
    if tersimpan and tersimpan.get("dibuat_pada") and tx_terakhir:
        basi = str(tx_terakhir) > str(tersimpan["dibuat_pada"])

    return {
        "month": month,
        "nama_bulan": nama_bulan(month),
        "bulan_berjalan": bulan_berjalan(path=path),
        "boleh_dianalisa": bulan_sudah_selesai(month, path=path),

        "angka": angka,
        "saran": saran,

        # Seberapa lengkap datanya. `peringatan` siap ditampilkan; None berarti
        # datanya sudah dianggap cukup. WAJIB ditampilkan UI kalau terisi —
        # tanpa itu, "sisa bebas" dari 3 hari data terlihat seperti uang nyata.
        "kelengkapan": kelengkapan_bulan(month, path=path),

        "ada_analisa": bool(tersimpan),
        "dibuat_pada": tersimpan["dibuat_pada"] if tersimpan else None,
        "model": tersimpan["model"] if tersimpan else None,
        "narasi": narasi,
        "narasi_basi": basi,
        "tx_terakhir": tx_terakhir,
        "catatan_analisa": tersimpan["catatan"] if tersimpan else None,
    }


def simpan_analisa(month, narasi, snapshot=None, model=None, catatan=None, path=DB_PATH):
    """Simpan narasi hasil analisa. Satu bulan satu narasi (diganti kalau ada)."""
    with connect(path) as conn:
        tx_terakhir = conn.execute("""
            SELECT MAX(COALESCE(NULLIF(created_at,''), occurred_on)) AS t
            FROM transactions WHERE substr(occurred_on,1,7) = ?
        """, (month,)).fetchone()["t"]
        conn.execute("""
            INSERT INTO analyses (month, dibuat_pada, tx_terakhir, narasi,
                                  snapshot, model, catatan)
            VALUES (?, datetime('now','localtime'), ?, ?, ?, ?, ?)
            ON CONFLICT(month) DO UPDATE SET
                dibuat_pada = datetime('now','localtime'),
                tx_terakhir = excluded.tx_terakhir,
                narasi      = excluded.narasi,
                snapshot    = excluded.snapshot,
                model       = excluded.model,
                catatan     = excluded.catatan
        """, (month, tx_terakhir,
              json.dumps(narasi, ensure_ascii=False) if narasi is not None else None,
              json.dumps(snapshot, ensure_ascii=False) if snapshot is not None else None,
              model, catatan))
    return analisa_lengkap(month, path=path)


def hapus_analisa(month, path=DB_PATH):
    with connect(path) as conn:
        cur = conn.execute("DELETE FROM analyses WHERE month = ?", (month,))
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Target tabungan
# ─────────────────────────────────────────────────────────────────────────────
# Yang dihitung sebagai "menabung": SALDO AKUN tempat target dipasang.
# Keputusan Deny 3 Okt 2026. Konsekuensinya harus disebut di panel: uang yang
# disimpan di instrumen lain (reksadana, deposito) TIDAK ikut terhitung kalau
# bukan akun yang dipakai target ini.
def target_aktif(path=DB_PATH):
    """Target tabungan yang sedang berjalan, atau None kalau belum ada."""
    with connect(path) as conn:
        row = conn.execute(
            "SELECT * FROM v_savings_progress WHERE is_archived = 0 "
            "ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None
        target = dict(row)

        # Riwayat setoran per bulan: transfer MASUK ke akun target.
        # Berguna untuk melihat bulan mana yang kosong — itu pertanyaan yang
        # muncul lebih dulu daripada "berapa persen".
        riwayat = [dict(r) for r in conn.execute("""
            SELECT substr(occurred_on,1,7) AS month,
                   SUM(amount) AS total,
                   COUNT(*) AS tx_count
            FROM transactions
            WHERE to_account_id = ? AND direction = 'transfer'
            GROUP BY substr(occurred_on,1,7)
            ORDER BY month DESC
        """, (target["account_id"],))]

        keluar = [dict(r) for r in conn.execute("""
            SELECT substr(occurred_on,1,7) AS month,
                   SUM(amount) AS total,
                   COUNT(*) AS tx_count
            FROM transactions
            WHERE account_id = ? AND direction = 'transfer'
            GROUP BY substr(occurred_on,1,7)
            ORDER BY month DESC
        """, (target["account_id"],))]

    target["riwayat_setoran"] = riwayat
    target["riwayat_penarikan"] = keluar

    # Rata-rata setoran per bulan — HANYA dari bulan yang benar-benar ada
    # setorannya. Kalau tidak ada sama sekali, None (bukan 0).
    if riwayat:
        total = sum(r["total"] for r in riwayat)
        target["rata_setoran_bulanan"] = round(total / len(riwayat))
        target["bulan_ada_setoran"] = len(riwayat)
    else:
        target["rata_setoran_bulanan"] = None
        target["bulan_ada_setoran"] = 0

    # Perkiraan berapa bulan lagi — HANYA kalau ada dasar hitungannya.
    # Kalau belum pernah menabung, tidak ada yang bisa diperkirakan; sistem
    # TIDAK boleh mengarang tanggal.
    if target["rata_setoran_bulanan"] and target["sisa"] > 0:
        target["perkiraan_bulan_lagi"] = -(-target["sisa"] // target["rata_setoran_bulanan"])
    else:
        target["perkiraan_bulan_lagi"] = None

    return target


def set_target(name, target_amount, account_hint=None, account_id=None,
               target_date=None, path=DB_PATH):
    """Pasang target tabungan. Menggantikan target aktif yang ada.

    Satu target saja untuk sekarang (keputusan Deny): target lama diarsipkan,
    bukan dihapus — supaya kalau salah isi, masih bisa dilihat jejaknya.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("nama target tidak boleh kosong")
    try:
        target_amount = int(round(float(target_amount)))
    except (TypeError, ValueError):
        raise ValueError("target harus angka bulat rupiah")
    if target_amount <= 0:
        raise ValueError("target harus lebih besar dari nol")

    if target_date:
        try:
            date.fromisoformat(str(target_date)[:10])
        except ValueError:
            raise ValueError("tanggal target '%s' tidak sah. Pakai YYYY-MM-DD." % target_date)

    # Arsip target lama + pasang yang baru dalam SATU transaksi database.
    #
    # Kalau dipisah, ada jendela di mana target lama sudah terarsip sementara
    # yang baru belum masuk — dan kalau INSERT-nya gagal di jendela itu, Deny
    # kehilangan targetnya tanpa dapat gantinya. Cacat ini ditemukan yuki
    # (3 Okt 2026) saat membaca alur ini; ia tidak menemukan kegagalannya,
    # tapi cacatnya nyata dan murah ditutup.
    #
    # `connect()` sudah membungkus semuanya dalam satu transaksi (commit di
    # akhir blok, rollback kalau ada exception) — jadi UPDATE dan INSERT di
    # bawah ini bersifat semua-atau-tidak-sama-sekali.
    with connect(path) as conn:
        akun = _resolve_account(conn, account_id, account_hint)
        conn.execute("UPDATE savings_goals SET is_archived = 1 WHERE is_archived = 0")
        cur = conn.execute("""
            INSERT INTO savings_goals (name, target_amount, account_id, target_date)
            VALUES (?,?,?,?)""", (name, target_amount, akun, target_date))
        baru = cur.lastrowid
    return target_aktif(path=path)


def hapus_target(path=DB_PATH):
    """Arsipkan target aktif. Data targetnya TIDAK dihapus.

    Kenapa diarsipkan dan bukan dihapus: target adalah niat yang pernah
    ditetapkan Deny. Menghapusnya berarti kehilangan jejak kenapa angkanya
    berubah — pola yang sama dengan alasan `is_active` dipakai di akun.
    """
    with connect(path) as conn:
        cur = conn.execute("UPDATE savings_goals SET is_archived = 1 WHERE is_archived = 0")
    return cur.rowcount > 0


# ─────────────────────────────────────────────────────────────────────────────
# Tulis — akun
# ─────────────────────────────────────────────────────────────────────────────
def create_account(name, kind, opening_balance=0, path=DB_PATH):
    """Tambah akun. Gagal kalau namanya sudah dipakai."""
    name = (name or "").strip()
    if not name:
        raise ValueError("nama akun tidak boleh kosong")
    with connect(path) as conn:
        ada = conn.execute("SELECT id FROM accounts WHERE lower(name) = lower(?)",
                           (name,)).fetchone()
        if ada:
            raise ValueError("sudah ada akun bernama '%s'" % name)
        cur = conn.execute(
            "INSERT INTO accounts (name, kind, opening_balance) VALUES (?,?,?)",
            (name, kind, int(opening_balance)))
        return {"id": cur.lastrowid, "name": name, "kind": kind,
                "opening_balance": int(opening_balance)}


def update_account(account_id, name=None, is_active=None, path=DB_PATH):
    """Ubah nama / aktif-nonaktifkan akun.

    `kind` dan `opening_balance` TIDAK bisa diubah di sini, dan itu disengaja:
    keduanya mengubah angka di v_net_worth tanpa satu pun transaksi.
    """
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id = ?",
                           (account_id,)).fetchone()
        if not row:
            raise ValueError("tidak ada akun dengan id %s" % account_id)

        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("nama akun tidak boleh kosong")
            bentrok = conn.execute(
                "SELECT id FROM accounts WHERE lower(name) = lower(?) AND id <> ?",
                (name, account_id)).fetchone()
            if bentrok:
                raise ValueError("sudah ada akun bernama '%s'" % name)

        if name is None:
            name = row["name"]
        if is_active is None:
            is_active = row["is_active"]

        conn.execute("UPDATE accounts SET name = ?, is_active = ? WHERE id = ?",
                     (name, is_active, account_id))
        return {"id": account_id, "name": name, "kind": row["kind"],
                "opening_balance": row["opening_balance"],
                "is_active": is_active}


# ─────────────────────────────────────────────────────────────────────────────
# Tulis — transaksi
# ─────────────────────────────────────────────────────────────────────────────
FLOW_TYPES = ("expense", "income", "receivable", "debt_payment", "transfer")

# Arah yang sah untuk tiap sifat. "income" hanya untuk uang masuk; sisanya
# keluar. Ini mencegah "income" tercatat sebagai pengeluaran.
FLOW_DIRECTION = {
    "expense":      "out",
    "receivable":   "out",
    "debt_payment": "out",
    "transfer":     "transfer",
    "income":       "in",
}


def save_transactions(items, path=DB_PATH):
    """Simpan beberapa transaksi dalam SATU transaksi database.

    Kalau satu baris gagal (kategori tidak dikenal, akun tidak ada), semuanya
    dibatalkan — tidak ada yang tersimpan setengah jadi. Ini aturan dari
    PLAN.md: draft multi-transaksi harus masuk seluruhnya atau tidak sama sekali.

    `flow_type` opsional; kalau kosong diturunkan dari `direction`
    (in -> income, out -> expense, transfer -> transfer).

    Mengembalikan daftar id yang tersimpan.
    """
    ids = []
    with connect(path) as conn:
        for it in items:
            direction = it.get("direction")
            flow_type = it.get("flow_type") or (
                "income" if direction == "in"
                else "transfer" if direction == "transfer"
                else "expense"
            )
            if flow_type not in FLOW_TYPES:
                raise ValueError("flow_type '%s' tidak dikenal" % flow_type)
            if FLOW_DIRECTION[flow_type] != direction:
                raise ValueError(
                    "flow_type '%s' tidak cocok dengan direction '%s' (harusnya '%s')"
                    % (flow_type, direction, FLOW_DIRECTION[flow_type]))

            account_id = _resolve_account(conn, it.get("account_id"),
                                          it.get("account_hint"))
            to_account_id = None
            if direction == "transfer":
                to_account_id = _resolve_account(conn, it.get("to_account_id"),
                                                 it.get("to_account_hint"))
                if to_account_id == account_id:
                    raise ValueError("transfer ke akun yang sama tidak masuk akal")
                category_id = None
            else:
                category_id = _resolve_category(conn, it.get("category"),
                                                it.get("direction"))
            cur = conn.execute(
                """INSERT INTO transactions
                   (occurred_on, direction, amount, account_id, to_account_id,
                    category_id, note, flow_type)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (it["occurred_on"], it["direction"], int(it["amount"]),
                 account_id, to_account_id, category_id, it.get("note"),
                 flow_type),
            )
            ids.append(cur.lastrowid)
    return ids


def _resolve_account(conn, account_id, hint):
    """Cari akun dari id atau dari tebakan nama.

    TIDAK ada cadangan otomatis. Kalau akun tidak bisa ditentukan, ini GAGAL —
    tidak menebak.

    Kenapa: sebelumnya fungsi ini jatuh ke akun 'Tunai' kalau tidak ada
    petunjuk. Akibatnya transaksi mendarat di akun yang salah TANPA ERROR,
    dan saldo jadi karut tanpa ada yang tahu. Untuk data keuangan, gagal
    dengan jelas jauh lebih baik daripada tersimpan di tempat yang salah.

    (Bug ini ditemukan yuki saat menguji panel; sekarang akarnya diperbaiki,
    bukan cuma diakali di UI.)
    """
    if account_id:
        row = conn.execute("SELECT id FROM accounts WHERE id = ? AND is_active = 1",
                           (account_id,)).fetchone()
        if row:
            return row["id"]
        raise ValueError("akun id %s tidak ada atau tidak aktif" % account_id)

    if hint and hint.strip():
        bersih = hint.strip()
        row = conn.execute(
            "SELECT id FROM accounts WHERE lower(name) = lower(?) AND is_active = 1",
            (bersih,)).fetchone()
        if row:
            return row["id"]
        row = conn.execute(
            "SELECT id FROM accounts WHERE lower(name) LIKE lower(?) AND is_active = 1 LIMIT 1",
            ("%" + bersih + "%",)).fetchone()
        if row:
            return row["id"]
        raise ValueError(
            "akun '%s' tidak ditemukan. Akun yang ada: %s"
            % (bersih, _daftar_akun(conn)))

    # Tanpa petunjuk sama sekali: kalau hanya ada SATU akun aktif, itu jelas.
    # Kalau lebih dari satu, menebak berarti bisa salah — dan salahnya senyap.
    rows = conn.execute("SELECT id, name FROM accounts WHERE is_active = 1").fetchall()
    if len(rows) == 1:
        return rows[0]["id"]

    raise ValueError(
        "akun tidak disebutkan. Ada %d akun aktif (%s) — sebutkan salah satunya."
        % (len(rows), ", ".join(r["name"] for r in rows)))


def _daftar_akun(conn):
    return ", ".join(r["name"] for r in conn.execute(
        "SELECT name FROM accounts WHERE is_active = 1 ORDER BY name"))


def _resolve_category(conn, name, direction):
    """Cari kategori dari nama + arah. Tidak dikenal -> 'Lainnya' pada arah itu."""
    name = (name or "Lainnya").strip()
    row = conn.execute(
        "SELECT id FROM categories WHERE lower(name) = lower(?) AND direction = ?",
        (name, direction),
    ).fetchone()
    if row:
        return row["id"]
    row = conn.execute(
        "SELECT id FROM categories WHERE name = 'Lainnya' AND direction = ?", (direction,)
    ).fetchone()
    if not row:
        raise ValueError("kategori '%s' tidak ada dan tidak ada 'Lainnya' untuk arah %s"
                         % (name, direction))
    return row["id"]


def get_transaction(tx_id, path=DB_PATH):
    """Satu transaksi, dengan nama akun & kategori. None kalau tidak ada."""
    with connect(path) as conn:
        row = conn.execute("""
            SELECT t.*, a.name AS account_name, a2.name AS to_account_name,
                   c.name AS category_name
            FROM transactions t
            JOIN accounts a        ON a.id  = t.account_id
            LEFT JOIN accounts a2  ON a2.id = t.to_account_id
            LEFT JOIN categories c ON c.id  = t.category_id
            WHERE t.id = ?
        """, (tx_id,)).fetchone()
    return dict(row) if row else None


def update_transaction(tx_id, changes, path=DB_PATH):
    """Ubah sebagian field transaksi. Hanya field yang ada di `changes` diubah.

    ATURAN yang tidak boleh dilanggar:
    - `direction` TIDAK bisa diubah langsung. Arah mengikuti `flow_type`, karena
      FLOW_DIRECTION di file ini yang jadi satu-satunya penentu pasangan
      arah/sifat. Kalau arah bisa diubah sendiri, akan ada baris dengan
      flow_type='income' tapi direction='out' — dan tidak ada yang tahu.
    - Kalau `flow_type` diubah ke/dari 'transfer', `to_account_id` wajib ada.
      Transfer tanpa tujuan melanggar constraint database.
    """
    TERKUNCI = ("direction", "id", "created_at", "source")
    for f in TERKUNCI:
        if f in changes:
            raise ValueError(
                "kolom '%s' tidak bisa diubah langsung%s"
                % (f, " — ubah 'flow_type', arahnya mengikuti" if f == "direction" else ""))

    with connect(path) as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?",
                           (tx_id,)).fetchone()
        if not row:
            raise ValueError("tidak ada transaksi dengan id %s" % tx_id)

        # Nilai awal
        direction = row["direction"]
        flow_type = row["flow_type"]
        amount = row["amount"]
        occurred_on = row["occurred_on"]
        account_id = row["account_id"]
        to_account_id = row["to_account_id"]
        category_id = row["category_id"]
        note = row["note"]

        if "occurred_on" in changes:
            tgl = str(changes["occurred_on"])[:10]
            try:
                date.fromisoformat(tgl)
            except ValueError:
                raise ValueError("tanggal '%s' tidak sah. Pakai format YYYY-MM-DD." % tgl)
            occurred_on = tgl

        if "amount" in changes:
            try:
                amount = int(round(float(changes["amount"])))
            except (TypeError, ValueError):
                raise ValueError("nominal harus angka bulat rupiah")
            if amount <= 0:
                raise ValueError("nominal harus lebih besar dari nol")

        if "account_id" in changes or "account_hint" in changes:
            account_id = _resolve_account(conn, changes.get("account_id"),
                                          changes.get("account_hint"))

        # flow_type menentukan direction — bukan sebaliknya.
        if "flow_type" in changes:
            baru = changes["flow_type"]
            if baru not in FLOW_TYPES:
                raise ValueError("flow_type '%s' tidak dikenal" % baru)
            flow_type = baru
            direction = FLOW_DIRECTION[baru]

        # transfer butuh tujuan; bukan transfer tidak boleh punya tujuan.
        if flow_type == "transfer":
            if "to_account_id" in changes or "to_account_hint" in changes:
                to_account_id = _resolve_account(conn, changes.get("to_account_id"),
                                                 changes.get("to_account_hint"))
            if not to_account_id:
                raise ValueError(
                    "transfer butuh akun tujuan. Kirim 'to_account_id' atau "
                    "'to_account_hint'. Kalau bukan transfer, ubah juga 'flow_type'.")
            if to_account_id == account_id:
                raise ValueError("transfer ke akun yang sama tidak masuk akal")
            category_id = None
        else:
            # Keluar dari transfer: akun tujuan HARUS dilepas. Kalau tidak,
            # barisnya melanggar CHECK constraint di schema (transfer wajib
            # punya tujuan, non-transfer wajib tidak punya) dan database
            # menolak — kesalahan yang membingungkan kalau tidak dijelaskan.
            if "to_account_id" in changes or "to_account_hint" in changes:
                raise ValueError(
                    "flow_type '%s' tidak boleh punya akun tujuan. "
                    "Akun tujuan hanya untuk transfer." % flow_type)
            to_account_id = None
            if "category" in changes or "category_id" in changes or category_id is None:
                category_id = _resolve_category(conn, changes.get("category"), direction)

        if "note" in changes:
            note = changes["note"]

        conn.execute("""UPDATE transactions SET
                          occurred_on = ?, direction = ?, flow_type = ?, amount = ?,
                          account_id = ?, to_account_id = ?, category_id = ?, note = ?
                        WHERE id = ?""",
                     (occurred_on, direction, flow_type, amount, account_id,
                      to_account_id, category_id, note, tx_id))
    return get_transaction(tx_id, path)


def delete_transaction(tx_id, path=DB_PATH, log_path=None):
    """Hapus transaksi — KERAS, tapi barisnya dicatat dulu ke berkas pemulihan.

    Menghapus data keuangan tidak bisa dibatalkan. Sebelum barisnya dibuang,
    seluruh isinya ditulis ke `finance-pribadi/terhapus.log` (JSON per baris)
    supaya masih bisa dipulihkan manual kalau ternyata salah hapus.

    Mengembalikan dict baris yang dihapus.
    """
    log_path = log_path or (DATA_DIR / "terhapus.log")
    with connect(path) as conn:
        row = conn.execute("""
            SELECT t.*, a.name AS account_name, c.name AS category_name,
                   a2.name AS to_account_name
            FROM transactions t
            JOIN accounts a        ON a.id  = t.account_id
            LEFT JOIN accounts a2  ON a2.id = t.to_account_id
            LEFT JOIN categories c ON c.id  = t.category_id
            WHERE t.id = ?
        """, (tx_id,)).fetchone()
        if not row:
            raise ValueError("tidak ada transaksi dengan id %s" % tx_id)

        isi = dict(row)
        # Tulis jejak SEBELUM menghapus. Kalau penulisan gagal, jangan hapus.
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "dihapus_pada": datetime.now().isoformat(timespec="seconds"),
                "transaksi": isi,
            }, ensure_ascii=False) + "\n")

        conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    return isi


# ─────────────────────────────────────────────────────────────────────────────
# Format
# ─────────────────────────────────────────────────────────────────────────────
def rupiah(n):
    """Rp 1.100.000 — titik sebagai pemisah ribuan."""
    try:
        return "Rp " + format(int(round(float(n))), ",d").replace(",", ".")
    except (TypeError, ValueError):
        return "Rp ?"
