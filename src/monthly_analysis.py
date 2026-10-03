#!/usr/bin/env python3
"""Narasi analisa bulanan — dihasilkan AI, TAPI angkanya tidak boleh dari AI.

Aturan yang menentukan seluruh bentuk berkas ini:

  **Model hanya boleh MENJELASKAN angka yang sudah dihitung `db.py`.
  Model tidak boleh menghasilkan angka baru.**

Kalau model menulis "bisa dihemat Rp 300.000" padahal angka itu tidak ada di
data yang dikirim, sarannya DIBUANG — bukan ditampilkan dengan catatan kecil.
Alasan: satu angka karangan di halaman analisa merusak kepercayaan pada semua
angka lain di halaman itu, dan tidak ada cara bagi Deny untuk tahu mana yang
karangan.

Karena itu alurnya:
  1. db.py menghitung angka → dikirim ke model sebagai FAKTA
  2. model menulis satu kalimat per kategori
  3. kalimat itu diperiksa: apakah mengandung angka yang tidak ada di fakta?
     Kalau ya → kalimat itu dibuang, dipakai kalimat bawaan dari db.py.
"""
import json
import os
import re
import urllib.request
from datetime import date

import model_config

BASE = model_config.BASE
MODEL = model_config.MODEL

SYS = """Kamu menganalisa keuangan pribadi berbahasa Indonesia. Balas HANYA JSON valid, tanpa penjelasan, tanpa markdown.

Kamu menerima FAKTA keuangan satu bulan. Tugasmu menjelaskannya dengan bahasa manusia.

ATURAN WAJIB — melanggar berarti kalimatmu dibuang:
- JANGAN menulis persentase. Tidak "naik 73%", tidak "73 persen". Sebut selisihnya dalam rupiah saja.
- JANGAN menulis angka apa pun yang tidak ada di FAKTA. Tidak boleh menghitung sendiri, tidak boleh memperkirakan, tidak boleh membulatkan.
- SELALU tulis nominal dalam format rupiah lengkap dengan titik dan awalan "Rp": Rp 8.200.000 — bukan 8096600.
- Kalau sebuah kategori tidak punya pembanding bulan lalu, KATAKAN bahwa belum ada pembanding. Jangan mengarang perbandingan.
- Jangan menasihati memotong kategori yang ditandai "wajib": true.
- Jangan menyebut utang atau talangan sebagai "pengeluaran" — keduanya sudah dipisah dan artinya berbeda.
- Kalau "data_lengkap" bernilai false, KATAKAN di ringkasan bahwa data bulan itu belum lengkap (sebutkan berapa hari yang tercatat dari jumlah hari bulan itu). Jangan menyimpulkan "masih banyak sisa" seolah bulan itu sudah penuh.
- Nada: tenang, langsung, tidak menghakimi. Tidak ada pujian, tidak ada ceramah.

Format balasan:
{"ringkasan": "2-3 kalimat tentang bulan itu",
 "per_kategori": {"NamaKategori": "1-2 kalimat tentang kategori itu",
                  "NamaKategoriLain": "..."},
 "penutup": "1 kalimat tentang sisa yang bisa ditabung"}

PENTING: "per_kategori" WAJIB memuat SETIAP kategori yang ada di FAKTA, memakai
nama persis seperti di FAKTA. Kalau kamu melewatkan satu kategori, penjelasan
kategori itu hilang dari laporan.
"""


def _bersihkan_persen(teks):
    """Buang bagian persentase dari kalimat, sisanya dipertahankan.

    Kenapa tidak seluruh kalimat dibuang: model sering menulis kalimat yang
    isinya benar seluruhnya, lalu menyelipkan satu persentase. Membuang
    kalimatnya berarti kehilangan penjelasan yang berguna; memotong bagian
    persennya saja menyelamatkan sisanya.

    Contoh:  "Makan naik 73 persen dari Rp 450.000"  ->  "Makan dari Rp 450.000"

    Percobaan pertama: menyaring dengan membuang seluruh kalimat. Hasilnya
    SEMUA kategori kosong, padahal angkanya benar — penyaringnya terlalu ketat.
    """
    t = str(teks)
    # buang pola "naik/turun/N% /N persen" beserta kata kerja di depannya
    t = re.sub(r"\b(naik|turun|lebih tinggi|lebih rendah)\s+\d[\d.,]*\s*(%|persen)",
               "", t, flags=re.IGNORECASE)
    # sisa persentase yang masih tertinggal
    t = re.sub(r"\d[\d.,]*\s*%", "", t)
    t = re.sub(r"\b\d[\d.,]*\s*persen\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+([,.;])", r"\1", t)     # spasi sebelum tanda baca
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = re.sub(r"^[,;]\s*", "", t)
    t = re.sub(r"\s*[,;]$", "", t)
    if t:
        t = t[0].upper() + t[1:]
    return t.strip()


def _angka_dalam(teks):
    """Ambil semua angka BERARTI dari teks.

    Hanya angka >= 1000 yang dianggap angka keuangan. Angka kecil (jumlah
    transaksi, persentase, urutan) TIDAK dikembalikan — kalau ikut dikembalikan,
    kalimat seperti "turun 30%" akan lolos penyaringan hanya karena ada angka
    "30" di suatu tempat di data. Itu kebocoran yang membuat model bisa menulis
    persentase karangan.
    """
    teks = str(teks)
    hasil = set()
    for m in re.findall(r"\d[\d.,]*", teks):
        bersih = m.replace(".", "").replace(",", ".")
        try:
            if bersih.endswith("."):
                bersih = bersih[:-1]
            v = float(bersih)
            if v >= 1000:
                hasil.add(int(v))
        except ValueError:
            pass
    return hasil


def _ada_persen(teks):
    """True kalau teks menyebut persentase."""
    return bool(re.search(r"\d[\d.,]*\s*%|\bpersen\b", str(teks), re.IGNORECASE))


def _fakta_angka(fakta):
    """Kumpulkan semua angka yang SAH, dari seluruh struktur fakta."""
    sah = set()

    def telusuri(x):
        if isinstance(x, dict):
            for v in x.values():
                telusuri(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                telusuri(v)
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            sah.add(int(x))
        elif isinstance(x, str):
            sah.update(_angka_dalam(x))

    telusuri(fakta)
    return sah


def _format_rupiah(teks):
    """Pastikan nominal muncul sebagai 'Rp 8.200.000', bukan 'Rp 8096600'.

    Model kadang menulis angka mentah, kadang sudah memberi awalan "Rp" tapi
    tanpa pemisah ribuan. Keduanya diperbaiki di sini.

    Yang TIDAK diformat:
      - angka < 1000          (jumlah transaksi tidak boleh jadi 'Rp 8')
      - tahun 1900-2100       ('Oktober 2026' jangan jadi 'Oktober Rp 2.026')
      - tanggal               ('2026-10-05' tetap tanggal)

    Bug nyata yang diperbaiki di sini: model menulis "Oktober 2026", lalu
    angkanya berubah jadi "Oktober Rp 2.026". Tahun dan nominal rupiah
    sama-sama empat digit, jadi harus dibedakan dengan rentang nilainya.
    """
    TAHUN_MIN, TAHUN_MAKS = 1900, 2100

    def rapikan(angka):
        try:
            v = int(angka)
        except ValueError:
            return None
        if v < 1000:
            return None
        if TAHUN_MIN <= v <= TAHUN_MAKS:
            return None               # ini tahun, bukan uang
        return "Rp " + format(v, ",d").replace(",", ".")

    def ganti_dengan_rp(m):
        isi = m.group(1)
        # kalau sudah berpemisah ribuan yang benar, biarkan
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", isi):
            v = int(isi.replace(".", ""))
            if TAHUN_MIN <= v <= TAHUN_MAKS and len(isi) == 4 and "." not in isi:
                return m.group(0)
            return "Rp " + format(v, ",d").replace(",", ".")
        hasil = rapikan(isi)
        return hasil if hasil else m.group(0)

    def ganti_telanjang(m):
        hasil = rapikan(m.group(0))
        return hasil if hasil else m.group(0)

    # 'Rp 8096600' / 'Rp8096600' / 'Rp 6750000.' -> 'Rp 8.200.000'
    # TANPA \b di depan: "Rp" selalu diikuti spasi/titik, dan \b gagal cocok
    # justru pada bentuk yang paling sering ditulis model.
    teks = re.sub(r"Rp\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)", ganti_dengan_rp, teks)
    # '8096600' telanjang -> 'Rp 8.200.000' (hindari tanggal, tahun, desimal)
    teks = re.sub(r"(?<![\d.\-:/])([1-9]\d{3,})(?![\d.\-:/])", ganti_telanjang, teks)
    return teks


def _kalimat_aman(kalimat, sah, ringkasan_data):
    """True kalau kalimat itu boleh ditampilkan apa adanya.

    Dua syarat:
      1. Tidak menyebut persentase — angka persen tidak bisa diverifikasi.
      2. Setiap angka >= 1000 yang disebut harus ada di fakta yang dikirim.

    Kalimat yang gagal karena persen TIDAK langsung dibuang — lihat
    `buat_narasi`: persennya dipotong dulu, lalu diperiksa ulang.
    """
    if not kalimat:
        return True
    if _ada_persen(kalimat):
        return False
    for a in _angka_dalam(kalimat):
        if a not in sah:
            return False
    return True


def _kalimat_bawaan(analisa):
    """Kalimat pengganti dari db.py, dipakai kalau narasi AI tidak layak.

    Halaman analisa TIDAK BOLEH kosong di bagian per-kategori. `asumsi` sudah
    memuat kalimat yang seluruhnya berasal dari hitungan, jadi selalu benar
    dan selalu ada.
    """
    hasil = {}
    for s in analisa["saran"]["kategori"]:
        hasil[s["kategori"]] = s["asumsi"]
    return hasil


def buat_narasi(analisa):
    """Hasilkan narasi untuk satu bulan.

    Selalu mengembalikan dict berbentuk sama, dengan `catatan` berisi alasan
    kalau ada yang dibuang/diganti. TIDAK pernah melempar exception — halaman
    analisa harus tetap tampil walaupun model mati.

    Urutan penanganan tiap kalimat dari model:
      1. ada persen?  -> potong bagian persennya, lanjut
      2. ada angka yang tidak dikenal? -> BUANG kalimat itu
      3. lolos        -> pakai
    Kalau tidak ada kalimat yang lolos untuk sebuah kategori, dipakai kalimat
    bawaan dari db.py.
    """
    fakta = _ringkas_untuk_model(analisa)
    sah = _fakta_angka(fakta)
    bawaan = _kalimat_bawaan(analisa)

    try:
        hasil = _panggil_model(fakta)
    except Exception as e:
        return {"ringkasan": None, "per_kategori": bawaan, "penutup": None,
                "catatan": "Model tidak bisa dihubungi (%s). Dipakai penjelasan "
                           "dari data." % e,
                "dibuang": [], "persen_dipotong": [], "kategori_diganti":
                    sorted(bawaan.keys())}

    dibuang, dipotong = [], []

    def olah(kalimat, label):
        kalimat = (kalimat or "").strip()
        if not kalimat:
            return None
        if _ada_persen(kalimat):
            asli = kalimat
            kalimat = _bersihkan_persen(kalimat)
            if kalimat and kalimat != asli:
                dipotong.append({"tempat": label, "asli": asli, "hasil": kalimat})
        if not kalimat:
            return None
        kalimat = _format_rupiah(kalimat)
        for a in _angka_dalam(kalimat):
            if a not in sah:
                dibuang.append({"tempat": label, "kalimat": kalimat,
                                "angka_asing": sorted(_angka_dalam(kalimat))})
                return None
        return kalimat

    ringkasan = olah(hasil.get("ringkasan"), "ringkasan")
    penutup = olah(hasil.get("penutup"), "penutup")

    per_kategori = {}
    diganti = []
    for nama in [k["kategori"] for k in analisa["saran"]["kategori"]]:
        kalimat = olah((hasil.get("per_kategori") or {}).get(nama), "kategori:%s" % nama)
        if kalimat:
            per_kategori[nama] = kalimat
        else:
            # Jaring pengaman: jangan biarkan kategori tanpa penjelasan.
            per_kategori[nama] = bawaan.get(nama)
            diganti.append(nama)

    bagian = []
    if dibuang:
        bagian.append("%d kalimat dibuang karena memuat angka yang tidak ada di data"
                      % len(dibuang))
    if dipotong:
        bagian.append("%d kalimat disebut ulang tanpa persentase" % len(dipotong))
    if diganti:
        bagian.append("%d kategori memakai penjelasan dari data" % len(diganti))

    return {
        "ringkasan": ringkasan,
        "per_kategori": per_kategori,
        "penutup": penutup,
        "catatan": ("; ".join(bagian) + ".") if bagian else None,
        "dibuang": dibuang,
        "persen_dipotong": dipotong,
        "kategori_diganti": diganti,
    }


def _ringkas_untuk_model(analisa):
    """Fakta yang dikirim ke model — HANYA angka dari db.py, tanpa opini.

    Catatan: `total_bulan_lalu` dan `perubahan_persen` ada di `angka["kategori"]`,
    sedangkan `potensi_hemat` dan `wajib` ada di `saran["kategori"]`. Keduanya
    digabung di sini berdasarkan nama kategori.
    """
    a = analisa["angka"]
    s = analisa["saran"]
    saran_per = {k["kategori"]: k for k in s["kategori"]}

    kategori = []
    for k in a["kategori"]:
        sr = saran_per.get(k["category"], {})
        kategori.append({
            "nama": k["category"],
            "total": k["total"],
            "transaksi": k["tx_count"],
            "wajib": k["wajib"],
            "bulan_lalu": k["total_bulan_lalu"],
            "perubahan_persen": k["perubahan_persen"],
            "potensi_hemat": sr.get("potensi_hemat"),
        })

    return {
        "bulan": analisa["nama_bulan"],
        "jumlah_transaksi": a["tx_count"],
        "uang_masuk": a["masuk"],
        "uang_keluar_semua": a["keluar_semua"],
        "pengeluaran_sesungguhnya": a["konsumsi"],
        "pelunasan_utang": a["pelunasan_utang"],
        "talangan_ke_project": a["talangan_piutang"],
        "sisa_kas": a["sisa_kas"],
        "sisa_bebas": a["sisa_bebas"],
        # Kalau data bulan itu belum lengkap, model HARUS tahu — tanpa ini dia
        # akan menulis kesimpulan seolah bulan itu sudah penuh, dan
        # "sisa bebas 7 juta" dari 3 hari data terdengar seperti fakta.
        "kelengkapan_data": {
            "hari_tercatat": analisa["kelengkapan"]["hari_tercatat"],
            "jumlah_hari_bulan": analisa["kelengkapan"]["jumlah_hari_bulan"],
            "data_lengkap": analisa["kelengkapan"]["lengkap"],
        },
        "ada_pembanding_bulan_lalu": s["ada_pembanding"],
        "bulan_pembanding": s["bulan_pembanding"],
        "kategori": kategori,
    }


def _panggil_model(fakta):
    key = os.environ.get("NINE_ROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("NINE_ROUTER_API_KEY tidak ada di environment")

    body = {
        "model": MODEL,
        "max_tokens": 1400,
        "stream": True,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYS},
            {"role": "user", "content":
                "FAKTA keuangan bulan ini:\n" +
                json.dumps(fakta, ensure_ascii=False, indent=1) +
                "\n\nTulis analisanya."},
        ],
    }
    req = urllib.request.Request(
        BASE, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=model_config.TIMEOUT) as r:
        raw = r.read().decode()

    chunks = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        p = line[5:].strip()
        if p == "[DONE]":
            break
        try:
            d = json.loads(p)
            ch = d.get("choices") or []
            if ch and (ch[0].get("delta") or {}).get("content"):
                chunks.append(ch[0]["delta"]["content"])
        except Exception:
            pass
    txt = "".join(chunks).strip().replace("```json", "").replace("```", "").strip()
    if not txt:
        raise RuntimeError("model tidak membalas (content kosong)")
    return json.loads(txt)
